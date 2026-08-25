"""Deterministic transport test double implementing the public protocol.

The fake models a single connected Modbus TCP endpoint and returns raw 16-bit
register words (``list[int]``) exactly as the :class:`IdmModbusTransport`
protocol requires. Device-side failures are surfaced as exceptions, not as
pymodbus-shaped response objects, so the fake honours the contract that
real transports (Pymodbus adapter, ``modbus-connection``/``tmodbus``) must
follow.

Scenario hooks (all optional, keyword-only):

* ``input_registers``/``holding_registers`` -- happy-path backing store.
* ``illegal_reads`` -- addresses that raise ``IllegalAddressError`` (code 2).
* ``error_reads`` -- addresses that raise a generic ``IdmDeviceError``.
* ``exception_reads`` -- addresses that raise a caller-supplied exception
  instance (``IdmConnectionError``, ``IdmTransportError``, ``OSError`` ...).
* ``short_reads`` -- addresses returning an arbitrary register list (used to
  simulate under-length or corrupt/shifted batch payloads).
* ``error_writes`` -- addresses whose write raises ``IdmDeviceError``.
* ``delay`` -- per-request await, used by the lock-serialisation test.
"""

from __future__ import annotations

import asyncio
from typing import Any

from idm_heatpump.client import IllegalAddressError
from idm_heatpump.exceptions import IdmDeviceError


class FakeModbusTransport:
    """Small async transport double returning raw register words."""

    def __init__(
        self,
        *,
        input_registers: dict[int, int] | None = None,
        holding_registers: dict[int, int] | None = None,
        error_reads: set[tuple[str, int, int]] | None = None,
        error_writes: set[int] | None = None,
        exception_reads: dict[tuple[str, int, int], Exception] | None = None,
        short_reads: dict[tuple[str, int, int], list[int]] | None = None,
        illegal_reads: set[tuple[str, int, int]] | None = None,
        delay: float = 0,
    ) -> None:
        self.input_registers = input_registers or {}
        self.holding_registers = holding_registers or {}
        self.error_reads = error_reads or set()
        self.error_writes = error_writes or set()
        self.exception_reads = exception_reads or {}
        self.short_reads = short_reads or {}
        self.illegal_reads = illegal_reads or set()
        self.delay = delay
        self.read_calls: list[tuple[str, int, int]] = []
        self.write_calls: list[tuple[int, list[int]]] = []
        self.active_requests = 0
        self.max_active_requests = 0
        self.connected = True

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.connected = False

    async def read_input_registers(self, *, address: int, count: int, **_: Any) -> list[int]:
        return await self._read("input", self.input_registers, address, count)

    async def read_holding_registers(self, *, address: int, count: int, **_: Any) -> list[int]:
        return await self._read("holding", self.holding_registers, address, count)

    async def write_registers(self, *, address: int, values: list[int], **_: Any) -> None:
        await self._enter_request()
        try:
            self.write_calls.append((address, list(values)))
            if address in self.error_writes:
                raise IdmDeviceError(f"Modbus error writing address {address}: error_writes stub")
            for offset, value in enumerate(values):
                self.holding_registers[address + offset] = int(value)
        finally:
            self._exit_request()

    async def _read(
        self,
        kind: str,
        registers: dict[int, int],
        address: int,
        count: int,
    ) -> list[int]:
        await self._enter_request()
        try:
            key = (kind, address, count)
            self.read_calls.append(key)
            if key in self.exception_reads:
                raise self.exception_reads[key]
            if key in self.illegal_reads:
                # Simulate a real Modbus "Illegal Data Address" (exception
                # code 2) device response: the transport surfaces it as
                # IllegalAddressError so the library retry loop can bail out.
                raise IllegalAddressError(  # type: ignore[no-untyped-call]
                    f"Illegal Data Address reading address {address}: illegal_reads stub"
                )
            if key in self.error_reads:
                raise IdmDeviceError(f"Modbus error reading address {address}: error_reads stub")
            if key in self.short_reads:
                return list(self.short_reads[key])
            return [registers.get(address + offset, 0) for offset in range(count)]
        finally:
            self._exit_request()

    async def _enter_request(self) -> None:
        self.active_requests += 1
        self.max_active_requests = max(self.max_active_requests, self.active_requests)
        if self.delay:
            await asyncio.sleep(self.delay)

    def _exit_request(self) -> None:
        self.active_requests -= 1
