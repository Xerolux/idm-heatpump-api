"""Navigator 1.0/1.7 protocol family: register map, detection, write block.

The 1.x family is a separate protocol family with its own official register
table (ma_de_812049, 2016-06-13). These tests pin the map contents, the
detection signature, and the read-only contract.
"""

from __future__ import annotations

import asyncio
import struct
from typing import Any

from idm_heatpump.client import (
    DataType,
    IdmModbusClient,
    IdmModelInfo,
    RegisterType,
)
from idm_heatpump.const import (
    HC_OPERATING_MODE_17_OPTIONS,
    MODEL_NAVIGATOR_10,
    MODEL_NAVIGATOR_17,
    MODEL_NAVIGATOR_20,
    MODEL_NAVIGATOR_PRO,
    MODEL_UNKNOWN,
    PUMP_STATUS_OPTIONS,
    SOLAR_OPERATING_MODE_17_OPTIONS,
    SYSTEM_MODE_17_OPTIONS,
)
from idm_heatpump.registers import (
    NAVIGATOR_17_HOLDING_SOURCE_VERSION,
    NAVIGATOR_17_REGISTER_SOURCE,
    NAVIGATOR_17_REGISTER_SOURCE_VERSION,
    _navigator_17_registers,
    build_register_map,
    get_register_registry,
)

from .fake_modbus import FakeModbusTransport

# Official 1.x table: FC04 FLOAT block 1000-1088, status words 1500-1524.
# Official FC03/FC06 RW holding block 2000-2152 of ma_de_812049 Rev.1;
# the operating modes were additionally confirmed by an FHEM capture
# against a real Navigator 1.7 (idm-heatpump-hass#319).
EXPECTED_HOLDING: dict[str, int] = {
    "system_mode_17": 2000,
    "solar_operating_mode_17": 2150,
    "external_demand_temp_heating": 2142,
    "external_demand_temp_cooling": 2144,
    "dhw_setpoint": 2152,
    "bivalence_point_1_17": 2146,
    "bivalence_point_2_17": 2148,
}
for _idx, _letter in enumerate("abcdefg"):
    EXPECTED_HOLDING[f"hc_{_letter}_operating_mode"] = 2002 + _idx * 2
    EXPECTED_HOLDING[f"hc_{_letter}_room_setpoint_heat_normal"] = 2016 + _idx * 2
    EXPECTED_HOLDING[f"hc_{_letter}_room_setpoint_heat_eco"] = 2030 + _idx * 2
    EXPECTED_HOLDING[f"hc_{_letter}_heating_curve"] = 2044 + _idx * 2
    EXPECTED_HOLDING[f"hc_{_letter}_heating_limit"] = 2058 + _idx * 2
    EXPECTED_HOLDING[f"hc_{_letter}_setpoint_flow_constant"] = 2072 + _idx * 2
    EXPECTED_HOLDING[f"hc_{_letter}_room_setpoint_cool_normal"] = 2086 + _idx * 2
    EXPECTED_HOLDING[f"hc_{_letter}_room_setpoint_cool_eco"] = 2100 + _idx * 2
    EXPECTED_HOLDING[f"hc_{_letter}_cooling_limit"] = 2114 + _idx * 2
    EXPECTED_HOLDING[f"hc_{_letter}_setpoint_flow_cooling"] = 2128 + _idx * 2
del _idx, _letter
EXPECTED_FLOATS: dict[str, int] = {
    "outdoor_temp": 1000,
    "hp_flow_temp": 1002,
    "hgl_flow_temp": 1004,
    "heat_source_outlet_temp": 1006,
    "storage_temp": 1008,
    "cold_storage_temp": 1010,
    "dhw_temp": 1012,
    "dhw_tapping_temp": 1014,
    "hot_gas_temp": 1044,
    "humidity_sensor": 1046,
    "air_intake_temp": 1048,
    "air_heat_exchanger_temp": 1050,
    "solar_collector_temp": 1052,
    "solar_charging_temp": 1054,
    "solar_collector_return_temp": 1056,
    "solar_pool_temp": 1058,
    "outdoor_temp_avg": 1060,
    "heat_source_inlet_temp": 1062,
    "isc_cooling_charge_temp": 1064,
    "isc_recooling_temp": 1066,
    "thermal_power_hp_flow": 1068,
    "thermal_power_hgl_flow": 1070,
    "thermal_power_total": 1072,
    "thermal_power_solar": 1074,
    "energy_total": 1076,
    "energy_heating": 1078,
    "energy_hgl": 1080,
    "energy_cooling": 1082,
    "energy_solar": 1084,
    "groundwater_pump_flow_total": 1086,
    "heat_source_pump_operating_hours": 1088,
}
EXPECTED_STATUS: dict[str, int] = {
    "error_number": 1500,
    "hp_operating_mode": 1501,
    "hc_a_status": 1502,
    "hc_b_status": 1503,
    "hc_c_status": 1504,
    "hc_d_status": 1505,
    "hc_e_status": 1506,
    "hc_f_status": 1507,
    "hc_g_status": 1508,
    "compressor_status_1": 1509,
    "compressor_status_2": 1510,
    "compressor_status_3": 1511,
    "compressor_status_4": 1512,
    "charging_pump_status": 1513,
    "heat_source_pump_status": 1514,
    "intermediate_circuit_pump_status": 1515,
    "isc_cold_storage_pump_status": 1516,
    "isc_recooling_pump_status": 1517,
    "compressor_stages_heating": 1518,
    "compressor_stages_cooling": 1519,
    "compressor_stages_dhw": 1520,
    "cascade_mode": 1521,
    "solar_mode": 1522,
    "smart_grid_status": 1523,
    "isc_mode": 1524,
}
for idx, letter in enumerate("abcdefg"):
    EXPECTED_FLOATS[f"hc_{letter}_flow_temp"] = 1016 + idx * 2
    EXPECTED_FLOATS[f"hc_{letter}_room_device_temp"] = 1030 + idx * 2


def navigator_17_model_info() -> IdmModelInfo:
    return IdmModelInfo(
        model_name=MODEL_NAVIGATOR_17,
        active_heating_circuits=[],
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=False,
        has_cascade=False,
    )


class Navigator17Transport(FakeModbusTransport):
    """Fake endpoint shaped like the observed 1.x family behaviour.

    The low input block (1000-1524) responds; every shared 2.0/10/Pro family
    probe address is rejected with Modbus exception code 2.
    """

    def __init__(self, *, status_block_responds: bool = True) -> None:
        input_registers: dict[int, int] = {}
        for address in range(1000, 1090):
            input_registers[address] = 0
        if status_block_responds:
            for address in range(1500, 1525):
                input_registers[address] = 1
        rejected: set[tuple[str, int, int]] = set()
        for address in (74, 76, 78, 82):  # PV block probes
            rejected.add(("input", address, 2))
        for i in range(7):  # heating-circuit flow temperatures 1350-1362
            rejected.add(("input", 1350 + i * 2, 2))
        for i in range(7):  # active-mode probes 1498-1504
            rejected.add(("input", 1498 + i, 1))
        if not status_block_responds:
            for address in range(1500, 1525):
                rejected.add(("input", address, 1))
        for address in (1850, 1870, 4108, 4120, 4122, 4126):
            rejected.add(("input", address, 2))
        for address in (1147, 4001):
            rejected.add(("input", address, 1))
        for i in range(10):  # zone-module slots 2000, 2065, ...
            rejected.add(("input", 2000 + i * 65, 1))
        super().__init__(
            input_registers=input_registers,
            illegal_reads=rejected,
        )


def _float_words(value: float) -> list[int]:
    raw = struct.pack("<f", value)
    return list(struct.unpack("<HH", raw))


def test_navigator_17_map_matches_official_table() -> None:
    regs = _navigator_17_registers()

    expected = {**EXPECTED_FLOATS, **EXPECTED_STATUS, **EXPECTED_HOLDING}
    assert set(regs) == set(expected), sorted(set(regs) ^ set(expected))
    for name, address in expected.items():
        assert regs[name].address == address, name


def test_navigator_17_base_map_is_read_only() -> None:
    """Read-only everywhere except the official RW holding block."""
    regs = _navigator_17_registers()
    holding = {name for name, reg in regs.items() if reg.register_type is RegisterType.HOLDING}
    assert holding == set(EXPECTED_HOLDING)
    for name, reg in regs.items():
        if name in holding:
            assert reg.writable, name
            assert reg.write_class.value != "forbidden", name
            continue
        assert not reg.writable, name
        assert reg.write_class.value == "forbidden", name
        assert reg.register_type is RegisterType.INPUT, name


def test_navigator_17_pv_supplement_adds_writable_registers() -> None:
    regs = _navigator_17_registers(has_pv=True)

    for name, address in {
        "pv_surplus": 74,
        "electric_heater_power": 76,
        "pv_production": 78,
        "house_consumption": 82,
        "power_consumption_hp": 4122,
    }.items():
        assert name in regs, name
        assert regs[name].address == address, name

    for name in ("pv_surplus", "electric_heater_power", "pv_production", "house_consumption"):
        assert regs[name].writable, name
        assert regs[name].unit == "kW", name
        assert regs[name].datatype is DataType.FLOAT, name
    # The power measurement stays read-only.
    assert not regs["power_consumption_hp"].writable
    assert regs["power_consumption_hp"].state_class == "measurement"
    # Without the probe response the supplement is absent.
    assert "pv_surplus" not in _navigator_17_registers(has_pv=False)


def test_navigator_17_map_declares_family_metadata() -> None:
    regs = _navigator_17_registers()
    holding = {name for name, reg in regs.items() if reg.register_type is RegisterType.HOLDING}
    for name, reg in regs.items():
        assert reg.supported_models == (MODEL_NAVIGATOR_17,), name
        assert reg.source == NAVIGATOR_17_REGISTER_SOURCE, name
        if name in holding:
            assert reg.source_version == NAVIGATOR_17_HOLDING_SOURCE_VERSION, name
        else:
            assert reg.source_version == NAVIGATOR_17_REGISTER_SOURCE_VERSION, name


def test_navigator_17_map_datatypes_and_units() -> None:
    regs = _navigator_17_registers()

    for name in EXPECTED_FLOATS:
        assert regs[name].datatype is DataType.FLOAT, name
        assert regs[name].size == 2, name
    for name in EXPECTED_STATUS:
        if name == "hp_operating_mode":
            # UCHAR per the 1.x table; firmwares double the byte into the word.
            assert regs[name].datatype is DataType.UCHAR, name
        else:
            assert regs[name].datatype is DataType.UINT16, name
        assert regs[name].size == 1, name
    assert regs["outdoor_temp"].unit == "°C"
    assert regs["humidity_sensor"].unit == "%"
    assert regs["thermal_power_total"].unit == "kW"
    assert regs["energy_total"].unit == "kWh"
    assert regs["heat_source_pump_operating_hours"].unit == "h"
    # The flow-counter volume unit is not documented in the 1.x table.
    assert regs["groundwater_pump_flow_total"].unit is None


def test_navigator_17_energy_and_power_state_classes() -> None:
    regs = _navigator_17_registers()

    for name in ("thermal_power_hp_flow", "thermal_power_hgl_flow", "thermal_power_total"):
        assert regs[name].state_class == "measurement", name
    for name in (
        "energy_total",
        "energy_heating",
        "energy_hgl",
        "energy_cooling",
        "energy_solar",
        "groundwater_pump_flow_total",
        "heat_source_pump_operating_hours",
    ):
        assert regs[name].state_class == "total_increasing", name


def test_navigator_17_status_enums() -> None:
    regs = _navigator_17_registers()

    assert regs["hp_operating_mode"].enum_options is not None
    for name in (
        "charging_pump_status",
        "heat_source_pump_status",
        "intermediate_circuit_pump_status",
        "isc_cold_storage_pump_status",
        "isc_recooling_pump_status",
    ):
        assert regs[name].enum_options == PUMP_STATUS_OPTIONS, name
    # Undocumented 1.x mode value sets stay numeric.
    for name in ("cascade_mode", "solar_mode", "smart_grid_status", "isc_mode"):
        assert regs[name].enum_options is None, name
    for idx in range(1, 5):
        assert regs[f"compressor_status_{idx}"].binary


def test_navigator_17_flow_block_is_contiguous() -> None:
    """The FLOAT block must cover 1000-1089 without word gaps.

    Batches only span exactly adjacent addresses; the official 1.x table
    places a FLOAT at every second address from 1000 through 1088.
    """
    regs = _navigator_17_registers()
    covered: set[int] = set()
    for reg in regs.values():
        if 1000 <= reg.address <= 1089:
            covered.update(range(reg.address, reg.address + reg.size))
    assert covered == set(range(1000, 1090))


def test_build_register_map_returns_1_7_map_only() -> None:
    model_info = navigator_17_model_info()
    built = build_register_map(model_info=model_info)

    assert set(built) == set(_navigator_17_registers())
    # Capability flags from a misdetection must not add shared-family
    # blocks; only has_pv opens the 1.x PV supplement.
    polluted = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_17,
        active_heating_circuits=["A", "B"],
        zone_modules=3,
        has_solar=True,
        has_isc=True,
        has_pv=False,
        has_cascade=True,
    )
    assert set(build_register_map(model_info=polluted)) == set(built)
    with_pv = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_17,
        active_heating_circuits=[],
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=True,
        has_cascade=False,
    )
    pv_map = build_register_map(model_info=with_pv)
    assert "pv_surplus" in pv_map
    assert set(pv_map) - set(built) == {
        "pv_surplus",
        "electric_heater_power",
        "pv_production",
        "house_consumption",
        "power_consumption_hp",
    }


def test_shared_family_maps_never_expose_1_7_only_registers() -> None:
    nav20 = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_20,
        active_heating_circuits=["A"],
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=False,
        has_cascade=False,
    )
    nav20_map = build_register_map(model_info=nav20)

    for name in ("hot_gas_temp", "thermal_power_total", "error_number"):
        assert name not in nav20_map
    # Shared names keep their shared-family addresses, not the 1.x ones.
    assert nav20_map["outdoor_temp"].address == 1000
    assert nav20_map["dhw_tapping_temp"].address == 1030
    assert nav20_map["hc_a_flow_temp"].address == 1350
    assert nav20_map["humidity_sensor"].address == 1392


def test_1_7_map_keeps_family_addresses() -> None:
    regs = _navigator_17_registers()

    assert regs["outdoor_temp"].address == 1000
    assert regs["hc_a_flow_temp"].address == 1016
    assert regs["humidity_sensor"].address == 1046


def test_register_registry_lookups_for_1_7() -> None:
    registry = get_register_registry(model_info=navigator_17_model_info())

    assert registry.get("hot_gas_temp") is not None
    assert registry.get("system_mode") is None
    assert registry.by_address(1046) is not None
    assert registry.by_address(1392) is None
    writable = registry.writable()
    assert set(writable) == set(EXPECTED_HOLDING)
    with_pv = get_register_registry(
        model_info=IdmModelInfo(
            model_name=MODEL_NAVIGATOR_17,
            active_heating_circuits=[],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=True,
            has_cascade=False,
        )
    )
    assert set(with_pv.writable()) == set(EXPECTED_HOLDING) | {
        "pv_surplus",
        "electric_heater_power",
        "pv_production",
        "house_consumption",
    }


def _detect_with_transport(transport: FakeModbusTransport) -> IdmModelInfo:
    client = IdmModbusClient("127.0.0.1", max_retries=1, transport=transport)
    return asyncio.run(client.detect_model())


def test_detect_model_classifies_navigator_17() -> None:
    info = _detect_with_transport(Navigator17Transport())

    assert info.model_name == MODEL_NAVIGATOR_17
    assert info.active_heating_circuits == []
    assert info.zone_modules == 0
    assert not info.has_solar
    assert not info.has_isc
    assert not info.has_pv
    assert not info.has_cascade
    assert info.features == set()


def test_detect_model_classifies_navigator_17_with_pv_supplement() -> None:
    """Updated 1.x firmware answers the PV block and 4122; it must still be a
    1.7 (with has_pv), not a Navigator 10."""
    transport = Navigator17Transport()
    for address in range(74, 90, 2):
        transport.input_registers[address] = 0
        transport.illegal_reads.discard(("input", address, 2))
    for address in (4120, 4122, 4126):
        transport.input_registers[address] = 0
        transport.illegal_reads.discard(("input", address, 2))

    info = _detect_with_transport(transport)

    assert info.model_name == MODEL_NAVIGATOR_17
    assert info.has_pv
    assert info.features == {"pv"}
    built = build_register_map(model_info=info)
    assert "pv_surplus" in built and "power_consumption_hp" in built


def test_detect_model_classifies_navigator_17_without_status_block() -> None:
    """A firmware that also rejects 1500+ still classifies as 1.7."""
    info = _detect_with_transport(Navigator17Transport(status_block_responds=False))

    assert info.model_name == MODEL_NAVIGATOR_17


def test_detect_model_does_not_leak_overlapping_probe_results() -> None:
    """Status words at 1500+ overlap the shared active-mode probes (1498+).

    The answers must not fake heating circuits into the 1.7 model info.
    """
    transport = Navigator17Transport()
    # Make the status words look like configured circuits (low byte != 255).
    for address in range(1500, 1505):
        transport.input_registers[address] = 2

    info = _detect_with_transport(transport)

    assert info.model_name == MODEL_NAVIGATOR_17
    assert info.active_heating_circuits == []


def _shared_family_transport(circuit_flow_words: list[int]) -> FakeModbusTransport:
    """Fake endpoint shaped like a shared-family (2.0) controller.

    The low block, heating-circuit block and active-mode registers answer;
    the Navigator-10-only blocks, optional blocks and zone slots are rejected
    with Modbus exception code 2, as a real 2.0 firmware does.
    """
    input_registers: dict[int, int] = {}
    for address in range(1000, 1099):
        input_registers[address] = 0
    input_registers.update(zip(range(1350, 1364), circuit_flow_words))
    for address in range(1498, 1505):
        input_registers[address] = 0xFFFF
    rejected: set[tuple[str, int, int]] = set()
    for address in (74, 1850, 1870, 4108, 4120, 4122, 4126):
        rejected.add(("input", address, 2))
    for address in (1147, 4001, 2000, 2065):
        rejected.add(("input", address, 1))
    return FakeModbusTransport(input_registers=input_registers, illegal_reads=rejected)


def test_detect_model_offline_device_cannot_classify_as_1_7() -> None:
    """A silent link must never yield a confident 1.7 classification."""

    class SilentTransport(FakeModbusTransport):
        async def _read(self, *args: Any, **kwargs: Any) -> list[int]:
            from idm_heatpump.exceptions import IdmTransportError

            raise IdmTransportError("no response")

    client = IdmModbusClient("127.0.0.1", max_retries=1, transport=SilentTransport())
    from idm_heatpump.exceptions import IdmConnectionError

    try:
        asyncio.run(client.detect_model())
    except IdmConnectionError:
        pass
    else:
        raise AssertionError("a silent transport must fail detection, not classify")


def test_detect_model_shared_family_with_sentinel_circuits_is_not_1_7() -> None:
    """A 2.0 whose circuits answer the -1.0 sentinel must not become 1.7."""
    transport = _shared_family_transport(_float_words(-1.0) * 7)

    info = _detect_with_transport(transport)

    # No circuit is active, but the heating-circuit block answers, so the
    # device cannot be the 1.x family; it falls back to Unknown like before.
    assert info.model_name == MODEL_UNKNOWN
    assert info.model_name != MODEL_NAVIGATOR_17


def test_detect_model_active_circuit_is_not_1_7() -> None:
    transport = _shared_family_transport(_float_words(35.0) * 7)

    info = _detect_with_transport(transport)

    assert info.model_name == MODEL_NAVIGATOR_20


def test_writes_follow_the_1_7_map() -> None:
    """Without the PV supplement every named register is read-only; with it,
    only the PV registers accept writes, exactly like the shared family."""
    client = IdmModbusClient("127.0.0.1")
    client.set_model_info(navigator_17_model_info())

    try:
        client.simulate_write("outdoor_temp", 20.0)
    except ValueError as err:
        assert "not available" in str(err) or "read-only" in str(err)
    else:
        raise AssertionError("outdoor_temp must not be writable on Navigator 1.7")

    with_pv = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_17,
        active_heating_circuits=[],
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=True,
        has_cascade=False,
    )
    client.set_model_info(with_pv)
    plan = client.simulate_write("pv_surplus", 2.5)
    assert plan.requested_value == 2.5
    try:
        client.simulate_write("outdoor_temp", 20.0)
    except ValueError:
        pass
    else:
        raise AssertionError("outdoor_temp must stay read-only with the PV supplement")


def test_get_register_uses_1_7_map() -> None:
    from idm_heatpump.registers import get_register

    reg = get_register("hot_gas_temp", model_info=navigator_17_model_info())
    assert reg is not None
    assert reg.address == 1044

    model_names = (MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_20, MODEL_NAVIGATOR_PRO)
    for model_name in model_names:
        info = IdmModelInfo(
            model_name=model_name,
            active_heating_circuits=["A"],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
        try:
            get_register("hot_gas_temp", model_info=info)
        except ValueError:
            continue
        raise AssertionError(f"hot_gas_temp must not resolve for {model_name}")


def test_1_7_holding_block_registers() -> None:
    """The official FC03/FC06 RW table of ma_de_812049 Rev.1, register by register.

    The table types the byte-sized values as UCHAR with a whole register
    reserved per parameter (2-register spacing); the FHEM capture read
    clean small values at word granularity, so they map as UINT16. The
    floats follow the map-wide low-word-first rule, which the official
    document states explicitly in its datatype section.
    """
    regs = _navigator_17_registers()

    system_mode = regs["system_mode_17"]
    assert system_mode.address == 2000
    assert system_mode.datatype is DataType.UINT16
    assert system_mode.register_type is RegisterType.HOLDING
    assert system_mode.writable is True
    assert system_mode.enum_options == SYSTEM_MODE_17_OPTIONS
    assert system_mode.eeprom_sensitive is True
    assert system_mode.supported_models == (MODEL_NAVIGATOR_17,)
    assert system_mode.last_verified == "2026-09-24"

    # Betriebsart Heizkreis A-G (HKA01-HKG01), one enum mode per circuit.
    for idx, letter in enumerate("abcdefg"):
        mode = regs[f"hc_{letter}_operating_mode"]
        assert mode.address == 2002 + idx * 2
        assert mode.datatype is DataType.UINT16
        assert mode.register_type is RegisterType.HOLDING
        assert mode.writable is True
        assert mode.enum_options == HC_OPERATING_MODE_17_OPTIONS
        assert mode.eeprom_sensitive is True

    # Room setpoints: Heizen Normal 15-30, Heizen ECO 10-25, Kühlen Normal
    # and ECO 15-30 (HKA04/HKA05/HKA50/HKA51).
    for idx, letter in enumerate("abcdefg"):
        normal = regs[f"hc_{letter}_room_setpoint_heat_normal"]
        assert normal.address == 2016 + idx * 2
        assert normal.datatype is DataType.FLOAT
        assert (normal.min_val, normal.max_val) == (15, 30)
        assert normal.unit == "°C"
        eco = regs[f"hc_{letter}_room_setpoint_heat_eco"]
        assert eco.address == 2030 + idx * 2
        assert (eco.min_val, eco.max_val) == (10, 25)
        cool = regs[f"hc_{letter}_room_setpoint_cool_normal"]
        assert cool.address == 2086 + idx * 2
        assert (cool.min_val, cool.max_val) == (15, 30)
        cool_eco = regs[f"hc_{letter}_room_setpoint_cool_eco"]
        assert cool_eco.address == 2100 + idx * 2
        assert (cool_eco.min_val, cool_eco.max_val) == (15, 30)

    # Heizkurve (HKA10) 0.1-3.5, controller precision 0.1 like the shared family.
    curve = regs["hc_a_heating_curve"]
    assert curve.address == 2044
    assert curve.datatype is DataType.FLOAT
    assert (curve.min_val, curve.max_val) == (0.1, 3.5)
    assert curve.step == 0.1
    assert curve.unit is None

    # Word-sized per-circuit limits and flow setpoints (HKA08/HKA03/HKA58/HKA53)
    # plus the shared family's names: identical official ranges.
    for name, address, min_val, max_val in [
        ("hc_a_heating_limit", 2058, 0, 50),
        ("hc_g_heating_limit", 2070, 0, 50),
        ("hc_a_setpoint_flow_constant", 2072, 20, 90),
        ("hc_g_setpoint_flow_constant", 2084, 20, 90),
        ("hc_a_cooling_limit", 2114, 0, 36),
        ("hc_g_cooling_limit", 2126, 0, 36),
        ("hc_a_setpoint_flow_cooling", 2128, 8, 30),
        ("hc_g_setpoint_flow_cooling", 2140, 8, 30),
        ("external_demand_temp_heating", 2142, 20, 65),
        ("external_demand_temp_cooling", 2144, 10, 25),
        ("dhw_setpoint", 2152, 35, 60),
    ]:
        reg = regs[name]
        assert reg.address == address, name
        assert reg.datatype is DataType.UINT16, name
        assert reg.register_type is RegisterType.HOLDING, name
        assert (reg.min_val, reg.max_val) == (min_val, max_val), name
        assert reg.unit == "°C", name
        assert reg.eeprom_sensitive is True, name

    # Bivalenzpunkte (BV002/BV003): signed words, -20..20 °C.
    for name, address in (("bivalence_point_1_17", 2146), ("bivalence_point_2_17", 2148)):
        reg = regs[name]
        assert reg.address == address, name
        assert reg.datatype is DataType.INT16, name
        assert reg.writable is True, name
        assert (reg.min_val, reg.max_val) == (-20, 20), name

    # Betriebsart Solar (SC002) with its own enum table.
    solar_mode = regs["solar_operating_mode_17"]
    assert solar_mode.address == 2150
    assert solar_mode.enum_options == SOLAR_OPERATING_MODE_17_OPTIONS
    assert solar_mode.eeprom_sensitive is True


def test_1_7_holding_enums_match_the_verified_mapping() -> None:
    """The value sets differ from the shared family on purpose."""
    assert SYSTEM_MODE_17_OPTIONS == {
        0: "Standby",
        1: "Automatic",
        2: "Hot Water",
        3: "Hot Water Once",
    }
    assert HC_OPERATING_MODE_17_OPTIONS == {
        0: "Off",
        1: "Time Program",
        2: "Normal",
        3: "ECO",
        4: "Heating Only",
    }
    assert SOLAR_OPERATING_MODE_17_OPTIONS == {
        0: "Automatic",
        1: "Domestic Water",
        2: "Heat Storage",
        3: "Domestic Water + Heat Storage",
        4: "Heat Source / Pool",
    }


def test_1_7_holding_modes_accept_writes() -> None:
    """The official holding table is the writable 1.x control surface."""
    client = IdmModbusClient("127.0.0.1")
    client.set_model_info(
        IdmModelInfo(
            model_name=MODEL_NAVIGATOR_17,
            active_heating_circuits=[],
            zone_modules=0,
            has_solar=False,
            has_isc=False,
            has_pv=False,
            has_cascade=False,
        )
    )

    plan = client.simulate_write("system_mode_17", 3)
    assert plan.requested_value == 3
    plan = client.simulate_write("hc_a_operating_mode", 2)
    assert plan.requested_value == 2
    plan = client.simulate_write("hc_g_operating_mode", 4)
    assert plan.requested_value == 4
    plan = client.simulate_write("hc_a_room_setpoint_heat_normal", 21.5)
    assert plan.requested_value == 21.5
    plan = client.simulate_write("hc_g_heating_curve", 1.2)
    assert plan.requested_value == 1.2
    plan = client.simulate_write("hc_a_heating_limit", 17)
    assert plan.requested_value == 17
    plan = client.simulate_write("dhw_setpoint", 48)
    assert plan.requested_value == 48
    # Signed bivalence words accept negative values within -20..20.
    plan = client.simulate_write("bivalence_point_1_17", -10)
    assert plan.requested_value == -10
    plan = client.simulate_write("solar_operating_mode_17", 4)
    assert plan.requested_value == 4

    # Out-of-range writes are rejected by the API's write safety.
    try:
        client.simulate_write("hc_a_room_setpoint_heat_normal", 31.0)
    except ValueError:
        pass
    else:
        raise AssertionError("room setpoint above the documented range must be rejected")
    try:
        client.simulate_write("bivalence_point_1_17", 21)
    except ValueError:
        pass
    else:
        raise AssertionError("bivalence point above the documented range must be rejected")
