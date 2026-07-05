"""Tests for the IDM Modbus client."""

import asyncio
import logging
from typing import Any

import pytest
from pymodbus.exceptions import ModbusException

from idm_heatpump.client import (
    DataType,
    IdmModbusClient,
    RegisterDef,
    RegisterType,
    quiet_pymodbus_logging,
)
from idm_heatpump.const import (
    FEATURE_CASCADE,
    FEATURE_HEATING_CIRCUITS,
    FEATURE_ISC,
    FEATURE_PV,
    FEATURE_SOLAR,
    FEATURE_ZONE_MODULES,
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    MODEL_UNKNOWN,
)


class ProbeOnlyClient(IdmModbusClient):
    """Client test double that answers model-detection probes without network I/O."""

    def __init__(self, probes: dict[tuple[int, int], list[int]]) -> None:
        super().__init__("127.0.0.1")
        self._probes = probes
        self.probe_calls: list[tuple[int, int]] = []

    async def _ensure_connected(self) -> Any:
        return object()

    async def probe_register(
        self,
        address: int,
        count: int = 1,
        **_: Any,
    ) -> list[int] | None:
        self.probe_calls.append((address, count))
        return self._probes.get((address, count))


class IncompleteResponseClient:
    """Minimal connected pymodbus double returning a short response."""

    connected = True

    async def read_input_registers(self, **kwargs: Any) -> Any:
        return type("Response", (), {"isError": lambda self: False, "registers": [1]})()


def test_detect_model_uses_shared_feature_constants() -> None:
    """Detected features should use public constants from const.py."""
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],  # 25.0 C, low word first
            (2000, 1): [1],
            (1850, 2): [0, 16968],
            (1870, 2): [0, 16968],
            (74, 2): [0, 16968],
            (1147, 1): [1],
            (1072, 1): [1],
            (4120, 2): [26214, 16622],  # firmware version 7.45
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.model_name == MODEL_NAVIGATOR_10
    assert model_info.active_heating_circuits == ["A"]
    assert model_info.zone_modules == 1
    assert model_info.features == {
        FEATURE_HEATING_CIRCUITS,
        FEATURE_ZONE_MODULES,
        FEATURE_SOLAR,
        FEATURE_ISC,
        FEATURE_PV,
        FEATURE_CASCADE,
    }
    assert model_info.firmware_version == 7.45
    assert client.model_name == MODEL_NAVIGATOR_10


def test_model_name_defaults_before_detection() -> None:
    """model_name should fall back to the default model until detection runs."""
    client = IdmModbusClient("127.0.0.1")
    assert client.model_name == MODEL_NAVIGATOR_20


def test_model_name_defaults_when_detection_inconclusive() -> None:
    """model_name should fall back to the default model when detection is inconclusive."""
    client = ProbeOnlyClient({})

    model_info = asyncio.run(client.detect_model())

    assert model_info.model_name == MODEL_UNKNOWN
    assert client.model_name == MODEL_NAVIGATOR_20
    assert model_info.firmware_version is None


def test_detect_model_ignores_incomplete_probe_responses() -> None:
    """Short Modbus responses must not crash detection or imply capabilities."""
    client = ProbeOnlyClient(
        {
            (1350, 2): [0],
            (2000, 1): [],
            (1850, 2): [0],
            (1870, 2): [],
            (74, 2): [0],
            (1147, 1): [],
            (1072, 1): [],
            (4108, 2): [0],
            (4120, 2): [0],
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.model_name != MODEL_NAVIGATOR_10
    assert model_info.active_heating_circuits == []
    assert model_info.zone_modules == 0
    assert FEATURE_ZONE_MODULES not in model_info.features
    assert not model_info.has_solar
    assert not model_info.has_isc
    assert not model_info.has_pv
    assert not model_info.has_cascade
    assert model_info.firmware_version is None


def test_detect_model_can_skip_unreliable_firmware_probe() -> None:
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],
            (1072, 1): [1],
            (4120, 2): [26214, 16622],
        }
    )

    model_info = asyncio.run(client.detect_model(read_firmware=False))

    assert model_info.model_name == MODEL_NAVIGATOR_10
    assert model_info.firmware_version is None
    assert (4120, 2) not in client.probe_calls


def test_detect_model_stops_after_consecutive_empty_optional_slots() -> None:
    """Missing contiguous optional blocks should not force every possible probe."""
    client = ProbeOnlyClient({})

    asyncio.run(client.detect_model())

    assert (1350, 2) in client.probe_calls
    assert (1352, 2) in client.probe_calls
    assert (1354, 2) not in client.probe_calls
    assert (2000, 1) in client.probe_calls
    assert (2065, 1) in client.probe_calls
    assert (2130, 1) not in client.probe_calls


def test_read_registers_rejects_incomplete_modbus_response() -> None:
    """Successful but short protocol responses must not reach value decoding."""
    client = IdmModbusClient("127.0.0.1", max_retries=1)
    client._client = IncompleteResponseClient()  # type: ignore[assignment]

    with pytest.raises(ModbusException, match="got 1 registers, expected 2"):
        asyncio.run(client._read_registers(1000, 2))


@pytest.mark.parametrize("field,value", [("datatype", "FLOAT"), ("register_type", "input")])
def test_register_definition_rejects_invalid_enum_values(field: str, value: str) -> None:
    """String lookalikes must not bypass register metadata validation."""
    values: dict[str, object] = {
        "address": 1,
        "datatype": DataType.FLOAT,
        "name": "invalid",
        field: value,
    }

    with pytest.raises(ValueError):
        RegisterDef(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize("multiplier", [0, float("nan"), float("inf")])
def test_register_definition_rejects_invalid_multiplier(multiplier: float) -> None:
    with pytest.raises(ValueError):
        RegisterDef(1, DataType.FLOAT, "invalid", multiplier=multiplier)


@pytest.mark.parametrize(
    "min_val,max_val",
    [(float("nan"), None), (None, float("inf")), (2, 1)],
)
def test_register_definition_rejects_invalid_bounds(
    min_val: float | None, max_val: float | None
) -> None:
    with pytest.raises(ValueError):
        RegisterDef(
            1,
            DataType.FLOAT,
            "invalid",
            min_val=min_val,
            max_val=max_val,
            register_type=RegisterType.INPUT,
        )


def test_pymodbus_retries_defaults_to_zero() -> None:
    """Library default should disable pymodbus internal retries to avoid double retry."""
    client = IdmModbusClient("127.0.0.1")
    assert client._pymodbus_retries == 0


def test_pymodbus_retries_can_be_overridden() -> None:
    client = IdmModbusClient("127.0.0.1", pymodbus_retries=2)
    assert client._pymodbus_retries == 2


def test_pymodbus_retries_rejects_negative_values() -> None:
    with pytest.raises(ValueError, match="pymodbus_retries"):
        IdmModbusClient("127.0.0.1", pymodbus_retries=-1)


def test_connect_internal_forwards_retries_and_reconnect_params(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_connect_internal must hand retries/reconnect_delay to AsyncModbusTcpClient."""
    captured: dict[str, Any] = {}

    class StubClient:
        connected = False

        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        async def connect(self) -> bool:
            return True

    monkeypatch.setattr("idm_heatpump.client.AsyncModbusTcpClient", StubClient)

    client = IdmModbusClient("127.0.0.1", pymodbus_retries=0)
    asyncio.run(client._connect_internal())

    assert captured["retries"] == 0
    assert captured["reconnect_delay"] == pytest.approx(0.5)
    assert captured["reconnect_delay_max"] == pytest.approx(10.0)
    assert captured["timeout"] == pytest.approx(client._timeout)


def test_connect_internal_forwards_custom_pymodbus_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class StubClient:
        connected = False

        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        async def connect(self) -> bool:
            return True

    monkeypatch.setattr("idm_heatpump.client.AsyncModbusTcpClient", StubClient)

    client = IdmModbusClient("127.0.0.1", pymodbus_retries=3)
    asyncio.run(client._connect_internal())

    assert captured["retries"] == 3


def test_quiet_pymodbus_logging_accepts_string_level() -> None:
    pymodbus_logger = logging.getLogger("pymodbus")
    original = pymodbus_logger.level
    try:
        quiet_pymodbus_logging("ERROR")
        assert pymodbus_logger.level == logging.ERROR
    finally:
        pymodbus_logger.setLevel(original)


def test_quiet_pymodbus_logging_accepts_int_level() -> None:
    pymodbus_logger = logging.getLogger("pymodbus")
    original = pymodbus_logger.level
    try:
        quiet_pymodbus_logging(logging.CRITICAL)
        assert pymodbus_logger.level == logging.CRITICAL
    finally:
        pymodbus_logger.setLevel(original)


def test_quiet_pymodbus_logging_rejects_unknown_level() -> None:
    with pytest.raises(ValueError, match="Unknown log level"):
        quiet_pymodbus_logging("not-a-level")


def test_detect_model_treats_zero_cascade_register_as_present() -> None:
    """Register 1147 presence means cascade is available even if value is 0."""
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],
            (1147, 1): [0],
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.has_cascade is True


def test_register_map_is_cached_after_model_detection() -> None:
    """_validate_model_availability should not rebuild the map on every call."""
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],
            (1072, 1): [1],
        }
    )
    asyncio.run(client.detect_model())

    reg = RegisterDef(1005, DataType.UCHAR, "system_mode", writable=True)
    client._validate_model_availability(reg)
    assert client._cached_register_map is not None
    cached = client._cached_register_map

    client._validate_model_availability(reg)
    assert client._cached_register_map is cached


def test_connection_suspect_starts_false() -> None:
    """Freshly constructed clients must not flag themselves as suspect."""
    client = IdmModbusClient("127.0.0.1")
    assert client._connection_suspect is False


def test_force_reconnect_closes_existing_client_and_reconnects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """force_reconnect must always close + reopen, ignoring .connected."""
    instances: list[Any] = []

    class StubClient:
        def __init__(self, **kwargs: Any) -> None:
            self.closed = False
            instances.append(self)

        connected = True

        def close(self) -> None:
            self.closed = True

        async def connect(self) -> bool:
            return True

    monkeypatch.setattr("idm_heatpump.client.AsyncModbusTcpClient", StubClient)

    client = IdmModbusClient("127.0.0.1")
    asyncio.run(client._connect_internal())  # establish first client
    first = instances[0]
    assert first.closed is False

    asyncio.run(client.force_reconnect())

    assert first.closed is True  # old connection hard-closed
    assert len(instances) == 2  # new client created
    assert client._connection_suspect is False


def test_force_reconnect_safe_when_no_existing_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Calling force_reconnect before connect() must not raise."""

    class StubClient:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def connect(self) -> bool:
            return True

    monkeypatch.setattr("idm_heatpump.client.AsyncModbusTcpClient", StubClient)

    client = IdmModbusClient("127.0.0.1")
    asyncio.run(client.force_reconnect())
    assert client._client is not None


def test_ensure_connected_forces_reconnect_when_suspect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A prior failure flag must trigger close+reconnect even if .connected=True."""

    class StubClient:
        def __init__(self, **kwargs: Any) -> None:
            self.closed = False

        connected = True

        def close(self) -> None:
            self.closed = True
            self.connected = False

        async def connect(self) -> bool:
            self.connected = True
            return True

    monkeypatch.setattr("idm_heatpump.client.AsyncModbusTcpClient", StubClient)

    client = IdmModbusClient("127.0.0.1")
    asyncio.run(client._connect_internal())
    original_client = client._client
    assert original_client is not None
    original_client.connected = True  # pymodbus still thinks it's connected

    client._connection_suspect = True  # simulate a prior IO failure

    returned = asyncio.run(client._ensure_connected())

    assert original_client.closed is True  # hard-closed despite .connected=True
    assert client._connection_suspect is False  # flag cleared after reconnect
    assert returned is not original_client  # brand-new client object


def test_ensure_connected_reuses_healthy_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the suspect flag, a healthy .connected client must be reused."""

    class StubClient:
        def __init__(self, **kwargs: Any) -> None:
            self.closed = False

        connected = True

        def close(self) -> None:
            self.closed = True

        async def connect(self) -> bool:
            return True

    monkeypatch.setattr("idm_heatpump.client.AsyncModbusTcpClient", StubClient)

    client = IdmModbusClient("127.0.0.1")
    asyncio.run(client._connect_internal())
    first = client._client
    assert first is not None

    returned = asyncio.run(client._ensure_connected())

    assert returned is first  # reused
    assert first.closed is False

