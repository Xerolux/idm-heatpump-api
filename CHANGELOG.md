# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.7] - 2026-07-02

### Fixed

- Exclude Navigator 10-only register blocks, including power limit register 4108, when
  `build_register_map()` receives detected Navigator 2.0, Navigator Pro, or unknown model data.

## [0.3.6] - 2026-07-02

### Fixed

- Reject invalid register data types, register types, scaling multipliers, and value bounds
  when register metadata is created, instead of failing later during device I/O.
- Reject incomplete Modbus responses and ignore malformed capability probes during automatic
  model detection.
- Restore the GitHub bug-report template, which accidentally contained funding configuration.

## [0.3.5] - 2026-06-23

### Added

- Added firmware-version detection to `detect_model()` results.
- Added the `model_name` convenience property with the Navigator 2.0 fallback for
  unknown or not-yet-detected models.

### Changed

- Improved automatic heat-pump model detection coverage.

## [0.3.4] - 2026-06-22

### Fixed

- Fixed package tool configuration for Ruff and mypy.
- Hardened CI and removed dead code around model/register handling.

## [0.3.3] - 2026-06-18

### Fixed

- Fixed model-detection feature handling.

## [0.3.2] - 2026-06

All register definitions were verified line by line against the official iDM
"Montageanleitung MODBUS TCP NAVIGATOR 10" (Stand 18.06.2025).

### Fixed

- **Zone modules: corrected room register stride from 8 to 7.** Room blocks are 7
  registers wide (e.g. zone module 1, room 2 starts at 2009, not 2010). All room
  addresses for rooms 2-6 were previously wrong.
- **`smart_grid_status` moved from address 1006 to address 90** with the correct
  Navigator 10 enum (0=Red, 1=Yellow, 2=Green, 4=Supergreen). Address 1006 is the
  variable input ("Variabler Eingang") and is now exposed as `variable_input`.
- **`battery_soc` (86): changed from `FLOAT` to `INT16`** — the official doc lists it
  as WORD (single register, -1 = unavailable). As FLOAT it read two registers and
  decoded garbage.
- **`internal_message` (1004): changed from `UCHAR` to `UINT16`** — message numbers
  range from 020 to 999 and were corrupted by the one-byte mask.
- **Pump status registers (1074, 1104, 1105, 1106, 1108, 1109) and booster pumps
  (4020, 4021, 4050, 4051): changed from `UINT16` to `INT16`** — these report -1 for
  "off", which previously decoded as 65535 %.
- **`isc_mode` (1874) is read-only again** — the official doc lists it as RO
  (writability was incorrectly introduced in 0.3.0).
- **`ext_demand_groundwater_pump_m15` (1714) / 1715: changed from `UINT16` to `UCHAR`**
  with range 0-100 per the official doc. Renamed `ext_demand_brine_pump_m16` to
  `ext_demand_groundwater_pump_m15_sw_max` — address 1715 controls the groundwater
  pump M15 on SW Max, not the brine pump M16.
- **`heat_source_pump_status` (1106): added missing `%` unit and state_class.**
- **`pyproject.toml`: fixed broken tool configs** — `ruff.target-version` and
  `mypy.python_version` contained the package version ("0.3.1") instead of
  "py312" / "3.12".
- `client.py`: heating-circuit detection now adds the `FEATURE_HEATING_CIRCUITS`
  constant instead of a hard-coded string, and `HEATING_CIRCUIT_LETTERS` is imported
  from `const` instead of being redefined.

### Added

- `pv_target_value` register (address 88, FLOAT, kW) — PV target value for
  Smartfox / Solar-Log.
- `VARIABLE_INPUT_OPTIONS` and `EVU_LOCK_OPTIONS` enums (exported from the package).
- `evu_lock` (1098) now has enum options (0=Locked, 1=Not Locked).
- Write limits per official doc: bivalence points 1120-1123 and cascade bivalence
  points 1226-1231 (-40..40 °C), `system_mode` (0..5), zone-module room modes (0..4).
- PV registers 74-88 are now writable (RW/RO per official doc — a building management
  system writes these values to the heat pump).
- Zone-module room temperature and humidity registers are now writable (RW/RO — RW
  when external/GLT room sensors are used), with documented ranges (15-30 °C / 0-100 %).
- `current_electricity_price` (1048) now has its documented unit (€/MWh).
- Address-accuracy tests for heating circuits, zone modules and PV registers.

### Changed

- `get_zone_module_registers` now accepts at most 6 rooms (matching the official
  register map; rooms beyond 6 would produce undocumented addresses).
- `HP_OPERATING_MODE_OPTIONS`: value 0 renamed from "Off" to "Standby" per official doc.
- `docs/Modbus-Register.md` regenerated as a verified register reference (it previously
  contained unrelated contributing guidelines).

## [0.3.1] - 2026-06-02

### Changed

- Added the first 0.3.x release-flow metadata updates after the package rename.

## [0.3.0] - 2026-06

### Breaking

- PyPI package renamed from `idm-heatpump` to `idm-heatpump-api`. Install with `pip install idm-heatpump-api`. Python import remains `from idm_heatpump import ...`.

### Added

- New `RegisterDef` metadata fields for better Home Assistant integration support:
  - `binary: bool` — mark registers as binary sensors (e.g. compressor status, alarms)
  - `enabled_by_default: bool` — control default entity visibility in HA
  - `state_class: str | None` — HA state class ("measurement", "total", "total_increasing")
  - `icon: str | None` — default icon for HA entities
  - `write_only: bool` — mark write-only registers (e.g. error_acknowledge)
  - `exclude_from_write: set[int] | None` — exclude enum values from being written (e.g. 255)
- 8 registers now marked as `binary=True`: `hp_sum_alarm`, `compressor_status_1-4`, `heating_demand`, `cooling_demand`, `dhw_demand`
- `isc_mode` (address 1874) is now writable with `exclude_from_write={255}`
- `exclude_from_write={255}` added to all heating circuit mode registers (`hc_X_mode`)
- Funding badges and support section in README

### Fixed

- `battery_soc` (address 86): changed from `UINT16` to `FLOAT` to match actual device encoding
- `firmware_version` (address 4120): changed from `UINT16` to `FLOAT` (all surrounding registers are FLOAT)
- `error_acknowledge` (address 1999): now correctly marked as `write_only=True` — read attempts will raise instead of failing silently
- `read_register()` and `read_batch()` now properly skip write-only registers
- `write_register()` now validates `exclude_from_write` values before sending to device
- Removed unused `RegisterType` import from `registers.py`

## [0.2.2] - 2026-05

### Changed

- Historical release without a dedicated changelog entry before changelog
  continuity checks were added.

## [0.2.1] - 2026-05

### Fixes

- Added support for value 255 ("Not configured / Unavailable") in `ISC_MODE_OPTIONS`, `ACTIVE_HC_MODE_OPTIONS`, and `CIRCUIT_MODE_OPTIONS`.
- Added `firmware_version` register (address 4120) to the default register map.
- Improved logging for `firmware_version`: now logs at debug level instead of warning when it permanently fails (common on some Navigator 10 firmwares).
- Minor improvements for better compatibility with real Navigator 10 devices.

## [0.2.0] - 2026-05

### Breaking / Important

- Restructured package for clean PyPI distribution (`import idm_heatpump`).
- The library is now the shared Modbus/register core for the Home Assistant custom integration (migration Option B).

### Features

- Full Navigator 10 support (heat sink flow rate 1072, boosters, power limitation, etc.).
- Improved model detection for Navigator 10.

### Packaging

- Added proper release workflow for PyPI (modeled after violet-poolController-api).
- Clean top-level package layout.
