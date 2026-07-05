"""Comprehensive register definitions for IDM Navigator heat pumps.

Register map sources:
- Official iDM "MODBUS TCP NAVIGATOR 10" documentation (Stand 18.06.2025, NAV10_20.23+)
- Earlier Navigator 2.0 / Pro documentation

Supports:
- Navigator 10 (current generation)
- Navigator 2.0
- Navigator Pro

All new descriptions are in English. German original terms kept in comments where helpful
for cross-reference with official iDM docs.

FLOAT encoding: IEEE 754, 32-bit, 2 registers, Low word first (Reg_L then Reg_H).
"""

from __future__ import annotations

from .client import DataType, IdmModelInfo, RegisterDef
from .const import (
    ACTIVE_HC_MODE_OPTIONS,
    BIVALENCE_STATE_OPTIONS,
    BOOSTER_FAULT_OPTIONS,
    CIRCUIT_MODE_OPTIONS,
    EVU_LOCK_OPTIONS,
    HP_OPERATING_MODE_OPTIONS,
    ISC_MODE_OPTIONS,
    MODEL_NAVIGATOR_10,
    ROOM_MODE_OPTIONS,
    SMART_GRID_OPTIONS,
    SOLAR_MODE_OPTIONS,
    SYSTEM_MODE_OPTIONS,
    VARIABLE_INPUT_OPTIONS,
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
        min_val=0,
        max_val=5,
        enum_options=SYSTEM_MODE_OPTIONS,
        eeprom_sensitive=True,
    ),
    "storage_temp": RegisterDef(
        address=1008,
        datatype=DataType.FLOAT,
        name="storage_temp",
        unit="°C",
    ),
    "hp_operating_mode": RegisterDef(
        address=1090,
        datatype=DataType.UCHAR,
        name="hp_operating_mode",
        enum_options=HP_OPERATING_MODE_OPTIONS,
    ),
    "error_acknowledge": RegisterDef(
        address=1999,
        datatype=DataType.UCHAR,
        name="error_acknowledge",
        writable=True,
        write_only=True,
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
            address=1004,
            datatype=DataType.UINT16,
            name="internal_message",
            # Message numbers range from 020 to 999 and therefore do not fit
            # into a single byte, even though the official doc lists UCHAR.
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
            address=90,
            datatype=DataType.UCHAR,
            name="smart_grid_status",
            enum_options=SMART_GRID_OPTIONS,
            # 0=Red, 1=Yellow, 2=Green, 4=Supergreen
        ),
        "variable_input": RegisterDef(
            address=1006,
            datatype=DataType.UCHAR,
            name="variable_input",
            enum_options=VARIABLE_INPUT_OPTIONS,
            # "Variabler Eingang" – configurable special-function input
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
            unit="€/MWh",
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
            address=1091, datatype=DataType.UCHAR, name="heating_demand", binary=True
        ),
        "cooling_demand": RegisterDef(
            address=1092, datatype=DataType.UCHAR, name="cooling_demand", binary=True
        ),
        "dhw_demand": RegisterDef(
            address=1093, datatype=DataType.UCHAR, name="dhw_demand", binary=True
        ),
        "evu_lock": RegisterDef(
            address=1098,
            datatype=DataType.UCHAR,
            name="evu_lock",
            enum_options=EVU_LOCK_OPTIONS,
        ),
        "hp_sum_alarm": RegisterDef(
            address=1099, datatype=DataType.UCHAR, name="hp_sum_alarm", binary=True
        ),
        "compressor_status_1": RegisterDef(
            address=1100, datatype=DataType.UCHAR, name="compressor_status_1", binary=True
        ),
        "compressor_status_2": RegisterDef(
            address=1101, datatype=DataType.UCHAR, name="compressor_status_2", binary=True
        ),
        "compressor_status_3": RegisterDef(
            address=1102, datatype=DataType.UCHAR, name="compressor_status_3", binary=True
        ),
        "compressor_status_4": RegisterDef(
            address=1103, datatype=DataType.UCHAR, name="compressor_status_4", binary=True
        ),
        # Pump status registers are WORD with -1 = off (0 = min speed,
        # 100 = max speed), so they must be decoded as signed values.
        "charging_pump_status": RegisterDef(
            address=1104,
            datatype=DataType.INT16,
            name="charging_pump_status",
            unit="%",
            state_class="measurement",
        ),
        "brine_pump_status": RegisterDef(
            address=1105,
            datatype=DataType.INT16,
            name="brine_pump_status",
            unit="%",
            state_class="measurement",
        ),
        "heat_source_pump_status": RegisterDef(
            address=1106,
            datatype=DataType.INT16,
            name="heat_source_pump_status",
            unit="%",
            state_class="measurement",
        ),
        "isc_cold_storage_pump_status": RegisterDef(
            address=1108,
            datatype=DataType.INT16,
            name="isc_cold_storage_pump_status",
            unit="%",
            state_class="measurement",
        ),
        "isc_recooling_pump_status": RegisterDef(
            address=1109,
            datatype=DataType.INT16,
            name="isc_recooling_pump_status",
            unit="%",
            state_class="measurement",
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
            min_val=-40,
            max_val=40,
            eeprom_sensitive=True,
        ),
        "bivalence_point_2_2nd_gen": RegisterDef(
            address=1121,
            datatype=DataType.INT16,
            name="bivalence_point_2_2nd_gen",
            unit="°C",
            writable=True,
            min_val=-40,
            max_val=40,
            eeprom_sensitive=True,
        ),
        "bivalence_point_1_3rd_gen": RegisterDef(
            address=1122,
            datatype=DataType.INT16,
            name="bivalence_point_1_3rd_gen",
            unit="°C",
            writable=True,
            min_val=-40,
            max_val=40,
            eeprom_sensitive=True,
        ),
        "bivalence_point_2_3rd_gen": RegisterDef(
            address=1123,
            datatype=DataType.INT16,
            name="bivalence_point_2_3rd_gen",
            unit="°C",
            writable=True,
            min_val=-40,
            max_val=40,
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
            state_class="total_increasing",
        ),
        "energy_total": RegisterDef(
            address=1750,
            datatype=DataType.FLOAT,
            name="energy_total",
            unit="kWh",
            state_class="total_increasing",
        ),
        "energy_cooling": RegisterDef(
            address=1752,
            datatype=DataType.FLOAT,
            name="energy_cooling",
            unit="kWh",
            state_class="total_increasing",
        ),
        "energy_dhw": RegisterDef(
            address=1754,
            datatype=DataType.FLOAT,
            name="energy_dhw",
            unit="kWh",
            state_class="total_increasing",
        ),
        "energy_defrost": RegisterDef(
            address=1756,
            datatype=DataType.FLOAT,
            name="energy_defrost",
            unit="kWh",
            state_class="total_increasing",
        ),
        "energy_passive_cooling": RegisterDef(
            address=1758,
            datatype=DataType.FLOAT,
            name="energy_passive_cooling",
            unit="kWh",
            state_class="total_increasing",
        ),
        "energy_solar": RegisterDef(
            address=1760,
            datatype=DataType.FLOAT,
            name="energy_solar",
            unit="kWh",
            state_class="total_increasing",
        ),
        "energy_electric_heater": RegisterDef(
            address=1762,
            datatype=DataType.FLOAT,
            name="energy_electric_heater",
            unit="kWh",
            state_class="total_increasing",
        ),
        "current_power": RegisterDef(
            address=1790,
            datatype=DataType.FLOAT,
            name="current_power",
            unit="kW",
            state_class="measurement",
        ),
        "current_power_solar": RegisterDef(
            address=1792,
            datatype=DataType.FLOAT,
            name="current_power_solar",
            unit="kW",
            state_class="measurement",
        ),
        "power_consumption_hp": RegisterDef(
            address=4122,
            datatype=DataType.FLOAT,
            name="power_consumption_hp",
            unit="kW",
            state_class="measurement",
        ),
        "firmware_version": RegisterDef(
            address=4120,
            datatype=DataType.FLOAT,
            name="firmware_version",
            # Some Navigator 10 firmware builds reject this register even though
            # the same version is available through the local web interface.
            enabled_by_default=False,
        ),
        "thermal_power_flow_sensor": RegisterDef(
            address=4126,
            datatype=DataType.FLOAT,
            name="thermal_power_flow_sensor",
            unit="kW",
            state_class="measurement",
        ),
        "total_heat_energy": RegisterDef(
            address=4128,
            datatype=DataType.FLOAT,
            name="total_heat_energy",
            unit="kWh",
            state_class="total_increasing",
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
            # Read-only per official Navigator 10 doc (0/1/4/8)
        ),
    }


def _pv_registers() -> dict[str, RegisterDef]:
    """PV / energy-management registers (addresses 74-88).

    All of these are RW/RO per the official doc: a building management system
    (GLT) writes the values to the heat pump, e.g. the PV surplus via address 74.
    """
    return {
        "pv_surplus": RegisterDef(
            address=74,
            datatype=DataType.FLOAT,
            name="pv_surplus",
            unit="kW",
            writable=True,
        ),
        "electric_heater_power": RegisterDef(
            address=76,
            datatype=DataType.FLOAT,
            name="electric_heater_power",
            unit="kW",
            writable=True,
        ),
        "pv_production": RegisterDef(
            address=78,
            datatype=DataType.FLOAT,
            name="pv_production",
            unit="kW",
            writable=True,
        ),
        "house_consumption": RegisterDef(
            address=82,
            datatype=DataType.FLOAT,
            name="house_consumption",
            unit="kW",
            writable=True,
        ),
        "battery_discharge": RegisterDef(
            address=84,
            datatype=DataType.FLOAT,
            name="battery_discharge",
            unit="kW",
            writable=True,
        ),
        "battery_soc": RegisterDef(
            address=86,
            datatype=DataType.INT16,
            name="battery_soc",
            unit="%",
            writable=True,
            min_val=0,
            max_val=100,
            # WORD per official doc (single register, not FLOAT), -1 = unavailable
        ),
        "pv_target_value": RegisterDef(
            address=88,
            datatype=DataType.FLOAT,
            name="pv_target_value",
            unit="kW",
            writable=True,
            # PV target value (Smartfox and Solar-Log)
        ),
    }


# ---------------------------------------------------------------------------
# Navigator 10 additions (from official MODBUS TCP NAVIGATOR 10 doc, 18.06.2025)
# ---------------------------------------------------------------------------


def _heat_sink_registers() -> dict[str, RegisterDef]:
    """Registers related to the heat sink / plate heat exchanger (Trennwärmetauscher).

    Especially useful when a hydraulic separator or plate heat exchanger is installed.
    Address 1072 (flow rate) is particularly valuable for filter monitoring.
    """
    return {
        "heat_sink_return_temp": RegisterDef(
            address=1068,
            datatype=DataType.FLOAT,
            name="heat_sink_return_temp",
            unit="°C",
            # B124 - Rücklauftemperatur Wärmesenke
        ),
        "heat_sink_flow_temp": RegisterDef(
            address=1070,
            datatype=DataType.FLOAT,
            name="heat_sink_flow_temp",
            unit="°C",
            # B125 - Vorlauftemperatur Wärmesenke
        ),
        "heat_sink_flow_rate": RegisterDef(
            address=1072,
            datatype=DataType.UCHAR,
            name="heat_sink_flow_rate",
            unit="L/min",
            state_class="measurement",
            # B2 - Durchfluss Wärmesenke (only available with plate heat exchanger / TWT)
        ),
        "heat_sink_charging_pump_signal": RegisterDef(
            address=1074,
            datatype=DataType.INT16,
            name="heat_sink_charging_pump_signal",
            unit="%",
            state_class="measurement",
            # M73 - Ladepumpe Wärmesenke Steuersignal (WORD, -1 = off)
        ),
    }


def _groundwater_registers() -> dict[str, RegisterDef]:
    """Groundwater source temperatures (Grundwasser)."""
    return {
        "groundwater_inlet_temp_1": RegisterDef(
            address=1086,
            datatype=DataType.FLOAT,
            name="groundwater_inlet_temp_1",
            unit="°C",
            # B119
        ),
        "groundwater_inlet_temp_2": RegisterDef(
            address=1088,
            datatype=DataType.FLOAT,
            name="groundwater_inlet_temp_2",
            unit="°C",
            # B120
        ),
    }


def _additional_fault_registers() -> dict[str, RegisterDef]:
    """Additional fault / alarm status registers (not part of the main hp_sum_alarm)."""
    return {
        "fault_heat_source_circuit": RegisterDef(
            address=1680,
            datatype=DataType.UCHAR,
            name="fault_heat_source_circuit",
            # 0 = fault, 1 = no fault
        ),
        "fault_heat_source_pressure_switch": RegisterDef(
            address=1681,
            datatype=DataType.UCHAR,
            name="fault_heat_source_pressure_switch",
            # iPump T / TERRA SWM specific
        ),
        "fault_charging_pump_1_intermediate": RegisterDef(
            address=1682,
            datatype=DataType.UCHAR,
            name="fault_charging_pump_1_intermediate",
            # M125
        ),
        "fault_charging_pump_2_intermediate": RegisterDef(
            address=1683,
            datatype=DataType.UCHAR,
            name="fault_charging_pump_2_intermediate",
            # M118
        ),
    }


def _external_pump_demand_registers() -> dict[str, RegisterDef]:
    """External demand / control of source pumps (mainly for SW/SWM models)."""
    return {
        "ext_demand_groundwater_pump_m15": RegisterDef(
            address=1714,
            datatype=DataType.UCHAR,
            name="ext_demand_groundwater_pump_m15",
            unit="%",
            writable=True,
            min_val=0,
            max_val=100,
            # Groundwater pump M15 (SW/SWM/SW Twin) and brine/intermediate
            # circuit pump M16 (SW/SWM/SW Twin/SW Max). UCHAR per official doc.
        ),
        "ext_demand_groundwater_pump_m15_sw_max": RegisterDef(
            address=1715,
            datatype=DataType.UCHAR,
            name="ext_demand_groundwater_pump_m15_sw_max",
            unit="%",
            writable=True,
            min_val=0,
            max_val=100,
            # Groundwater pump M15 on SW Max. UCHAR per official doc.
        ),
    }


def _power_limit_registers() -> dict[str, RegisterDef]:
    """Power limitation (Leistungsbegrenzung) – very useful for grid services / peak shaving."""
    return {
        "power_limit_hp": RegisterDef(
            address=4108,
            datatype=DataType.FLOAT,
            name="power_limit_hp",
            unit="kW",
            writable=True,
            # Leistungsbegrenzung Wärmepumpe (-1 = no limit)
        ),
        "power_limit_cascade": RegisterDef(
            address=4112,
            datatype=DataType.FLOAT,
            name="power_limit_cascade",
            unit="kW",
            writable=True,
            # Leistungsbegrenzung Kaskade
        ),
        "power_consumption_hp_smartfox": RegisterDef(
            address=4124,
            datatype=DataType.FLOAT,
            name="power_consumption_hp_smartfox",
            unit="kW",
            # Elektr. Gesamtleistung Wärmepumpe (Smartfox variant)
        ),
    }


def _booster_registers() -> dict[str, RegisterDef]:
    """Registers for Booster A + B (additional heat generators / 2nd stage).

    Covers temperatures, pumps, compressor status and combined fault/interlock states.
    """
    return {
        # --- Booster A ---
        "booster_fault": RegisterDef(
            address=4001,
            datatype=DataType.UCHAR,
            name="booster_fault",
            enum_options=BOOSTER_FAULT_OPTIONS,
        ),
        "booster_interlock": RegisterDef(
            address=4002,
            datatype=DataType.UCHAR,
            name="booster_interlock",
        ),
        "booster_a_source_inlet_temp": RegisterDef(
            address=4010,
            datatype=DataType.FLOAT,
            name="booster_a_source_inlet_temp",
            unit="°C",
        ),
        "booster_a_source_outlet_temp": RegisterDef(
            address=4012,
            datatype=DataType.FLOAT,
            name="booster_a_source_outlet_temp",
            unit="°C",
        ),
        "booster_a_storage_temp": RegisterDef(
            address=4014,
            datatype=DataType.FLOAT,
            name="booster_a_storage_temp",
            unit="°C",
        ),
        "booster_a_flow_temp": RegisterDef(
            address=4016,
            datatype=DataType.FLOAT,
            name="booster_a_flow_temp",
            unit="°C",
        ),
        "booster_a_return_temp": RegisterDef(
            address=4018,
            datatype=DataType.FLOAT,
            name="booster_a_return_temp",
            unit="°C",
        ),
        "booster_a_source_pump": RegisterDef(
            address=4020,
            datatype=DataType.INT16,
            name="booster_a_source_pump",
            unit="%",
            state_class="measurement",
            # WORD per official doc, -1 = off
        ),
        "booster_a_charging_pump": RegisterDef(
            address=4021,
            datatype=DataType.INT16,
            name="booster_a_charging_pump",
            unit="%",
            state_class="measurement",
            # WORD per official doc, -1 = off
        ),
        "booster_a_compressor": RegisterDef(
            address=4022,
            datatype=DataType.UCHAR,
            name="booster_a_compressor",
        ),
        # --- Booster B ---
        "booster_b_source_inlet_temp": RegisterDef(
            address=4040,
            datatype=DataType.FLOAT,
            name="booster_b_source_inlet_temp",
            unit="°C",
        ),
        "booster_b_source_outlet_temp": RegisterDef(
            address=4042,
            datatype=DataType.FLOAT,
            name="booster_b_source_outlet_temp",
            unit="°C",
        ),
        "booster_b_storage_temp": RegisterDef(
            address=4044,
            datatype=DataType.FLOAT,
            name="booster_b_storage_temp",
            unit="°C",
        ),
        "booster_b_flow_temp": RegisterDef(
            address=4046,
            datatype=DataType.FLOAT,
            name="booster_b_flow_temp",
            unit="°C",
        ),
        "booster_b_return_temp": RegisterDef(
            address=4048,
            datatype=DataType.FLOAT,
            name="booster_b_return_temp",
            unit="°C",
        ),
        "booster_b_source_pump": RegisterDef(
            address=4050,
            datatype=DataType.INT16,
            name="booster_b_source_pump",
            unit="%",
            state_class="measurement",
            # WORD per official doc, -1 = off
        ),
        "booster_b_charging_pump": RegisterDef(
            address=4051,
            datatype=DataType.INT16,
            name="booster_b_charging_pump",
            unit="%",
            state_class="measurement",
            # WORD per official doc, -1 = off
        ),
        "booster_b_compressor": RegisterDef(
            address=4052,
            datatype=DataType.UCHAR,
            name="booster_b_compressor",
        ),
    }


def _more_cascade_registers() -> dict[str, RegisterDef]:
    """Additional cascade bivalence points (parallel / alternative)."""
    return {
        "cascade_bivalence_heating_parallel": RegisterDef(
            address=1226,
            datatype=DataType.INT16,
            name="cascade_bivalence_heating_parallel",
            unit="°C",
            writable=True,
            min_val=-40,
            max_val=40,
        ),
        "cascade_bivalence_heating_alternative": RegisterDef(
            address=1227,
            datatype=DataType.INT16,
            name="cascade_bivalence_heating_alternative",
            unit="°C",
            writable=True,
            min_val=-40,
            max_val=40,
        ),
        "cascade_bivalence_cooling_parallel": RegisterDef(
            address=1228,
            datatype=DataType.INT16,
            name="cascade_bivalence_cooling_parallel",
            unit="°C",
            writable=True,
            min_val=-40,
            max_val=40,
        ),
        "cascade_bivalence_cooling_alternative": RegisterDef(
            address=1229,
            datatype=DataType.INT16,
            name="cascade_bivalence_cooling_alternative",
            unit="°C",
            writable=True,
            min_val=-40,
            max_val=40,
        ),
        "cascade_bivalence_dhw_parallel": RegisterDef(
            address=1230,
            datatype=DataType.INT16,
            name="cascade_bivalence_dhw_parallel",
            unit="°C",
            writable=True,
            min_val=-40,
            max_val=40,
        ),
        "cascade_bivalence_dhw_alternative": RegisterDef(
            address=1231,
            datatype=DataType.INT16,
            name="cascade_bivalence_dhw_alternative",
            unit="°C",
            writable=True,
            min_val=-40,
            max_val=40,
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
            unit="%",
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
        exclude_from_write={255},
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
        address=1443 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_heating_limit",
        unit="°C",
        writable=True,
        min_val=0,
        max_val=50,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_setpoint_flow_constant"] = RegisterDef(
        address=1450 + idx,
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
        address=1485 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_cooling_limit",
        unit="°C",
        writable=True,
        min_val=0,
        max_val=36,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_setpoint_flow_cooling"] = RegisterDef(
        address=1492 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_setpoint_flow_cooling",
        unit="°C",
        writable=True,
        min_val=8,
        max_val=30,
        eeprom_sensitive=True,
    )
    regs[f"hc_{c}_active_mode"] = RegisterDef(
        address=1499 + idx,
        datatype=DataType.UCHAR,
        name=f"hc_{c}_active_mode",
        enum_options=ACTIVE_HC_MODE_OPTIONS,
    )
    regs[f"hc_{c}_parallel_shift"] = RegisterDef(
        address=1506 + idx,
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
    room_count: int = 6,
) -> dict[str, RegisterDef]:
    """Return all registers for a specific zone module (1-10).

    Each zone module supports up to 6 rooms (1-6).
    Zone module base addresses: 2000, 2065, 2130, 2195, 2260, 2325, 2390, 2455, 2520, 2585
    (65 addresses apart; registers used per module: base .. base+43).

    Room register layout (verified against the official Navigator 10 doc):
    each room occupies 7 registers starting at base+2, e.g. zone module 1:
    room 1 = 2002/2004/2006/2007/2008, room 2 = 2009/2011/2013/2014/2015, ...
    """
    if not (1 <= zone_index <= 10):
        raise ValueError(f"Zone index must be 1-10, got {zone_index}")
    if not (1 <= room_count <= 6):
        raise ValueError(f"Room count must be 1-6, got {room_count}")

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
        room_base = base + 2 + (room - 1) * 7
        regs[f"zm{z}_room{room}_temp"] = RegisterDef(
            address=room_base,
            datatype=DataType.FLOAT,
            name=f"zm{z}_room{room}_temp",
            unit="°C",
            writable=True,
            min_val=15,
            max_val=30,
            # RW when using external (GLT) room sensors, RO with iDM sensors
        )
        regs[f"zm{z}_room{room}_setpoint"] = RegisterDef(
            address=room_base + 2,
            datatype=DataType.FLOAT,
            name=f"zm{z}_room{room}_setpoint",
            unit="°C",
            writable=True,
            # Setpoint can only be communicated in 0.5 °C steps
        )
        regs[f"zm{z}_room{room}_humidity"] = RegisterDef(
            address=room_base + 4,
            datatype=DataType.UCHAR,
            name=f"zm{z}_room{room}_humidity",
            unit="%",
            writable=True,
            min_val=0,
            max_val=100,
            # RW when using external (GLT) room sensors, RO with iDM sensors
        )
        regs[f"zm{z}_room{room}_mode"] = RegisterDef(
            address=room_base + 5,
            datatype=DataType.UCHAR,
            name=f"zm{z}_room{room}_mode",
            writable=True,
            min_val=0,
            max_val=4,
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
    rooms_per_zone: int = 6,
) -> dict[str, RegisterDef]:
    """Build a complete register map based on detected model or manual config.

    Args:
        model_info: Auto-detected model info (takes priority over manual params).
        circuits: Manual list of active circuit letters (e.g. ["A", "B"]).
        zone_modules: Manual number of zone modules (0-10).
        rooms_per_zone: Number of rooms per zone module (default 6 for Navigator 10 / current hardware).

    Returns:
        Complete dict of register definitions keyed by name.
    """
    if circuits is not None:
        invalid = [c for c in circuits if c.upper() not in "ABCDEFG"]
        if invalid:
            raise ValueError(f"Invalid heating circuit letters: {invalid}")
    if not (0 <= zone_modules <= 10):
        raise ValueError(f"zone_modules must be 0-10, got {zone_modules}")
    if not (1 <= rooms_per_zone <= 6):
        raise ValueError(f"rooms_per_zone must be 1-6, got {rooms_per_zone}")

    all_regs: dict[str, RegisterDef] = {}

    all_regs.update(_system_registers())
    all_regs.update(_hp_status_registers())
    all_regs.update(_energy_registers())

    # Preserve the complete map for callers without detection data. Once a
    # model has been detected, do not poll Navigator 10-only addresses on
    # older controllers: they respond with Modbus "Illegal Data Address".
    include_navigator_10 = model_info is None or model_info.model_name == MODEL_NAVIGATOR_10
    if include_navigator_10:
        all_regs.update(_heat_sink_registers())
        all_regs.update(_groundwater_registers())
        all_regs.update(_additional_fault_registers())
        all_regs.update(_external_pump_demand_registers())
        all_regs.update(_power_limit_registers())
        all_regs.update(_booster_registers())

    active_circuits: list[str]
    num_zones: int

    if model_info is not None:
        active_circuits = model_info.active_heating_circuits
        num_zones = model_info.zone_modules

        if model_info.has_cascade:
            all_regs.update(_cascade_registers())
            all_regs.update(_more_cascade_registers())
        if model_info.has_solar:
            all_regs.update(_solar_registers())
        if model_info.has_isc:
            all_regs.update(_isc_registers())
        if model_info.has_pv:
            all_regs.update(_pv_registers())
    else:
        active_circuits = circuits or list("ABCDEFG")
        num_zones = zone_modules

        # Without model_info, include all optional register blocks.
        # hide_unused_registers in the HA integration handles availability.
        all_regs.update(_solar_registers())
        all_regs.update(_isc_registers())
        all_regs.update(_pv_registers())
        all_regs.update(_cascade_registers())
        all_regs.update(_more_cascade_registers())

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
        write_only=True,
    )
    all_regs["humidity_sensor"] = RegisterDef(
        address=1392,
        datatype=DataType.UCHAR,
        name="humidity_sensor",
        unit="%",
        state_class="measurement",
    )

    return all_regs


def get_register(name: str, *, model_info: IdmModelInfo | None = None) -> RegisterDef:
    """Return a register definition by canonical name.

    By default only the small legacy ``CORE_REGISTERS`` set is searched.
    Pass ``model_info`` (or build the full map manually) to look up any
    register.
    """
    if name in CORE_REGISTERS:
        return CORE_REGISTERS[name]
    full_map = build_register_map(model_info=model_info)
    if name not in full_map:
        raise ValueError(f"Register '{name}' not found.")
    return full_map[name]


def get_all_registers(*, model_info: IdmModelInfo | None = None) -> list[RegisterDef]:
    """Return all register definitions.

    By default only the small legacy ``CORE_REGISTERS`` set is returned.
    Pass ``model_info`` to build the full map.
    """
    if model_info is None:
        return list(CORE_REGISTERS.values())
    return list(build_register_map(model_info=model_info).values())
