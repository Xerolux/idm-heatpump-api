"""Capture Navigator 10 WebSocket frames through a logging local proxy.

Maintainer tooling for the WebSocket-first roadmap (Phase 3): the browser is
pointed at this proxy instead of at the Navigator, and every frame in both
directions is written to a JSONL file — the raw material for documenting the
level-0 ``settingId`` catalog and the ``setting/save`` / ``notification/save``
payload shapes. The proxy itself never fabricates frames; it only forwards
what the browser and the controller exchange, so what is captured is exactly
what the official web UI sends.

Pure standard library — no project dependencies, runnable on any Python 3.11+
that is installed on the machine with browser access.

Usage::

    python scripts/ws_capture.py --host 192.168.178.103 --pin 2634
    # then open the Navigator web UI at http://127.0.0.1:61221/
    # (the proxy rewrites the WebSocket URL of the page it serves a redirect
    #  for; simplest manual step: open the UI as usual and re-point its
    #  WebSocket URL, or use the DevTools recipe documented on the wiki)

Privacy: the PIN never appears in the log (it lives only in the handshake
URL, which is not logged); everything else is recorded verbatim, so sanitize
serial numbers, myIDM data and addresses before sharing a capture. Raw
captures stay on the maintainer's machine.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import secrets
import socket
import struct
import sys
import threading
import time
from pathlib import Path

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
DEFAULT_NAVIGATOR_PORT = 61220
DEFAULT_LISTEN_PORT = 61221
MAX_FRAME_PAYLOAD = 4 * 1024 * 1024


def _recv_exact(conn: socket.socket, count: int) -> bytes:
    chunks = []
    remaining = count
    while remaining > 0:
        chunk = conn.recv(remaining)
        if not chunk:
            raise ConnectionError("socket closed mid-frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _handshake_key() -> str:
    return base64.b64encode(secrets.token_bytes(16)).decode("ascii")


def _accept_key(key: str) -> str:
    return base64.b64encode(hashlib.sha1(f"{key}{WS_GUID}".encode("ascii")).digest()).decode(
        "ascii"
    )


def _read_head(conn: socket.socket) -> str:
    """Read one HTTP head byte-wise so no WebSocket frame byte is swallowed.

    The Navigator pushes its first frame (``{"authorized": true}``) in the
    same TCP segment as its 101 response, so a buffered read of the head
    would discard it and the relay would look like a controller that never
    answers.
    """
    data = bytearray()
    while b"\r\n\r\n" not in data:
        byte = conn.recv(1)
        if not byte:
            raise ConnectionError("peer closed before the HTTP head was complete")
        data += byte
    return data.decode("latin-1")


def _parse_head(head: str) -> tuple[str, dict[str, str]]:
    lines = head.split("\r\n")
    first_line = lines[0]
    headers: dict[str, str] = {}
    for line in lines[1:]:
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
    return first_line, headers


def _read_http_request(conn: socket.socket) -> tuple[str, dict[str, str]]:
    """Read one HTTP request head from the socket."""
    return _parse_head(_read_head(conn))


def _read_http_response(conn: socket.socket) -> tuple[str, dict[str, str]]:
    """Read one HTTP response head from the socket."""
    return _parse_head(_read_head(conn))


def read_frame(conn: socket.socket) -> tuple[int, bool, bytes]:
    """Read one WebSocket frame; return (opcode, fin, payload)."""
    first_two = _recv_exact(conn, 2)
    fin = bool(first_two[0] & 0x80)
    opcode = first_two[0] & 0x0F
    masked = bool(first_two[1] & 0x80)
    length = first_two[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", _recv_exact(conn, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", _recv_exact(conn, 8))[0]
    if length > MAX_FRAME_PAYLOAD:
        raise ConnectionError(f"frame of {length} bytes exceeds the safety limit")
    mask = _recv_exact(conn, 4) if masked else None
    payload = _recv_exact(conn, length) if length else b""
    if mask is not None:
        payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
    return opcode, fin, payload


def build_frame(opcode: int, payload: bytes, *, mask: bool) -> bytes:
    """Build one WebSocket frame, optionally masked (client-to-server)."""
    header = bytes([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header += bytes([(0x80 if mask else 0) | length])
    elif length < 65536:
        header += bytes([(0x80 if mask else 0) | 126]) + struct.pack(">H", length)
    else:
        header += bytes([(0x80 if mask else 0) | 127]) + struct.pack(">Q", length)
    if mask:
        mask_key = secrets.token_bytes(4)
        masked = bytes(byte ^ mask_key[index % 4] for index, byte in enumerate(payload))
        return header + mask_key + masked
    return header + payload


class FrameLogger:
    """Append captured text frames to a JSONL file, PIN-redacted."""

    def __init__(self, path: Path, redactions: tuple[str, ...] = ()) -> None:
        self._path = path
        self._redactions = tuple(item for item in redactions if item)
        self._lock = threading.Lock()

    def _redact(self, text: str) -> str:
        for secret in self._redactions:
            text = text.replace(secret, "***")
        return text

    def log(self, direction: str, opcode: int, payload: bytes) -> None:
        if opcode != 1:
            # Control frames and binary frames are metadata, not protocol
            # content; note them only as markers.
            entry = {"ts": round(time.time(), 3), "dir": direction, "opcode": opcode}
        else:
            text = self._redact(payload.decode("utf-8", errors="replace"))
            try:
                parsed: object = json.loads(text)
            except json.JSONDecodeError:
                parsed = text
            entry = {"ts": round(time.time(), 3), "dir": direction, "payload": parsed}
        with self._lock:
            with self._path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def note(self, message: str) -> None:
        message = self._redact(message)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"ts": round(time.time(), 3), "note": message}) + "\n")


def _pump(
    source: socket.socket, target: socket.socket, direction: str, logger: FrameLogger
) -> None:
    """Forward frames one way, logging text frames."""
    try:
        while True:
            opcode, fin, payload = read_frame(source)
            # The forwarder re-masks only when the target expects masked
            # frames (the controller); the browser accepts unmasked frames.
            masked = direction == "c2s"
            try:
                target.sendall(build_frame(opcode, payload, mask=masked))
            except OSError:
                return
            logger.log(direction, opcode, payload)
            if opcode == 8:
                return
    except (OSError, ConnectionError):
        return


def _serve_one_session(
    listen: socket.socket, host: str, port: int, pin: str, logger: FrameLogger
) -> None:
    client_conn, _addr = listen.accept()
    upstream: socket.socket | None = None
    client_sock: socket.socket | None = None
    upstream_sock: socket.socket | None = None
    try:
        try:
            request_line, headers = _read_http_request(client_conn)
            request_key = headers.get("sec-websocket-key", "")
        except (OSError, ConnectionError) as err:
            logger.note(f"handshake with the browser failed: {err!r}")
            return
        upstream = socket.create_connection((host, port), timeout=10)
        upstream_key = _handshake_key()
        upstream.sendall(
            (
                f"GET /?auth_code={pin} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {upstream_key}\r\n"
                "Sec-WebSocket-Version: 13\r\n"
                "\r\n"
            ).encode("ascii")
        )
        status_line, _ = _read_http_response(upstream)
        if "101" not in status_line:
            logger.note(f"controller refused the upgrade: {status_line}")
            client_conn.sendall(b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            return
        # The relay must block indefinitely on both sockets; the connect
        # timeout must not survive the handshake.
        upstream.settimeout(None)
        client_conn.sendall(
            (
                "HTTP/1.1 101 Switching Protocols\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Accept: {_accept_key(request_key)}\r\n"
                "\r\n"
            ).encode("ascii")
        )
        # Hand the file descriptors to fresh socket objects so they outlive
        # this function's error paths; the relay threads own them from here.
        upstream_sock = socket.socket(fileno=upstream.detach())
        client_sock = socket.socket(fileno=client_conn.detach())
    finally:
        for sock in (client_conn, upstream):
            if sock is not None and sock.fileno() != -1:
                try:
                    sock.close()
                except OSError:
                    pass

    assert client_sock is not None and upstream_sock is not None
    logger.note(
        f"session relay started ({request_line.split()[1] if ' ' in request_line else '?'})"
    )
    to_controller = threading.Thread(
        target=_pump, args=(client_sock, upstream_sock, "c2s", logger), daemon=True
    )
    to_browser = threading.Thread(
        target=_pump, args=(upstream_sock, client_sock, "s2c", logger), daemon=True
    )
    to_controller.start()
    to_browser.start()
    to_controller.join()
    to_browser.join(timeout=5)
    for sock in (client_sock, upstream_sock):
        try:
            sock.close()
        except OSError:
            pass
    logger.note("session relay ended")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--host", required=True, help="Navigator host (for example 192.168.178.103)"
    )
    parser.add_argument("--pin", required=True, help="local web PIN (SYSLPIN); never logged")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_NAVIGATOR_PORT, help="Navigator WebSocket port"
    )
    parser.add_argument(
        "--listen-port",
        type=int,
        default=DEFAULT_LISTEN_PORT,
        help="local port the browser connects to",
    )
    parser.add_argument(
        "--out", default="ws-capture.jsonl", help="JSONL output file (default: ws-capture.jsonl)"
    )
    parser.add_argument("--once", action="store_true", help="capture one browser session and exit")
    args = parser.parse_args(argv)

    out_path = Path(args.out)
    logger = FrameLogger(out_path, redactions=(args.pin,))
    listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen.bind(("0.0.0.0", args.listen_port))
    listen.listen(1)
    print(
        f"listening on 0.0.0.0:{args.listen_port} -> ws://{args.host}:{args.port}/ "
        f"(log: {out_path.resolve()}); PIN is not logged",
        file=sys.stderr,
    )
    print(
        "point the Navigator web UI's WebSocket at this proxy and operate it normally",
        file=sys.stderr,
    )
    try:
        while True:
            _serve_one_session(listen, args.host, args.port, args.pin, logger)
            if args.once:
                break
    except KeyboardInterrupt:
        pass
    finally:
        listen.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
