# Register Metadata

This document explains the metadata attributes on `RegisterDef` and how a
consumer (for example the Home Assistant integration) maps them to entities.
For the full register table, see [Modbus Register](Modbus-Register); for the
method reference, see [Client Methods](Services).

## RegisterDef fields

`RegisterDef` is the dataclass describing one Modbus data point. The fields a
consumer cares about:

| Field | Type | Meaning |
|-------|------|---------|
| `address` | `int` | Documented Modbus start address. |
| `datatype` | `DataType` | `FLOAT`, `UCHAR`, `INT8`, `INT16`, `UINT16`, `BOOL`, `BITFLAG`. |
| `name` | `str` | Canonical register key used by the registry. |
| `unit` | `str \| None` | Physical unit, following Home Assistant conventions. |
| `writable` | `bool` | Whether the register accepts writes. |
| `min_val` / `max_val` | `float \| None` | Documented physical range; validated on write. |
| `enum_options` | `dict[int, str] \| None` | Allowed raw-value → label mapping. |
| `multiplier` | `float` | Scale factor applied during decode/encode. |
| `register_type` | `RegisterType` | `INPUT` (FC04) or `HOLDING` (FC03/FC06/FC16). |
| `eeprom_sensitive` | `bool` | Persisted to EEPROM on write — throttled. |
| `cyclic_required` | `bool` | Must be re-written cyclically to stay active. |
| `binary` | `bool` | Consumer hint: expose as a binary sensor. |
| `enabled_by_default` | `bool` | Consumer hint: entity enabled by default. |
| `state_class` | `str \| None` | Consumer hint: `"measurement"` or `"total_increasing"`. |
| `icon` | `str \| None` | Consumer hint, e.g. `"mdi:thermometer"`. |
| `write_only` | `bool` | Write-only register (e.g. `error_acknowledge`). |
| `exclude_from_write` | `set[int] \| None` | Raw values that must never be written (e.g. `{255}`). |
| `source` | `str` | Origin of the definition, default `official_idm_modbus`. |
| `source_version` | `str` | Source document / verification version. |
| `supported_models` | `tuple[str, ...]` | Expected Navigator models. |
| `sentinel_values` | `tuple[int \| float \| str, ...]` | Context-specific unavailable values. |
| `last_verified` | `str \| None` | Optional hardware verification label. |
| `size` | `int` | Computed: 2 for `FLOAT`, otherwise 1. |
| `write_class` | `WriteClass` | Derived (see below). |

### WriteClass derivation

`write_class` is derived from the write-related flags:

| `WriteClass` | Condition |
|--------------|-----------|
| `FORBIDDEN` | not writable |
| `WRITE_ONLY` | `write_only=True` |
| `CYCLIC` | `cyclic_required=True` |
| `EEPROM` | `eeprom_sensitive=True` |
| `VOLATILE` | writable, none of the above |

## Unit strings

Register units must follow **Home Assistant conventions** for compatibility:

- `"kWh"` – energy
- `"kW"` – power
- `"L/min"` – flow rate (uppercase `L`, not `l`)
- `"°C"` – temperature
- `"%"` – percentage / humidity (not `"%rF"`)

## state_class (consumer mapping hint)

`state_class` enables long-term statistics in Home Assistant and should be
applied to read-only measurement registers only.

- `"total_increasing"` — cumulative energy meters that only increase (or reset):
  `energy_heating`, `energy_total`, `energy_cooling`, `energy_dhw`,
  `energy_defrost`, `energy_passive_cooling`, `energy_solar`,
  `energy_electric_heater`, `total_heat_energy`.
- `"measurement"` — instantaneous readings: power sensors, flow rate, pump
  status, booster pumps, PV sensors, humidity sensors.
- Not set on writable/control registers — Home Assistant does not use
  `state_class` for `number`/`select`/`switch` entities.

The distinction is a **consumer mapping concern**: the library records
`state_class` so an integration can decide whether a register becomes a
`sensor` (statistics-eligible) or a control entity.

## Sentinel values

`sentinel_values` records context-specific unavailable values (for example
`-1.0` for an unused heating circuit's flow temperature, or `255` for a
not-configured heating-circuit mode). These are decoded using the documented
datatype and then interpreted as "unavailable" — they are never clamped or
discarded at the raw-byte level. Sentinels also participate in batch-value
validation (see [Data Polling](Data-Update)).

## Testing register metadata

The test suite validates metadata consistency:

- All energy registers have `state_class="total_increasing"`.
- All read-only power/flow/humidity registers have `state_class="measurement"`.
- No writable registers have `state_class` set.
- All humidity units are `"%"` (not `"%rF"`).
- All flow-rate units are `"L/min"` (not `"l/min"`).

```bash
pytest tests/test_registers.py -v
```

The public API snapshot test also guards the registry surface:

```bash
pytest tests/test_public_api.py -v
```
