# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2] - 2026-05

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

## [0.2.1] - 2026-05

### Fixes

- Added support for value 255 ("Not configured / Unavailable") in `ISC_MODE_OPTIONS`, `ACTIVE_HC_MODE_OPTIONS`, and `CIRCUIT_MODE_OPTIONS`.
- Added `firmware_version` register (address 4120) to the default register map.
- Improved logging for `firmware_version`: now logs at debug level instead of warning when it permanently fails (common on some Navigator 10 firmwares).
- Minor improvements for better compatibility with real Navigator 10 devices.

## [0.2.0] - 2026-05

### Breaking / Important

- Restructured package for clean PyPI distribution (`import idm_heatpump`).
- The library is now the official core for the Home Assistant integration (migration Option B).

### Features

- Full Navigator 10 support (heat sink flow rate 1072, boosters, power limitation, etc.).
- Improved model detection for Navigator 10.

### Packaging

- Added proper release workflow for PyPI (modeled after violet-poolController-api).
- Clean top-level package layout.
