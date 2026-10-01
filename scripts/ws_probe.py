"""Read-only Navigator 10 WebSocket probe for the Heizsystem circuit type.

Maintainer tooling for integration issue #429 (heating circuit type
"Differenztemperaturgeregelt"): the level-0 web UI shows a *Heizsystem* page
per heating circuit whose first parameter (``HSD01`` on circuit D) carries the
circuit's regulation type — Keines / Ungeregelt / Geregelt / Konstant /
Differenztemperaturgeregelt. Neither the library nor the protocol wiki knows
which WebSocket frame serves that page. This probe asks the controllers that
might carry it and dumps every raw response, so the frame that holds the
circuit type can be identified without a browser capture session.

Strictly read-only: it sends only ``detail`` / ``overview`` requests, never
``save`` or ``execute``. Pure standard library, like ``ws_capture.py``.

What it asks, in order:

1. ``system.heatingcircuit/detail`` for every requested circuit letter
   (default A-G; each frame also lists ``availableHeatingCircuits``).
2. ``setting/detail`` for every setting page known to answer at level 0.
3. ``system/overview`` — the complete plant as JSON.

Every response is written verbatim to a JSONL file and scanned for the
markers ``HSD``, ``Differenz`` and ``Heizsystem`` (case-insensitive) plus
every parameter id found in the heating-circuit frames; the summary is
printed. The PIN never appears in the log (it lives only in the handshake
URL, which is not logged). Everything else is recorded verbatim, so
sanitize serial numbers, myIDM data and addresses before sharing a log.
Raw logs stay on the maintainer's machine.

Usage::

    python scripts/ws_probe.py --host 192.0.2.10 --pin 0000
"""

from __future__ import annotations

import argparse
import base64
import json
import secrets
import socket
import sys
import time
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

from ws_capture import build_frame, read_frame

DEFAULT_NAVIGATOR_PORT = 61220
DEFAULT_CIRCUITS = "ABCDEFG"
KNOWN_SETTING_IDS = ("4768", "4775", "4782", "4789", "4754", "13256", "13259")
MARKERS = ("hsd", "differenz", "heizsystem")


class ProbeError(RuntimeError):
    """The probe could not complete."""


def _handshake(sock: socket.socket, host: str, port: int, pin: str) -> None:
    """Perform the WebSocket client handshake against the controller."""
    key = base64.b64encode(secrets.token_bytes(16)).decode("ascii")
    sock.sendall(
        (
            f"GET /?auth_code={quote(pin)} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode("ascii")
    )
    head = bytearray()
    while b"\r\n\r\n" not in head:
        chunk = sock.recv(1)
        if not chunk:
            raise ProbeError("controller closed the connection during the handshake")
        head += chunk
    status_line = head.decode("latin-1").split("\r\n", 1)[0]
    if "101" not in status_line:
        raise ProbeError(f"controller refused the upgrade: {status_line}")


class NavigatorProbe:
    """One authorized WebSocket session used for read-only requests."""

    def __init__(self, host: str, port: int, pin: str, timeout: float) -> None:
        self._host = host
        self._port = port
        self._pin = pin
        self._timeout = timeout
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        sock = socket.create_connection((self._host, self._port), timeout=10)
        try:
            _handshake(sock, self._host, self._port, self._pin)
            # The controller must never see the connect timeout again, but a
            # frame-level timeout keeps a silent controller from hanging the
            # probe forever.
            sock.settimeout(self._timeout)
            first = self._next_text_frame(sock)
            try:
                payload = json.loads(first)
            except json.JSONDecodeError:
                payload = None
            if not (isinstance(payload, dict) and payload.get("authorized") is True):
                raise ProbeError("the controller did not authorize the session - wrong PIN?")
        except Exception:
            sock.close()
            raise
        self._sock = sock

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _next_text_frame(self, sock: socket.socket) -> str:
        while True:
            opcode, _fin, payload = read_frame(sock)
            if opcode == 1:
                return payload.decode("utf-8", errors="replace")
            if opcode == 8:
                raise ProbeError("the controller closed the session")

    def request(self, controller: str, command: str, data: object) -> str:
        """Send one request frame and return the next text frame verbatim."""
        sock = self._sock
        if sock is None:
            raise ProbeError("the probe is not connected")
        frame = json.dumps({"controller": controller, "command": command, "data": data}).encode(
            "utf-8"
        )
        sock.sendall(build_frame(1, frame, mask=True))
        return self._next_text_frame(sock)


def _walk(node: object, path: str = "$") -> Iterator[tuple[str, object]]:
    """Yield every (JSON path, scalar) pair of a parsed response."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk(value, f"{path}[{index}]")
    else:
        yield path, node


def _marker_hits(payload_text: str) -> list[str]:
    """Return human-readable paths whose key or value carries a marker."""
    try:
        parsed: object = json.loads(payload_text)
    except json.JSONDecodeError:
        return ["<response is not JSON>"]
    hits: list[str] = []
    for path, value in _walk(parsed):
        haystacks = [path.rsplit(".", 1)[-1], ""]
        if isinstance(value, str):
            haystacks[1] = value
        for haystack in haystacks:
            if haystack and any(marker in haystack.lower() for marker in MARKERS):
                hits.append(f"{path} = {value!r}")
                break
    return hits


def _parameter_ids(payload_text: str) -> list[str]:
    """Return every value of a JSON key named ``id`` (parameter ids)."""
    try:
        parsed: object = json.loads(payload_text)
    except json.JSONDecodeError:
        return []
    ids: list[str] = []
    if isinstance(parsed, dict):
        stack: list[tuple[str, object]] = [("$", parsed)]
        while stack:
            path, node = stack.pop()
            if isinstance(node, dict):
                for key, value in node.items():
                    if key == "id" and isinstance(value, str):
                        ids.append(value)
                    stack.append((f"{path}.{key}", value))
            elif isinstance(node, list):
                stack.extend((f"{path}[{i}]", item) for i, item in enumerate(node))
    return ids


def _log(out: Path, entry: dict[str, object]) -> None:
    with out.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _probe_circuits(probe: NavigatorProbe, circuits: str, out: Path) -> None:
    """Ask ``system.heatingcircuit/detail`` for every requested circuit."""
    for letter in circuits:
        label = f"heatingcircuit {letter}"
        try:
            response = probe.request("system.heatingcircuit", "detail", {"hcId": letter})
        except (ProbeError, OSError) as err:
            print(f"  {label}: request failed: {err!r}")
            _log(out, {"label": label, "error": repr(err)})
            continue
        ids = _parameter_ids(response)
        _log(
            out,
            {
                "label": label,
                "request": {
                    "controller": "system.heatingcircuit",
                    "command": "detail",
                    "data": {"hcId": letter},
                },
                "response": response,
            },
        )
        print(f"  {label}: {len(response)} bytes, parameter ids: {', '.join(ids) or '-'}")


def _probe_settings(probe: NavigatorProbe, out: Path) -> None:
    """Ask ``setting/detail`` for every known level-0 setting page."""
    for setting_id in KNOWN_SETTING_IDS:
        label = f"setting {setting_id}"
        try:
            response = probe.request("setting", "detail", {"settingId": setting_id})
        except (ProbeError, OSError) as err:
            print(f"  {label}: request failed: {err!r}")
            _log(out, {"label": label, "error": repr(err)})
            continue
        _log(
            out,
            {
                "label": label,
                "request": {
                    "controller": "setting",
                    "command": "detail",
                    "data": {"settingId": setting_id},
                },
                "response": response,
            },
        )
        print(f"  {label}: {len(response)} bytes")


def _probe_system_overview(probe: NavigatorProbe, out: Path) -> None:
    """Ask ``system/overview`` for the complete plant JSON."""
    label = "system overview"
    try:
        response = probe.request("system", "overview", None)
    except (ProbeError, OSError) as err:
        print(f"  {label}: request failed: {err!r}")
        _log(out, {"label": label, "error": repr(err)})
        return
    _log(
        out,
        {
            "label": label,
            "request": {"controller": "system", "command": "overview", "data": None},
            "response": response,
        },
    )
    print(f"  {label}: {len(response)} bytes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", required=True, help="Navigator host (for example 192.0.2.10)")
    parser.add_argument("--pin", required=True, help="local web PIN (SYSLPIN); never logged")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_NAVIGATOR_PORT, help="Navigator WebSocket port"
    )
    parser.add_argument(
        "--circuits", default=DEFAULT_CIRCUITS, help="circuit letters to probe (default: ABCDEFG)"
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=15.0,
        help="seconds to wait for one response frame (default: 15)",
    )
    parser.add_argument(
        "--out", default="ws-probe.jsonl", help="JSONL output file (default: ws-probe.jsonl)"
    )
    args = parser.parse_args(argv)

    out_path = Path(args.out)
    if out_path.exists():
        out_path.unlink()

    probe = NavigatorProbe(args.host, args.port, args.pin, args.timeout)
    try:
        probe.connect()
    except (ProbeError, OSError) as err:
        print(f"connection failed: {err}", file=sys.stderr)
        return 2

    started = time.strftime("%Y-%m-%dT%H:%M:%S")
    print(f"authorized; probing (log: {out_path.resolve()}); PIN is not logged")
    _log(out_path, {"note": f"probe started {started}"})
    try:
        print("heating circuits:")
        _probe_circuits(probe, args.circuits.upper(), out_path)
        print("setting pages:")
        _probe_settings(probe, out_path)
        print("plant:")
        _probe_system_overview(probe, out_path)
    finally:
        probe.close()
        _log(out_path, {"note": "probe finished"})

    print()
    print("marker scan (HSD / Differenz / Heizsystem):")
    hits = 0
    with out_path.open(encoding="utf-8") as stream:
        for line in stream:
            entry = json.loads(line)
            response = entry.get("response")
            if not isinstance(response, str):
                continue
            for hit in _marker_hits(response):
                hits += 1
                print(f"  [{entry['label']}] {hit}")
    if hits == 0:
        print("  no marker found - the Heizsystem page needs a browser capture")
        print("  (run scripts/ws_capture.py and open the Heizsystem page of a circuit)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
