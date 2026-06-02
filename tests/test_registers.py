"""Tests for register definitions and validation."""

import pytest

from idm_heatpump.registers import (
    _energy_registers,
    _heat_sink_registers,
    _pv_registers,
    build_register_map,
    get_heating_circuit_registers,
    get_zone_module_registers,
)


class TestEnergyRegisters:
    """Test energy register definitions."""

    def test_energy_registers_have_state_class(self):
        """All kWh energy registers should have state_class=total_increasing."""
        regs = _energy_registers()
        energy_keys = [k for k in regs if k.startswith("energy_")]

        for key in energy_keys:
            reg = regs[key]
            assert reg.unit == "kWh", f"{key} should have unit=kWh"
            assert reg.state_class == "total_increasing", f"{key} should have state_class=total_increasing"

    def test_power_registers_have_state_class(self):
        """All read-only kW power registers should have state_class=measurement."""
        regs = _energy_registers()
        power_keys = ["current_power", "current_power_solar", "power_consumption_hp", "thermal_power_flow_sensor"]

        for key in power_keys:
            if key in regs:
                reg = regs[key]
                assert reg.unit == "kW", f"{key} should have unit=kW"
                assert reg.state_class == "measurement", f"{key} should have state_class=measurement"

    def test_total_heat_energy_has_state_class(self):
        """total_heat_energy should have proper state_class."""
        regs = _energy_registers()
        reg = regs["total_heat_energy"]
        assert reg.unit == "kWh"
        assert reg.state_class == "total_increasing"


class TestPVRegisters:
    """Test PV register definitions."""

    def test_pv_power_registers_have_state_class(self):
        """All read-only PV power registers should have state_class=measurement."""
        regs = _pv_registers()
        power_keys = ["pv_surplus", "electric_heater_power", "pv_production", "house_consumption", "battery_discharge"]

        for key in power_keys:
            reg = regs[key]
            assert reg.unit == "kW", f"{key} should have unit=kW"
            assert reg.state_class == "measurement", f"{key} should have state_class=measurement"


class TestHeatSinkRegisters:
    """Test heat sink register definitions."""

    def test_heat_sink_flow_rate_unit_and_state_class(self):
        """heat_sink_flow_rate should have correct unit and state_class."""
        regs = _heat_sink_registers()
        reg = regs["heat_sink_flow_rate"]
        assert reg.unit == "L/min", "Unit should be L/min (not l/min)"
        assert reg.state_class == "measurement"


class TestHumidityRegisters:
    """Test humidity register definitions."""

    def test_humidity_unit_strings(self):
        """All humidity registers should use % (not %rF)."""
        all_regs = build_register_map(circuits=["A"], zone_modules=1)

        humidity_keys = [k for k in all_regs if "humidity" in k]
        for key in humidity_keys:
            reg = all_regs[key]
            assert reg.unit == "%", f"{key} should have unit=% (not %rF)"
            # Only read-only humidity registers should have state_class
            if not reg.writable:
                assert reg.state_class == "measurement", f"{key} should have state_class=measurement"


class TestBuildRegisterMap:
    """Test register map building."""

    def test_build_register_map_without_model_info(self):
        """Should build register map with manual parameters."""
        regs = build_register_map(circuits=["A", "B"], zone_modules=1)
        assert len(regs) > 0
        assert "outdoor_temp" in regs
        assert "hc_a_flow_temp" in regs
        assert "hc_b_flow_temp" in regs

    def test_build_register_map_with_zones(self):
        """Should include zone module registers when specified."""
        regs = build_register_map(circuits=["A"], zone_modules=2)
        assert any("zm1_" in k for k in regs)
        assert any("zm2_" in k for k in regs)

    def test_no_writable_with_state_class(self):
        """No writable registers should have state_class (HA doesn't use it for controls)."""
        regs = build_register_map()

        for key, reg in regs.items():
            if reg.writable:
                assert reg.state_class is None, f"Writable register {key} should not have state_class"


class TestHeatingCircuits:
    """Test heating circuit register generation."""

    def test_heating_circuit_registers_generation(self):
        """Should generate registers for valid circuit letters."""
        for letter in ["A", "B", "C", "D", "E", "F", "G"]:
            regs = get_heating_circuit_registers(letter)
            assert len(regs) > 0
            assert f"hc_{letter.lower()}_flow_temp" in regs

    def test_heating_circuit_invalid_letter(self):
        """Should raise ValueError for invalid circuit letters."""
        with pytest.raises(ValueError):
            get_heating_circuit_registers("H")


class TestZoneModules:
    """Test zone module register generation."""

    def test_zone_module_registers_generation(self):
        """Should generate registers for valid zone indices."""
        for zone in range(1, 11):
            regs = get_zone_module_registers(zone, room_count=6)
            assert len(regs) > 0
            assert f"zm{zone}_room1_temp" in regs

    def test_zone_module_invalid_index(self):
        """Should raise ValueError for invalid zone indices."""
        with pytest.raises(ValueError):
            get_zone_module_registers(0)
        with pytest.raises(ValueError):
            get_zone_module_registers(11)

    def test_zone_module_humidity_has_state_class(self):
        """Zone module humidity registers should have state_class."""
        regs = get_zone_module_registers(1, room_count=1)
        humidity_reg = regs["zm1_room1_humidity"]
        assert humidity_reg.unit == "%"
        assert humidity_reg.state_class == "measurement"
