# Known Limitations

This page documents the boundaries of `idm-heatpump-api` so consumers know what
is intentionally unsupported and where to be careful.

## Unsupported protocol families

- **Navigator 1.0 / 1.7** is a separate protocol family. Its addresses must
  not be copied into the Navigator 2.0/10/Pro map and it is **not supported**.
- The optional web supplement is strictly **read-only**. There is no write path
  through the local HTTP / WebSocket interface.

## Documented logical range overlaps

The official Navigator 2.0/10 map contains documented logical range overlaps at
block boundaries (for example, humidity at `1392/count=2` and heating-circuit A
mode at `1393/count=1`). The library reads each overlapping data point using
its exact documented start address and size, and never shifts an official
address merely to eliminate a logical range overlap. See
[Register-Map Invariants](Register-Map-Invariants) for the full rules.

There is **no no-overlap invariant** — by design.

## EEPROM-sensitive registers

`EEPROM_SENSITIVE_ADDRESSES` contains 89 addresses that are persisted to
EEPROM on write and therefore have a limited number of write cycles. The
library throttles writes to these addresses; consumers should write them
sparingly and never in a tight loop.

## Cyclic GLT writes

The GLT demand temperature registers (`1696` / `1698`) must be re-written
cyclically (every 10 minutes) to stay active. Successful writes refresh an
in-memory heartbeat deadline. Consumers can inspect the state:

```python
client.get_active_cyclic_writes()    # name -> deadline monotonic timestamp
client.get_expired_cyclic_writes()   # names whose deadline has passed
client.reset_cyclic_write_state()    # clear on shutdown/reload
```

## Write safety

Writes are safety-sensitive. The library validates datatype, enum options,
min/max bounds, finiteness, and integer-vs-fractional values before sending,
and preserves EEPROM guards, cyclic-write rules, exact function codes, and
documented sentinels. The `allow_custom_register=True` escape hatch bypasses
**only** detected-model map membership; all other validation remains active.
Expose it only behind an explicit advanced-user risk acknowledgement.

## Model detection depends on raw captures

Auto-detection probes capability registers to determine the model, active
heating circuits, zone modules, solar, ISC, PV, and cascade. Status:

- **Navigator 10** (NAV10_20.23+): maintainer-confirmed.
- **Navigator 2.0 / Pro:** expected to work, but need broader raw detection
  captures and complete diagnostics. Detection may be incomplete on older or
  unusual firmware. Provide diagnostics via `get_diagnostics()` when reporting
  issues.

## Web supplement requires a PIN

The local web supplement requires a configured local network PIN. Without a
PIN, the factory helpers return `None` and only Modbus operation continues:

```python
from idm_heatpump import web_pin_configured, create_optional_navigator10_web_client

web_pin_configured(None)                       # False
create_optional_navigator10_web_client(h, None)  # returns None
```

## Local web transport is device-specific

- **Navigator 10** uses a local WebSocket on port `61220`.
- **Navigator 2.0** uses local HTTP with CSRF token handling.

These are reverse-engineered boundaries, not a published API. See
[Navigator Protocol Analysis](Navigator-Protocol-Analysis) for the validated
transport boundary and explicitly unsupported areas.

## Sentinel handling

Context-specific unavailable values are decoded using the documented datatype
and then interpreted as unavailable — they are never clamped or discarded at
the raw-byte level to hide a datatype/address error. See [Data Polling](Data-Update)
for how sentinels interact with batch validation.

## No implied affiliation

This project is an unofficial community project and is not affiliated with,
endorsed by, or connected to IDM Energiesysteme GmbH. All trademarks belong to
their respective owners.
