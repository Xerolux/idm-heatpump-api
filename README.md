# IDM Heatpump API

[![PyPI](https://img.shields.io/pypi/v/idm-heatpump?style=for-the-badge&logo=pypi&logoColor=white)](https://pypi.org/project/idm-heatpump/)
[![Python](https://img.shields.io/pypi/pyversions/idm-heatpump?style=for-the-badge&logo=python&logoColor=white)](https://pypi.org/project/idm-heatpump/)
[![License: MIT](https://img.shields.io/github/license/Xerolux/idm-heatpump-api?style=for-the-badge)](LICENSE)
[![GitHub Release](https://img.shields.io/github/v/release/Xerolux/idm-heatpump-api?style=for-the-badge&logo=github)](https://github.com/Xerolux/idm-heatpump-api/releases)

[![GitHub Sponsors](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

**Official Python library** for communicating with IDM Navigator heat pumps (2.0, Pro, and Navigator 10) over Modbus TCP.

This package is published on PyPI as `idm-heatpump` and is the core dependency for the [Home Assistant integration](https://github.com/Xerolux/idm-heatpump-hass).

```bash
pip install idm-heatpump
```

---

## Documentation

- GitHub Pages: https://xerolux.github.io/idm-heatpump-api/
- GitHub Wiki: https://github.com/Xerolux/idm-heatpump-api/wiki
- Project Repository: https://github.com/Xerolux/idm-heatpump-api
- PyPI: https://pypi.org/project/idm-heatpump/

The `docs/` directory is the single source of truth:
- GitHub Pages is deployed automatically from `docs/`.
- GitHub Wiki is synchronized automatically from `docs/`.

## Supported Devices

| Device | Firmware | Heating Circuits | Zone Modules | Status |
|-------|----------|------------|-------------|--------|
| IDM Navigator 10 | NAV10_20.23+ (2025) | up to 7 (A-G) | up to 10 (6 rooms each) | Confirmed |
| IDM Navigator 2.0 | all versions | up to 7 (A-G) | no | Confirmed |
| IDM Navigator Pro | all versions | up to 7 (A-G) | up to 10 (6 rooms each) | Confirmed |

**Note**: Zone modules on current hardware (including Navigator 10) support 6 rooms per module. Older documentation sometimes mentioned 8; the library defaults to 6 for accuracy.

## Requirements

- Modbus TCP must be enabled in the IDM controller (Settings -> Building Management -> Modbus TCP = On).
- Default port: `502`
- Default slave ID: `1`

## Navigator 10 Support

The library fully covers the official 2025 Navigator 10 Modbus TCP specification, including:

- Heat sink / plate heat exchanger sensors (flow rate in l/min at 1072)
- Power limitation registers (4108 / 4112) for demand response / peak shaving
- Complete Booster A + B (second heat generator) monitoring
- Additional source pump faults and external pump demand control
- Groundwater temperatures and more cascade bivalence points
- All zone module rooms (6 rooms per module on current hardware)
- PV / energy management, solar thermal, and ISC (Intelligent Surface Cooling)
- Cascade temperatures and bivalence points

## Installation

```bash
pip install idm-heatpump
```

## Contributing

Please open an issue or pull request for bug reports, improvements, and documentation updates.

## Support

This library is developed in my spare time. If you find it useful, consider supporting:

[![GitHub Sponsors](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?logo=tesla&style=for-the-badge)](https://ts.la/sebastian564489)

- Star the repository on GitHub
- [Report bugs](https://github.com/Xerolux/idm-heatpump-api/issues)
- Share with other IDM heat pump owners

---

## Disclaimer

This project is an **unofficial community project** and is not affiliated with, endorsed by, or connected to IDM Energiesysteme GmbH.

All trademarks, logos, and product names (e.g., "IDM", "Navigator") are property of their respective owners. The logos and images used are solely for identifying the compatible device and are not used commercially.

This project is provided without any warranty. Use at your own risk — especially when writing Modbus registers.

IDM Energiesysteme GmbH has neither authorized nor endorsed this project.
