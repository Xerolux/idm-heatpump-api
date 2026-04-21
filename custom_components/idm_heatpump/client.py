"""Async Modbus TCP client for IDM Navigator heat pumps."""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pymodbus
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException

_LOGGER = logging.getLogger(__name__)
_MAX_GROUP_FAILURES = 3


def _get_slave_param() -> str:
    """Return the pymodbus slave parameter name for the installed version."""
    try:
        params = inspect.signature(AsyncModbusTcpClient.read_input_registers).parameters
        if "device_id" in params:
            return "device_id"
        return "slave"
    except Exception:  # noqa: BLE001
        parts = pymodbus.__version__.split(".")
        try:
            major = int(parts[0])
            minor = int(parts[1])
            if major > 3 or (major == 3 and minor >= 10):
                return "device_id"
        except (ValueError, IndexError):
            pass
        return "slave"


_PMODBUS_SLAVE_PARAM = _get_slave_param()


class DataType(Enum):
    FLOAT = "FLOAT"
    UCHAR = "UCHAR"
    INT8 = "INT8"
    INT16 = "INT16"
    UINT16 = "UINT16"
    BOOL = "BOOL"
    BITFLAG = "BITFLAG"


@dataclass
class RegisterDef:
    address: int
    datatype: DataType
    name: str
    unit: str | None = None
    writable: bool = False
    min_val: float | None = None
    max_val: float | None = None
    enum_options: dict[int, str] | None = None
    multiplier: float = 1.0
    size: int = field(init=False)

    def __post_init__(self) -> None:
        self.size = 2 if self.datatype == DataType.FLOAT else 1


class IdmModbusClient:
    def __init__(self, host: str, port: int = 502, slave_id: int = 1) -> None:
        self._host = host
        self._port = int(port)
        self._slave_id = int(slave_id)
        self._client: AsyncModbusTcpClient | None = None
        self._lock = asyncio.Lock()
        self._permanently_failed_registers: set[str] = set()

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    async def connect(self) -> None:
        async with self._lock:
            if self._client is None or not self._client.connected:
                self._client = AsyncModbusTcpClient(
                    host=str(self._host),
                    port=int(self._port),
                    timeout=10,
                )
                if not await self._client.connect():
                    self._client = None
                    raise ConnectionException(f"Failed to connect to {self._host}:{self._port}")

    async def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def _get_client(self) -> AsyncModbusTcpClient:
        if self._client is None or not self._client.connected:
            raise ConnectionException(f"Not connected to {self._host}:{self._port}")
        return self._client

    async def _read_registers(self, address: int, count: int) -> list[int]:
        async with self._lock:
            client = self._get_client()
            kwargs: Any = {_PMODBUS_SLAVE_PARAM: int(self._slave_id)}
            result = await client.read_input_registers(
                address=int(address), count=int(count), **kwargs
            )

            if result.isError():
                raise ModbusException(f"Modbus error reading address {address}")
            return list(result.registers)

    async def _write_registers(self, address: int, values: list[int]) -> None:
        async with self._lock:
            client = self._get_client()
            kwargs: Any = {_PMODBUS_SLAVE_PARAM: int(self._slave_id)}
            result = await client.write_registers(
                address=int(address),
                values=[int(v) for v in values],
                **kwargs,
            )

            if result.isError():
                raise ModbusException(f"Modbus error writing address {address}")

    def decode_value(self, registers: list[int], reg: RegisterDef) -> Any:
        if reg.datatype == DataType.FLOAT:
            if len(registers) < 2:
                raise ValueError("Not enough registers for FLOAT")
            low_word, high_word = registers[0], registers[1]
            raw = struct.pack("<HH", low_word, high_word)
            value = struct.unpack("<f", raw)[0]
            if math.isnan(value):
                return None
            return round(value * reg.multiplier, 2)

        if reg.datatype == DataType.UCHAR:
            val = registers[0] & 0xFF
            return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

        if reg.datatype == DataType.INT8:
            val = registers[0] & 0xFF
            if val >= 128:
                val -= 256
            return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

        if reg.datatype == DataType.INT16:
            val = registers[0]
            if val >= 32768:
                val -= 65536
            return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

        if reg.datatype == DataType.UINT16:
            val = registers[0]
            return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

        if reg.datatype == DataType.BOOL:
            return bool(registers[0] & 0x01)

        if reg.datatype == DataType.BITFLAG:
            return registers[0] & 0xFF

        raise ValueError(f"Unknown or unsupported decode datatype: {reg.datatype}")

    def encode_value(self, value: Any, reg: RegisterDef) -> list[int]:
        if reg.datatype == DataType.FLOAT:
            float_val = float(value) / reg.multiplier
            raw = struct.pack("<f", float_val)
            low, high = struct.unpack("<HH", raw)
            return [low, high]

        if reg.datatype == DataType.UCHAR:
            val = int(round(float(value) / reg.multiplier))
            return [val & 0xFF]

        if reg.datatype == DataType.INT8:
            val = int(round(float(value) / reg.multiplier))
            if val < 0:
                val += 256
            return [val & 0xFF]

        if reg.datatype == DataType.INT16:
            val = int(round(float(value) / reg.multiplier))
            if val < 0:
                val += 65536
            return [val & 0xFFFF]

        if reg.datatype == DataType.UINT16:
            val = int(round(float(value) / reg.multiplier))
            return [val & 0xFFFF]

        if reg.datatype == DataType.BOOL:
            return [1 if value else 0]

        if reg.datatype == DataType.BITFLAG:
            return [int(value) & 0xFF]

        raise ValueError(f"Unknown or unsupported encode datatype: {reg.datatype}")

    async def read_register(self, reg: RegisterDef) -> Any:
        if self._client is None or not self._client.connected:
            await self.connect()
        registers = await self._read_registers(reg.address, reg.size)
        return self.decode_value(registers, reg)

    async def write_register(self, reg: RegisterDef, value: Any) -> None:
        if not reg.writable:
            raise ValueError(f"Register {reg.name} is read-only")

        if reg.min_val is not None and value < reg.min_val:
            raise ValueError(f"Value {value} below minimum {reg.min_val}")
        if reg.max_val is not None and value > reg.max_val:
            raise ValueError(f"Value {value} above maximum {reg.max_val}")

        if self._client is None or not self._client.connected:
            await self.connect()
        encoded = self.encode_value(value, reg)
        await self._write_registers(reg.address, encoded)

    async def read_batch(self, register_list: list[RegisterDef]) -> dict[str, Any]:
        if not register_list:
            return {}

        # Filter out registers that have permanently failed
        valid_regs = [r for r in register_list if r.name not in self._permanently_failed_registers]
        if not valid_regs:
            return {}

        if self._client is None or not self._client.connected:
            await self.connect()

        sorted_regs = sorted(valid_regs, key=lambda r: r.address)
        groups: list[list[RegisterDef]] = []
        current_group: list[RegisterDef] = [sorted_regs[0]]
        current_group_word_count = sorted_regs[0].size

        for reg in sorted_regs[1:]:
            last = current_group[-1]
            expected_next = last.address + last.size
            if (
                reg.address == expected_next
                and (current_group_word_count + reg.size) <= 30
            ):
                current_group.append(reg)
                current_group_word_count += reg.size
            else:
                groups.append(current_group)
                current_group = [reg]
                current_group_word_count = reg.size
        groups.append(current_group)

        results: dict[str, Any] = {}
        for group in groups:
            group_res = await self._read_group(group)
            results.update(group_res)

        return results

    async def _read_group(self, group: list[RegisterDef]) -> dict[str, Any]:
        start = group[0].address
        end = group[-1].address + group[-1].size
        count = end - start

        try:
            registers = await self._read_registers(start, count)
        except ConnectionException as err:
            _LOGGER.debug("Connection failed while reading group starting at %s: %s", start, err)
            raise
        except ModbusException as err:
            _LOGGER.debug("Failed to read group starting at %s: %s. Falling back to individual reads.", start, err)
            # Fall back to individual reads to isolate the failure
            return await self._read_individual_fallback(group)

        data: dict[str, Any] = {}
        offset = 0
        for reg in group:
            try:
                reg_slice = registers[offset : offset + reg.size]
                data[reg.name] = self.decode_value(reg_slice, reg)
            except (ValueError, IndexError):
                pass
            offset += reg.size
        return data

    async def _read_individual_fallback(self, group: list[RegisterDef]) -> dict[str, Any]:
        """Read registers one by one to find the failing one."""
        data: dict[str, Any] = {}
        for reg in group:
            try:
                registers = await self._read_registers(reg.address, reg.size)
                data[reg.name] = self.decode_value(registers, reg)
            except ConnectionException as err:
                _LOGGER.debug("Connection failed during individual read of %s (%s): %s", reg.name, reg.address, err)
                raise
            except ModbusException as err:
                _LOGGER.warning("Register %s (%s) failed during individual read: %s. Marking as permanently failed.", reg.name, reg.address, err)
                self._permanently_failed_registers.add(reg.name)
            except (ValueError, IndexError) as err:
                _LOGGER.warning("Register %s (%s) failed during decode: %s", reg.name, reg.address, err)
        return data
