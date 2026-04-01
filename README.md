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
| IDM Navigator 2.0 | all versions | up to 7 (A-G) | no | Confirmed |
| IDM Navigator Pro | all versions | up to 7 (A-G) | up to 10 (8 rooms each) | Confirmed |

## Requirements

- Modbus TCP must be enabled in the IDM controller.
- Default port: `502`
- Default slave ID: `1`

## Installation

```bash
pip install idm-heatpump
```

## Contributing

Please open an issue or pull request for bug reports, improvements, and documentation updates.
