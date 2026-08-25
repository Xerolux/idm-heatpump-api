# IDM Heatpump API

[![PyPI version](https://img.shields.io/pypi/v/idm-heatpump-api.svg?style=for-the-badge)](https://pypi.org/project/idm-heatpump-api/)
[![PyPI downloads](https://img.shields.io/pypi/dm/idm-heatpump-api.svg?style=for-the-badge)](https://pypistats.org/packages/idm-heatpump-api)
[![Python versions](https://img.shields.io/pypi/pyversions/idm-heatpump-api.svg?style=for-the-badge)](https://pypi.org/project/idm-heatpump-api/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

[![GitHub Sponsors](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?style=for-the-badge&logo=tesla)](https://ts.la/sebastian564489)

An asynchronous Python library for communicating with **IDM Navigator heat pumps** (Navigator 2.0, Pro, and Navigator 10) over Modbus TCP.

This library is primarily designed to power the unofficial [IDM Heatpump Home Assistant custom integration](https://github.com/Xerolux/idm-heatpump-hass), but it can be used independently for any Python project that needs to monitor or control an IDM heat pump.

> **Documentation:**
> - GitHub Pages: https://xerolux.github.io/idm-heatpump-api/
> - GitHub Wiki: https://github.com/Xerolux/idm-heatpump-api/wiki
> - PyPI: https://pypi.org/project/idm-heatpump-api/
> - API contract: [docs/API-Contract.md](docs/API-Contract.md)
> - Register-map invariants: [docs/Register-Map-Invariants.md](docs/Register-Map-Invariants.md)
>
> The `docs/` directory is the single source of truth and is used for both GitHub Pages and Wiki sync.

## Features

* **Asynchronous:** Fully async operations using `pymodbus` with automatic reconnection.
* **Auto-Detection:** Probes registers to detect the controller model, active heating circuits, zone modules, solar, ISC, PV, and cascade.
* **Comprehensive Register Map:** 100+ registers covering temperatures, energy, status, heating circuits (A–G), zone modules, solar, ISC, cascade, boosters, heat-sink sensors, power limitation, and more.
* **Safe Batch Reads:** Grouping of exactly adjacent, non-overlapping register ranges (up to 40 registers per request) with automatic single-register fallback for implausible grouped values.
* **Resilient:** Configurable retries with adaptive exponential backoff, permanent-failure tracking for unavailable registers, and connection-suspect detection that forces a reconnect on dead sessions.
* **Write Support:** Safe register writes with datatype, enum, min/max and finiteness validation, EEPROM throttling, and cyclic-write heartbeats. Includes a `dry_run`/`simulate_write` path for validating without sending.
* **Optional Web Supplement:** Read-only access to local-web-only values (flow rate, hot gas, refrigerant pressure, board temperature, software version, …) via Navigator 10 WebSocket or Navigator 2.0 HTTP, including notifications and statistics.
* **Metadata-Rich:** Each register carries Home Assistant mapping fields plus source, source version, supported models, sentinel values, and verification metadata.
* **Typed:** Ships a `py.typed` marker and full inline type annotations.

## Supported Devices

| Device | Firmware | Heating Circuits | Zone Modules | Status |
|-------|----------|------------------|--------------|--------|
| IDM Navigator 10 | NAV10_20.23+ (2025) | up to 7 (A–G) | up to 10 (6 default, 8 configurable) | Maintainer-confirmed |
| IDM Navigator 2.0 | firmware-dependent | up to 7 (A–G) | firmware-dependent | Expected; needs broader raw detection captures |
| IDM Navigator Pro | firmware-dependent | up to 7 (A–G) | up to 10 (8 configurable) | Expected; needs complete diagnostics |

> Navigator 1.0/1.7 is a separate protocol family and is **not** supported.

## Requirements

- Modbus TCP must be enabled on the IDM controller (Settings → Building Management → Modbus TCP = On).
- Default port: `502` (`DEFAULT_PORT`)
- Default slave ID: `1` (`DEFAULT_SLAVE_ID`)
- Python 3.12+

## Installation

**Since `2.0.0` the plain package installs no Modbus stack.** Pick the line that
matches what you are building:

```bash
# Talking to a heat pump with the built-in Modbus TCP transport.
# This is what you want if you are using the library on its own.
pip install "idm-heatpump-api[pymodbus]"

# The same, plus the local-web supplement
# (Navigator 10 WebSocket / Navigator 2.0 HTTP).
pip install "idm-heatpump-api[web,pymodbus]"

# Register maps, codecs and batching only -- you bring your own transport.
# This is how the Home Assistant integration uses the library.
pip install idm-heatpump-api
```

Without the `pymodbus` extra, `IdmModbusClient(host=...)` raises an `ImportError`
naming the extra: the built-in transport is still there, it just is not a
required dependency any more. Everything else — register definitions, decoding,
model detection, write safety — works with no extra at all.

### Upgrading from `1.x`

You do **not** need to stay on `1.0.3`. `pip install "idm-heatpump-api[pymodbus]"`
gives you what `1.0.3` gave you. Two things change:

| `1.x` | `2.x` |
|---|---|
| `pip install idm-heatpump-api` | `pip install "idm-heatpump-api[pymodbus]"` |
| `except ModbusException` | `except IdmModbusError` |

`IdmModbusError` is the base of the library's own hierarchy
(`IdmConnectionError`, `IdmTransportError`, `IdmDeviceError`,
`IllegalAddressError`), so a `pymodbus` import disappears from your code
entirely. Register addresses, datatypes and the wire protocol are unchanged.

## Basic Usage

```python
import asyncio
from idm_heatpump import IdmModbusClient, build_register_map

async def main():
    client = IdmModbusClient(host="192.168.1.100", port=502, slave_id=1)

    try:
        await client.connect()

        # Auto-detect model and capabilities
        model_info = await client.detect_model()
        print(f"Detected: {model_info.model_name} (firmware {model_info.firmware_version})")
        print(f"Circuits: {model_info.active_heating_circuits}")
        print(f"Solar: {model_info.has_solar}, ISC: {model_info.has_isc}")

        # Build register map based on detected model
        registers = build_register_map(model_info=model_info)

        # Read all registers in efficient batches
        values = await client.read_batch(list(registers.values()))

        for name, value in sorted(values.items()):
            reg = registers[name]
            unit = f" {reg.unit}" if reg.unit else ""
            print(f"  {name}: {value}{unit}")

        # Write a register (e.g. set DHW target temperature)
        if "dhw_setpoint" in registers:
            await client.write_register(registers["dhw_setpoint"], 48)

    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
```

## Advanced Usage

The library provides fine-grained control for advanced scenarios:

- `build_register_map(circuits=["A", "B"], zone_modules=2, rooms_per_zone=4)`: Manual register map without auto-detection.
- `get_heating_circuit_registers("A")`: Registers for a single heating circuit.
- `get_zone_module_registers(zone_index=1, room_count=6)`: Registers for a single zone module.
- `client.read_value("outdoor_temp")` / `client.set_value("dhw_setpoint", 48)`: Key-based read/write helpers (resolve via the registry).
- `client.set_value("dhw_setpoint", 48, dry_run=True)`: Validate and encode a write **without sending** it. Returns a `WriteSafetyResult`.
- `client.simulate_write(reg, value, dry_run=True)`: Lower-level validation/encoding of a `RegisterDef` or key; also returns `WriteSafetyResult`.
- `client.write_register(custom_reg, value, allow_custom_register=True)`: Explicit advanced escape hatch for user-authorized raw writes. Model-map membership is skipped, but datatype and value-safety validation remains active.
- `client.probe_register(address=1850, count=2)`: Probe a single register without affecting failure tracking.
- `client.force_reconnect()`: Hard-close the current TCP connection and open a fresh one.
- `client.get_diagnostics()`: Return an `IdmClientDiagnostics` snapshot (navigator type, connection state, firmware, last error, permanently-failed and batch-unsafe registers, connection-suspect flag).
- `client.get_last_error_context()` / `client.clear_last_error_context()`: Inspect the last structured `ModbusErrorContext` (operation, address, count, register type, error type, message, attempt).
- `client.reset_failed_registers()`: Retry permanently failed registers.
- `client.get_unsupported_registers()`: Return the register names explicitly rejected by the controller with Modbus exception code 2 ("Illegal Data Address"). Useful for consumers that maintain their own polling skip-list; it never includes registers that merely failed repeatedly for a transient reason.
- `client.get_batch_unsafe_registers()` / `client.mark_batch_unsafe(reg)`: Registers that produced an invalid grouped value are read individually for the rest of the client session. `mark_batch_unsafe` lets a consumer quarantine a register when an external plausibility check detects a valid-looking but incorrect grouped value.
- `client.get_active_cyclic_writes()` / `client.get_expired_cyclic_writes()` / `client.reset_cyclic_write_state()`: Track cyclic GLT write heartbeats. Successful writes to cyclic GLT registers refresh an in-memory deadline; consumers can detect stale external demands and clear the state on reload or shutdown.
- `client.decode_value(registers, reg)` / `client.encode_value(value, reg)`: Public codec helpers (`ModbusCodec` mixin) for manual (de)serialization.

Register metadata for HA integration mapping:

```python
reg = registers["compressor_status_1"]
print(reg.binary)                # True -> BinarySensor
print(reg.writable)              # False
print(reg.write_only)            # False
print(reg.write_class)           # forbidden / volatile / cyclic / eeprom / write_only
print(reg.enabled_by_default)    # True
print(reg.state_class)           # None (or "measurement", "total_increasing")
print(reg.icon)                  # None (or "mdi:thermometer")
print(reg.exclude_from_write)    # None (or {255})
print(reg.source)                # official_idm_modbus
print(reg.source_version)        # source document / verification version
print(reg.supported_models)      # expected Navigator models
print(reg.sentinel_values)       # context-specific unavailable values
print(reg.last_verified)         # optional hardware verification label
```

## Optional Local Web Supplement

Some IDM values are available in the local web interface but not in the published Modbus map, for example flow rate, hot gas temperature, refrigerant pressure values, board temperature, central-unit battery voltage, and the controller software version. The optional `idm_heatpump.web` module is read-only and is intended to run alongside the Modbus client.

See [`docs/Navigator-Protocol-Analysis.md`](docs/Navigator-Protocol-Analysis.md) for the validated local transport boundary, reverse-engineering evidence and explicitly unsupported protocol areas.

Two transports are supported:

- **Navigator 10** — local WebSocket on port `61220` via `IdmNavigator10WebClient` (created through `create_optional_navigator10_web_client()`). Supports `read_data()`, `read_statistics()`, and `read_notifications()`.
- **Navigator 2.0** — local HTTP with CSRF token handling via `IdmNavigator20WebClient` (created through `create_optional_navigator20_web_client()`). Supports `read_data()`, `read_extra_data()`, and `capabilities()`.

If the user does not configure a local network PIN, consumers should not create a web client. Both factories return `None` for `None`, empty, or whitespace-only PIN values so Modbus-only operation can continue without errors. Use `web_pin_configured(pin)` to check explicitly.

A Home Assistant consumer should poll Modbus and web data in parallel, or start the web poll a few milliseconds after the Modbus poll if the controller needs gentler pacing:

```python
import asyncio
from idm_heatpump import (
    IdmModbusClient,
    build_register_map,
    create_optional_navigator10_web_client,
)

async def main():
    modbus = IdmModbusClient("192.168.1.100")
    web = create_optional_navigator10_web_client("192.168.1.100", pin="1234")

    await modbus.connect()
    model_info = await modbus.detect_model()
    registers = build_register_map(model_info=model_info)

    if web is None:
        modbus_values = await modbus.read_batch(list(registers.values()))
        web_data = None
    else:
        modbus_task = modbus.read_batch(list(registers.values()))
        web_task = web.read_data()
        modbus_values, web_data = await asyncio.gather(modbus_task, web_task)

    if web_data is not None:
        print(web_data.navigator_version)
        print(web_data.software_version)
        print(web_data.heatpump_model)
        print(web_data.get_numeric("flowmeter"))

    if web is not None:
        await web.close()
    await modbus.disconnect()

asyncio.run(main())
```

Web errors are raised as subclasses of `IdmWebError` (e.g. `IdmWebConnectionError`, `IdmWebAuthenticationError`/`IdmWebPinRejectedError`, `IdmWebCsrfError`, `IdmWebProtocolError`/`IdmWebWebSocketError`/`IdmWebResponseError`, `IdmWebTimeoutError`, `IdmWebDependencyError`). Short legacy aliases (`AuthenticationError`, `ConnectionError`, `TimeoutError`, `CsrfError`, `WebSocketError`, `ProtocolError`, `PinRejectedError`) remain available but the `IdmWeb*` names are preferred. The recommended web scan interval is `RECOMMENDED_WEB_SCAN_INTERVAL` (30 s).

## Public API

Supported consumers should import from the package root:

```python
from idm_heatpump import IdmModbusClient, build_register_map
```

The public API is the package root `__all__` contract, protected by a snapshot test (`tests/test_public_api.py`). It currently includes:

- **Client and metadata types:** `IdmModbusClient`, `IdmModelInfo`, `RegisterDef`, `DataType`, `RegisterType`, `WriteClass`, `WriteSafetyResult`, `ModbusErrorContext`, `ModbusCodec`, `IdmClientDiagnostics`, `FeatureFlags`, `IllegalAddressError`, `AdaptiveBackoff`, `PollRateLimiter`, `quiet_pymodbus_logging`
- **Register builders and registry:** `build_register_map`, `get_all_registers`, `get_register`, `get_register_registry`, `get_detection_registers`, `get_heating_circuit_registers`, `get_zone_module_registers`, `RegisterRegistry`, `CORE_REGISTERS`
- **Optional web supplement:** `IdmNavigator10WebClient`, `IdmNavigator20WebClient`, `create_optional_navigator10_web_client`, `create_optional_navigator20_web_client`, `web_pin_configured`, `IdmWebData`, `IdmWebValue`, `IdmWebValueDescription`, `IdmWebNotifications`, `IdmWebNotification`, `IdmWebDiagnostics`, `WEB_VALUE_DESCRIPTIONS`, `RECOMMENDED_WEB_SCAN_INTERVAL`, `IdmWebError`, `IdmWebDependencyError`, `IdmWebConnectionError`, `IdmWebTimeoutError`, `IdmWebAuthenticationError`, `IdmWebPinRejectedError`, `IdmWebCsrfError`, `IdmWebProtocolError`, `IdmWebWebSocketError`, `IdmWebResponseError`, and the legacy aliases `AuthenticationError`, `PinRejectedError`, `CsrfError`, `ConnectionError`, `TimeoutError`, `WebSocketError`, `ProtocolError`
- **Option maps:** `SYSTEM_MODE_OPTIONS`, `CIRCUIT_MODE_OPTIONS`, `ROOM_MODE_OPTIONS`, `ZONE_MODULE_MODE_OPTIONS`, `ACTIVE_HC_MODE_OPTIONS`, `SOLAR_MODE_OPTIONS`, `SMART_GRID_OPTIONS`, `ISC_MODE_OPTIONS`, `HP_OPERATING_MODE_OPTIONS`, `BIVALENCE_STATE_OPTIONS`, `BOOSTER_FAULT_OPTIONS`, `EVU_LOCK_OPTIONS`, `VARIABLE_INPUT_OPTIONS`
- **Model, feature, and connection constants:** `MODEL_NAVIGATOR_20`, `MODEL_NAVIGATOR_PRO`, `MODEL_NAVIGATOR_10`, `MODEL_UNKNOWN`, `MODEL_DETECTION_TIMEOUT`, `MODEL_DETECTION_MAX_RETRIES`, `FEATURE_HEATING_CIRCUITS`, `FEATURE_ZONE_MODULES`, `FEATURE_SOLAR`, `FEATURE_ISC`, `FEATURE_PV`, `FEATURE_CASCADE`, `HEATING_CIRCUIT_LETTERS`, `MAX_HEATING_CIRCUITS`, `MAX_ZONE_MODULES`, `MAX_ROOMS_PER_ZONE`, `DEFAULT_PORT`, `DEFAULT_SLAVE_ID`, `DEFAULT_TIMEOUT`, `MAX_RETRIES`, `RETRY_BACKOFF_BASE`, `EEPROM_SENSITIVE_ADDRESSES`

The package ships a `py.typed` marker so type checkers can consume its inline type annotations.

Imports from submodules such as `idm_heatpump.client` or `idm_heatpump.registers` are internal convenience imports and may change as the library is reorganized.

## Navigator 10 Support

The library fully covers the official 2025 Navigator 10 Modbus TCP specification, including:

- Heat sink / plate heat exchanger sensors (flow rate in l/min at 1072)
- Power limitation registers (4108 / 4112) for demand response / peak shaving
- Complete Booster A + B (second heat generator) monitoring
- Additional source pump faults and external pump demand control
- Groundwater temperatures and more cascade bivalence points
- Up to 8 configurable rooms per zone module (6 is the current Navigator 10 default)
- PV / energy management, solar thermal, and ISC (Intelligent Surface Cooling)
- Cascade temperatures and bivalence points

## Contributing

Please open an issue or pull request for bug reports, improvements, and documentation updates. See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/Contributing (2).md](docs/Contributing%20%282%29.md) for details.

## License

MIT License — see [LICENSE](LICENSE).

---

## Support

This library is developed in my spare time. If you find it useful, consider supporting:

[![GitHub Sponsors](https://img.shields.io/github/sponsors/xerolux?logo=github&style=for-the-badge&color=blue)](https://github.com/sponsors/xerolux)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-xerolux-blue?logo=ko-fi&style=for-the-badge)](https://ko-fi.com/xerolux)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-xerolux-yellow?logo=buy-me-a-coffee&style=for-the-badge)](https://www.buymeacoffee.com/xerolux)
[![PayPal](https://img.shields.io/badge/PayPal-xerolux-blue?logo=paypal&style=for-the-badge)](https://paypal.me/xerolux)
[![Tesla Referral](https://img.shields.io/badge/Tesla-Referral-red?style=for-the-badge&logo=tesla)](https://ts.la/sebastian564489)

- Star the repository on GitHub
- [Report bugs](https://github.com/Xerolux/idm-heatpump-api/issues)
- Share with other IDM heat pump owners

---

## Disclaimer

This project is an **unofficial community project** and is not affiliated with, endorsed by, or connected to IDM Energiesysteme GmbH.

All trademarks, logos, and product names (e.g., "IDM", "Navigator") are property of their respective owners. The logos and images used are solely for identifying the compatible device and are not used commercially.

This project is provided without any warranty. Use at your own risk — especially when writing Modbus registers.

IDM Energiesysteme GmbH has neither authorized nor endorsed this project.
