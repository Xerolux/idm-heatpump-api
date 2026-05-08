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

from .const import DEFAULT_TIMEOUT, MAX_RETRIES, RETRY_BACKOFF_BASE

_LOGGER = logging.getLogger(__name__)

_MAX_GROUP_GAP = 10
_MAX_GROUP_SIZE = 40
_PERMANENT_FAILURE_THRESHOLD = 3


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
        if self.datatype not in DataType:
            raise ValueError(f"Invalid datatype: {self.datatype}")
        if self.address < 0:
            raise ValueError(f"Register address must be non-negative, got {self.address}")
        self.size = 2 if self.datatype == DataType.FLOAT else 1


class IdmModbusClient:
    """Async Modbus TCP client for IDM Navigator heat pumps.

    Features:
      - Automatic reconnection on connection loss
      - Configurable retries with exponential backoff
      - Batch reads with automatic grouping and fallback to individual reads
      - Permanently failed register tracking to avoid repeated failures
    """

    def __init__(
        self,
        host: str,
        port: int = 502,
        slave_id: int = 1,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        if not host:
            raise ValueError("Host must not be empty")
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")
        if not (1 <= slave_id <= 247):
            raise ValueError(f"Slave ID must be between 1 and 247, got {slave_id}")

        self._host = host
        self._port = int(port)
        self._slave_id = int(slave_id)
        self._timeout = float(timeout)
        self._max_retries = int(max_retries)
        self._client: AsyncModbusTcpClient | None = None
        self._lock = asyncio.Lock()
        self._register_failures: dict[str, int] = {}
        self._permanently_failed_registers: set[str] = set()

    def __repr__(self) -> str:
        connected = self._client is not None and self._client.connected
        return (
            f"IdmModbusClient(host={self._host!r}, port={self._port}, "
            f"slave_id={self._slave_id}, connected={connected})"
        )

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.connected

    async def connect(self) -> None:
        """Establish a connection to the Modbus device."""
        async with self._lock:
            await self._connect_internal()

    async def _connect_internal(self) -> None:
        """Internal connect that must be called while holding self._lock."""
        if self._client is not None and self._client.connected:
            return
        self._client = AsyncModbusTcpClient(
            host=self._host,
            port=self._port,
            timeout=self._timeout,
        )
        if not await self._client.connect():
            self._client = None
            raise ConnectionException(
                f"Failed to connect to {self._host}:{self._port}"
            )
        _LOGGER.debug("Connected to %s:%s", self._host, self._port)

    async def disconnect(self) -> None:
        """Close the connection and release resources."""
        if self._client is not None:
            self._client.close()
            self._client = None
            _LOGGER.debug("Disconnected from %s:%s", self._host, self._port)

    async def _ensure_connected(self) -> AsyncModbusTcpClient:
        """Return a connected client, reconnecting if necessary."""
        if self._client is not None and self._client.connected:
            return self._client
        async with self._lock:
            await self._connect_internal()
            return self._client  # type: ignore[return-value]

    def _require_client(self) -> AsyncModbusTcpClient:
        """Return the client or raise if not connected (call while holding lock)."""
        if self._client is None or not self._client.connected:
            raise ConnectionException(
                f"Not connected to {self._host}:{self._port}"
            )
        return self._client

    async def _read_registers(self, address: int, count: int) -> list[int]:
        """Read input registers with retries and exponential backoff."""
        async with self._lock:
            for attempt in range(self._max_retries):
                try:
                    client = self._require_client()
                    kwargs: Any = {_PMODBUS_SLAVE_PARAM: self._slave_id}
                    result = await client.read_input_registers(
                        address=address, count=count, **kwargs
                    )
                    if result.isError():
                        raise ModbusException(
                            f"Modbus error reading address {address}: {result}"
                        )
                    return list(result.registers)
                except ConnectionException:
                    if attempt == self._max_retries - 1:
                        raise
                    await self._try_reconnect()
                    await asyncio.sleep(
                        RETRY_BACKOFF_BASE * (2 ** attempt)
                    )
                except ModbusException:
                    if attempt == self._max_retries - 1:
                        raise
                    await asyncio.sleep(
                        RETRY_BACKOFF_BASE * (2 ** attempt)
                    )
            raise ModbusException("Unexpected: all retries exhausted")

    async def _try_reconnect(self) -> None:
        """Attempt a single reconnect (must be called while holding self._lock)."""
        if self._client is not None:
            self._client.close()
            self._client = None
        _LOGGER.debug("Attempting reconnect to %s:%s", self._host, self._port)
        try:
            await self._connect_internal()
        except ConnectionException:
            _LOGGER.debug("Reconnect attempt failed")

    async def _write_registers(self, address: int, values: list[int]) -> None:
        """Write holding registers with retries and exponential backoff."""
        async with self._lock:
            for attempt in range(self._max_retries):
                try:
                    client = self._require_client()
                    kwargs: Any = {_PMODBUS_SLAVE_PARAM: self._slave_id}
                    result = await client.write_registers(
                        address=address,
                        values=[int(v) for v in values],
                        **kwargs,
                    )
                    if result.isError():
                        raise ModbusException(
                            f"Modbus error writing address {address}: {result}"
                        )
                    return
                except ConnectionException:
                    if attempt == self._max_retries - 1:
                        raise
                    await self._try_reconnect()
                    await asyncio.sleep(
                        RETRY_BACKOFF_BASE * (2 ** attempt)
                    )
                except ModbusException:
                    if attempt == self._max_retries - 1:
                        raise
                    await asyncio.sleep(
                        RETRY_BACKOFF_BASE * (2 ** attempt)
                    )

    def decode_value(self, registers: list[int], reg: RegisterDef) -> Any:
        """Decode raw Modbus register values into a Python value."""
        if not registers:
            raise ValueError(
                f"Empty register list for {reg.name} (expected {reg.size})"
            )
        if len(registers) < reg.size:
            raise ValueError(
                f"Not enough registers for {reg.name}: "
                f"got {len(registers)}, need {reg.size}"
            )

        if reg.datatype == DataType.FLOAT:
            low_word, high_word = registers[0], registers[1]
            raw = struct.pack("<HH", low_word, high_word)
            value = struct.unpack("<f", raw)[0]
            if math.isnan(value) or math.isinf(value):
                _LOGGER.debug(
                    "Register %s returned NaN/Inf at address %s",
                    reg.name, reg.address,
                )
                return None
            return round(value * reg.multiplier, 2)

        word = registers[0]

        if reg.datatype == DataType.UCHAR:
            val = word & 0xFF
            return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

        if reg.datatype == DataType.INT8:
            val = word & 0xFF
            if val >= 128:
                val -= 256
            return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

        if reg.datatype == DataType.INT16:
            val = word
            if val >= 32768:
                val -= 65536
            return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

        if reg.datatype == DataType.UINT16:
            val = word
            return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

        if reg.datatype == DataType.BOOL:
            return bool(word & 0x01)

        if reg.datatype == DataType.BITFLAG:
            return word & 0xFF

        raise ValueError(f"Unsupported datatype for decoding: {reg.datatype}")

    def encode_value(self, value: Any, reg: RegisterDef) -> list[int]:
        """Encode a Python value into raw Modbus register values."""
        if reg.datatype == DataType.FLOAT:
            float_val = float(value) / reg.multiplier
            if math.isnan(float_val) or math.isinf(float_val):
                raise ValueError(
                    f"Cannot encode NaN/Inf for register {reg.name}"
                )
            raw = struct.pack("<f", float_val)
            low, high = struct.unpack("<HH", raw)
            return [low, high]

        if reg.datatype == DataType.UCHAR:
            val = int(round(float(value) / reg.multiplier))
            if not (0 <= val <= 255):
                raise ValueError(
                    f"Value {value} out of UCHAR range for {reg.name}"
                )
            return [val & 0xFF]

        if reg.datatype == DataType.INT8:
            val = int(round(float(value) / reg.multiplier))
            if not (-128 <= val <= 127):
                raise ValueError(
                    f"Value {value} out of INT8 range for {reg.name}"
                )
            if val < 0:
                val += 256
            return [val & 0xFF]

        if reg.datatype == DataType.INT16:
            val = int(round(float(value) / reg.multiplier))
            if not (-32768 <= val <= 32767):
                raise ValueError(
                    f"Value {value} out of INT16 range for {reg.name}"
                )
            if val < 0:
                val += 65536
            return [val & 0xFFFF]

        if reg.datatype == DataType.UINT16:
            val = int(round(float(value) / reg.multiplier))
            if not (0 <= val <= 65535):
                raise ValueError(
                    f"Value {value} out of UINT16 range for {reg.name}"
                )
            return [val & 0xFFFF]

        if reg.datatype == DataType.BOOL:
            return [1 if value else 0]

        if reg.datatype == DataType.BITFLAG:
            return [int(value) & 0xFF]

        raise ValueError(f"Unsupported datatype for encoding: {reg.datatype}")

    async def read_register(self, reg: RegisterDef) -> Any:
        """Read a single register, auto-connecting if needed."""
        await self._ensure_connected()
        registers = await self._read_registers(reg.address, reg.size)
        return self.decode_value(registers, reg)

    async def write_register(self, reg: RegisterDef, value: Any) -> None:
        """Write a single register after validation, auto-connecting if needed."""
        if not reg.writable:
            raise ValueError(f"Register '{reg.name}' is read-only")

        if reg.min_val is not None and float(value) < reg.min_val:
            raise ValueError(
                f"Value {value} for '{reg.name}' is below minimum {reg.min_val}"
            )
        if reg.max_val is not None and float(value) > reg.max_val:
            raise ValueError(
                f"Value {value} for '{reg.name}' exceeds maximum {reg.max_val}"
            )

        await self._ensure_connected()
        encoded = self.encode_value(value, reg)
        await self._write_registers(reg.address, encoded)

    async def read_batch(
        self, register_list: list[RegisterDef]
    ) -> dict[str, Any]:
        """Read multiple registers efficiently using grouped batch reads."""
        if not register_list:
            return {}

        valid_regs = [
            r for r in register_list
            if r.name not in self._permanently_failed_registers
        ]
        if not valid_regs:
            return {}

        await self._ensure_connected()
        groups = self._group_registers(valid_regs)

        results: dict[str, Any] = {}
        for group in groups:
            group_res = await self._read_group(group)
            results.update(group_res)

        return results

    @staticmethod
    def _group_registers(
        regs: list[RegisterDef],
    ) -> list[list[RegisterDef]]:
        """Sort and group registers into contiguous chunks for batch reads."""
        sorted_regs = sorted(regs, key=lambda r: r.address)
        groups: list[list[RegisterDef]] = []
        current_group: list[RegisterDef] = [sorted_regs[0]]

        for reg in sorted_regs[1:]:
            first = current_group[0]
            last = current_group[-1]
            expected_next = last.address + last.size

            if (
                reg.address <= expected_next + _MAX_GROUP_GAP
                and (reg.address + reg.size - first.address) <= _MAX_GROUP_SIZE
            ):
                current_group.append(reg)
            else:
                groups.append(current_group)
                current_group = [reg]

        groups.append(current_group)
        return groups

    async def _read_group(
        self, group: list[RegisterDef]
    ) -> dict[str, Any]:
        """Read a group of registers in one batch, falling back to individual reads."""
        start = group[0].address
        end = group[-1].address + group[-1].size
        count = end - start

        try:
            registers = await self._read_registers(start, count)
        except ConnectionException:
            _LOGGER.warning(
                "Connection lost while reading group at address %d", start
            )
            raise
        except ModbusException as err:
            _LOGGER.debug(
                "Group read at address %d failed: %s. "
                "Falling back to individual reads.",
                start, err,
            )
            return await self._read_individual_fallback(group)

        data: dict[str, Any] = {}
        for reg in group:
            offset = reg.address - start
            try:
                reg_slice = registers[offset : offset + reg.size]
                if len(reg_slice) < reg.size:
                    _LOGGER.warning(
                        "Incomplete data for register %s (address %d)",
                        reg.name, reg.address,
                    )
                    continue
                data[reg.name] = self.decode_value(reg_slice, reg)
            except (ValueError, IndexError) as err:
                _LOGGER.debug(
                    "Failed to decode register %s (address %d): %s",
                    reg.name, reg.address, err,
                )
        return data

    async def _read_individual_fallback(
        self, group: list[RegisterDef]
    ) -> dict[str, Any]:
        """Read registers one by one and track failures."""
        data: dict[str, Any] = {}
        for reg in group:
            try:
                registers = await self._read_registers(reg.address, reg.size)
                data[reg.name] = self.decode_value(registers, reg)
            except ConnectionException:
                _LOGGER.warning(
                    "Connection lost during individual read of %s (address %d)",
                    reg.name, reg.address,
                )
                raise
            except ModbusException as err:
                failures = self._register_failures.get(reg.name, 0) + 1
                self._register_failures[reg.name] = failures
                if failures >= _PERMANENT_FAILURE_THRESHOLD:
                    self._permanently_failed_registers.add(reg.name)
                    _LOGGER.warning(
                        "Register %s (address %d) has failed %d times. "
                        "Marking as permanently failed.",
                        reg.name, reg.address, failures,
                    )
                else:
                    _LOGGER.debug(
                        "Register %s (address %d) failed: %s (%d/%d attempts)",
                        reg.name, reg.address, err,
                        failures, _PERMANENT_FAILURE_THRESHOLD,
                    )
            except (ValueError, IndexError) as err:
                _LOGGER.warning(
                    "Decoding failed for register %s (address %d): %s",
                    reg.name, reg.address, err,
                )
        return data

    def reset_failed_registers(self) -> None:
        """Clear the permanently failed register set so they will be retried."""
        self._permanently_failed_registers.clear()
        self._register_failures.clear()
        _LOGGER.info("Permanently failed registers have been reset")
