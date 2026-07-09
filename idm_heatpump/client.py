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
from typing import Any, Awaitable, Callable, ClassVar, TypeVar

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
    MODEL_DETECTION_MAX_RETRIES,
    MODEL_DETECTION_TIMEOUT,
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
    MODEL_UNKNOWN,
    RETRY_BACKOFF_BASE,
)

_LOGGER = logging.getLogger(__name__)

_T = TypeVar("_T")

_MAX_GROUP_GAP = 10
_MAX_GROUP_SIZE = 40
_PERMANENT_FAILURE_THRESHOLD = 3
DEFAULT_EEPROM_WRITE_INTERVAL = 60.0
DEFAULT_CYCLIC_WRITE_TTL = 300.0

# Pymodbus internal retries are disabled by default. The library already
# implements its own retry loop with exponential backoff in
# ``_read_registers`` / ``_write_registers``. Stacking pymodbus's internal
# retries on top multiplies the effective attempt count (e.g. 3 library
# retries x 3 pymodbus retries = up to 9 attempts per register) which makes
# recovery from connection drops slow and produces noisy
# "No response received after N retries" log lines on every failure.
_PMODBUS_RETRIES_DEFAULT = 0
_PMODBUS_RECONNECT_DELAY = 0.5
_PMODBUS_RECONNECT_DELAY_MAX = 10.0

_DETECT_HC_FLOW_BASE = 1350
_DETECT_HC_STEP = 2
_DETECT_ZONE_MODULE_BASE = 2000
_DETECT_ZONE_MODULE_STEP = 65
_DETECT_EMPTY_SLOT_STOP_THRESHOLD = 2
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


def quiet_pymodbus_logging(level: str | int = "WARNING") -> None:
    """Reduce pymodbus frame-logging noise (``>>>>> send/recv`` lines).

    pymodbus logs every raw Modbus frame at DEBUG level via the
    ``pymodbus.logging`` logger, and logs transport failures such as
    ``Cancel send, because not connected!`` at ERROR level. On unstable TCP
    links this floods the Home Assistant log.

    Consumers can opt in to quieter pymodbus logging by calling this helper
    once during setup, e.g.::

        from idm_heatpump import quiet_pymodbus_logging
        quiet_pymodbus_logging("WARNING")

    This only adjusts the ``pymodbus`` logger tree and is safe to call even
    if the consumer later raises the level again.
    """
    if isinstance(level, str):
        numeric = logging.getLevelName(level.upper())
        if not isinstance(numeric, int):
            raise ValueError(f"Unknown log level: {level}")
        level = numeric
    logging.getLogger("pymodbus").setLevel(level)


class IllegalAddressError(ModbusException):
    """Modbus ``Illegal Data Address`` (exception code 2).

    Raised when the device reports that a register address does not exist.
    Unlike a generic :class:`ModbusException`, this is a permanent condition
    for the address in question: retrying is pointless and only produces noisy
    log lines. Callers that detect this marker (via ``isinstance`` or the
    ``is_illegal_address`` attribute) can short-circuit retries and suppress
    the repeated "failed after N attempts" warnings that otherwise flood the
    log when optional registers are probed on devices that do not implement
    them (e.g. Navigator-10-only blocks read against a Navigator 2.0).
    """

    #: Sentinel attribute checked by the retry loop to bail out silently.
    is_illegal_address: bool = True


def _is_illegal_address_exception(err: BaseException) -> bool:
    """Return whether ``err`` represents a Modbus ``Illegal Data Address``.

    Detects both our own :class:`IllegalAddressError` marker and raw pymodbus
    exception-code-2 responses (``ExceptionResponse(exception_code=2)``),
    which is how the device signals an unsupported address before we wrap it.
    """
    if isinstance(err, IllegalAddressError):
        return True
    message = str(err).casefold()
    return "exception_code=2" in message or "illegal data address" in message


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


@dataclass(frozen=True)
class WriteSafetyResult:
    """Validated write plan before any Modbus packet is sent."""

    register: "RegisterDef"
    requested_value: Any
    encoded_registers: tuple[int, ...]
    dry_run: bool = False


@dataclass(frozen=True)
class IdmClientDiagnostics:
    """Sanitized diagnostics for the Modbus backend."""

    navigator_type: str
    modbus_connected: bool
    firmware: str | None = None
    last_error: str | None = None
    permanently_failed_registers: tuple[str, ...] = ()
    connection_suspect: bool = False


@dataclass(frozen=True)
class FeatureFlags:
    """Opt-in feature switches for safer rollout of new API surfaces."""

    enable_nav2_web: bool = True
    enable_nav10_ws: bool = True
    enable_experimental_features: bool = False
    enable_write_support: bool = True
    enable_debug_endpoints: bool = False


class AdaptiveBackoff:
    """Small reusable exponential backoff helper for network retry loops."""

    def __init__(
        self,
        *,
        initial: float = 5.0,
        multiplier: float = 3.0,
        maximum: float = 300.0,
    ) -> None:
        if initial <= 0:
            raise ValueError("initial backoff must be positive")
        if multiplier < 1:
            raise ValueError("backoff multiplier must be >= 1")
        if maximum < initial:
            raise ValueError("maximum backoff must be >= initial")
        self._initial = float(initial)
        self._multiplier = float(multiplier)
        self._maximum = float(maximum)
        self._current = self._initial

    def next_delay(self) -> float:
        delay = self._current
        self._current = min(self._current * self._multiplier, self._maximum)
        return delay

    def reset(self) -> None:
        self._current = self._initial


class PollRateLimiter:
    """Simple monotonic rate limiter for Modbus/web/diagnostic polling loops."""

    def __init__(self, interval: float, *, clock: Any = time.monotonic) -> None:
        if interval < 0:
            raise ValueError("poll interval must be >= 0")
        self._interval = float(interval)
        self._clock = clock
        self._next_allowed = 0.0

    @property
    def interval(self) -> float:
        return self._interval

    def remaining(self) -> float:
        return max(0.0, self._next_allowed - float(self._clock()))

    def allow(self) -> bool:
        return self.remaining() <= 0

    def mark(self) -> None:
        self._next_allowed = self._clock() + self._interval


class ModbusCodec:
    """Centralized Modbus register encoder/decoder."""

    @staticmethod
    def decode_float32(registers: list[int], *, swapped: bool = False) -> float:
        if len(registers) < 2:
            raise ValueError("FLOAT32 decoding requires two registers")
        words = (registers[1], registers[0]) if swapped else (registers[0], registers[1])
        return float(struct.unpack("<f", struct.pack("<HH", words[0], words[1]))[0])

    @staticmethod
    def encode_float32(value: float, *, swapped: bool = False) -> list[int]:
        raw = struct.pack("<f", value)
        low, high = struct.unpack("<HH", raw)
        return [high, low] if swapped else [low, high]

    @staticmethod
    def decode_int16(register: int) -> int:
        value = register & 0xFFFF
        return value - 65536 if value >= 32768 else value

    @staticmethod
    def encode_int16(value: int) -> int:
        if not (-32768 <= value <= 32767):
            raise ValueError(f"Value {value} out of INT16 range")
        return value + 65536 if value < 0 else value

    @staticmethod
    def decode_int8(register: int) -> int:
        value = register & 0xFF
        return value - 256 if value >= 128 else value

    @staticmethod
    def encode_int8(value: int) -> int:
        if not (-128 <= value <= 127):
            raise ValueError(f"Value {value} out of INT8 range")
        return value + 256 if value < 0 else value


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
        *,
        pymodbus_retries: int = _PMODBUS_RETRIES_DEFAULT,
        max_group_size: int = _MAX_GROUP_SIZE,
    ) -> None:
        if not host:
            raise ValueError("Host must not be empty")
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")
        if not (1 <= slave_id <= 247):
            raise ValueError(f"Slave ID must be between 1 and 247, got {slave_id}")
        if max_retries < 1:
            raise ValueError(f"max_retries must be >= 1, got {max_retries}")
        if pymodbus_retries < 0:
            raise ValueError(f"pymodbus_retries must be >= 0, got {pymodbus_retries}")
        if max_group_size < 1:
            raise ValueError(f"max_group_size must be >= 1, got {max_group_size}")

        self._host = host
        self._port = int(port)
        self._slave_id = int(slave_id)
        self._timeout = float(timeout)
        self._max_retries = int(max_retries)
        self._pymodbus_retries = int(pymodbus_retries)
        self._max_group_size = int(max_group_size)
        self._client: AsyncModbusTcpClient | None = None
        self._lock = asyncio.Lock()
        self._register_failures: dict[str, int] = {}
        self._permanently_failed_registers: set[str] = set()
        self._unsupported_registers: set[str] = set()
        self._model_info: IdmModelInfo | None = None
        self._last_eeprom_writes: dict[str, float] = {}
        self._cyclic_write_deadlines: dict[str, float] = {}
        self._last_error_context: ModbusErrorContext | None = None
        self._eeprom_write_interval = DEFAULT_EEPROM_WRITE_INTERVAL
        self._time = time.monotonic
        # Set to True after any IO failure (ConnectionException/OSError). The
        # next _ensure_connected() then closes the (possibly half-open) socket
        # and reconnects hard, instead of trusting pymodbus's .connected flag
        # which stays True after the remote end silently drops the TCP link.
        # This avoids the first failed send that would otherwise log
        # "Cancel send, because not connected!" at ERROR level inside pymodbus.
        self._connection_suspect: bool = False
        # Cache the register map built from the detected model info. The map is
        # deterministic and is consulted on every write for model availability,
        # so rebuilding it repeatedly is wasteful.
        self._cached_register_map: dict[str, RegisterDef] | None = None

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
            retries=self._pymodbus_retries,
            reconnect_delay=_PMODBUS_RECONNECT_DELAY,
            reconnect_delay_max=_PMODBUS_RECONNECT_DELAY_MAX,
        )
        if not await self._client.connect():
            self._client = None
            raise ConnectionException(  # type: ignore[no-untyped-call]
                f"Failed to connect to {self._host}:{self._port}"
            )
        _LOGGER.debug("Connected to %s:%s", self._host, self._port)

    async def disconnect(self) -> None:
        """Close the connection and release resources."""
        async with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None
                _LOGGER.debug("Disconnected from %s:%s", self._host, self._port)

    async def _ensure_connected(self) -> AsyncModbusTcpClient:
        """Return a connected client, reconnecting if necessary.

        If ``_connection_suspect`` is set (a prior IO failed) the current
        pymodbus client is closed even when ``.connected`` is still True,
        because pymodbus only detects a remotely-dropped TCP link on the
        next send. Closing proactively avoids the noisy
        ``Log.error("Cancel send, because not connected!")`` record that
        pymodbus otherwise emits before our retry loop can reconnect.
        """
        if self._client is not None and self._client.connected and not self._connection_suspect:
            return self._client
        async with self._lock:
            if self._connection_suspect and self._client is not None:
                _LOGGER.debug(
                    "Closing suspect pymodbus connection to %s:%s before reconnect",
                    self._host,
                    self._port,
                )
                self._client.close()
                self._client = None
                self._connection_suspect = False
            await self._connect_internal()
            return self._client  # type: ignore[return-value]

    async def force_reconnect(self) -> None:
        """Hard-close the current TCP connection and open a fresh one.

        Public hook for consumers (e.g. the Home Assistant integration)
        to trigger an immediate reconnect after repeated failures without
        waiting for the next poll cycle. Safe to call when no connection
        exists yet. Always clears ``_connection_suspect``.
        """
        async with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None
            self._connection_suspect = False
            await self._connect_internal()

    def _require_client(self) -> AsyncModbusTcpClient:
        """Return the client or raise if not connected (call while holding lock)."""
        if self._client is None or not self._client.connected:
            raise ConnectionException(  # type: ignore[no-untyped-call]
                f"Not connected to {self._host}:{self._port}"
            )
        return self._client

    async def _retry_command(
        self,
        operation: str,
        address: int,
        count: int,
        reg_type: RegisterType,
        command: Callable[[], Awaitable[_T]],
        *,
        max_retries: int | None = None,
    ) -> _T:
        """Execute an async Modbus command with retries and exponential backoff.

        The lock is held for the duration of the retry loop so that connection
        state cannot change underneath us between attempts.
        """
        retries = self._max_retries if max_retries is None else max(1, int(max_retries))
        async with self._lock:
            for attempt in range(retries):
                try:
                    result = await command()
                    self._connection_suspect = False
                    return result
                except ConnectionException as err:
                    self._connection_suspect = True
                    self._record_error_context(
                        operation,
                        address,
                        count,
                        reg_type,
                        err,
                        attempt + 1,
                    )
                    if attempt == retries - 1:
                        _LOGGER.warning(
                            "Modbus %s at address %d failed after %d attempts: %s",
                            operation,
                            address,
                            retries,
                            err,
                        )
                        raise
                    _LOGGER.debug(
                        "Modbus %s at address %d failed (attempt %d/%d): %s; retrying",
                        operation,
                        address,
                        attempt + 1,
                        retries,
                        err,
                    )
                    await self._try_reconnect()
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2**attempt))
                except IllegalAddressError as err:
                    # Illegal Data Address is permanent for the given address
                    # (the register is not implemented on this device). Retrying
                    # would only produce repeated warnings that flood the log
                    # when optional register blocks are read against a device
                    # that does not support them. Re-raise immediately at debug
                    # level so callers can react and isolate the address.
                    self._record_error_context(
                        operation,
                        address,
                        count,
                        reg_type,
                        err,
                        attempt + 1,
                    )
                    _LOGGER.debug(
                        "Modbus %s at address %d reports Illegal Data Address; "
                        "not retrying (register not implemented on this device)",
                        operation,
                        address,
                    )
                    raise
                except ModbusException as err:
                    self._record_error_context(
                        operation,
                        address,
                        count,
                        reg_type,
                        err,
                        attempt + 1,
                    )
                    if attempt == retries - 1:
                        _LOGGER.warning(
                            "Modbus %s at address %d failed after %d attempts: %s",
                            operation,
                            address,
                            retries,
                            err,
                        )
                        raise
                    _LOGGER.debug(
                        "Modbus %s at address %d failed (attempt %d/%d): %s; retrying",
                        operation,
                        address,
                        attempt + 1,
                        retries,
                        err,
                    )
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2**attempt))
                except (OSError, TimeoutError) as err:
                    self._connection_suspect = True
                    self._record_error_context(
                        operation,
                        address,
                        count,
                        reg_type,
                        err,
                        attempt + 1,
                    )
                    if attempt == retries - 1:
                        _LOGGER.warning(
                            "Modbus %s at address %d failed after %d attempts: %s",
                            operation,
                            address,
                            retries,
                            err,
                        )
                        raise
                    _LOGGER.debug(
                        "Modbus %s at address %d failed (attempt %d/%d): %s; retrying",
                        operation,
                        address,
                        attempt + 1,
                        retries,
                        err,
                    )
                    await self._try_reconnect()
                    await asyncio.sleep(RETRY_BACKOFF_BASE * (2**attempt))
        raise RuntimeError("Unreachable: max_retries validated to be >= 1")

    async def _read_registers(
        self,
        address: int,
        count: int,
        reg_type: RegisterType = RegisterType.INPUT,
        *,
        max_retries: int | None = None,
        request_timeout: float | None = None,
    ) -> list[int]:
        """Read registers with retries and exponential backoff."""

        async def _command() -> list[int]:
            client = self._require_client()
            kwargs: Any = {_PMODBUS_SLAVE_PARAM: self._slave_id}
            if reg_type == RegisterType.HOLDING:
                read_task = client.read_holding_registers(address=address, count=count, **kwargs)
            else:
                read_task = client.read_input_registers(address=address, count=count, **kwargs)
            result = (
                await asyncio.wait_for(read_task, timeout=request_timeout)
                if request_timeout is not None
                else await read_task
            )
            if result.isError():
                # Pymodbus returns an ExceptionResponse for device-side errors.
                # Exception code 2 (Illegal Data Address) is permanent for the
                # given address: the register is simply not implemented on this
                # device. Surface it as IllegalAddressError so the retry loop
                # can bail out silently instead of retrying and logging a
                # warning on every poll.
                if getattr(result, "exception_code", None) == 2:
                    raise IllegalAddressError(  # type: ignore[no-untyped-call]
                        f"Illegal Data Address reading address {address}: {result}"
                    )
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

        return await self._retry_command(
            "read",
            address,
            count,
            reg_type,
            _command,
            max_retries=max_retries,
        )

    async def _try_reconnect(self) -> None:
        """Attempt a single reconnect (must be called while holding self._lock)."""
        if self._client is not None:
            self._client.close()
            self._client = None
        _LOGGER.debug("Attempting reconnect to %s:%s", self._host, self._port)
        try:
            await self._connect_internal()
        except ConnectionException:
            # Leave _connection_suspect set so the next _ensure_connected()
            # outside the retry loop will try a fresh connect rather than
            # trusting a stale .connected flag.
            _LOGGER.debug("Reconnect attempt failed")
            return
        # Successful TCP handshake. The link may still be unproven for
        # Modbus traffic, so we keep _connection_suspect=True until a real
        # IO round-trip succeeds (the read/write loops clear it on success).

    async def _write_registers(self, address: int, values: list[int]) -> None:
        """Write holding registers with retries and exponential backoff."""

        async def _command() -> None:
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

        await self._retry_command(
            "write",
            address,
            len(values),
            RegisterType.HOLDING,
            _command,
        )

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

    async def probe_register(
        self,
        address: int,
        count: int = 1,
        *,
        max_retries: int | None = None,
        timeout: float | None = None,
    ) -> list[int] | None:
        """Try to read a register without affecting failure tracking.

        Returns the register values or None if the read fails.
        """
        try:
            await self._ensure_connected()
            return await self._read_registers(
                address,
                count,
                max_retries=max_retries,
                request_timeout=timeout,
            )
        except (ModbusException, ConnectionException, OSError):
            return None

    async def _probe_model_register(self, address: int, count: int = 1) -> list[int] | None:
        """Probe model/capability registers with short, single-attempt reads."""
        return await self.probe_register(
            address,
            count,
            max_retries=MODEL_DETECTION_MAX_RETRIES,
            timeout=MODEL_DETECTION_TIMEOUT,
        )

    @staticmethod
    def _probe_float_value(
        regs: list[int] | None,
        *,
        min_val: float | None = None,
        max_val: float | None = None,
    ) -> float | None:
        """Decode and optionally validate a FLOAT32 register pair from probing.

        Returns the decoded float if the response is valid and within bounds.
        Returns None for missing/short responses, NaN/Inf, out-of-range values,
        or struct decode errors.
        """
        if regs is None or len(regs) != 2:
            return None
        try:
            val = ModbusCodec.decode_float32(regs)
        except (struct.error, ValueError):
            return None
        if math.isnan(val) or math.isinf(val):
            return None
        if min_val is not None and val < min_val:
            return None
        if max_val is not None and val > max_val:
            return None
        return val

    async def detect_model(self, *, read_firmware: bool = True) -> IdmModelInfo:
        """Detect the IDM heat pump model and capabilities by probing registers.

        Strategy:
          1. Probe heating circuit flow temperatures (1350-1362)
          2. Probe zone module presence (2000, 2065, ...)
          3. Probe solar register (1850)
          4. Probe ISC register (1870)
          5. Probe PV register (74)
          6. Probe cascade register (1147)
          7. Probe Navigator-10-only power-limit register (4108) when needed

        Args:
            read_firmware: Probe Modbus register 4120 for the firmware version.
                Disable this when a consumer prefers the optional local web
                software version or wants to avoid this unreliable register.
        """
        await self._ensure_connected()

        active_circuits: list[str] = []
        missing_circuit_slots = 0
        for i in range(MAX_HEATING_CIRCUITS):
            addr = _DETECT_HC_FLOW_BASE + i * _DETECT_HC_STEP
            regs = await self._probe_model_register(addr, 2)
            val = self._probe_float_value(regs, min_val=-50.0, max_val=80.0)
            if val is not None:
                active_circuits.append(HEATING_CIRCUIT_LETTERS[i])
                missing_circuit_slots = 0
            elif regs is not None and len(regs) == 2:
                # Registers responded but value was out-of-range or not decodable;
                # treat the heating circuit slot as active anyway.
                active_circuits.append(HEATING_CIRCUIT_LETTERS[i])
                missing_circuit_slots = 0
            else:
                missing_circuit_slots += 1
            if missing_circuit_slots >= _DETECT_EMPTY_SLOT_STOP_THRESHOLD:
                break

        zone_modules = 0
        missing_zone_slots = 0
        for zm in range(MAX_ZONE_MODULES):
            addr = _DETECT_ZONE_MODULE_BASE + zm * _DETECT_ZONE_MODULE_STEP
            regs = await self._probe_model_register(addr, 1)
            if regs is not None and len(regs) == 1:
                zone_modules = zm + 1
                missing_zone_slots = 0
            else:
                missing_zone_slots += 1
            if missing_zone_slots >= _DETECT_EMPTY_SLOT_STOP_THRESHOLD:
                break

        # A solar/ISC register that responds at all is treated as present, even
        # if the FLOAT value cannot be decoded (some firmwares return sentinel
        # patterns).
        solar_regs = await self._probe_model_register(1850, 2)
        has_solar = self._probe_float_value(solar_regs) is not None or (
            solar_regs is not None and len(solar_regs) == 2
        )

        isc_regs = await self._probe_model_register(1870, 2)
        has_isc = self._probe_float_value(isc_regs) is not None or (
            isc_regs is not None and len(isc_regs) == 2
        )

        pv_regs = await self._probe_model_register(74, 2)
        has_pv = pv_regs is not None and len(pv_regs) == 2

        has_cascade = False
        cascade_regs = await self._probe_model_register(1147, 1)
        if cascade_regs is not None and len(cascade_regs) == 1:
            # Register 1147 only exists on cascade-capable controllers. A value
            # of 0 can simply mean "cascade present but not active right now".
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
        # Prefer Navigator 10 when we see strong indicators (newer registers present).
        # Address 1072 (heat_sink_flow_rate) is NOT a reliable Navigator 10 signal:
        # it is also present on some Navigator 2.0 controllers (e.g. IDM Terra SWM
        # with software 20.23-245) and would misclassify them as Navigator 10.
        # Address 4108 (power_limit_hp) is a much safer differentiator because it
        # belongs to the Navigator-10-only power-limitation register block.
        has_navigator_10_indicators = False
        try:
            pl = await self._probe_model_register(4108, 2)
            if pl is not None and len(pl) == 2:
                has_navigator_10_indicators = True
        except (ModbusException, ConnectionException, OSError):
            pass

        if has_navigator_10_indicators or zone_modules > 0:
            # Navigator 10 is the current generation; also report Pro-like capabilities
            model_name = MODEL_NAVIGATOR_10 if has_navigator_10_indicators else MODEL_NAVIGATOR_PRO
        elif active_circuits:
            model_name = MODEL_NAVIGATOR_20
        else:
            model_name = MODEL_UNKNOWN

        firmware_version: float | None = None
        if read_firmware:
            fw_regs = await self._probe_model_register(4120, 2)
            val = self._probe_float_value(fw_regs)
            if val is not None:
                firmware_version = round(val, 2)

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
        self._cached_register_map = None
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

    @staticmethod
    def _decode_float(registers: list[int], reg: RegisterDef) -> Any:
        value = ModbusCodec.decode_float32(registers)
        if math.isnan(value) or math.isinf(value):
            _LOGGER.debug(
                "Register %s returned NaN/Inf at address %s",
                reg.name,
                reg.address,
            )
            return None
        return round(value * reg.multiplier, 2)

    @staticmethod
    def _decode_uchar(registers: list[int], reg: RegisterDef) -> Any:
        val = registers[0] & 0xFF
        return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

    @staticmethod
    def _decode_int8(registers: list[int], reg: RegisterDef) -> Any:
        val = ModbusCodec.decode_int8(registers[0])
        return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

    @staticmethod
    def _decode_int16(registers: list[int], reg: RegisterDef) -> Any:
        val = ModbusCodec.decode_int16(registers[0])
        return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

    @staticmethod
    def _decode_uint16(registers: list[int], reg: RegisterDef) -> Any:
        val = registers[0]
        return round(val * reg.multiplier, 2) if reg.multiplier != 1.0 else val

    @staticmethod
    def _decode_bool(registers: list[int], reg: RegisterDef) -> Any:
        return bool(registers[0] & 0x01)

    @staticmethod
    def _decode_bitflag(registers: list[int], reg: RegisterDef) -> Any:
        return registers[0] & 0xFF

    @staticmethod
    def _encode_float(value: Any, reg: RegisterDef) -> list[int]:
        float_val = float(value) / reg.multiplier
        if math.isnan(float_val) or math.isinf(float_val):
            raise ValueError(f"Cannot encode NaN/Inf for register {reg.name}")
        return ModbusCodec.encode_float32(float_val)

    @staticmethod
    def _encode_uchar(value: Any, reg: RegisterDef) -> list[int]:
        val = int(round(float(value) / reg.multiplier))
        if not (0 <= val <= 255):
            raise ValueError(f"Value {value} out of UCHAR range for {reg.name}")
        return [val & 0xFF]

    @staticmethod
    def _encode_int8(value: Any, reg: RegisterDef) -> list[int]:
        val = int(round(float(value) / reg.multiplier))
        return [ModbusCodec.encode_int8(val) & 0xFF]

    @staticmethod
    def _encode_int16(value: Any, reg: RegisterDef) -> list[int]:
        val = int(round(float(value) / reg.multiplier))
        return [ModbusCodec.encode_int16(val) & 0xFFFF]

    @staticmethod
    def _encode_uint16(value: Any, reg: RegisterDef) -> list[int]:
        val = int(round(float(value) / reg.multiplier))
        if not (0 <= val <= 65535):
            raise ValueError(f"Value {value} out of UINT16 range for {reg.name}")
        return [val & 0xFFFF]

    @staticmethod
    def _encode_bool(value: Any, reg: RegisterDef) -> list[int]:
        return [1 if value else 0]

    @staticmethod
    def _encode_bitflag(value: Any, reg: RegisterDef) -> list[int]:
        return [int(value) & 0xFF]

    _DECODERS: ClassVar[dict[DataType, Callable[[list[int], RegisterDef], Any]]] = {
        DataType.FLOAT: _decode_float,
        DataType.UCHAR: _decode_uchar,
        DataType.INT8: _decode_int8,
        DataType.INT16: _decode_int16,
        DataType.UINT16: _decode_uint16,
        DataType.BOOL: _decode_bool,
        DataType.BITFLAG: _decode_bitflag,
    }

    _ENCODERS: ClassVar[dict[DataType, Callable[[Any, RegisterDef], list[int]]]] = {
        DataType.FLOAT: _encode_float,
        DataType.UCHAR: _encode_uchar,
        DataType.INT8: _encode_int8,
        DataType.INT16: _encode_int16,
        DataType.UINT16: _encode_uint16,
        DataType.BOOL: _encode_bool,
        DataType.BITFLAG: _encode_bitflag,
    }

    def decode_value(self, registers: list[int], reg: RegisterDef) -> Any:
        """Decode raw Modbus register values into a Python value."""
        if not registers:
            raise ValueError(f"Empty register list for {reg.name} (expected {reg.size})")
        if len(registers) < reg.size:
            raise ValueError(
                f"Not enough registers for {reg.name}: got {len(registers)}, need {reg.size}"
            )
        decoder = self._DECODERS.get(reg.datatype)
        if decoder is None:
            raise ValueError(f"Unsupported datatype for decoding: {reg.datatype}")
        return decoder(registers, reg)

    def encode_value(self, value: Any, reg: RegisterDef) -> list[int]:
        """Encode a Python value into raw Modbus register values."""
        encoder = self._ENCODERS.get(reg.datatype)
        if encoder is None:
            raise ValueError(f"Unsupported datatype for encoding: {reg.datatype}")
        return encoder(value, reg)

    async def read_register(self, reg: RegisterDef) -> Any:
        """Read a single register, auto-connecting if needed.

        Permanently failed registers are skipped immediately to avoid repeated
        futile network requests. Consumers can reset the failure state with
        ``reset_failed_registers()``.
        """
        if reg.write_only:
            raise ValueError(f"Register '{reg.name}' is write-only")
        if reg.name in self._permanently_failed_registers:
            raise ValueError(
                f"Register '{reg.name}' is permanently failed; "
                f"call reset_failed_registers() to retry"
            )
        await self._ensure_connected()
        registers = await self._read_registers(reg.address, reg.size, reg.register_type)
        return self.decode_value(registers, reg)

    async def write_register(self, reg: RegisterDef, value: Any) -> None:
        """Write a single register after validation, auto-connecting if needed."""
        plan = self.simulate_write(reg, value)
        await self._ensure_connected()
        await self._write_registers(reg.address, list(plan.encoded_registers))
        self._record_successful_write(reg)

    async def read_value(self, key: str) -> Any:
        """Read one register by registry key/name."""
        reg = self._get_register_by_key(key)
        return await self.read_register(reg)

    async def set_value(self, key: str, value: Any, *, dry_run: bool = False) -> WriteSafetyResult:
        """Safely write one register by key/name, optionally as dry run."""
        reg = self._get_register_by_key(key)
        plan = self.simulate_write(reg, value, dry_run=dry_run)
        if not dry_run:
            await self._ensure_connected()
            await self._write_registers(reg.address, list(plan.encoded_registers))
            self._record_successful_write(reg)
        return plan

    def simulate_write(
        self,
        reg: RegisterDef | str,
        value: Any,
        *,
        dry_run: bool = True,
    ) -> WriteSafetyResult:
        """Validate and encode a write without necessarily sending it."""
        register = self._get_register_by_key(reg) if isinstance(reg, str) else reg
        if not register.writable:
            raise ValueError(f"Register '{register.name}' is read-only")
        self._validate_write_allowed(register, value)
        encoded = tuple(self.encode_value(value, register))
        return WriteSafetyResult(register, value, encoded, dry_run=dry_run)

    def get_diagnostics(self) -> IdmClientDiagnostics:
        """Return a sanitized Modbus diagnostics snapshot."""
        firmware = None
        if self._model_info and self._model_info.firmware_version is not None:
            firmware = str(self._model_info.firmware_version)
        return IdmClientDiagnostics(
            navigator_type=self.model_name,
            modbus_connected=self.is_connected,
            firmware=firmware,
            last_error=self._last_error_context.message if self._last_error_context else None,
            permanently_failed_registers=tuple(sorted(self._permanently_failed_registers)),
            connection_suspect=self._connection_suspect,
        )

    def _get_register_by_key(self, key: str) -> RegisterDef:
        from .registers import get_register

        try:
            return get_register(key, model_info=self._model_info)
        except ValueError as exc:
            raise KeyError(f"Unknown IDM register key: {key}") from exc

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

        if self._cached_register_map is None:
            from .registers import build_register_map

            self._cached_register_map = build_register_map(model_info=self._model_info)

        available = self._cached_register_map.get(reg.name)
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

        groups = self._group_registers(valid_regs)
        results: dict[str, Any] = {}
        for group in groups:
            group_res = await self._read_group(group, group[0].register_type)
            results.update(group_res)

        return results

    def _group_registers(
        self,
        regs: list[RegisterDef],
    ) -> list[list[RegisterDef]]:
        """Sort and group registers into contiguous chunks for batch reads.

        Registers are grouped by type (input/holding) and then merged into
        contiguous chunks when the gap between them is small enough. Sorting
        once by ``(register_type, address)`` avoids the previous two-pass split
        and keeps the grouping logic in one place.
        """
        sorted_regs = sorted(regs, key=lambda r: (r.register_type.value, r.address))
        groups: list[list[RegisterDef]] = []
        current_group: list[RegisterDef] = [sorted_regs[0]]

        for reg in sorted_regs[1:]:
            first = current_group[0]
            last = current_group[-1]

            # Start a new group when the register type changes.
            if reg.register_type != first.register_type:
                groups.append(current_group)
                current_group = [reg]
                continue

            expected_next = last.address + last.size
            if (
                reg.address <= expected_next + _MAX_GROUP_GAP
                and (reg.address + reg.size - first.address) <= self._max_group_size
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
        suspect_regs: list[RegisterDef] = []
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
                value = self.decode_value(reg_slice, reg)
                if self._is_value_suspect(reg, value):
                    suspect_regs.append(reg)
                else:
                    data[reg.name] = value
            except (ValueError, IndexError) as err:
                _LOGGER.debug(
                    "Failed to decode register %s (address %d): %s",
                    reg.name,
                    reg.address,
                    err,
                )

        # Some IDM controllers return inconsistent data for certain registers
        # when read as part of a large contiguous batch, even though individual
        # reads return correct values. Re-read any register whose decoded value
        # falls outside its declared valid range to recover the real value.
        if suspect_regs:
            _LOGGER.debug(
                "Batch read at address %d returned %d suspect value(s); "
                "re-reading individually: %s",
                start,
                len(suspect_regs),
                [r.name for r in suspect_regs],
            )
            re_read = await self._read_individual_fallback(suspect_regs, reg_type)
            data.update(re_read)
        return data

    @staticmethod
    def _is_value_suspect(reg: RegisterDef, value: Any) -> bool:
        """Return True if a decoded value is outside the register's valid range.

        Used after batch reads to detect registers where the controller
        returned corrupt data in a large contiguous read. Registers without
        ``enum_options`` or ``min_val``/``max_val`` are never flagged.
        """
        if value is None or isinstance(value, bool):
            return False
        if reg.enum_options is not None:
            if value not in reg.enum_options:
                return True
            return False
        if reg.min_val is not None and isinstance(value, (int, float)):
            if value < reg.min_val:
                return True
        if reg.max_val is not None and isinstance(value, (int, float)):
            if value > reg.max_val:
                return True
        return False

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
            except IllegalAddressError:
                # The register is not implemented on this device. Mark it as
                # permanently failed immediately (no need to wait for the
                # threshold of 3 transient failures) so it is skipped on the
                # next read_batch call. Log at debug only: this is an expected
                # condition when optional register blocks are probed.
                self._permanently_failed_registers.add(reg.name)
                self._unsupported_registers.add(reg.name)
                _LOGGER.debug(
                    "Register %s (address %d) is not implemented on this device "
                    "(Illegal Data Address); skipping it on future reads",
                    reg.name,
                    reg.address,
                )
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
        """Clear failure tracking and unsupported-register state so reads are retried."""
        self._permanently_failed_registers.clear()
        self._unsupported_registers.clear()
        self._register_failures.clear()
        _LOGGER.info("Permanently failed registers have been reset")

    def get_unsupported_registers(self) -> tuple[str, ...]:
        """Return register names the device rejected as not implemented.

        These are registers that responded with Modbus ``Illegal Data Address``
        (exception code 2) during a :meth:`read_batch` or individual read.
        The set grows monotonically within a client's lifetime and is cleared
        by :meth:`reset_failed_registers`.

        Consumers (e.g. the Home Assistant integration coordinator) can merge
        this into their own skip-list so unsupported addresses are not
        re-attempted on every poll, which keeps the log quiet and avoids
        needless Modbus traffic.
        """
        return tuple(sorted(self._unsupported_registers))
