"""Tests for the IDM Modbus client."""

import asyncio
from typing import Any

from idm_heatpump.client import IdmModbusClient
from idm_heatpump.const import (
    FEATURE_CASCADE,
    FEATURE_HEATING_CIRCUITS,
    FEATURE_ISC,
    FEATURE_PV,
    FEATURE_SOLAR,
    FEATURE_ZONE_MODULES,
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
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
    assert client.model_name == MODEL_NAVIGATOR_10


def test_model_name_defaults_before_detection() -> None:
    """model_name should fall back to the default model until detection runs."""
    client = IdmModbusClient("127.0.0.1")
    assert client.model_name == MODEL_NAVIGATOR_20


def test_model_name_defaults_when_detection_inconclusive() -> None:
    """model_name should fall back to the default model when detection is inconclusive."""
    client = ProbeOnlyClient({})

    model_info = asyncio.run(client.detect_model())

    assert model_info.model_name == "Unknown"
    assert client.model_name == MODEL_NAVIGATOR_20
