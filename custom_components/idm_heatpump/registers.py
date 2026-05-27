"""Comprehensive register definitions for IDM Navigator heat pumps.

Register map source: iDM Navigatorregelung 2.0 Modbus TCP documentation.
Supports Navigator 2.0 and Navigator Pro with all optional subsystems.

FLOAT encoding: IEEE 754, 32-bit, 2 registers, Low word first (Reg_L then Reg_H).
"""

from __future__ import annotations

from .client import DataType, IdmModelInfo, RegisterDef, RegisterType
from .const import (
    ACTIVE_HC_MODE_OPTIONS,
    BIVALENCE_STATE_OPTIONS,
    CIRCUIT_MODE_OPTIONS,
    HP_OPERATING_MODE_OPTIONS,
    ISC_MODE_OPTIONS,
    ROOM_MODE_OPTIONS,
    SMART_GRID_OPTIONS,
    SOLAR_MODE_OPTIONS,
    SYSTEM_MODE_OPTIONS,
    ZONE_MODULE_MODE_OPTIONS,
)

CORE_REGISTERS: dict[str, RegisterDef] = {
    "outdoor_temp": RegisterDef(
        address=1000,
        datatype=DataType.FLOAT,
        name="outdoor_temp",
        unit="°C",
    ),
    "system_mode": RegisterDef(
        address=1005,
        datatype=DataType.UCHAR,
        name="system_mode",
        writable=True,
        enum_options=SYSTEM_MODE_OPTIONS,
        eeprom_sensitive=True,
    ),
    "storage_temp": RegisterDef(
        address=1008,
        datatype=DataType.FLOAT,
        name="storage_temp",
        unit="°C",
    ),
    "heatpump_status": RegisterDef(
        address=1090,
        datatype=DataType.UCHAR,
        name="heatpump_status",
        enum_options=HP_OPERATING_MODE_OPTIONS,
    ),
    "error_acknowledge": RegisterDef(
        address=1999,
        datatype=DataType.UCHAR,
        name="error_acknowledge",
        writable=True,
    ),
}


def _system_registers() -> dict[str, RegisterDef]:
    return {
        "outdoor_temp": RegisterDef(
            address=1000, datatype=DataType.FLOAT, name="outdoor_temp", unit="°C"
        ),
        "outdoor_temp_avg": RegisterDef(
            address=1002,
            datatype=DataType.FLOAT,
            name="outdoor_temp_avg",
            unit="°C",
        ),
        "internal_message": RegisterDef(
            address=1004, datatype=DataType.UCHAR, name="internal_message"
        ),
        "system_mode": RegisterDef(
            address=1005,
            datatype=DataType.UCHAR,
            name="system_mode",
            writable=True,
            min_val=0,
            max_val=5,
            enum_options=SYSTEM_MODE_OPTIONS,
            eeprom_sensitive=True,
        ),
        "smart_grid_status": RegisterDef(
            address=1006,
            datatype=DataType.UCHAR,
            name="smart_grid_status",
            enum_options=SMART_GRID_OPTIONS,
        ),
        "storage_temp": RegisterDef(
            address=1008, datatype=DataType.FLOAT, name="storage_temp", unit="°C"
        ),
        "cold_storage_temp": RegisterDef(
            address=1010,
            datatype=DataType.FLOAT,
            name="cold_storage_temp",
            unit="°C",
        ),
        "dhw_temp_bottom": RegisterDef(
            address=1012,
            datatype=DataType.FLOAT,
            name="dhw_temp_bottom",
            unit="°C",
        ),
        "dhw_temp_top": RegisterDef(
            address=1014,
            datatype=DataType.FLOAT,
            name="dhw_temp_top",
            unit="°C",
        ),
        "dhw_tapping_temp": RegisterDef(
            address=1030,
            datatype=DataType.FLOAT,
            name="dhw_tapping_temp",
            unit="°C",
        ),
        "dhw_setpoint": RegisterDef(
            address=1032,
            datatype=DataType.UCHAR,
            name="dhw_setpoint",
            unit="°C",
            writable=True,
            min_val=35,
            max_val=95,
            eeprom_sensitive=True,
        ),
        "dhw_charge_on_temp": RegisterDef(
            address=1033,
            datatype=DataType.UCHAR,
            name="dhw_charge_on_temp",
            unit="°C",
            writable=True,
            min_val=30,
            max_val=50,
            eeprom_sensitive=True,
        ),
        "dhw_charge_off_temp": RegisterDef(
            address=1034,
            datatype=DataType.UCHAR,
            name="dhw_charge_off_temp",
            unit="°C",
            writable=True,
            min_val=46,
            max_val=53,
            eeprom_sensitive=True,
        ),
        "current_electricity_price": RegisterDef(
            address=1048,
            datatype=DataType.FLOAT,
            name="current_electricity_price",
        ),
        "hp_flow_temp": RegisterDef(
            address=1050, datatype=DataType.FLOAT, name="hp_flow_temp", unit="°C"
        ),
        "hp_return_temp": RegisterDef(
            address=1052, datatype=DataType.FLOAT, name="hp_return_temp", unit="°C"
        ),
        "hgl_flow_temp": RegisterDef(
            address=1054, datatype=DataType.FLOAT, name="hgl_flow_temp", unit="°C"
        ),
        "heat_source_inlet_temp": RegisterDef(
            address=1056,
            datatype=DataType.FLOAT,
            name="heat_source_inlet_temp",
            unit="°C",
        ),
        "heat_source_outlet_temp": RegisterDef(
            address=1058,
            datatype=DataType.FLOAT,
            name="heat_source_outlet_temp",
            unit="°C",
        ),
        "air_intake_temp": RegisterDef(
            address=1060,
            datatype=DataType.FLOAT,
            name="air_intake_temp",
            unit="°C",
        ),
        "air_heat_exchanger_temp": RegisterDef(
            address=1062,
            datatype=DataType.FLOAT,
            name="air_heat_exchanger_temp",
            unit="°C",
        ),
        "air_intake_temp_2": RegisterDef(
            address=1064,
            datatype=DataType.FLOAT,
            name="air_intake_temp_2",
            unit="°C",
        ),
        "charging_sensor_temp": RegisterDef(
            address=1066,
            datatype=DataType.FLOAT,
            name="charging_sensor_temp",
            unit="°C",
        ),
    }


def _hp_status_registers() -> dict[str, RegisterDef]:
    return {
        "hp_operating_mode": RegisterDef(
            address=1090,
            datatype=DataType.UCHAR,
            name="hp_operating_mode",
            enum_options=HP_OPERATING_MODE_OPTIONS,
        ),
        "heating_demand": RegisterDef(
            address=1091, datatype=DataType.UCHAR, name="heating_demand"
        ),
        "cooling_demand": RegisterDef(
            address=1092, datatype=DataType.UCHAR, name="cooling_demand"
        ),
        "dhw_demand": RegisterDef(
            address=1093, datatype=DataType.UCHAR, name="dhw_demand"
        ),
        "evu_lock": RegisterDef(
            address=1098, datatype=DataType.UCHAR, name="evu_lock"
        ),
        "hp_sum_alarm": RegisterDef(
            address=1099, datatype=DataType.UCHAR, name="hp_sum_alarm"
        ),
        "compressor_status_1": RegisterDef(
            address=1100, datatype=DataType.UCHAR, name="compressor_status_1"
        ),
        "compressor_status_2": RegisterDef(
            address=1101, datatype=DataType.UCHAR, name="compressor_status_2"
        ),
        "compressor_status_3": RegisterDef(
            address=1102, datatype=DataType.UCHAR, name="compressor_status_3"
        ),
        "compressor_status_4": RegisterDef(
            address=1103, datatype=DataType.UCHAR, name="compressor_status_4"
        ),
        "charging_pump_status": RegisterDef(
            address=1104,
            datatype=DataType.UINT16,
            name="charging_pump_status",
            unit="%",
        ),
        "brine_pump_status": RegisterDef(
            address=1105,
            datatype=DataType.UINT16,
            name="brine_pump_status",
            unit="%",
        ),
        "heat_source_pump_status": RegisterDef(
            address=1106,
            datatype=DataType.UINT16,
            name="heat_source_pump_status",
        ),
        "isc_cold_storage_pump_status": RegisterDef(
            address=1108,
            datatype=DataType.UINT16,
            name="isc_cold_storage_pump_status",
            unit="%",
        ),
        "isc_recooling_pump_status": RegisterDef(
            address=1109,
            datatype=DataType.UINT16,
            name="isc_recooling_pump_status",
            unit="%",
        ),
        "valve_hc_heat_cool": RegisterDef(
            address=1110,
            datatype=DataType.UINT16,
            name="valve_hc_heat_cool",
        ),
        "valve_storage_heat_cool": RegisterDef(
            address=1111,
            datatype=DataType.UINT16,
            name="valve_storage_heat_cool",
        ),
        "valve_heat_dhw": RegisterDef(
            address=1112,
            datatype=DataType.UINT16,
            name="valve_heat_dhw",
        ),
        "valve_heat_source_heat_cool": RegisterDef(
            address=1113,
            datatype=DataType.UINT16,
            name="valve_heat_source_heat_cool",
        ),
        "valve_solar_heat_dhw": RegisterDef(
            address=1114,
            datatype=DataType.UINT16,
            name="valve_solar_heat_dhw",
        ),
        "valve_solar_storage_heat_source": RegisterDef(
            address=1115,
            datatype=DataType.UINT16,
            name="valve_solar_storage_heat_source",
        ),
        "valve_isc_heat_source_cold_storage": RegisterDef(
            address=1116,
            datatype=DataType.UINT16,
            name="valve_isc_heat_source_cold_storage",
        ),
        "valve_isc_storage_bypass": RegisterDef(
            address=1117,
            datatype=DataType.UINT16,
            name="valve_isc_storage_bypass",
        ),
        "circulation_pump": RegisterDef(
            address=1118,
            datatype=DataType.UINT16,
            name="circulation_pump",
        ),
        "bivalence_point_1_2nd_gen": RegisterDef(
            address=1120,
            datatype=DataType.INT16,
            name="bivalence_point_1_2nd_gen",
            unit="°C",
            writable=True,
            eeprom_sensitive=True,
        ),
        "bivalence_point_2_2nd_gen": RegisterDef(
            address=1121,
            datatype=DataType.INT16,
            name="bivalence_point_2_2nd_gen",
            unit="°C",
            writable=True,
            eeprom_sensitive=True,
        ),
        "bivalence_point_1_3rd_gen": RegisterDef(
            address=1122,
            datatype=DataType.INT16,
            name="bivalence_point_1_3rd_gen",
            unit="°C",
            writable=True,
            eeprom_sensitive=True,
        ),
        "bivalence_point_2_3rd_gen": RegisterDef(
            address=1123,
            datatype=DataType.INT16,
            name="bivalence_point_2_3rd_gen",
            unit="°C",
            writable=True,
            eeprom_sensitive=True,
        ),
        "bivalence_state": RegisterDef(
            address=1124,
            datatype=DataType.UCHAR,
            name="bivalence_state",
            enum_options=BIVALENCE_STATE_OPTIONS,
        ),
        "cascade_available_heating": RegisterDef(
            address=1147,
            datatype=DataType.UCHAR,
            name="cascade_available_heating",
        ),
        "cascade_available_cooling": RegisterDef(
            address=1148,
            datatype=DataType.UCHAR,
            name="cascade_available_cooling",
        ),
        "cascade_available_dhw": RegisterDef(
            address=1149,
            datatype=DataType.UCHAR,
            name="cascade_available_dhw",
        ),
        "cascade_running_heating": RegisterDef(
            address=1150,
            datatype=DataType.UCHAR,
            name="cascade_running_heating",
        ),
        "cascade_running_cooling": RegisterDef(
            address=1151,
            datatype=DataType.UCHAR,
            name="cascade_running_cooling",
        ),
        "cascade_running_dhw": RegisterDef(
            address=1152,
            datatype=DataType.UCHAR,
            name="cascade_running_dhw",
        ),
    }


def _cascade_registers() -> dict[str, RegisterDef]:
    return {
        "cascade_req_heating_temp": RegisterDef(
            address=1200,
            datatype=DataType.FLOAT,
            name="cascade_req_heating_temp",
            unit="°C",
        ),
        "cascade_req_cooling_temp": RegisterDef(
            address=1202,
            datatype=DataType.FLOAT,
            name="cascade_req_cooling_temp",
            unit="°C",
        ),
        "cascade_req_dhw_temp": RegisterDef(
            address=1204,
            datatype=DataType.FLOAT,
            name="cascade_req_dhw_temp",
            unit="°C",
        ),
        "cascade_avg_flow_heating": RegisterDef(
            address=1206,
            datatype=DataType.FLOAT,
            name="cascade_avg_flow_heating",
            unit="°C",
        ),
        "cascade_avg_flow_cooling": RegisterDef(
            address=1208,
            datatype=DataType.FLOAT,
            name="cascade_avg_flow_cooling",
            unit="°C",
        ),
        "cascade_avg_flow_dhw": RegisterDef(
            address=1210,
            datatype=DataType.FLOAT,
            name="cascade_avg_flow_dhw",
            unit="°C",
        ),
        "cascade_min_power_heating": RegisterDef(
            address=1220,
            datatype=DataType.UCHAR,
            name="cascade_min_power_heating",
            unit="%",
            writable=True,
            min_val=0,
            max_val=100,
        ),
        "cascade_max_power_heating": RegisterDef(
            address=1221,
            datatype=DataType.UCHAR,
            name="cascade_max_power_heating",
            unit="%",
            writable=True,
            min_val=0,
            max_val=100,
        ),
        "cascade_min_power_cooling": RegisterDef(
            address=1222,
            datatype=DataType.UCHAR,
            name="cascade_min_power_cooling",
            unit="%",
            writable=True,
            min_val=0,
            max_val=100,
        ),
        "cascade_max_power_cooling": RegisterDef(
            address=1223,
            datatype=DataType.UCHAR,
            name="cascade_max_power_cooling",
            unit="%",
            writable=True,
            min_val=0,
            max_val=100,
        ),
        "cascade_min_power_dhw": RegisterDef(
            address=1224,
            datatype=DataType.UCHAR,
            name="cascade_min_power_dhw",
            unit="%",
            writable=True,
            min_val=0,
            max_val=100,
        ),
        "cascade_max_power_dhw": RegisterDef(
            address=1225,
            datatype=DataType.UCHAR,
            name="cascade_max_power_dhw",
            unit="%",
            writable=True,
            min_val=0,
            max_val=100,
        ),
    }


def _energy_registers() -> dict[str, RegisterDef]:
    return {
        "energy_heating": RegisterDef(
            address=1748,
            datatype=DataType.FLOAT,
            name="energy_heating",
            unit="kWh",
        ),
        "energy_total": RegisterDef(
            address=1750,
            datatype=DataType.FLOAT,
            name="energy_total",
            unit="kWh",
        ),
        "energy_cooling": RegisterDef(
            address=1752,
            datatype=DataType.FLOAT,
            name="energy_cooling",
            unit="kWh",
        ),
        "energy_dhw": RegisterDef(
            address=1754,
            datatype=DataType.FLOAT,
            name="energy_dhw",
            unit="kWh",
        ),
        "energy_defrost": RegisterDef(
            address=1756,
            datatype=DataType.FLOAT,
            name="energy_defrost",
            unit="kWh",
        ),
        "energy_passive_cooling": RegisterDef(
            address=1758,
            datatype=DataType.FLOAT,
            name="energy_passive_cooling",
            unit="kWh",
        ),
        "energy_solar": RegisterDef(
            address=1760,
            datatype=DataType.FLOAT,
            name="energy_solar",
            unit="kWh",
        ),
        "energy_electric_heater": RegisterDef(
            address=1762,
            datatype=DataType.FLOAT,
            name="energy_electric_heater",
            unit="kWh",
        ),
        "current_power": RegisterDef(
            address=1790,
            datatype=DataType.FLOAT,
            name="current_power",
            unit="kW",
        ),
        "current_power_solar": RegisterDef(
            address=1792,
            datatype=DataType.FLOAT,
            name="current_power_solar",
            unit="kW",
        ),
        "power_consumption_hp": RegisterDef(
            address=4122,
            datatype=DataType.FLOAT,
            name="power_consumption_hp",
            unit="kW",
        ),
        "thermal_power_flow_sensor": RegisterDef(
            address=4126,
            datatype=DataType.FLOAT,
            name="thermal_power_flow_sensor",
            unit="kW",
        ),
        "total_heat_energy": RegisterDef(
            address=4128,
            datatype=DataType.FLOAT,
            name="total_heat_energy",
            unit="kWh",
        ),
    }


def _solar_registers() -> dict[str, RegisterDef]:
    return {
        "solar_collector_temp": RegisterDef(
            address=1850,
            datatype=DataType.FLOAT,
            name="solar_collector_temp",
            unit="°C",
        ),
        "solar_return_temp": RegisterDef(
            address=1852,
            datatype=DataType.FLOAT,
            name="solar_return_temp",
            unit="°C",
        ),
        "solar_charging_temp": RegisterDef(
            address=1854,
            datatype=DataType.FLOAT,
            name="solar_charging_temp",
            unit="°C",
        ),
        "solar_mode": RegisterDef(
            address=1856,
            datatype=DataType.UCHAR,
            name="solar_mode",
            writable=True,
            min_val=0,
            max_val=4,
            enum_options=SOLAR_MODE_OPTIONS,
            eeprom_sensitive=True,
        ),
        "solar_wq_pool_temp": RegisterDef(
            address=1857,
            datatype=DataType.FLOAT,
            name="solar_wq_pool_temp",
            unit="°C",
        ),
    }


def _isc_registers() -> dict[str, RegisterDef]:
    return {
        "isc_charging_temp_cooling": RegisterDef(
            address=1870,
            datatype=DataType.FLOAT,
            name="isc_charging_temp_cooling",
            unit="°C",
        ),
        "isc_recooling_temp": RegisterDef(
            address=1872,
            datatype=DataType.FLOAT,
            name="isc_recooling_temp",
            unit="°C",
        ),
        "isc_mode": RegisterDef(
            address=1874,
            datatype=DataType.UCHAR,
            name="isc_mode",
            enum_options=ISC_MODE_OPTIONS,
        ),
    }


def _pv_registers() -> dict[str, RegisterDef]:
    return {
        "pv_surplus": RegisterDef(
            address=74,
            datatype=DataType.FLOAT,
            name="pv_surplus",
            unit="kW",
        ),
        "electric_heater_power": RegisterDef(
            address=76,
            datatype=DataType.FLOAT,
            name="electric_heater_power",
            unit="kW",
        ),
        "pv_production": RegisterDef(
            address=78,
            datatype=DataType.FLOAT,
            name="pv_production",
            unit="kW",
        ),
        "house_consumption": RegisterDef(
            address=82,
            datatype=DataType.FLOAT,
            name="house_consumption",
            unit="kW",
        ),
        "battery_discharge": RegisterDef(
            address=84,
            datatype=DataType.FLOAT,
            name="battery_discharge",
            unit="kW",
        ),
        "battery_soc": RegisterDef(
            address=86,
            datatype=DataType.UINT16,
            name="battery_soc",
            unit="%",
        ),
    }


def _glt_registers() -> dict[str, RegisterDef]:
    return {
        "ext_outdoor_temp": RegisterDef(
            address=1690,
            datatype=DataType.FLOAT,
            name="ext_outdoor_temp",
            unit="°C",
            writable=True,
        ),
        "ext_humidity": RegisterDef(
            address=1692,
            datatype=DataType.FLOAT,
            name="ext_humidity",
            unit="%rF",
            writable=True,
            min_val=0,
            max_val=100,
        ),
        "ext_demand_temp_heating": RegisterDef(
            address=1694,
            datatype=DataType.UCHAR,
            name="ext_demand_temp_heating",
            unit="°C",
            writable=True,
            min_val=20,
            max_val=65,
            eeprom_sensitive=True,
        ),
        "ext_demand_temp_cooling": RegisterDef(
            address=1695,
            datatype=DataType.UCHAR,
            name="ext_demand_temp_cooling",
            unit="°C",
            writable=True,
            min_val=10,
            max_val=25,
            eeprom_sensitive=True,
        ),
        "glt_temp_demand_heating": RegisterDef(
            address=1696,
            datatype=DataType.FLOAT,
            name="glt_temp_demand_heating",
            unit="°C",
            writable=True,
            cyclic_required=True,
        ),
        "glt_temp_demand_cooling": RegisterDef(
            address=1698,
            datatype=DataType.FLOAT,
            name="glt_temp_demand_cooling",
            unit="°C",
            writable=True,
            cyclic_required=True,
        ),
        "demand_heating": RegisterDef(
            address=1710,
            datatype=DataType.BOOL,
            name="demand_heating",
            writable=True,
        ),
        "demand_cooling": RegisterDef(
            address=1711,
            datatype=DataType.BOOL,
            name="demand_cooling",
            writable=True,
        ),
        "demand_dhw_charging": RegisterDef(
            address=1712,
            datatype=DataType.BOOL,
            name="demand_dhw_charging",
            writable=True,
        ),
        "demand_onetime_dhw": RegisterDef(
            address=1713,
            datatype=DataType.BOOL,
            name="demand_onetime_dhw",
            writable=True,
        ),
        "glt_heat_storage_temp": RegisterDef(
            address=1716,
            datatype=DataType.FLOAT,
            name="glt_heat_storage_temp",
            unit="°C",
            writable=True,
        ),
        "glt_cold_storage_temp": RegisterDef(
            address=1718,
            datatype=DataType.FLOAT,
            name="glt_cold_storage_temp",
            unit="°C",
            writable=True,
        ),
        "glt_dhw_temp_bottom": RegisterDef(
            address=1720,
            datatype=DataType.FLOAT,
            name="glt_dhw_temp_bottom",
            unit="°C",
            writable=True,
        ),
        "glt_dhw_temp_top": RegisterDef(
            address=1722,
            datatype=DataType.FLOAT,
            name="glt_dhw_temp_top",
            unit="°C",
            writable=True,
        ),
    }


def get_heating_circuit_registers(
    circuit_letter: str,
) -> dict[str, RegisterDef]:
    """Return all registers for a specific heating circuit (A-G).

    Circuit index: A=0, B=1, C=2, D=3, E=4, F=5, G=6
    """
    idx = ord(circuit_letter.upper()) - ord("A")
    if not (0 <= idx <= 6):
        raise ValueError(f"Invalid circuit letter: {circuit_letter}")
    c = circuit_letter.lower()
    regs: dict[str, RegisterDef] = {}

    regs[f"hc_{c}_flow_temp"] = RegisterDef(
        address=1350 + idx * 2,
        datatype=DataType.FLOAT,
        name=f"hc_{c}_flow_temp",
        unit="°C",
    )
    regs[f"hc_{c}_room_temp"] = RegisterDef(
        address=1364 + idx * 2,
        datatype=DataType.FLOAT,
        name=f"hc_{c}_room_temp",
        unit="°C",
    )
    regs[f"hc_{c}_setpoint_flow_temp"] = RegisterDef(
        address=1378 + idx * 2,
        datatype=DataType.FLOAT,
        name=f"hc_{c}_setpoint_flow_temp",
        unit="°C",
    )
    regs[f"hc_{c}_mode"] = RegisterDef(
        address=1393 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_mode",
        writable=True,
        min_val=0,
        max_val=5,
        enum_options=CIRCUIT_MODE_OPTIONS,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_room_setpoint_heat_normal"] = RegisterDef(
        address=1401 + idx * 2,
        datatype=DataType.FLOAT,
        name=f"hc_{c}_room_setpoint_heat_normal",
        unit="°C",
        writable=True,
        min_val=15,
        max_val=30,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_room_setpoint_heat_eco"] = RegisterDef(
        address=1415 + idx * 2,
        datatype=DataType.FLOAT,
        name=f"hc_{c}_room_setpoint_heat_eco",
        unit="°C",
        writable=True,
        min_val=10,
        max_val=25,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_heating_curve"] = RegisterDef(
        address=1429 + idx * 2,
        datatype=DataType.FLOAT,
        name=f"hc_{c}_heating_curve",
        writable=True,
        min_val=0.1,
        max_val=3.5,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_heating_limit"] = RegisterDef(
        address=1442 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_heating_limit",
        unit="°C",
        writable=True,
        min_val=0,
        max_val=50,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_setpoint_flow_constant"] = RegisterDef(
        address=1449 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_setpoint_flow_constant",
        unit="°C",
        writable=True,
        min_val=20,
        max_val=90,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_room_setpoint_cool_normal"] = RegisterDef(
        address=1457 + idx * 2,
        datatype=DataType.FLOAT,
        name=f"hc_{c}_room_setpoint_cool_normal",
        unit="°C",
        writable=True,
        min_val=15,
        max_val=30,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_room_setpoint_cool_eco"] = RegisterDef(
        address=1471 + idx * 2,
        datatype=DataType.FLOAT,
        name=f"hc_{c}_room_setpoint_cool_eco",
        unit="°C",
        writable=True,
        min_val=15,
        max_val=30,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_cooling_limit"] = RegisterDef(
        address=1484 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_cooling_limit",
        unit="°C",
        writable=True,
        min_val=0,
        max_val=36,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_setpoint_flow_cooling"] = RegisterDef(
        address=1491 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_setpoint_flow_cooling",
        unit="°C",
        writable=True,
        min_val=8,
        max_val=30,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_active_mode"] = RegisterDef(
        address=1498 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_active_mode",
        enum_options=ACTIVE_HC_MODE_OPTIONS,
    )
    regs[f"hc_{c}_parallel_shift"] = RegisterDef(
        address=1505 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_parallel_shift",
        unit="°C",
        writable=True,
        min_val=0,
        max_val=30,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_ext_room_temp"] = RegisterDef(
        address=1650 + idx * 2,
        datatype=DataType.FLOAT,
        name=f"hc_{c}_ext_room_temp",
        unit="°C",
        writable=True,
        min_val=15,
        max_val=30,
    )

    return regs


def get_zone_module_registers(
    zone_index: int,
    room_count: int = 8,
) -> dict[str, RegisterDef]:
    """Return all registers for a specific zone module (1-10).

    Each zone module supports up to 8 rooms.
    Zone module base addresses: 2000, 2065, 2130, 2195, 2260, 2325, 2390, 2455, 2520, 2585
    """
    if not (1 <= zone_index <= 10):
        raise ValueError(f"Zone index must be 1-10, got {zone_index}")
    if not (1 <= room_count <= 8):
        raise ValueError(f"Room count must be 1-8, got {room_count}")

    base = 2000 + (zone_index - 1) * 65
    z = zone_index
    regs: dict[str, RegisterDef] = {}

    regs[f"zm{z}_mode_heat_cool"] = RegisterDef(
        address=base,
        datatype=DataType.UCHAR,
        name=f"zm{z}_mode_heat_cool",
        enum_options=ZONE_MODULE_MODE_OPTIONS,
    )
    regs[f"zm{z}_dehumidification"] = RegisterDef(
        address=base + 1,
        datatype=DataType.UCHAR,
        name=f"zm{z}_dehumidification",
    )

    for room in range(1, room_count + 1):
        room_base = base + 2 + (room - 1) * 8
        regs[f"zm{z}_room{room}_temp"] = RegisterDef(
            address=room_base,
            datatype=DataType.FLOAT,
            name=f"zm{z}_room{room}_temp",
            unit="°C",
        )
        regs[f"zm{z}_room{room}_setpoint"] = RegisterDef(
            address=room_base + 2,
            datatype=DataType.FLOAT,
            name=f"zm{z}_room{room}_setpoint",
            unit="°C",
            writable=True,
        )
        regs[f"zm{z}_room{room}_humidity"] = RegisterDef(
            address=room_base + 4,
            datatype=DataType.UCHAR,
            name=f"zm{z}_room{room}_humidity",
            unit="%rF",
        )
        regs[f"zm{z}_room{room}_mode"] = RegisterDef(
            address=room_base + 5,
            datatype=DataType.UCHAR,
            name=f"zm{z}_room{room}_mode",
            writable=True,
            enum_options=ROOM_MODE_OPTIONS,
        )
        regs[f"zm{z}_room{room}_relay"] = RegisterDef(
            address=room_base + 6,
            datatype=DataType.UCHAR,
            name=f"zm{z}_room{room}_relay",
        )

    return regs


def get_detection_registers() -> list[RegisterDef]:
    """Return registers used for model/capability detection probing."""
    regs: list[RegisterDef] = [
        RegisterDef(
            address=1000,
            datatype=DataType.FLOAT,
            name="detect_outdoor_temp",
        ),
    ]
    for i in range(7):
        regs.append(
            RegisterDef(
                address=1350 + i * 2,
                datatype=DataType.FLOAT,
                name=f"detect_hc_{chr(65 + i).lower()}_flow_temp",
            )
        )
    regs.extend(
        [
            RegisterDef(
                address=1850,
                datatype=DataType.FLOAT,
                name="detect_solar",
            ),
            RegisterDef(
                address=1870,
                datatype=DataType.FLOAT,
                name="detect_isc",
            ),
            RegisterDef(
                address=74,
                datatype=DataType.FLOAT,
                name="detect_pv",
            ),
            RegisterDef(
                address=1147,
                datatype=DataType.UCHAR,
                name="detect_cascade",
            ),
        ]
    )
    for zm in range(10):
        regs.append(
            RegisterDef(
                address=2000 + zm * 65,
                datatype=DataType.UCHAR,
                name=f"detect_zm{zm + 1}",
            )
        )
    return regs


def build_register_map(
    model_info: IdmModelInfo | None = None,
    circuits: list[str] | None = None,
    zone_modules: int = 0,
    rooms_per_zone: int = 8,
) -> dict[str, RegisterDef]:
    """Build a complete register map based on detected model or manual config.

    Args:
        model_info: Auto-detected model info (takes priority over manual params).
        circuits: Manual list of active circuit letters (e.g. ["A", "B"]).
        zone_modules: Manual number of zone modules (0-10).
        rooms_per_zone: Number of rooms per zone module (1-8).

    Returns:
        Complete dict of register definitions keyed by name.
    """
    all_regs: dict[str, RegisterDef] = {}

    all_regs.update(_system_registers())
    all_regs.update(_hp_status_registers())
    all_regs.update(_energy_registers())

    active_circuits: list[str]
    num_zones: int

    if model_info is not None:
        active_circuits = model_info.active_heating_circuits
        num_zones = model_info.zone_modules

        if model_info.has_cascade:
            all_regs.update(_cascade_registers())
        if model_info.has_solar:
            all_regs.update(_solar_registers())
        if model_info.has_isc:
            all_regs.update(_isc_registers())
        if model_info.has_pv:
            all_regs.update(_pv_registers())
    else:
        active_circuits = circuits or list("ABCDEFG")
        num_zones = zone_modules

    for letter in active_circuits:
        try:
            all_regs.update(get_heating_circuit_registers(letter))
        except ValueError:
            continue

    for z in range(1, num_zones + 1):
        try:
            all_regs.update(get_zone_module_registers(z, rooms_per_zone))
        except ValueError:
            continue

    all_regs.update(_glt_registers())

    all_regs["error_acknowledge"] = RegisterDef(
        address=1999,
        datatype=DataType.UCHAR,
        name="error_acknowledge",
        writable=True,
    )
    all_regs["humidity_sensor"] = RegisterDef(
        address=1392,
        datatype=DataType.FLOAT,
        name="humidity_sensor",
        unit="%rF",
    )

    return all_regs


def get_register(name: str) -> RegisterDef:
    """Return a register definition by canonical name."""
    if name not in CORE_REGISTERS:
        raise ValueError(f"Register '{name}' not found in core registers.")
    return CORE_REGISTERS[name]


def get_all_registers() -> list[RegisterDef]:
    """Return all core register definitions."""
    return list(CORE_REGISTERS.values())
