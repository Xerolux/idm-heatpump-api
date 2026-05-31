# IDM Heatpump API

Python package for interacting with IDM heatpump systems and related Home Assistant integrations.

## Documentation

- GitHub Pages: https://xerolux.github.io/idm-heatpump-api/
- GitHub Wiki: https://github.com/Xerolux/idm-heatpump-api/wiki
- Project Repository: https://github.com/Xerolux/idm-heatpump-api

The `docs/` directory is the single source of truth:
- GitHub Pages is deployed automatically from `docs/`.
- GitHub Wiki is synchronized automatically from `docs/`.

## Supported Devices (Current Status)

| Device | Firmware | Heating Circuits | Zone Modules | Status |
|-------|----------|------------|-------------|--------|
| IDM Navigator 10 | NAV10_20.23+ (2025) | up to 7 (A-G) | up to 10 (6 rooms each) | Confirmed |
| IDM Navigator 2.0 | all versions | up to 7 (A-G) | no | Confirmed |
| IDM Navigator Pro | all versions | up to 7 (A-G) | up to 10 (6 rooms each) | Confirmed |

**Note**: Zone modules on current hardware (including Navigator 10) support 6 rooms per module. Older documentation sometimes mentioned 8; the library defaults to 6 for accuracy.

## Requirements

- Modbus TCP must be enabled in the IDM controller (Settings → Building Management → Modbus TCP = On).
- Default port: `502`
- Default slave ID: `1`

## New in Navigator 10 Support

The library now fully covers the official 2025 Navigator 10 Modbus TCP specification, including:

- Heat sink / plate heat exchanger sensors (flow rate in l/min at 1072 — excellent for filter monitoring)
- Power limitation registers (4108 / 4112) for demand response / peak shaving
- Complete Booster A + B (second heat generator) monitoring
- Additional source pump faults and external pump demand control
- Groundwater temperatures and more cascade bivalence points
- All zone module rooms (6 rooms per module on current hardware)

## Installation

```bash
pip install idm-heatpump
```

## Contributing

Please open an issue or pull request for bug reports, improvements, and documentation updates.
