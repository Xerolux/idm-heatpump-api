# Register Metadata Guide

This document explains the metadata attributes used in register definitions and how they map to Home Assistant entities.

## Unit Strings

Register units must follow **Home Assistant conventions** for compatibility:

### Energy
- `"kWh"` – Kilowatt-hours (energy consumption)

### Power
- `"kW"` – Kilowatts (power consumption/generation)

### Flow Rate
- `"L/min"` – Liters per minute (note: uppercase `L`, not `l`)

### Temperature
- `"°C"` – Celsius

### Percentage / Humidity
- `"%"` – Plain percent (not `"%rF"` relative fahrenheit)

## state_class Attribute

The `state_class` attribute enables Home Assistant long-term statistics tracking. It should be applied to read-only measurement registers only.

### total_increasing
Used for **cumulative energy measurements** that only increase (or reset):
```python
RegisterDef(
    address=1748,
    name="energy_heating",
    unit="kWh",
    state_class="total_increasing",  # For energy accumulation
)
```

**Applies to:**
- All energy registers (`energy_heating`, `energy_total`, `energy_cooling`, `energy_dhw`, `energy_defrost`, `energy_passive_cooling`, `energy_solar`, `energy_electric_heater`, `total_heat_energy`)

### measurement
Used for **instantaneous sensor readings**:
```python
RegisterDef(
    address=1790,
    name="current_power",
    unit="kW",
    state_class="measurement",  # For instantaneous measurements
)
```

**Applies to:**
- Power sensors: `current_power`, `current_power_solar`, `power_consumption_hp`, `thermal_power_flow_sensor`
- Flow rate: `heat_sink_flow_rate`
- Pump status: `charging_pump_status`, `brine_pump_status`, `isc_cold_storage_pump_status`, `isc_recooling_pump_status`, `heat_sink_charging_pump_signal`
- Booster pumps: `booster_a_source_pump`, `booster_a_charging_pump`, `booster_b_source_pump`, `booster_b_charging_pump`
- PV sensors: `pv_surplus`, `electric_heater_power`, `pv_production`, `house_consumption`, `battery_discharge`
- Humidity sensors: `humidity_sensor`, `zm{z}_room{room}_humidity`

## Writable Registers (No state_class)

**Intentionally skipped** – Home Assistant does not use `state_class` for control entities (number, select, switch):
```python
RegisterDef(
    address=1692,
    name="ext_humidity",
    unit="%",
    writable=True,
    # No state_class – this is a control entity, not a sensor
)
```

Examples:
- Temperature setpoints: `dhw_setpoint`, `hc_*_room_setpoint_*`
- Mode selections: `system_mode`, `hc_*_mode`, `zm*_room*_mode`
- Demand signals: `demand_heating`, `demand_cooling`
- External inputs: `ext_humidity`, `ext_demand_temp_*`

## Summary Table

| Category | Unit | state_class | Writable | Example |
|----------|------|-------------|----------|---------|
| Energy | kWh | total_increasing | ❌ | energy_heating |
| Power (instantaneous) | kW | measurement | ❌ | current_power |
| Flow rate | L/min | measurement | ❌ | heat_sink_flow_rate |
| Humidity (read-only) | % | measurement | ❌ | humidity_sensor |
| Humidity (control) | % | ❌ | ✅ | ext_humidity |
| Temperature (read-only) | °C | ❌ | ❌ | outdoor_temp |
| Temperature (setpoint) | °C | ❌ | ✅ | dhw_setpoint |
| Pump status | % | measurement | ❌ | charging_pump_status |

## Testing Register Metadata

The test suite (`tests/test_registers.py`) validates:
- All energy registers have `state_class="total_increasing"`
- All read-only power/flow/humidity registers have `state_class="measurement"`
- No writable registers have `state_class` set
- All humidity units are `"%"` (not `"%rF"`)
- All flow rate units are `"L/min"` (not `"l/min"`)

Run tests with:
```bash
pytest tests/test_registers.py -v
```
