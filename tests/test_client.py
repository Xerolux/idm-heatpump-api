"""Tests for the IDM Modbus client."""

import asyncio
import logging
from typing import Any

import pytest
from pymodbus.exceptions import ModbusException

from idm_heatpump.client import (
    DataType,
    IdmModbusClient,
    IdmModelInfo,
    IllegalAddressError,
    ModbusCodec,
    PollRateLimiter,
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
            (4108, 2): [0, 16968],  # Navigator 10 power-limit register
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


def test_detect_model_does_not_misclassify_sentinel_power_limit_as_navigator_10() -> None:
    """A Navigator 2.0 controller (e.g. IDM Terra SWM) that answers the
    Navigator-10-only power_limit_hp register (4108) with a sentinel value
    must NOT be classified as Navigator 10. Regression test: previously any
    non-error response at 4108 was treated as a Navigator 10 indicator,
    which then broke setup because the 4001+ register block was polled next
    and correctly rejected by the Navigator 2.0 controller.
    """
    # Sentinel -1.0 encoded as FLOAT32 little-endian word pair [0, 49024].
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],  # 25.0 C -> circuit A present
            (1498, 1): [0],  # active-mode A configured
            (4108, 2): [0, 49024],  # power_limit_hp sentinel (-1.0)
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.model_name == MODEL_NAVIGATOR_20
    assert client.model_name == MODEL_NAVIGATOR_20


def test_detect_model_does_not_misclassify_zero_power_limit_as_navigator_10() -> None:
    """A zero power_limit_hp (0.0, i.e. feature configured-off) must also not
    imply Navigator 10, mirroring the sentinel guard."""
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],  # 25.0 C -> circuit A present
            (1498, 1): [0],  # active-mode A configured
            (4108, 2): [0, 0],  # power_limit_hp = 0.0
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.model_name == MODEL_NAVIGATOR_20


def test_detect_model_classifies_real_power_limit_as_navigator_10() -> None:
    """A plausible configured power limit (>0) at 4108 still classifies as
    Navigator 10, preserving the original detection behavior."""
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],  # 25.0 C -> circuit A present
            (1498, 1): [0],  # active-mode A configured
            (4108, 2): [0, 16968],  # power_limit_hp = 25.0 kW (plausible)
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.model_name == MODEL_NAVIGATOR_10


def test_detect_model_does_not_misclassify_sentinel_booster_fault_as_navigator_10() -> None:
    """#170: a Navigator 2.0 that answers booster_fault (4001) with its declared
    "not configured" sentinel (255 / raw 0xFFFF) must NOT be classified as Navigator 10.
    Some Navigator 2.0 firmwares answer Navigator-10-only registers with a sentinel
    instead of rejecting them (the same Terra SWM behavior seen at 4108). Only a
    non-sentinel 4001 value is a genuine Navigator 10 indicator."""
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],  # 25.0 C -> circuit A present
            (1498, 1): [0],  # active-mode A configured
            (4108, 2): [0, 49024],  # power_limit_hp sentinel (-1.0)
            (4001, 1): [65535],  # booster_fault "not configured" sentinel (255)
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.model_name == MODEL_NAVIGATOR_20
    assert client.model_name == MODEL_NAVIGATOR_20


def test_detect_model_classifies_navigator_10_with_real_booster_block() -> None:
    """A genuine Navigator 10 with the booster block present (4001 answers a real,
    non-sentinel fault value) MUST still be detected as Navigator 10 when power_limit
    is at its factory sentinel, preserving the 0.8.4 fallback behavior."""
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],  # 25.0 C -> circuit A present
            (1498, 1): [0],  # active-mode A configured
            (4108, 2): [0, 49024],  # power_limit_hp sentinel (-1.0, no limit configured)
            (4001, 1): [0],  # booster_fault = 0 (booster present, no fault) -> real Nav10
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.model_name == MODEL_NAVIGATOR_10
    assert client.model_name == MODEL_NAVIGATOR_10


def test_set_model_info_overrides_detected_model() -> None:
    """set_model_info should allow explicitly setting/overriding model_info on client."""
    client = IdmModbusClient("127.0.0.1")
    info = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_10,
        active_heating_circuits=["A"],
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=False,
        has_cascade=False,
    )
    client.set_model_info(info)
    assert client.model_info == info
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


def test_detect_model_ignores_unavailable_heating_circuit_sentinel() -> None:
    """A -1.0 flow register with no active-mode confirmation means an unconfigured slot.

    All seven slots A-G are probed (no early-break); each unconfigured slot has
    both a -1.0 flow-temperature sentinel and the active-mode UCHAR sentinel
    (raw word 0xFFFF), so neither presence signal fires and only circuit A is
    reported. This documents the "only A is installed" case.
    """
    unavailable_flow = ModbusCodec.encode_float32(-1.0)
    client = ProbeOnlyClient(
        {
            (1350, 2): ModbusCodec.encode_float32(27.12),
            (1352, 2): unavailable_flow,
            (1354, 2): unavailable_flow,
            (1356, 2): unavailable_flow,
            (1358, 2): unavailable_flow,
            (1360, 2): unavailable_flow,
            (1362, 2): unavailable_flow,
            # Active-mode registers: A configured (0), B-G "not configured" sentinel.
            (1498, 1): [0],
            (1499, 1): [0xFFFF],
            (1500, 1): [0xFFFF],
            (1501, 1): [0xFFFF],
            (1502, 1): [0xFFFF],
            (1503, 1): [0xFFFF],
            (1504, 1): [0xFFFF],
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.active_heating_circuits == ["A"]
    # All seven heating-circuit slots are now probed (no early-break).
    assert (1350, 2) in client.probe_calls
    assert (1352, 2) in client.probe_calls
    assert (1356, 2) in client.probe_calls
    assert (1362, 2) in client.probe_calls


def test_detect_model_finds_non_contiguous_heating_circuits() -> None:
    """Non-contiguous installed circuits (e.g. only A and D) must be detected.

    Regression guard for a 2-device Navigator 10 capture (2026-07-16): an ALM
    with heating circuits A and D physically installed reported only ['A'],
    because detection early-broke after the two unconfigured sentinel slots
    B and C and never reached D. D reports a real flow temperature (26.9 C)
    AND a non-sentinel active-mode value; B/C report -1.0 flow temperature AND
    the UCHAR 0xFFFF "not configured" sentinel, so they are correctly excluded.
    """
    unavailable_flow = ModbusCodec.encode_float32(-1.0)
    client = ProbeOnlyClient(
        {
            # Flow temperatures: A and D real, B/C/E/F/G sentinel.
            (1350, 2): ModbusCodec.encode_float32(27.61),
            (1352, 2): unavailable_flow,
            (1354, 2): unavailable_flow,
            (1356, 2): ModbusCodec.encode_float32(26.90),
            (1358, 2): unavailable_flow,
            (1360, 2): unavailable_flow,
            (1362, 2): unavailable_flow,
            # Active-mode: A and D configured (0), B/C/E/F/G "not configured".
            (1498, 1): [0],
            (1499, 1): [0xFFFF],
            (1500, 1): [0xFFFF],
            (1501, 1): [0],
            (1502, 1): [0xFFFF],
            (1503, 1): [0xFFFF],
            (1504, 1): [0xFFFF],
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.active_heating_circuits == ["A", "D"]
    assert FEATURE_HEATING_CIRCUITS in model_info.features


def test_detect_model_active_mode_detects_circuit_without_flow_temp() -> None:
    """A circuit whose flow temp is -1.0 but whose active-mode is configured counts.

    ODER-logic presence: an installed circuit can report -1.0 on flow temperature
    (e.g. pump off, no flow sensor) while its active-mode register confirms it is
    configured. This must still be detected as active.
    """
    unavailable_flow = ModbusCodec.encode_float32(-1.0)
    client = ProbeOnlyClient(
        {
            # A: real flow. B: flow sentinel BUT active-mode configured.
            (1350, 2): ModbusCodec.encode_float32(25.0),
            (1352, 2): unavailable_flow,
            (1354, 2): unavailable_flow,
            (1356, 2): unavailable_flow,
            (1358, 2): unavailable_flow,
            (1360, 2): unavailable_flow,
            (1362, 2): unavailable_flow,
            (1498, 1): [0],
            (1499, 1): [2],  # circuit B configured despite -1.0 flow temp
            (1500, 1): [0xFFFF],
            (1501, 1): [0xFFFF],
            (1502, 1): [0xFFFF],
            (1503, 1): [0xFFFF],
            (1504, 1): [0xFFFF],
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.active_heating_circuits == ["A", "B"]


def test_detect_model_navigator_20_with_heat_sink_flow_rate() -> None:
    """Address 1072 alone must not classify a Navigator 2.0 as Navigator 10.

    Some Navigator 2.0 controllers (e.g. IDM Terra SWM with software
    20.23-245) expose address 1072 but reject the Navigator-10-only power
    limit register at 4108. The detector must rely on 4108, not 1072.
    """
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],  # 25.0 C, heating circuit A active
            (1072, 1): [1],  # heat_sink_flow_rate present on Nav 2.0
            # 4108 intentionally missing -> Navigator 2.0
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.model_name == MODEL_NAVIGATOR_20
    assert model_info.active_heating_circuits == ["A"]


def test_detect_model_can_skip_unreliable_firmware_probe() -> None:
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],
            (1072, 1): [1],
            (4108, 2): [0, 16968],  # Navigator 10 power-limit register
            (4120, 2): [26214, 16622],
        }
    )

    model_info = asyncio.run(client.detect_model(read_firmware=False))

    assert model_info.model_name == MODEL_NAVIGATOR_10
    assert model_info.firmware_version is None
    assert (4120, 2) not in client.probe_calls


def test_detect_model_scans_all_heating_circuits_but_stops_zone_modules() -> None:
    """Heating circuits are fully scanned A-G; zone modules still early-break.

    Heating-circuit detection no longer early-breaks on empty slots, because
    installed circuits can be non-contiguous (e.g. A+D with B/C unconfigured),
    so all seven flow-temperature and active-mode slots are probed. Zone-module
    detection keeps its early-break, since those are always contiguous.
    """
    client = ProbeOnlyClient({})

    asyncio.run(client.detect_model())

    # All seven heating-circuit flow-temperature slots are probed.
    assert (1350, 2) in client.probe_calls
    assert (1352, 2) in client.probe_calls
    assert (1354, 2) in client.probe_calls
    assert (1356, 2) in client.probe_calls
    assert (1358, 2) in client.probe_calls
    assert (1360, 2) in client.probe_calls
    assert (1362, 2) in client.probe_calls
    # Zone-module probing still early-breaks after consecutive empty slots.
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


def test_detect_model_treats_cascade_sentinel_as_unavailable() -> None:
    """The UCHAR sentinel 255 is a response, but not cascade capability."""
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],
            (1147, 1): [0xFFFF],
        }
    )

    model_info = asyncio.run(client.detect_model())

    assert model_info.has_cascade is False


def test_register_map_is_cached_after_model_detection() -> None:
    """_validate_model_availability should not rebuild the map on every call."""
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],
            (1072, 1): [1],
            (4108, 2): [0, 16968],  # Navigator 10 power-limit register
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
    original_client.connected = True  # type: ignore[misc] # pymodbus still thinks it's connected

    client._connection_suspect = True  # simulate a prior IO failure

    returned = asyncio.run(client._ensure_connected())

    assert original_client.closed is True  # type: ignore[attr-defined] # hard-closed despite .connected=True
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
    assert first.closed is False  # type: ignore[attr-defined]


def test_modbus_codec_centralizes_float_and_integer_encoding() -> None:
    encoded = ModbusCodec.encode_float32(21.5)

    assert ModbusCodec.decode_float32(encoded) == 21.5
    assert ModbusCodec.decode_int16(0xFFFF) == -1
    assert ModbusCodec.encode_int16(-1) == 0xFFFF
    assert ModbusCodec.decode_int8(0xFF) == -1
    assert ModbusCodec.encode_int8(-1) == 0xFF


def test_write_safety_simulate_write_validates_and_encodes_without_io() -> None:
    client = IdmModbusClient("192.0.2.10")
    plan = client.simulate_write("system_mode", 2)

    assert plan.register.name == "system_mode"
    assert plan.requested_value == 2
    assert plan.encoded_registers == (2,)
    assert plan.dry_run is True


def test_write_safety_rejects_unknown_and_read_only_registers() -> None:
    client = IdmModbusClient("192.0.2.10")

    with pytest.raises(KeyError, match="Unknown IDM register key"):
        client.simulate_write("does_not_exist", 1)
    with pytest.raises(ValueError, match="read-only"):
        client.simulate_write("outdoor_temp", 21.5)


def test_custom_write_requires_explicit_model_validation_bypass() -> None:
    client = ProbeOnlyClient(
        {
            (1350, 2): [0, 16968],
            (4108, 2): [0, 16968],
        }
    )
    asyncio.run(client.detect_model())
    custom = RegisterDef(1999, DataType.UINT16, "manual_1999", writable=True)

    with pytest.raises(ValueError, match="not available for detected model"):
        client.simulate_write(custom, 42)

    plan = client.simulate_write(custom, 42, allow_custom_register=True)

    assert plan.encoded_registers == (42,)


def test_write_safety_rejects_invalid_enum_boolean_and_fractional_integer_values() -> None:
    client = IdmModbusClient("192.0.2.10")
    bool_reg = RegisterDef(1710, DataType.BOOL, "demand_heating", writable=True)
    int_reg = RegisterDef(1714, DataType.UCHAR, "pump_demand", writable=True)

    with pytest.raises(ValueError, match="not a supported option"):
        client.simulate_write("system_mode", 3)
    with pytest.raises(ValueError, match="must be a boolean"):
        client.simulate_write(bool_reg, "false")
    with pytest.raises(ValueError, match="must be an integer"):
        client.simulate_write(int_reg, 1.5)


def test_modbus_diagnostics_reports_sanitized_state() -> None:
    client = IdmModbusClient("192.0.2.10")

    diagnostics = client.get_diagnostics()

    assert diagnostics.navigator_type == MODEL_NAVIGATOR_20
    assert diagnostics.modbus_connected is False
    assert diagnostics.last_error is None


def test_poll_rate_limiter_tracks_remaining_interval() -> None:
    now = 100.0

    def clock() -> float:
        return now

    limiter = PollRateLimiter(30.0, clock=clock)

    assert limiter.allow() is True
    limiter.mark()
    assert limiter.allow() is False
    assert limiter.remaining() == 30.0
    now = 130.0
    assert limiter.allow() is True


class TimeoutOnFirstReadClient:
    """pymodbus double that raises TimeoutError on the first read attempt."""

    connected = True

    def __init__(self) -> None:
        self.attempts = 0

    async def read_input_registers(self, **kwargs: Any) -> Any:
        self.attempts += 1
        if self.attempts == 1:
            raise TimeoutError("simulated timeout")
        return type("Response", (), {"isError": lambda self: False, "registers": [0, 16968]})()

    def close(self) -> None:
        self.connected = False


def test_retry_command_recovers_from_timeout_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TimeoutError must use the same retry/reconnect path as OSError."""
    transport = TimeoutOnFirstReadClient()
    client = IdmModbusClient("127.0.0.1", max_retries=2)
    client._client = transport  # type: ignore[assignment]

    # Keep the test offline: reconnect just re-attaches the fake transport.
    async def fake_connect() -> None:
        client._client = transport  # type: ignore[assignment]
        transport.connected = True

    monkeypatch.setattr(client, "_connect_internal", fake_connect)

    result = asyncio.run(client._read_registers(1000, 2))

    assert transport.attempts == 2
    assert result == [0, 16968]


def test_read_register_skips_permanently_failed_registers() -> None:
    """Explicit single reads must not hammer registers already known to fail."""
    client = IdmModbusClient("127.0.0.1")
    client._permanently_failed_registers.add("outdoor_temp")

    reg = RegisterDef(1000, DataType.FLOAT, "outdoor_temp", unit="°C")
    with pytest.raises(ValueError, match="permanently failed"):
        asyncio.run(client.read_register(reg))


def test_successful_individual_read_resets_transient_failure_counter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = IdmModbusClient("127.0.0.1")
    reg = RegisterDef(1200, DataType.UCHAR, "transient_register")
    client._register_failures[reg.name] = 2

    async def successful_read(
        address: int,
        count: int,
        reg_type: RegisterType = RegisterType.INPUT,
    ) -> list[int]:
        del address, count, reg_type
        return [7]

    monkeypatch.setattr(client, "_read_registers", successful_read)

    result = asyncio.run(client._read_individual_fallback([reg]))

    assert result == {reg.name: 7}
    assert reg.name not in client._register_failures


# ---------------------------------------------------------------------------
# Illegal Data Address (Modbus exception code 2) handling
#
# Optional register blocks that a device does not implement respond with
# exception code 2. This is a permanent condition: retrying is pointless and
# only produces noisy "failed after N attempts" warnings on every poll. The
# library must surface it as IllegalAddressError, bail out of the retry loop
# silently, and let read_batch isolate the offending register immediately.
# ---------------------------------------------------------------------------


def _make_client_with_transport(transport: Any, *, max_retries: int = 3) -> IdmModbusClient:
    client = IdmModbusClient("127.0.0.1", max_retries=max_retries)
    client._client = transport  # type: ignore[assignment]
    return client


def test_read_registers_raises_illegal_address_error_for_exception_code_2() -> None:
    """A device exception_code=2 response surfaces as IllegalAddressError."""
    from .fake_modbus import FakeModbusTransport

    transport = FakeModbusTransport(illegal_reads={("input", 1200, 2)})
    client = _make_client_with_transport(transport)

    with pytest.raises(IllegalAddressError):
        asyncio.run(client._read_registers(1200, 2))


def test_retry_command_does_not_retry_illegal_address_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """IllegalAddressError must bail out of the retry loop immediately.

    A normal Modbus failure would be retried up to max_retries and emit a
    'failed after N attempts' WARNING on exhaustion. Illegal Data Address is
    permanent, so neither retries nor the warning must occur.
    """
    from .fake_modbus import FakeModbusTransport

    transport = FakeModbusTransport(illegal_reads={("input", 1200, 1)})
    client = _make_client_with_transport(transport, max_retries=3)

    caplog.set_level(logging.DEBUG, logger="idm_heatpump.client")
    with pytest.raises(IllegalAddressError):
        asyncio.run(client._read_registers(1200, 1))

    # Only one transport read attempt: the retry loop must not have looped.
    assert transport.read_calls == [("input", 1200, 1)]
    assert not any("failed after" in rec.getMessage() for rec in caplog.records), (
        "IllegalAddressError must not emit a 'failed after N attempts' warning"
    )


def test_read_batch_isolates_illegal_address_and_marks_register_unsupported() -> None:
    """read_batch must mark an illegal-address register as permanently failed.

    Two adjacent registers are read as a single batch range. When one of them
    responds with exception code 2, the batch read falls back to individual
    reads; the illegal one must be isolated immediately (not after the
    transient-failure threshold of 3) and exposed via get_unsupported_registers.
    """
    from .fake_modbus import FakeModbusTransport

    good = RegisterDef(1198, DataType.FLOAT, "good_temp", unit="°C")
    bad = RegisterDef(1200, DataType.FLOAT, "cascade_temp", unit="°C")

    # Batch range covers 1198..1201 (2 floats). Individual reads target the
    # exact register addresses/sizes.
    transport = FakeModbusTransport(
        input_registers={1198: 0, 1199: 16968},
        illegal_reads={
            ("input", 1198, 4),  # the batch range read fails as a whole
            ("input", 1200, 2),  # the individual bad-register read fails
        },
    )
    client = _make_client_with_transport(transport)

    data = asyncio.run(client.read_batch([good, bad]))

    assert "good_temp" in data
    assert "cascade_temp" not in data
    assert client.get_unsupported_registers() == ("cascade_temp",)


def test_get_unsupported_registers_starts_empty() -> None:
    """A fresh client has no unsupported registers."""
    client = IdmModbusClient("127.0.0.1")
    assert client.get_unsupported_registers() == ()


def test_reset_failed_registers_clears_unsupported_set() -> None:
    """reset_failed_registers must also clear the unsupported (illegal-address) set."""
    client = IdmModbusClient("127.0.0.1")
    client._permanently_failed_registers.add("cascade_temp")
    client._unsupported_registers.add("cascade_temp")
    assert client.get_unsupported_registers() == ("cascade_temp",)

    client.reset_failed_registers()

    assert client.get_unsupported_registers() == ()
