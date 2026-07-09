"""Tests for register definitions and validation."""

import pytest

from idm_heatpump.client import DataType, IdmModelInfo
from idm_heatpump.const import (
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
    MODEL_UNKNOWN,
)
from idm_heatpump.registers import (
    CORE_REGISTERS,
    _energy_registers,
    _heat_sink_registers,
    _hp_status_registers,
    _pv_registers,
    _system_registers,
    build_register_map,
    get_all_registers,
    get_heating_circuit_registers,
    get_register,
    get_register_registry,
    get_zone_module_registers,
)


class TestEnergyRegisters:
    """Test energy register definitions."""

    def test_energy_registers_have_state_class(self) -> None:
        """All kWh energy registers should have state_class=total_increasing."""
        regs = _energy_registers()
        energy_keys = [k for k in regs if k.startswith("energy_")]

        for key in energy_keys:
            reg = regs[key]
            assert reg.unit == "kWh", f"{key} should have unit=kWh"
            assert reg.state_class == "total_increasing", (
                f"{key} should have state_class=total_increasing"
            )

    def test_power_registers_have_state_class(self) -> None:
        """All read-only kW power registers should have state_class=measurement."""
        regs = _energy_registers()
        power_keys = [
            "current_power",
            "current_power_solar",
            "power_consumption_hp",
            "thermal_power_flow_sensor",
        ]

        for key in power_keys:
            if key in regs:
                reg = regs[key]
                assert reg.unit == "kW", f"{key} should have unit=kW"
                assert reg.state_class == "measurement", (
                    f"{key} should have state_class=measurement"
                )

    def test_total_heat_energy_has_state_class(self) -> None:
        """total_heat_energy should have proper state_class."""
        regs = _energy_registers()
        reg = regs["total_heat_energy"]
        assert reg.unit == "kWh"
        assert reg.state_class == "total_increasing"


class TestPVRegisters:
    """Test PV register definitions (addresses 74-88, all RW/RO per official doc)."""

    def test_pv_power_registers(self) -> None:
        """All PV power registers are FLOAT kW and writable (RW/RO)."""
        regs = _pv_registers()
        power_keys = [
            "pv_surplus",
            "electric_heater_power",
            "pv_production",
            "house_consumption",
            "battery_discharge",
            "pv_target_value",
        ]

        for key in power_keys:
            reg = regs[key]
            assert reg.unit == "kW", f"{key} should have unit=kW"
            assert reg.datatype == DataType.FLOAT, f"{key} should be FLOAT"
            assert reg.writable, f"{key} should be writable (RW/RO)"

    def test_pv_addresses(self) -> None:
        """PV register addresses match the official Navigator 10 doc."""
        regs = _pv_registers()
        expected = {
            "pv_surplus": 74,
            "electric_heater_power": 76,
            "pv_production": 78,
            "house_consumption": 82,
            "battery_discharge": 84,
            "battery_soc": 86,
            "pv_target_value": 88,
        }
        for key, addr in expected.items():
            assert regs[key].address == addr, f"{key} should be at address {addr}"

    def test_battery_soc_is_single_register(self) -> None:
        """battery_soc (86) is WORD (1 register, signed: -1 = unavailable), not FLOAT."""
        reg = _pv_registers()["battery_soc"]
        assert reg.datatype == DataType.INT16
        assert reg.size == 1


class TestSystemRegisters:
    """Verify system register addresses/types against the official doc."""

    def test_smart_grid_status_address(self) -> None:
        """Smart Grid status is at address 90 on Navigator 10 (not 1006)."""
        regs = _system_registers()
        assert regs["smart_grid_status"].address == 90

    def test_variable_input_address(self) -> None:
        """Address 1006 is the variable input ('Variabler Eingang')."""
        regs = _system_registers()
        reg = regs["variable_input"]
        assert reg.address == 1006
        assert not reg.writable

    def test_internal_message_is_uint16(self) -> None:
        """Message numbers go up to 999, so 1004 must not be masked to one byte."""
        regs = _system_registers()
        assert regs["internal_message"].datatype == DataType.UINT16

    def test_dhw_setpoint_range(self) -> None:
        """DHW setpoint (1032) range is 35-95 °C per official doc."""
        reg = _system_registers()["dhw_setpoint"]
        assert reg.min_val == 35
        assert reg.max_val == 95


class TestHpStatusRegisters:
    """Verify heat pump status registers against the official doc."""

    def test_pump_status_registers_signed(self) -> None:
        """Pump status WORD registers use -1 = off and must decode signed."""
        regs = _hp_status_registers()
        for key in [
            "charging_pump_status",
            "brine_pump_status",
            "heat_source_pump_status",
            "isc_cold_storage_pump_status",
            "isc_recooling_pump_status",
        ]:
            reg = regs[key]
            assert reg.datatype == DataType.INT16, f"{key} should be INT16"
            assert reg.unit == "%", f"{key} should have unit=%"

    def test_bivalence_points_range(self) -> None:
        """Bivalence points (1120-1123) accept -40..40 °C."""
        regs = _hp_status_registers()
        for key in [
            "bivalence_point_1_2nd_gen",
            "bivalence_point_2_2nd_gen",
            "bivalence_point_1_3rd_gen",
            "bivalence_point_2_3rd_gen",
        ]:
            reg = regs[key]
            assert reg.min_val == -40, f"{key} min should be -40"
            assert reg.max_val == 40, f"{key} max should be 40"
            assert reg.datatype == DataType.INT16, f"{key} should be INT16"


class TestIscMode:
    """ISC mode (1874) is read-only per official doc."""

    def test_isc_mode_read_only(self) -> None:
        regs = build_register_map()
        assert not regs["isc_mode"].writable


class TestHeatSinkRegisters:
    """Test heat sink register definitions."""

    def test_heat_sink_flow_rate_unit_and_state_class(self) -> None:
        """heat_sink_flow_rate should have correct unit and state_class."""
        regs = _heat_sink_registers()
        reg = regs["heat_sink_flow_rate"]
        assert reg.unit == "L/min", "Unit should be L/min (not l/min)"
        assert reg.state_class == "measurement"


class TestHumidityRegisters:
    """Test humidity register definitions."""

    def test_humidity_unit_strings(self) -> None:
        """All humidity registers should use % (not %rF)."""
        all_regs = build_register_map(circuits=["A"], zone_modules=1)

        humidity_keys = [k for k in all_regs if "humidity" in k]
        for key in humidity_keys:
            reg = all_regs[key]
            assert reg.unit == "%", f"{key} should have unit=% (not %rF)"
            # Only read-only humidity registers should have state_class
            if not reg.writable:
                assert reg.state_class == "measurement", (
                    f"{key} should have state_class=measurement"
                )


class TestBuildRegisterMap:
    """Test register map building."""

    def test_build_register_map_without_model_info(self) -> None:
        """Should build register map with manual parameters."""
        regs = build_register_map(circuits=["A", "B"], zone_modules=1)
        assert len(regs) > 0
        assert "outdoor_temp" in regs
        assert "hc_a_flow_temp" in regs
        assert "hc_b_flow_temp" in regs

    def test_build_register_map_with_zones(self) -> None:
        """Should include zone module registers when specified."""
        regs = build_register_map(circuits=["A"], zone_modules=2)
        assert any("zm1_" in k for k in regs)
        assert any("zm2_" in k for k in regs)

    @pytest.mark.parametrize("circuits", [[""], ["AB"], ["A", "BC"]])
    def test_build_register_map_rejects_non_single_letter_circuits(
        self, circuits: list[str]
    ) -> None:
        with pytest.raises(ValueError, match="Invalid heating circuit letters"):
            build_register_map(circuits=circuits)

    def test_no_writable_with_state_class(self) -> None:
        """No writable registers should have state_class (HA doesn't use it for controls)."""
        regs = build_register_map()

        for key, reg in regs.items():
            if reg.writable:
                assert reg.state_class is None, (
                    f"Writable register {key} should not have state_class"
                )

    @pytest.mark.parametrize("model_name", [MODEL_NAVIGATOR_20, MODEL_NAVIGATOR_PRO, MODEL_UNKNOWN])
    def test_older_or_unknown_model_excludes_navigator_10_registers(self, model_name: str) -> None:
        model_info = IdmModelInfo(
            model_name=model_name,
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )

        regs = build_register_map(model_info=model_info)

        assert "outdoor_temp" in regs
        assert "hc_a_flow_temp" in regs
        assert "power_limit_hp" not in regs
        assert all(reg.address != 4108 for reg in regs.values())
        assert "booster_fault" not in regs
        assert "heat_sink_flow_rate" not in regs

    def test_navigator_10_model_includes_navigator_10_registers(self) -> None:
        model_info = IdmModelInfo(
            model_name=MODEL_NAVIGATOR_10,
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )

        regs = build_register_map(model_info=model_info)

        assert regs["power_limit_hp"].address == 4108
        assert "booster_fault" in regs
        assert "heat_sink_flow_rate" in regs

    def test_manual_map_keeps_complete_backward_compatible_register_set(self) -> None:
        regs = build_register_map(circuits=["A"])

        assert regs["power_limit_hp"].address == 4108


class TestHeatingCircuits:
    """Test heating circuit register generation."""

    def test_heating_circuit_registers_generation(self) -> None:
        """Should generate registers for valid circuit letters."""
        for letter in ["A", "B", "C", "D", "E", "F", "G"]:
            regs = get_heating_circuit_registers(letter)
            assert len(regs) > 0
            assert f"hc_{letter.lower()}_flow_temp" in regs

    def test_heating_circuit_invalid_letter(self) -> None:
        """Should raise ValueError for invalid circuit letters."""
        with pytest.raises(ValueError):
            get_heating_circuit_registers("H")


class TestZoneModules:
    """Test zone module register generation."""

    def test_zone_module_registers_generation(self) -> None:
        """Should generate registers for valid zone indices."""
        for zone in range(1, 11):
            regs = get_zone_module_registers(zone, room_count=6)
            assert len(regs) > 0
            assert f"zm{zone}_room1_temp" in regs

    def test_zone_module_invalid_index(self) -> None:
        """Should raise ValueError for invalid zone indices."""
        with pytest.raises(ValueError):
            get_zone_module_registers(0)
        with pytest.raises(ValueError):
            get_zone_module_registers(11)

    def test_zone_module_invalid_room_count(self) -> None:
        """Zone modules support at most 8 rooms."""
        with pytest.raises(ValueError):
            get_zone_module_registers(1, room_count=9)
        with pytest.raises(ValueError):
            get_zone_module_registers(1, room_count=0)

    def test_zone_module_eight_rooms(self) -> None:
        """Eight-room zone modules generate rooms 7 and 8 correctly."""
        regs = get_zone_module_registers(1, room_count=8)
        # Room 7: room_base = 2002 + 6*7 = 2044
        assert regs["zm1_room7_temp"].address == 2044
        assert regs["zm1_room7_setpoint"].address == 2046
        assert regs["zm1_room7_humidity"].address == 2048
        assert regs["zm1_room7_mode"].address == 2049
        assert regs["zm1_room7_relay"].address == 2050
        # Room 8: room_base = 2002 + 7*7 = 2051
        assert regs["zm1_room8_temp"].address == 2051
        assert regs["zm1_room8_setpoint"].address == 2053
        assert regs["zm1_room8_humidity"].address == 2055
        assert regs["zm1_room8_mode"].address == 2056
        assert regs["zm1_room8_relay"].address == 2057
        # Zone 2 room 8 mode at 2121 (matches issue #69 reporter addresses)
        regs2 = get_zone_module_registers(2, room_count=8)
        assert regs2["zm2_room8_mode"].address == 2121
        assert regs2["zm2_room7_mode"].address == 2114

    def test_zone_module_humidity(self) -> None:
        """Zone module humidity registers are % and writable (RW/RO for GLT sensors)."""
        regs = get_zone_module_registers(1, room_count=1)
        humidity_reg = regs["zm1_room1_humidity"]
        assert humidity_reg.unit == "%"
        assert humidity_reg.writable
        assert humidity_reg.min_val == 0
        assert humidity_reg.max_val == 100

    def test_zone_module_room_addresses(self) -> None:
        """Room blocks are 7 registers wide; addresses match the official doc."""
        regs = get_zone_module_registers(1, room_count=6)
        # Zone module 1, room 1: 2002/2004/2006/2007/2008
        assert regs["zm1_room1_temp"].address == 2002
        assert regs["zm1_room1_setpoint"].address == 2004
        assert regs["zm1_room1_humidity"].address == 2006
        assert regs["zm1_room1_mode"].address == 2007
        assert regs["zm1_room1_relay"].address == 2008
        # Zone module 1, room 2 starts at 2009
        assert regs["zm1_room2_temp"].address == 2009
        assert regs["zm1_room2_setpoint"].address == 2011
        assert regs["zm1_room2_humidity"].address == 2013
        assert regs["zm1_room2_mode"].address == 2014
        assert regs["zm1_room2_relay"].address == 2015
        # Zone module 1, room 6 ends at 2043
        assert regs["zm1_room6_temp"].address == 2037
        assert regs["zm1_room6_relay"].address == 2043

        # Zone module 2 starts at 2065, room 1 temp at 2067
        regs2 = get_zone_module_registers(2, room_count=1)
        assert regs2["zm2_mode_heat_cool"].address == 2065
        assert regs2["zm2_room1_temp"].address == 2067

        # Zone module 10 starts at 2585, last relay at 2628
        regs10 = get_zone_module_registers(10, room_count=6)
        assert regs10["zm10_mode_heat_cool"].address == 2585
        assert regs10["zm10_room6_relay"].address == 2628


class TestHeatingCircuitAddresses:
    """Verify heating circuit addresses against the official doc."""

    def test_circuit_a_addresses(self) -> None:
        regs = get_heating_circuit_registers("A")
        assert regs["hc_a_flow_temp"].address == 1350
        assert regs["hc_a_room_temp"].address == 1364
        assert regs["hc_a_setpoint_flow_temp"].address == 1378
        assert regs["hc_a_mode"].address == 1393
        assert regs["hc_a_room_setpoint_heat_normal"].address == 1401
        assert regs["hc_a_heating_curve"].address == 1429
        assert regs["hc_a_heating_limit"].address == 1443
        assert regs["hc_a_active_mode"].address == 1499
        assert regs["hc_a_parallel_shift"].address == 1506
        assert regs["hc_a_ext_room_temp"].address == 1650

    def test_circuit_g_addresses(self) -> None:
        regs = get_heating_circuit_registers("G")
        assert regs["hc_g_flow_temp"].address == 1362
        assert regs["hc_g_mode"].address == 1399
        assert regs["hc_g_heating_limit"].address == 1449
        assert regs["hc_g_setpoint_flow_cooling"].address == 1498
        assert regs["hc_g_parallel_shift"].address == 1512
        assert regs["hc_g_ext_room_temp"].address == 1662

    def test_heating_curve_range(self) -> None:
        regs = get_heating_circuit_registers("A")
        curve = regs["hc_a_heating_curve"]
        assert curve.min_val == 0.1
        assert curve.max_val == 3.5


def test_full_register_map_has_no_address_overlaps() -> None:
    """Every Modbus address must be owned by exactly one register."""
    regs = build_register_map(
        circuits=list("ABCDEFG"),
        zone_modules=10,
        rooms_per_zone=6,
    )
    occupied: dict[int, str] = {}
    overlaps: list[tuple[int, str, str]] = []
    for name, reg in regs.items():
        for addr in range(reg.address, reg.address + reg.size):
            if addr in occupied:
                overlaps.append((addr, occupied[addr], name))
            else:
                occupied[addr] = name
    assert not overlaps, f"Address overlaps detected: {overlaps[:10]}"


def test_humidity_sensor_does_not_overlap_heating_circuit_mode() -> None:
    """humidity_sensor occupies the single free register between setpoint_flow_temp G and hc_a_mode."""
    regs = build_register_map(circuits=list("ABCDEFG"))
    assert regs["humidity_sensor"].address == 1392
    assert regs["humidity_sensor"].size == 1
    assert regs["hc_a_mode"].address == 1393


def test_build_register_map_rejects_invalid_circuits() -> None:
    with pytest.raises(ValueError, match="Invalid heating circuit letters"):
        build_register_map(circuits=["A", "H"])


def test_build_register_map_rejects_invalid_zone_modules() -> None:
    with pytest.raises(ValueError, match="zone_modules"):
        build_register_map(zone_modules=11)


def test_build_register_map_rejects_invalid_rooms_per_zone() -> None:
    with pytest.raises(ValueError, match="rooms_per_zone"):
        build_register_map(rooms_per_zone=0)


def test_build_register_map_accepts_eight_rooms_per_zone() -> None:
    """Issue #68: 8-room zone modules must be supported."""
    regs = build_register_map(zone_modules=1, rooms_per_zone=8)
    assert "zm1_room7_temp" in regs
    assert "zm1_room8_mode" in regs
    assert regs["zm1_room8_mode"].address == 2056


def test_build_register_map_rejects_nine_rooms_per_zone() -> None:
    with pytest.raises(ValueError, match="rooms_per_zone"):
        build_register_map(zone_modules=1, rooms_per_zone=9)


def test_get_register_defaults_to_core_registers() -> None:
    reg = get_register("outdoor_temp")
    assert reg.address == 1000


def test_get_register_looks_up_full_map_with_model_info() -> None:
    model_info = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_10,
        active_heating_circuits=list("ABCDEFG"),
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=False,
        has_cascade=False,
    )
    reg = get_register("dhw_temp_top", model_info=model_info)
    assert reg.address == 1014


def test_get_register_raises_for_unknown_name() -> None:
    with pytest.raises(ValueError, match="Register 'unknown' not found"):
        get_register("unknown")


def test_get_all_registers_defaults_to_core() -> None:
    assert {reg.name for reg in get_all_registers()} == set(CORE_REGISTERS)


def test_get_all_registers_returns_full_map_with_model_info() -> None:
    model_info = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_10,
        active_heating_circuits=["A"],
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=False,
        has_cascade=False,
    )
    names = {reg.name for reg in get_all_registers(model_info=model_info)}
    assert "hc_a_flow_temp" in names
    assert "hc_b_flow_temp" not in names


def test_register_registry_provides_key_address_and_schema_lookups() -> None:
    registry = get_register_registry()

    assert registry.require("system_mode").address == 1005
    by_addr = registry.by_address(1005)
    assert by_addr is not None
    assert by_addr.name == "system_mode"
    assert "system_mode" in registry.writable()
    schema = registry.to_schema()
    system_mode_schema = next(item for item in schema if item["key"] == "system_mode")
    assert system_mode_schema["datatype"] == "UCHAR"
    assert system_mode_schema["writable"] is True
