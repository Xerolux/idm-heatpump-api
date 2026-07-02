"""Tests for the IDM Modbus client."""

import asyncio
from typing import Any

import pytest
from pymodbus.exceptions import ModbusException

from idm_heatpump.client import DataType, IdmModbusClient, RegisterDef, RegisterType
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

    async def _ensure_connected(self) -> Any:
        return object()

    async def probe_register(self, address: int, count: int = 1) -> list[int] | None:
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
    assert not model_info.has_solar
    assert not model_info.has_isc
    assert not model_info.has_pv
    assert not model_info.has_cascade
    assert model_info.firmware_version is None


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
