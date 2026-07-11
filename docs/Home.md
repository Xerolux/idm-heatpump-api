# IDM Heatpump API Wiki

[![PyPI version](https://img.shields.io/pypi/v/idm-heatpump-api.svg)](https://pypi.org/project/idm-heatpump-api/)
[![Python versions](https://img.shields.io/pypi/pyversions/idm-heatpump-api.svg)](https://pypi.org/project/idm-heatpump-api/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue)](LICENSE)

Welcome to the documentation for **idm-heatpump-api**, an asynchronous Python
library for communicating with **IDM Navigator heat pumps** (Navigator 2.0,
Navigator Pro, and Navigator 10) over Modbus TCP.

The library powers the unofficial
[IDM Heatpump Home Assistant custom integration](https://github.com/Xerolux/idm-heatpump-hass),
but it can be used by any Python project that needs to monitor or control an
IDM heat pump.

## Quick Start

```bash
pip install idm-heatpump-api
```

```python
import asyncio
from idm_heatpump import IdmModbusClient, build_register_map

async def main():
    client = IdmModbusClient("192.168.1.100")
    await client.connect()
    model_info = await client.detect_model()
    registers = build_register_map(model_info=model_info)
    values = await client.read_batch(list(registers.values()))
    for name, value in sorted(values.items()):
        print(f"{name}: {value}")
    await client.disconnect()

asyncio.run(main())
```

See [Installation and Setup](Installation-and-Setup) and [Examples](Examples)
for the full walkthrough.

## Documentation Index

| Page | What it covers |
|------|----------------|
| [Installation and Setup](Installation-and-Setup) | Requirements, install, Modbus setup, developer setup |
| [Examples](Examples) | Python usage patterns: read, write, detect, web supplement, error handling |
| [Client Methods](Services) | Full method reference for `IdmModbusClient` and the web clients |
| [Data Polling](Data-Update) | Batch reads, fallback, retries, failure tracking, polling guidance |
| [Supported Devices](Supported-Devices) | Navigator 2.0 / Pro / 10 matrix and feature-gated register groups |
| [Known Limitations](Known-Limitations) | Unsupported protocols, overlaps, EEPROM, cyclic writes, web read-only |
| [Modbus Register](Modbus-Register) | Full register map reference |
| [Register Metadata](Register-Metadata) | `RegisterDef` fields, units, `state_class`, write classes |
| [Troubleshooting](Troubleshooting) | Connection issues, log noise, diagnostics, common pitfalls |
| [API Contract](API-Contract) | Public compatibility contract for consumers and maintainers |
| [Register-Map Invariants](Register-Map-Invariants) | Mandatory rules for editing the register map |
| [Navigator Protocol Analysis](Navigator-Protocol-Analysis) | Local web transport boundary and reverse-engineering evidence |
| [Firmware Compatibility](firmware_compatibility) | Firmware notes and references |

## Other Entry Points

- **Repository:** https://github.com/Xerolux/idm-heatpump-api
- **PyPI:** https://pypi.org/project/idm-heatpump-api/
- **GitHub Pages:** https://xerolux.github.io/idm-heatpump-api/
- **Changelog:** [CHANGELOG.md](https://github.com/Xerolux/idm-heatpump-api/blob/main/CHANGELOG.md)

> This wiki is synchronized automatically from the `docs/` folder in the
> repository. Edits should be made there, not directly in the wiki.
