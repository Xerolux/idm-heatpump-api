"""Smoke tests for the maintainer WebSocket capture proxy (scripts/ws_capture.py)."""

from __future__ import annotations

import json
import socket
import threading
from pathlib import Path

from scripts.ws_capture import (
    FrameLogger,
    _accept_key,
    build_frame,
    read_frame,
)


def _socket_pair() -> tuple[socket.socket, socket.socket]:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(listener.getsockname())
    server, _ = listener.accept()
    listener.close()
    return client, server


def test_frame_roundtrip_with_masking() -> None:
    payload = json.dumps({"controller": "setting", "command": "detail"}).encode("utf-8")

    writer, reader = _socket_pair()
    with writer, reader:
        writer.sendall(build_frame(1, payload, mask=True))
        opcode, fin, received = read_frame(reader)

    assert opcode == 1
    assert fin is True
    assert received == payload


def test_frame_roundtrip_unmasked_large_payload() -> None:
    payload = b"x" * 70000

    writer, reader = _socket_pair()
    with writer, reader:
        writer.sendall(build_frame(2, payload, mask=False))
        opcode, _, received = read_frame(reader)

    assert opcode == 2
    assert received == payload


def test_accept_key_matches_rfc6455_example() -> None:
    assert _accept_key("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_logger_redacts_the_pin_and_parses_json(tmp_path: Path) -> None:
    log = tmp_path / "capture.jsonl"
    logger = FrameLogger(log, redactions=("9999",))

    logger.log("c2s", 1, b'{"controller": "setting", "command": "save", "data": {"pin": "9999"}}')

    entry = json.loads(log.read_text(encoding="utf-8"))
    assert entry["dir"] == "c2s"
    assert entry["payload"]["data"]["pin"] == "***"


def test_logger_keeps_non_json_text_verbatim(tmp_path: Path) -> None:
    log = tmp_path / "capture.jsonl"
    logger = FrameLogger(log)

    logger.log("s2c", 1, b"<html>not json</html>")

    entry = json.loads(log.read_text(encoding="utf-8"))
    assert entry["payload"] == "<html>not json</html>"


def test_logger_is_thread_safe(tmp_path: Path) -> None:
    log = tmp_path / "capture.jsonl"
    logger = FrameLogger(log)

    def write_hundred(index: int) -> None:
        for count in range(100):
            logger.log("c2s", 1, json.dumps({"thread": index, "count": count}).encode("utf-8"))

    threads = [threading.Thread(target=write_hundred, args=(index,)) for index in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 400
    assert all(json.loads(line)["dir"] == "c2s" for line in lines)
