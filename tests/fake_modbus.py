"""Deterministic pymodbus-style test doubles."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass
class FakeModbusResponse:
    registers: list[int] | None = None
    error: bool = False

    def isError(self) -> bool:  # noqa: N802 - pymodbus compatibility
        return self.error


class FakeModbusTransport:
    """Small async transport double implementing the pymodbus methods we use."""

    connected = True

    def __init__(
        self,
        *,
        input_registers: dict[int, int] | None = None,
        holding_registers: dict[int, int] | None = None,
        error_reads: set[tuple[str, int, int]] | None = None,
        short_reads: dict[tuple[str, int, int], list[int]] | None = None,
        delay: float = 0,
    ) -> None:
        self.input_registers = input_registers or {}
        self.holding_registers = holding_registers or {}
        self.error_reads = error_reads or set()
        self.short_reads = short_reads or {}
        self.delay = delay
        self.read_calls: list[tuple[str, int, int]] = []
        self.write_calls: list[tuple[int, list[int]]] = []
        self.active_requests = 0
        self.max_active_requests = 0

    def close(self) -> None:
        self.connected = False

    async def read_input_registers(self, *, address: int, count: int, **_: Any) -> Any:
        return await self._read("input", self.input_registers, address, count)

    async def read_holding_registers(self, *, address: int, count: int, **_: Any) -> Any:
        return await self._read("holding", self.holding_registers, address, count)

    async def write_registers(self, *, address: int, values: list[int], **_: Any) -> Any:
        await self._enter_request()
        try:
            self.write_calls.append((address, list(values)))
            for offset, value in enumerate(values):
                self.holding_registers[address + offset] = int(value)
            return FakeModbusResponse()
        finally:
            self._exit_request()

    async def _read(
        self,
        kind: str,
        registers: dict[int, int],
        address: int,
        count: int,
    ) -> FakeModbusResponse:
        await self._enter_request()
        try:
            key = (kind, address, count)
            self.read_calls.append(key)
            if key in self.error_reads:
                return FakeModbusResponse(error=True)
            if key in self.short_reads:
                return FakeModbusResponse(registers=self.short_reads[key])
            return FakeModbusResponse(
                registers=[registers.get(address + offset, 0) for offset in range(count)]
            )
        finally:
            self._exit_request()

    async def _enter_request(self) -> None:
        self.active_requests += 1
        self.max_active_requests = max(self.max_active_requests, self.active_requests)
        if self.delay:
            await asyncio.sleep(self.delay)

    def _exit_request(self) -> None:
        self.active_requests -= 1
