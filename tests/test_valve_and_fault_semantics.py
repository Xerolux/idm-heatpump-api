"""Documented value semantics for the changeover valve and heat-source fault.

The official Navigator 10 table (2025-06-18) labels two status words this
library had modelled as raw numbers:

- Register 1110 ``valve_hc_heat_cool``: 0 ... Heizen (Heating),
  1 ... Kühlen (Cooling).
- Register 1680 ``fault_heat_source_circuit``: 0 ... Störung (fault),
  1 ... Keine Störung (no fault) - inverted against the usual active-high
  convention.

Found by the enum audit that followed idm-heatpump-hass#596: every documented
value list must survive validated polls, and undocumented polarity must stay
raw instead of being inferred from neighbouring registers.
"""

from __future__ import annotations

import pytest

from idm_heatpump.binary_metadata import get_binary_register_metadata
from idm_heatpump.client import DataType, IdmModbusClient, IdmModelInfo, RegisterType
from idm_heatpump.const import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_17,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
    VALVE_HC_HEAT_COOL_OPTIONS,
)
from idm_heatpump.registers import build_register_map

from .fake_modbus import FakeModbusTransport


def _model_info(model: str) -> IdmModelInfo:
    return IdmModelInfo(model, ["A"], 0, False, False, False, False)


def test_valve_enum_matches_official_table() -> None:
    reg = build_register_map(model_info=_model_info(MODEL_NAVIGATOR_10))["valve_hc_heat_cool"]
    assert VALVE_HC_HEAT_COOL_OPTIONS == {0: "Heating", 1: "Cooling"}
    assert (reg.address, reg.datatype, reg.register_type) == (
        1110,
        DataType.UINT16,
        RegisterType.INPUT,
    )
    assert reg.enum_options == VALVE_HC_HEAT_COOL_OPTIONS
    assert reg.writable is False


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [MODEL_NAVIGATOR_20, MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_PRO])
@pytest.mark.parametrize("position", [0, 1])
async def test_valve_positions_survive_validated_poll(model: str, position: int) -> None:
    reg = build_register_map(model_info=_model_info(model))["valve_hc_heat_cool"]
    transport = FakeModbusTransport(input_registers={1110: position})
    client = IdmModbusClient("127.0.0.1", transport=transport)

    assert await client.read_batch([reg]) == {"valve_hc_heat_cool": position}
    assert client.get_register_outcomes()["valve_hc_heat_cool"]["status"] == "ok"


def test_fault_register_binary_metadata_is_inverted() -> None:
    reg = build_register_map(model_info=_model_info(MODEL_NAVIGATOR_10))[
        "fault_heat_source_circuit"
    ]
    assert reg.binary is True
    assert reg.writable is False
    metadata = get_binary_register_metadata("fault_heat_source_circuit")
    assert metadata is not None
    assert metadata.on_values == (0,)
    assert metadata.off_values == (1,)
    assert metadata.device_class == "problem"


@pytest.mark.asyncio
@pytest.mark.parametrize("state", [0, 1])
async def test_fault_states_survive_validated_poll(state: int) -> None:
    reg = build_register_map(model_info=_model_info(MODEL_NAVIGATOR_10))[
        "fault_heat_source_circuit"
    ]
    transport = FakeModbusTransport(input_registers={1680: state})
    client = IdmModbusClient("127.0.0.1", transport=transport)

    assert await client.read_batch([reg]) == {"fault_heat_source_circuit": state}
    assert client.get_register_outcomes()["fault_heat_source_circuit"]["status"] == "ok"


def test_undocumented_polarity_stays_raw() -> None:
    """Registers 1111-1116 and 1681-1683 document no value labels.

    Their 0/1 polarity must not be inferred from the two documented
    neighbours; they stay raw until a field capture confirms it.
    """
    regs = build_register_map(model_info=_model_info(MODEL_NAVIGATOR_10))
    for name in (
        "valve_storage_heat_cool",
        "valve_heat_dhw",
        "fault_heat_source_pressure_switch",
        "fault_charging_pump_1_intermediate",
        "fault_charging_pump_2_intermediate",
    ):
        assert regs[name].enum_options in (None, {}), name
        assert regs[name].binary is False, name
        assert get_binary_register_metadata(name) is None, name


def test_navigator_17_keeps_its_separate_map() -> None:
    legacy = build_register_map(model_info=_model_info(MODEL_NAVIGATOR_17))
    assert "valve_hc_heat_cool" not in legacy
    assert "fault_heat_source_circuit" not in legacy
