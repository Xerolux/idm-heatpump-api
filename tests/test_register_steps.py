"""Numeric control hints must not change register protocol definitions."""

import pytest

from idm_heatpump.client import DataType, RegisterDef, RegisterType
from idm_heatpump.registers import (
    RegisterRegistry,
    get_heating_circuit_registers,
    get_zone_module_registers,
)


@pytest.mark.parametrize("step", [0, -0.5, float("nan"), float("inf")])
def test_step_rejects_invalid_metadata(step: float) -> None:
    with pytest.raises(ValueError, match="Step"):
        RegisterDef(1000, DataType.FLOAT, "test", step=step)


@pytest.mark.parametrize("circuit", list("ABCDEFG"))
def test_heating_curve_step_keeps_protocol(circuit: str) -> None:
    reg = get_heating_circuit_registers(circuit)[f"hc_{circuit.lower()}_heating_curve"]
    assert (reg.address, reg.datatype, reg.size, reg.register_type) == (
        1429 + 2 * (ord(circuit) - ord("A")),
        DataType.FLOAT,
        2,
        RegisterType.INPUT,
    )
    assert (reg.min_val, reg.max_val, reg.step) == (0.1, 3.5, 0.1)
    assert reg.eeprom_sensitive
    assert RegisterRegistry({reg.name: reg}).to_schema()[0]["step"] == 0.1


@pytest.mark.parametrize("zone", range(1, 11))
def test_zone_setpoint_step_does_not_invent_limits(zone: int) -> None:
    registers = get_zone_module_registers(zone)
    for room in range(1, 7):
        reg = registers[f"zm{zone}_room{room}_setpoint"]
        assert (reg.address, reg.datatype, reg.size, reg.register_type) == (
            2004 + (zone - 1) * 65 + (room - 1) * 7,
            DataType.FLOAT,
            2,
            RegisterType.INPUT,
        )
        assert reg.writable and reg.step == 0.5
        assert reg.min_val is None and reg.max_val is None
        assert RegisterRegistry({reg.name: reg}).to_schema()[0]["step"] == 0.5
    assert registers[f"zm{zone}_room1_temp"].step is None
