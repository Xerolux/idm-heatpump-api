"""Async Modbus TCP client for IDM Navigator heat pumps."""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pymodbus
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusException

from .const import (
    DEFAULT_TIMEOUT,
    FEATURE_CASCADE,
    FEATURE_HEATING_CIRCUITS,
    FEATURE_ISC,
    FEATURE_PV,
    FEATURE_SOLAR,
    FEATURE_ZONE_MODULES,
    HEATING_CIRCUIT_LETTERS,
    MAX_HEATING_CIRCUITS,
    MAX_RETRIES,
    MAX_ZONE_MODULES,
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
    MODEL_UNKNOWN,
    RETRY_BACKOFF_BASE,
)

_LOGGER = logging.getLogger(__name__)

_MAX_GROUP_GAP = 10
_MAX_GROUP_SIZE = 40
_PERMANENT_FAILURE_THRESHOLD = 3
DEFAULT_EEPROM_WRITE_INTERVAL = 60.0
DEFAULT_CYCLIC_WRITE_TTL = 300.0

_DETECT_HC_FLOW_BASE = 1350
_DETECT_HC_STEP = 2
_DETECT_ZONE_MODULE_BASE = 2000
_DETECT_ZONE_MODULE_STEP = 65
DEFAULT_REGISTER_SOURCE = "official_idm_modbus"
DEFAULT_REGISTER_SOURCE_VERSION = (
    "MODBUS TCP NAVIGATOR 10 2025-06-18 plus Navigator 2.0/Pro legacy docs"
)


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


class RegisterType(Enum):
    INPUT = "input"
    HOLDING = "holding"


class WriteClass(Enum):
    FORBIDDEN = "forbidden"
    VOLATILE = "volatile"
    CYCLIC = "cyclic"
    EEPROM = "eeprom"
    WRITE_ONLY = "write_only"


@dataclass
class IdmModelInfo:
    model_name: str
    active_heating_circuits: list[str]
    zone_modules: int
    has_solar: bool
    has_isc: bool
    has_pv: bool
    has_cascade: bool
    features: set[str] = field(default_factory=set)
    firmware_version: float | None = None

    @property
    def is_pro(self) -> bool:
        return self.zone_modules > 0


@dataclass(frozen=True)
class ModbusErrorContext:
    operation: str
    address: int
    count: int
    register_type: str
    error_type: str
    message: str
    attempt: int


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
    register_type: RegisterType = RegisterType.INPUT
    eeprom_sensitive: bool = False
    cyclic_required: bool = False
    cyclic_write_ttl: float | None = None
    binary: bool = False
    enabled_by_default: bool = True
    state_class: str | None = None
    icon: str | None = None
    write_only: bool = False
    exclude_from_write: set[int] | None = None
    source: str = DEFAULT_REGISTER_SOURCE
    source_version: str = DEFAULT_REGISTER_SOURCE_VERSION
    supported_models: tuple[str, ...] = field(
        default_factory=lambda: (MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_20, MODEL_NAVIGATOR_PRO)
    )
    sentinel_values: tuple[int | float | str, ...] = ()
    last_verified: str | None = None
    size: int = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.datatype, DataType):
            raise ValueError(f"Invalid datatype: {self.datatype}")
        if not isinstance(self.register_type, RegisterType):
            raise ValueError(f"Invalid register type: {self.register_type}")
        if self.address < 0:
            raise ValueError(f"Register address must be non-negative, got {self.address}")
        if not self.source:
            raise ValueError(f"Register source must not be empty for {self.name}")
        if not self.source_version:
            raise ValueError(f"Register source version must not be empty for {self.name}")
        if not self.supported_models:
            raise ValueError(f"Register {self.name} must declare at least one supported model")
        if not math.isfinite(self.multiplier) or self.multiplier == 0:
            raise ValueError(f"Multiplier must be finite and non-zero, got {self.multiplier}")
        if self.min_val is not None and not math.isfinite(self.min_val):
            raise ValueError(f"Minimum value must be finite, got {self.min_val}")
        if self.max_val is not None and not math.isfinite(self.max_val):
            raise ValueError(f"Maximum value must be finite, got {self.max_val}")
        if self.min_val is not None and self.max_val is not None and self.min_val > self.max_val:
            raise ValueError(f"Minimum value {self.min_val} exceeds maximum {self.max_val}")
        if not self.writable and (
            self.eeprom_sensitive
            or self.cyclic_required
            or self.write_only
            or self.exclude_from_write
        ):
            raise ValueError(f"Write metadata requires writable=True for register {self.name}")
        if self.eeprom_sensitive and self.cyclic_required:
            raise ValueError(f"Register {self.name} cannot be both EEPROM-sensitive and cyclic")
        if self.cyclic_write_ttl is not None:
            if not self.cyclic_required:
                raise ValueError(f"Cyclic write TTL requires cyclic_required=True for {self.name}")
            if not math.isfinite(self.cyclic_write_ttl) or self.cyclic_write_ttl <= 0:
                raise ValueError(f"Cyclic write TTL must be finite and positive for {self.name}")
        self.size = 2 if self.datatype == DataType.FLOAT else 1

    @property
    def write_class(self) -> WriteClass:
        if not self.writable:
            return WriteClass.FORBIDDEN
        if self.write_only:
            return WriteClass.WRITE_ONLY
        if self.cyclic_required:
            return WriteClass.CYCLIC
        if self.eeprom_sensitive:
            return WriteClass.EEPROM
        return WriteClass.VOLATILE


class IdmModbusClient:
    """Async Modbus TCP client for IDM Navigator heat pumps.

    Features:
      - Automatic reconnection on connection loss
      - Configurable retries with exponential backoff
      - Batch reads with automatic grouping and fallback to individual reads
      - Permanently failed register tracking to avoid repeated failures
      - Model detection with capability probing
      - Support for both input and holding registers
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
        if max_retries < 1:
            raise ValueError(f"max_retries must be >= 1, got {max_retries}")

        self._host = host
        self._port = int(port)
        self._slave_id = int(slave_id)
        self._timeout = float(timeout)
        self._max_retries = int(max_retries)
        self._client: AsyncModbusTcpClient | None = None
        self._lock = asyncio.Lock()
        self._register_failures: dict[str, int] = {}
        self._permanently_failed_registers: set[str] = set()
        self._model_info: IdmModelInfo | None = None
        self._last_eeprom_writes: dict[str, float] = {}
        self._cyclic_write_deadlines: dict[str, float] = {}
        self._last_error_context: ModbusErrorContext | None = None
        self._eeprom_write_interval = DEFAULT_EEPROM_WRITE_INTERVAL
        self._time = time.monotonic

    def __repr__(self) -> str:
        connected = self._client is not None and self._client.connected
        return f"IdmModbusClient(host={self._host!r}, port={self._port}, slave_id={self._slave_id}, connected={connected})"

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return self._port

    @property
    def is_connected(self) -> bool:
        return self._client is not None and self._client.connected

    @property
    def model_info(self) -> IdmModelInfo | None:
        return self._model_info

    @property
    def model_name(self) -> str:
        """Return the detected model name, falling back to the default model.

        Falls back to MODEL_NAVIGATOR_20 if detect_model() has not been
        called yet, or if detection was inconclusive (MODEL_UNKNOWN).
        """
        if self._model_info is None or self._model_info.model_name == MODEL_UNKNOWN:
            return MODEL_NAVIGATOR_20
        return self._model_info.model_name

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
            raise ConnectionException(  # type: ignore[no-untyped-call]
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
            raise ConnectionException(  # type: ignore[no-untyped-call]
                f"Not connected to {self._host}:{self._port}"
            )
        return self._client

    async def _read_registers(
        self,
        address: int,
        count: int,
        reg_type: RegisterType = RegisterType.INPUT,
    ) -> list[int]:
        """Read registers with retries and exponential backoff."""
        async with self._lock:
            for attempt in range(self._max_retries):
                try:
                    client = self._require_client()
                    kwargs: Any = {_PMODBUS_SLAVE_PARAM: self._slave_id}
                    if reg_type == RegisterType.HOLDING:
                        result = await client.read_holding_registers(
                            address=address, count=count, **kwargs
                        )
                    else:
                        result = await client.read_input_registers(
                            address=address, count=count, **kwargs
                        )
                    if result.isError():
                        raise ModbusException(  # type: ignore[no-untyped-call]
                            f"Modbus error reading address {address}: {result}"
                        )
                    registers = list(result.registers)
                    if len(registers) != count:
                        raise ModbusException(  # type: ignore[no-untyped-call]
                            f"Incomplete Modbus response at address {address}: "
                            f"got {len(registers)} registers, expected {count}"
                        )
                    return registers
                except ConnectionException as err:
                    self._record_error_context(
                        "read",
                        address,
                        count,
                        reg_type,
                        err,
                        attempt + 1,
                    )
                    if attempt == self._max_retries - 1:
                        raise
                    await self._try_reconnect()
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2**attempt))
                except ModbusException as err:
                    self._record_error_context(
                        "read",
                        address,
                        count,
                        reg_type,
                        err,
                        attempt + 1,
                    )
                    if attempt == self._max_retries - 1:
                        raise
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2**attempt))
            raise RuntimeError("Unreachable: max_retries validated to be >= 1")

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
                        raise ModbusException(  # type: ignore[no-untyped-call]
                            f"Modbus error writing address {address}: {result}"
                        )
                    return
                except ConnectionException as err:
                    self._record_error_context(
                        "write",
                        address,
                        len(values),
                        RegisterType.HOLDING,
                        err,
                        attempt + 1,
                    )
                    if attempt == self._max_retries - 1:
                        raise
                    await self._try_reconnect()
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2**attempt))
                except ModbusException as err:
                    self._record_error_context(
                        "write",
                        address,
                        len(values),
                        RegisterType.HOLDING,
                        err,
                        attempt + 1,
                    )
                    if attempt == self._max_retries - 1:
                        raise
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2**attempt))

    def _record_error_context(
        self,
        operation: str,
        address: int,
        count: int,
        reg_type: RegisterType,
        err: Exception,
        attempt: int,
    ) -> None:
        self._last_error_context = ModbusErrorContext(
            operation=operation,
            address=address,
            count=count,
            register_type=reg_type.value,
            error_type=type(err).__name__,
            message=str(err),
            attempt=attempt,
        )

    def get_last_error_context(self) -> ModbusErrorContext | None:
        return self._last_error_context

    def clear_last_error_context(self) -> None:
        self._last_error_context = None

    async def probe_register(self, address: int, count: int = 1) -> list[int] | None:
        """Try to read a register without affecting failure tracking.

        Returns the register values or None if the read fails.
        """
        try:
            await self._ensure_connected()
            return await self._read_registers(address, count)
        except (ModbusException, ConnectionException, OSError):
            return None

    async def detect_model(self) -> IdmModelInfo:
        """Detect the IDM heat pump model and capabilities by probing registers.

        Strategy:
          1. Verify basic connectivity by reading outdoor temperature (1000)
          2. Probe heating circuit flow temperatures (1350-1362)
          3. Probe zone module presence (2000, 2065, ...)
          4. Probe solar register (1850)
          5. Probe ISC register (1870)
          6. Probe PV register (74)
          7. Probe cascade register (1147)
        """
        await self._ensure_connected()

        active_circuits: list[str] = []
        for i in range(MAX_HEATING_CIRCUITS):
            addr = _DETECT_HC_FLOW_BASE + i * _DETECT_HC_STEP
            regs = await self.probe_register(addr, 2)
            if regs is not None and len(regs) == 2:
                try:
                    raw = struct.pack("<HH", regs[0], regs[1])
                    val = struct.unpack("<f", raw)[0]
                    if not (math.isnan(val) or math.isinf(val)) and -50 < val < 80:
                        active_circuits.append(HEATING_CIRCUIT_LETTERS[i])
                except (struct.error, ValueError):
                    if regs is not None:
                        active_circuits.append(HEATING_CIRCUIT_LETTERS[i])

        zone_modules = 0
        for zm in range(MAX_ZONE_MODULES):
            addr = _DETECT_ZONE_MODULE_BASE + zm * _DETECT_ZONE_MODULE_STEP
            regs = await self.probe_register(addr, 1)
            if regs is not None:
                zone_modules = zm + 1

        has_solar = False
        solar_regs = await self.probe_register(1850, 2)
        if solar_regs is not None and len(solar_regs) == 2:
            try:
                raw = struct.pack("<HH", solar_regs[0], solar_regs[1])
                val = struct.unpack("<f", raw)[0]
                if not (math.isnan(val) or math.isinf(val)):
                    has_solar = True
            except (struct.error, ValueError):
                has_solar = True

        has_isc = False
        isc_regs = await self.probe_register(1870, 2)
        if isc_regs is not None and len(isc_regs) == 2:
            try:
                raw = struct.pack("<HH", isc_regs[0], isc_regs[1])
                val = struct.unpack("<f", raw)[0]
                if not (math.isnan(val) or math.isinf(val)):
                    has_isc = True
            except (struct.error, ValueError):
                has_isc = True

        pv_regs = await self.probe_register(74, 2)
        has_pv = pv_regs is not None and len(pv_regs) == 2

        has_cascade = False
        cascade_regs = await self.probe_register(1147, 1)
        if cascade_regs is not None and len(cascade_regs) == 1 and cascade_regs[0] != 0:
            has_cascade = True

        features: set[str] = set()
        if active_circuits:
            features.add(FEATURE_HEATING_CIRCUITS)
        if zone_modules > 0:
            features.add(FEATURE_ZONE_MODULES)
        if has_solar:
            features.add(FEATURE_SOLAR)
        if has_isc:
            features.add(FEATURE_ISC)
        if has_pv:
            features.add(FEATURE_PV)
        if has_cascade:
            features.add(FEATURE_CASCADE)

        # Determine model name
        # Prefer Navigator 10 when we see strong indicators (newer registers present)
        has_navigator_10_indicators = False
        try:
            # Heat sink flow (1072) or power limit (4108) are good Navigator 10 signals
            hs = await self.probe_register(1072, 1)
            pl = await self.probe_register(4108, 2)
            if (hs is not None and len(hs) == 1) or (pl is not None and len(pl) == 2):
                has_navigator_10_indicators = True
        except Exception:
            pass

        if has_navigator_10_indicators or zone_modules > 0:
            # Navigator 10 is the current generation; also report Pro-like capabilities
            model_name = MODEL_NAVIGATOR_10 if has_navigator_10_indicators else MODEL_NAVIGATOR_PRO
        elif active_circuits:
            model_name = MODEL_NAVIGATOR_20
        else:
            model_name = MODEL_UNKNOWN

        firmware_version: float | None = None
        fw_regs = await self.probe_register(4120, 2)
        if fw_regs is not None and len(fw_regs) == 2:
            try:
                raw = struct.pack("<HH", fw_regs[0], fw_regs[1])
                val = struct.unpack("<f", raw)[0]
                if not (math.isnan(val) or math.isinf(val)):
                    firmware_version = round(val, 2)
            except (struct.error, ValueError):
                pass

        info = IdmModelInfo(
            model_name=model_name,
            active_heating_circuits=active_circuits,
            zone_modules=zone_modules,
            has_solar=has_solar,
            has_isc=has_isc,
            has_pv=has_pv,
            has_cascade=has_cascade,
            features=features,
            firmware_version=firmware_version,
        )
        self._model_info = info
        _LOGGER.info(
            "Detected IDM model: %s (circuits=%s, zones=%d, solar=%s, isc=%s, pv=%s, cascade=%s, firmware=%s)",
            model_name,
            active_circuits,
            zone_modules,
            has_solar,
            has_isc,
            has_pv,
            has_cascade,
            firmware_version,
        )
        return info

    def decode_value(self, registers: list[int], reg: RegisterDef) -> Any:
        """Decode raw Modbus register values into a Python value."""
        if not registers:
            raise ValueError(f"Empty register list for {reg.name} (expected {reg.size})")
        if len(registers) < reg.size:
            raise ValueError(
                f"Not enough registers for {reg.name}: got {len(registers)}, need {reg.size}"
            )

        if reg.datatype == DataType.FLOAT:
            low_word, high_word = registers[0], registers[1]
            raw = struct.pack("<HH", low_word, high_word)
            value = struct.unpack("<f", raw)[0]
            if math.isnan(value) or math.isinf(value):
                _LOGGER.debug(
                    "Register %s returned NaN/Inf at address %s",
                    reg.name,
                    reg.address,
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
                raise ValueError(f"Cannot encode NaN/Inf for register {reg.name}")
            raw = struct.pack("<f", float_val)
            low, high = struct.unpack("<HH", raw)
            return [low, high]

        if reg.datatype == DataType.UCHAR:
            val = int(round(float(value) / reg.multiplier))
            if not (0 <= val <= 255):
                raise ValueError(f"Value {value} out of UCHAR range for {reg.name}")
            return [val & 0xFF]

        if reg.datatype == DataType.INT8:
            val = int(round(float(value) / reg.multiplier))
            if not (-128 <= val <= 127):
                raise ValueError(f"Value {value} out of INT8 range for {reg.name}")
            if val < 0:
                val += 256
            return [val & 0xFF]

        if reg.datatype == DataType.INT16:
            val = int(round(float(value) / reg.multiplier))
            if not (-32768 <= val <= 32767):
                raise ValueError(f"Value {value} out of INT16 range for {reg.name}")
            if val < 0:
                val += 65536
            return [val & 0xFFFF]

        if reg.datatype == DataType.UINT16:
            val = int(round(float(value) / reg.multiplier))
            if not (0 <= val <= 65535):
                raise ValueError(f"Value {value} out of UINT16 range for {reg.name}")
            return [val & 0xFFFF]

        if reg.datatype == DataType.BOOL:
            return [1 if value else 0]

        if reg.datatype == DataType.BITFLAG:
            return [int(value) & 0xFF]

        raise ValueError(f"Unsupported datatype for encoding: {reg.datatype}")

    async def read_register(self, reg: RegisterDef) -> Any:
        """Read a single register, auto-connecting if needed."""
        if reg.write_only:
            raise ValueError(f"Register '{reg.name}' is write-only")
        await self._ensure_connected()
        registers = await self._read_registers(reg.address, reg.size, reg.register_type)
        return self.decode_value(registers, reg)

    async def write_register(self, reg: RegisterDef, value: Any) -> None:
        """Write a single register after validation, auto-connecting if needed."""
        if not reg.writable:
            raise ValueError(f"Register '{reg.name}' is read-only")

        self._validate_write_allowed(reg, value)

        await self._ensure_connected()
        encoded = self.encode_value(value, reg)
        await self._write_registers(reg.address, encoded)
        self._record_successful_write(reg)

    def _validate_write_allowed(self, reg: RegisterDef, value: Any) -> None:
        self._validate_model_availability(reg)

        if reg.exclude_from_write and int(value) in reg.exclude_from_write:
            raise ValueError(
                f"Value {value} for '{reg.name}' is not writable (excluded values: {reg.exclude_from_write})"
            )

        if reg.min_val is not None and float(value) < reg.min_val:
            raise ValueError(f"Value {value} for '{reg.name}' is below minimum {reg.min_val}")
        if reg.max_val is not None and float(value) > reg.max_val:
            raise ValueError(f"Value {value} for '{reg.name}' exceeds maximum {reg.max_val}")

        if reg.write_class is WriteClass.EEPROM:
            now = self._time()
            last_write = self._last_eeprom_writes.get(reg.name)
            if last_write is not None:
                elapsed = now - last_write
                if elapsed < self._eeprom_write_interval:
                    remaining = self._eeprom_write_interval - elapsed
                    raise ValueError(
                        f"EEPROM-sensitive register '{reg.name}' was written too recently "
                        f"(try again in {remaining:.1f}s)"
                    )

    def _validate_model_availability(self, reg: RegisterDef) -> None:
        if self._model_info is None:
            return

        from .registers import build_register_map

        available = build_register_map(model_info=self._model_info).get(reg.name)
        if available is None or available.address != reg.address:
            raise ValueError(
                f"Register '{reg.name}' is not available for detected model {self._model_info.model_name}"
            )

    def _record_successful_write(self, reg: RegisterDef) -> None:
        if reg.write_class is WriteClass.EEPROM:
            self._last_eeprom_writes[reg.name] = self._time()
        if reg.write_class is WriteClass.CYCLIC:
            ttl = reg.cyclic_write_ttl or DEFAULT_CYCLIC_WRITE_TTL
            self._cyclic_write_deadlines[reg.name] = self._time() + ttl

    def reset_write_throttle(self, reg: RegisterDef | None = None) -> None:
        if reg is None:
            self._last_eeprom_writes.clear()
        else:
            self._last_eeprom_writes.pop(reg.name, None)

    def get_active_cyclic_writes(self) -> dict[str, float]:
        now = self._time()
        return {
            name: deadline
            for name, deadline in self._cyclic_write_deadlines.items()
            if deadline > now
        }

    def get_expired_cyclic_writes(self) -> set[str]:
        now = self._time()
        return {name for name, deadline in self._cyclic_write_deadlines.items() if deadline <= now}

    def reset_cyclic_write_state(self, reg: RegisterDef | None = None) -> None:
        if reg is None:
            self._cyclic_write_deadlines.clear()
        else:
            self._cyclic_write_deadlines.pop(reg.name, None)

    async def read_batch(self, register_list: list[RegisterDef]) -> dict[str, Any]:
        """Read multiple registers efficiently using grouped batch reads."""
        if not register_list:
            return {}

        valid_regs = [
            r
            for r in register_list
            if r.name not in self._permanently_failed_registers and not r.write_only
        ]
        if not valid_regs:
            return {}

        await self._ensure_connected()

        input_regs = [r for r in valid_regs if r.register_type == RegisterType.INPUT]
        holding_regs = [r for r in valid_regs if r.register_type == RegisterType.HOLDING]

        results: dict[str, Any] = {}

        if input_regs:
            groups = self._group_registers(input_regs)
            for group in groups:
                group_res = await self._read_group(group, RegisterType.INPUT)
                results.update(group_res)

        if holding_regs:
            groups = self._group_registers(holding_regs)
            for group in groups:
                group_res = await self._read_group(group, RegisterType.HOLDING)
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
        self,
        group: list[RegisterDef],
        reg_type: RegisterType = RegisterType.INPUT,
    ) -> dict[str, Any]:
        """Read a group of registers in one batch, falling back to individual reads."""
        start = group[0].address
        end = group[-1].address + group[-1].size
        count = end - start

        try:
            registers = await self._read_registers(start, count, reg_type)
        except ConnectionException:
            _LOGGER.warning("Connection lost while reading group at address %d", start)
            raise
        except ModbusException as err:
            _LOGGER.debug(
                "Group read at address %d failed: %s. Falling back to individual reads.",
                start,
                err,
            )
            return await self._read_individual_fallback(group, reg_type)

        data: dict[str, Any] = {}
        for reg in group:
            offset = reg.address - start
            try:
                reg_slice = registers[offset : offset + reg.size]
                if len(reg_slice) < reg.size:
                    _LOGGER.warning(
                        "Incomplete data for register %s (address %d)",
                        reg.name,
                        reg.address,
                    )
                    continue
                data[reg.name] = self.decode_value(reg_slice, reg)
            except (ValueError, IndexError) as err:
                _LOGGER.debug(
                    "Failed to decode register %s (address %d): %s",
                    reg.name,
                    reg.address,
                    err,
                )
        return data

    async def _read_individual_fallback(
        self,
        group: list[RegisterDef],
        reg_type: RegisterType = RegisterType.INPUT,
    ) -> dict[str, Any]:
        """Read registers one by one and track failures."""
        data: dict[str, Any] = {}
        for reg in group:
            try:
                registers = await self._read_registers(reg.address, reg.size, reg_type)
                data[reg.name] = self.decode_value(registers, reg)
            except ConnectionException:
                _LOGGER.warning(
                    "Connection lost during individual read of %s (address %d)",
                    reg.name,
                    reg.address,
                )
                raise
            except ModbusException as err:
                failures = self._register_failures.get(reg.name, 0) + 1
                self._register_failures[reg.name] = failures
                if failures >= _PERMANENT_FAILURE_THRESHOLD:
                    self._permanently_failed_registers.add(reg.name)

                    # Some registers (e.g. firmware_version on certain Navigator 10 firmwares)
                    # are expected to be missing or unreliable. Log at debug level for those.
                    if "firmware" in reg.name.lower():
                        _LOGGER.debug(
                            "Register %s (address %d) is not available on this device. "
                            "Marking as permanently failed (this is normal on some firmware versions).",
                            reg.name,
                            reg.address,
                        )
                    else:
                        _LOGGER.warning(
                            "Register %s (address %d) has failed %d times. Marking as permanently failed.",
                            reg.name,
                            reg.address,
                            failures,
                        )
                else:
                    _LOGGER.debug(
                        "Register %s (address %d) failed: %s (%d/%d attempts)",
                        reg.name,
                        reg.address,
                        err,
                        failures,
                        _PERMANENT_FAILURE_THRESHOLD,
                    )
            except (ValueError, IndexError) as err:
                _LOGGER.warning(
                    "Decoding failed for register %s (address %d): %s",
                    reg.name,
                    reg.address,
                    err,
                )
        return data

    def reset_failed_registers(self) -> None:
        """Clear the permanently failed register set so they will be retried."""
        self._permanently_failed_registers.clear()
        self._register_failures.clear()
        _LOGGER.info("Permanently failed registers have been reset")
