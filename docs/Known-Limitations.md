# Known Limitations

This page documents the boundaries of `idm-heatpump-api` so consumers know what
is intentionally unsupported and where to be careful.

## Unsupported protocol families

- **Navigator 1.0 / 1.7** is a separate protocol family, supported with
  its own read-only map (input blocks 1000-1088 and 1500-1524 from its
  official register table) plus a writable PV supplement (74/76/78/82 and
  the read-only power measurement 4122) that is included only when the
  detection probe at address 74 responded. Its addresses must never be
  copied into the Navigator 2.0/10/Pro map; the holding/coil blocks
  (2000+/3000+) stay unmapped because their per-register semantics are
  undocumented in the sources available.
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

One "unavailable" answer is not covered by any declared sentinel: a
temperature input whose sensor is not wired answers with uninitialized
controller memory. A Navigator 2.0 heating circuit without an iDM room sensor
reports about -327 °C on register 1364 (observed -327.33 °C and -327.22 °C;
idm-heatpump-hass issues #504 and #668) — a finite value that the official
tables do not bound, so range validation cannot catch it either.
`is_uninitialized_temperature()` classifies readings at or below
`UNINITIALIZED_TEMPERATURE_C` (-300 °C) as that memory garbage. Decoding is
unchanged: the value still flows through, and consumers decide what to
publish — the same contract as the declared sentinel sets.

## No implied affiliation

This project is an unofficial community project and is not affiliated with,
endorsed by, or connected to IDM Energiesysteme GmbH. All trademarks belong to
their respective owners.


## Diagnostic donations reviewed on 9 November 2026

Navigator 10 replies can explicitly report a circuit as unavailable using a
note-only `heatingcircuitDetail`. The parser distinguishes this confirmed shape
with `IdmWebHeatingCircuitUnavailableError` (a subclass of `IdmWebResponseError`);
unknown notes and malformed replies remain protocol errors. The request reader
rejects a note naming a different circuit. Consumers can skip the unavailable
circuit without inventing a value or discarding other successful circuit reads.
Synthetic regression fixtures reproduce the shape, not donated measurements.
Numeric setting parameters remain distinct from HTML setting sections.

Open evidence work: a donation declared as NAVIGATOR Pro contains additional
readable FC03/FC04 address pairs but no authenticated web data. Readability alone
does not establish register meaning or prove the physical controller identity.
Do not add or alter mappings from these words alone. Web login rejection remains
ambiguous between rejected credentials and an unsupported authentication flow;
the capture tool needs sanitized per-attempt diagnostics and a browser-login
comparison. No new #577-referenced evidence settles its remaining parser or
packed-register questions. Community firmware sightings remain channel-specific;
`NAV10_` and `T_NAV10_` must not be mixed.
