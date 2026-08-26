# Data Polling

This page describes how the library reads data from the controller, how it
recovers from implausible or rejected values, and the retry/reconnect model.
See [Client Methods](Services) for the method signatures and [Examples](Examples)
for copy-paste snippets.

All communication is **local Modbus TCP** — there is no cloud connection.

## Batch reads

`read_batch()` is the primary read path:

- Registers are grouped in a single pass by `(register_type, address)`.
- Each group spans exactly adjacent, non-overlapping addresses — never across
  gaps and never across overlapping logical data points (see
  [Register-Map Invariants](Register-Map-Invariants)).
- A single Modbus request reads up to `max_group_size` registers (default 40).
- All entities share one read per polling cycle, minimizing network requests.

## Implausible-value recovery

Some controllers occasionally return corrupt values inside large grouped
responses. The library validates every decoded value against the register's
declared enum options, numeric range, and sentinel metadata:

1. If a grouped value is implausible, the register is re-read individually.
2. The individual value is validated before being exposed.
3. If the individual value is valid, it is returned and the register stays on
   the safe individual-read path for the rest of the session.
4. The affected register names are exposed via `get_batch_unsafe_registers()`
   and `IdmClientDiagnostics.batch_unsafe_registers`.

Consumers can quarantine a register themselves when an external plausibility
check detects a grouped value that is syntactically valid but wrong:

```python
client.mark_batch_unsafe("humidity_sensor")
```

This is session-local and does not persist across client instances.

## Unsupported-register tracking

When the controller rejects an address with Modbus exception code 2
("Illegal Data Address"), the register is recorded as unsupported:

- `get_unsupported_registers()` returns the sorted tuple of explicitly
  rejected register names.
- It never includes registers that merely failed repeatedly for a transient
  reason.
- `reset_failed_registers()` clears the tracking so they can be retried.

Consumers that maintain their own polling skip-list can use this to avoid
futile requests.

## Permanently failed registers

Registers that fail repeatedly after retries are marked permanently failed and
are skipped by subsequent `read_register()` / `read_batch()` calls until
`reset_failed_registers()` is invoked. A successful individual read resets the
transient failure counter, so intermittent errors cannot permanently disable a
working register.

## Retry and reconnect model

- Each command is retried up to `max_retries` (default `MAX_RETRIES = 3`).
- The backoff uses adaptive exponential growth (`RETRY_BACKOFF_BASE = 0.5`).
- `TimeoutError` (including `asyncio.TimeoutError`) is treated as a retryable
  transport error — a slow or unresponsive controller no longer bypasses the
  retry loop.
- `IdmConnectionError` and no-response `IdmTransportError` failures mark the
  connection as suspect: the potentially stale TCP socket is closed, a
  reconnect is attempted, and the interrupted request is retried instead of
  reusing a dead session.
- Exhausted transport and no-response failures from grouped and individual
  fallback reads are propagated rather than treated as register-specific
  errors, so valid registers are not disabled.
- The connection-suspect flag (`IdmClientDiagnostics.connection_suspect`)
  indicates the client wants a fresh connection; consumers can trigger it
  immediately with `force_reconnect()`.

## Sentinel values

Context-specific unavailable values (for example `-1.0` for an unused heating
circuit's flow temperature, or hardware-verified sentinels like `255` at
specific capability registers) are recorded in each register's
`sentinel_values` metadata. These are decoded using the documented datatype
and then interpreted as "unavailable" — they are never clamped or discarded at
the raw-byte level to hide a datatype/address error.

## Polling guidance for consumers

- **Modbus poll interval:** choose based on the use case. 10–30 seconds is a
  good default for active monitoring; 60+ seconds for quieter systems.
- **Web poll interval:** the recommended interval is
  `RECOMMENDED_WEB_SCAN_INTERVAL` (30 seconds). Poll Modbus and web in
  parallel, or start the web task a few milliseconds later if the controller
  needs gentler pacing.
- **Writes:** EEPROM-sensitive registers are throttled (write sparingly). Cyclic
  GLT demand registers must be re-written periodically (every 10 minutes) to
  stay active — see [Known Limitations](Known-Limitations).
