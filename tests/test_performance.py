"""Performance and efficiency sanity tests for the API."""

from __future__ import annotations

import asyncio

from idm_heatpump.client import IdmModbusClient, IdmModelInfo
from idm_heatpump.const import (
    FEATURE_CASCADE,
    FEATURE_HEATING_CIRCUITS,
    FEATURE_ISC,
    FEATURE_PV,
    FEATURE_SOLAR,
    FEATURE_ZONE_MODULES,
    MODEL_NAVIGATOR_10,
)
from idm_heatpump.registers import build_register_map

from .fake_modbus import FakeModbusTransport


def test_build_register_map_is_deterministic_and_cached() -> None:
    """Repeated builds for the same model must return equivalent maps cheaply."""
    model_info = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_10,
        active_heating_circuits=["A", "B"],
        zone_modules=2,
        has_solar=True,
        has_isc=True,
        has_pv=True,
        has_cascade=True,
        features={
            FEATURE_HEATING_CIRCUITS,
            FEATURE_ZONE_MODULES,
            FEATURE_SOLAR,
            FEATURE_ISC,
            FEATURE_PV,
            FEATURE_CASCADE,
        },
    )
    first = build_register_map(model_info=model_info)
    second = build_register_map(model_info=model_info)

    assert first.keys() == second.keys()
    for key in first:
        assert first[key].address == second[key].address
        assert first[key].datatype == second[key].datatype


def test_read_batch_groups_registers_efficiently() -> None:
    """read_batch must use fewer Modbus requests than registers."""
    model_info = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_10,
        active_heating_circuits=["A"],
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=False,
        has_cascade=False,
    )
    registers = list(build_register_map(model_info=model_info).values())
    assert len(registers) > 10
    readable_registers = [r for r in registers if not r.write_only]

    # Provide deterministic values for all input registers so batch reads succeed.
    input_values: dict[int, int] = {}
    for reg in registers:
        if reg.register_type.value == "input":
            for offset in range(reg.size):
                input_values[reg.address + offset] = 0

    transport = FakeModbusTransport(input_registers=input_values)
    client = IdmModbusClient("127.0.0.1")
    client._client = transport  # type: ignore[assignment]

    result = asyncio.run(client.read_batch(registers))

    assert len(result) == len(readable_registers)
    # The whole map must be read in far fewer requests than readable registers.
    assert len(transport.read_calls) < len(readable_registers)
