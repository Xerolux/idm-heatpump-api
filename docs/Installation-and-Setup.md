# Installation and Setup

This page covers installing the library, enabling Modbus TCP on the IDM
Navigator controller, and the developer setup for contributing to the library
itself.

For a usage walkthrough, continue to [Examples](Examples). For the full method
reference, see [Client Methods](Services).

## Requirements

- **Python 3.12 or newer.**
- An IDM Navigator **2.0**, **Pro**, or **10** controller.
- **Modbus TCP** enabled on the controller (see below).
- Network access from the machine running the library to the controller.

> Navigator 1.0/1.7 is a separate protocol family and is **not** supported.

## Enable Modbus TCP on the Navigator

1. Open the Navigator controller menu.
2. Navigate to **Settings → Building Management → Modbus TCP**.
3. Set **Modbus TCP = On**.
4. Note the controller **IP address**, **port** (default `502`), and
   **slave / unit ID** (default `1`).

The library defaults match the IDM defaults:

| Parameter | Default | Constant |
|-----------|---------|----------|
| Port | `502` | `DEFAULT_PORT` |
| Slave ID | `1` | `DEFAULT_SLAVE_ID` |
| Timeout (s) | `10.0` | `DEFAULT_TIMEOUT` |
| Max retries | `3` | `MAX_RETRIES` |
| Retry backoff base (s) | `0.5` | `RETRY_BACKOFF_BASE` |

## Install from PyPI

Talking to a heat pump with the built-in Modbus TCP transport — this is what
you want when using the library on its own:

```bash
pip install "idm-heatpump-api[pymodbus]"
```

With the optional local-web supplement (Navigator 10 WebSocket /
Navigator 2.0 HTTP, requires `aiohttp`):

```bash
pip install "idm-heatpump-api[web,pymodbus]"
```

Register maps, codecs and batching only, bringing your own transport — this is
how the Home Assistant integration uses the library:

```bash
pip install idm-heatpump-api
```

Since `2.0.0` the plain package installs no Modbus stack, so `IdmModbusClient`
raises an `ImportError` naming the `pymodbus` extra when it is missing. The
built-in transport is still there; it just is not a required dependency any
more.

## Minimal Program

```python
import asyncio
from idm_heatpump import IdmModbusClient, build_register_map

async def main():
    client = IdmModbusClient(host="192.168.1.100", port=502, slave_id=1)
    try:
        await client.connect()
        model_info = await client.detect_model()
        print(f"Detected: {model_info.model_name}")
        registers = build_register_map(model_info=model_info)
        values = await client.read_batch(list(registers.values()))
        for name, value in sorted(values.items()):
            print(f"  {name}: {value}")
    finally:
        await client.disconnect()

asyncio.run(main())
```

## Importing

Always import from the package root. The package root `__all__` list is the
public API contract and is protected by a snapshot test.

```python
from idm_heatpump import IdmModbusClient, build_register_map
```

Imports from submodules such as `idm_heatpump.client` or
`idm_heatpump.registers` are internal convenience imports and may change as the
library is reorganized.

## Optional: Local Web Supplement

The web supplement reads values that exist only in the local web interface
(for example flow rate, hot gas temperature, refrigerant pressure, board
temperature, and the software version). It is **read-only** and requires a
configured local network PIN.

```python
from idm_heatpump import create_optional_navigator10_web_client

web = create_optional_navigator10_web_client("192.168.1.100", pin="1234")
```

The factory returns `None` when no PIN is configured, so Modbus-only operation
continues without errors. See [Examples](Examples) and
[Navigator Protocol Analysis](Navigator-Protocol-Analysis) for details.

## Developer Setup

To contribute to the library itself:

```bash
git clone https://github.com/Xerolux/idm-heatpump-api.git
cd idm-heatpump-api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,test]"
```

Run the full local quality gate before pushing:

```bash
pytest                       # tests + coverage (fail-under 75)
ruff check .                 # lint
mypy                         # strict type checking
```

Additional developer notes:

- [MAINTENANCE.md](MAINTENANCE) — routine maintenance tasks.
- [RELEASE_PROCESS.md](RELEASE_PROCESS) — how a release is cut.
- [API Contract](API-Contract) — public compatibility contract.
- [Register-Map Invariants](Register-Map-Invariants) — mandatory rules before
  editing the register map.
