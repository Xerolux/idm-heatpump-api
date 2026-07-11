# Supported Devices

This page describes which IDM Navigator controllers the library supports, how
feature detection gates register groups, and the `IdmModelInfo` shape consumers
can rely on. For the full register map, see [Modbus Register](Modbus-Register).

## Device matrix

| Device | Firmware | Heating circuits | Zone modules | Status |
|--------|----------|------------------|--------------|--------|
| IDM Navigator 10 | NAV10_20.23+ (2025) | up to 7 (A–G) | up to 10 (6 default, 8 configurable) | Maintainer-confirmed |
| IDM Navigator 2.0 | firmware-dependent | up to 7 (A–G) | firmware-dependent | Expected; needs broader raw detection captures |
| IDM Navigator Pro | firmware-dependent | up to 7 (A–G) | up to 10 (8 configurable) | Expected; needs complete diagnostics |

> Navigator 1.0/1.7 is a separate protocol family and is **not** supported.

For firmware references, see [Firmware Compatibility](firmware_compatibility)
and the machine-readable [`compatibility-matrix.json`](compatibility-matrix.json).

## Feature-gated register groups

`detect_model()` returns an `IdmModelInfo` whose flags and features gate which
register groups `build_register_map(model_info=...)` includes. The constants
`FEATURE_HEATING_CIRCUITS`, `FEATURE_ZONE_MODULES`, `FEATURE_SOLAR`,
`FEATURE_ISC`, `FEATURE_PV`, and `FEATURE_CASCADE` label these groups.

| Register group | Gated by | Examples |
|----------------|----------|----------|
| Heating circuits A–G | active circuits + `FEATURE_HEATING_CIRCUITS` | flow/return temps, setpoints, mode, curve, room temp, mixer |
| Zone modules | `zone_modules` count + `FEATURE_ZONE_MODULES` | per-room temp / setpoint / humidity / mode / relay |
| Solar | `has_solar` + `FEATURE_SOLAR` | solar temps, solar mode |
| ISC (Intelligent Surface Cooling) | `has_isc` + `FEATURE_ISC` | cold storage / recooling pump status |
| PV / energy management | `has_pv` + `FEATURE_PV` | PV surplus, production, battery SoC/discharge, electric heater power |
| Cascade | `has_cascade` + `FEATURE_CASCADE` | cascade temps, bivalence points |
| Booster A/B | Navigator 10 map | second heat generator monitoring |
| Heat sink / plate heat exchanger | Navigator 10 map | flow rate (1072 l/min) |
| Power limitation | Navigator 10 map | demand response / peak shaving (4108 / 4112) |
| Groundwater | Navigator 10 map | groundwater temperatures |
| Additional faults / external pump demand | Navigator 10 map | source pump faults, external pump demands |

`build_register_map()` with no `model_info` returns only `CORE_REGISTERS`.

## IdmModelInfo

`detect_model()` returns a mutable `IdmModelInfo` dataclass:

| Field | Type | Meaning |
|-------|------|---------|
| `model_name` | `str` | One of `MODEL_NAVIGATOR_10`, `MODEL_NAVIGATOR_20`, `MODEL_NAVIGATOR_PRO`, or `MODEL_UNKNOWN`. |
| `active_heating_circuits` | `list[str]` | Active circuit letters (subset of `HEATING_CIRCUIT_LETTERS`). |
| `zone_modules` | `int` | Detected zone-module count. |
| `has_solar` | `bool` | Solar thermal detected. |
| `has_isc` | `bool` | ISC detected. |
| `has_pv` | `bool` | PV / energy management detected. |
| `has_cascade` | `bool` | Cascade controller detected. |
| `features` | `set[str]` | Feature flag set using the `FEATURE_*` constants. |
| `firmware_version` | `float \| None` | Firmware version, when `read_firmware=True`. |

The `is_pro` property returns `True` when `zone_modules > 0`.

## Limits

| Constant | Value |
|----------|-------|
| `MAX_HEATING_CIRCUITS` | 7 |
| `MAX_ZONE_MODULES` | 10 |
| `MAX_ROOMS_PER_ZONE` | 8 (6 is the current Navigator 10 default) |
| `HEATING_CIRCUIT_LETTERS` | `['A', 'B', 'C', 'D', 'E', 'F', 'G']` |

## Detection diagnostics

If detection returns unexpected results, collect a diagnostics snapshot and
attach it to a bug report:

```python
model_info = await client.detect_model()
diag = client.get_diagnostics()
print(model_info)
print(diag)
```

See [Known Limitations](Known-Limitations) for the detection caveats.
