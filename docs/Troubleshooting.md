# Troubleshooting

This page covers the most common issues when using the library against an IDM
Navigator controller, plus the diagnostic hooks the library exposes. For Home
Assistant integration troubleshooting, see the
[integration repository](https://github.com/Xerolux/idm-heatpump-hass).

---

## "Cancel send, because not connected!" / noisy pymodbus logs

### Symptom

Repeated log entries like:

```
Logger: pymodbus.logging
Cancel send, because not connected!
>>>>> recv: 0xb 0x4 0x4 ... extra data:
>>>>> send: 0xb 0x4 0x0 0xec 0x0 0x2 0xb0 0x94
No response received after 3 retries, continue with next request
```

### Cause

The TCP connection between the library and the IDM Navigator drops during
operation. pymodbus logs every single Modbus frame (`>>>>> send/recv`) at DEBUG
level and connection breaks at ERROR level, so unstable connections flood the
log quickly.

The library catches connection breaks and reconnects automatically, so the
warnings are usually cosmetic — but they can indicate a real network problem.

### Fix

**1. Quiet the pymodbus logger.** The library ships a helper for consumers:

```python
from idm_heatpump import quiet_pymodbus_logging

quiet_pymodbus_logging("WARNING")  # suppresses the ">>>>> send/recv" flood
```

A Home Assistant consumer would instead set:

```yaml
logger:
  default: info
  logs:
    pymodbus.logging: warning
```

**2. Check the network.**

| Possible cause | What to check |
|----------------|---------------|
| Other Modbus clients (app, ioBroker, second HA instance) connect at the same time | Stop other clients; the Navigator often accepts only one TCP connection. |
| Wi-Fi link to the Navigator | Try a wired LAN connection. |
| Router/firewall kills idle TCP connections | Check router idle/timeout settings. |
| Navigator's Modbus server crashes internally | Restart the Navigator; check for a firmware update. |

**3. Force a reconnect.** If the client keeps operating on a suspect
connection, trigger a fresh one immediately:

```python
await client.force_reconnect()
```

The library also sets `connection_suspect=True` after `IdmConnectionError` or a
no-response `IdmTransportError` and automatically closes/reopens the socket on
the next retry.

---

## "Register X has failed N times. Marking as permanently failed."

A single register has failed to read several times in a row. This is normal for
optional registers that do not exist on the present hardware (for example
`firmware_version` on certain Navigator 10 firmwares).

If a genuinely available register is wrongly marked as permanently failed, reset
the tracking:

```python
client.reset_failed_registers()
```

To distinguish "explicitly rejected by the controller" from "failed
transiently", use `get_unsupported_registers()` — it returns only the names
rejected with Modbus exception code 2 ("Illegal Data Address"):

```python
print(client.get_unsupported_registers())
```

---

## Implausible values in batch reads

Some controllers occasionally return corrupt values inside large grouped
responses. The library validates every decoded value against the register's
declared enum options, numeric range, and sentinel metadata. When a grouped
value is implausible, it is re-read individually and validated before being
exposed, and the register is moved to the safe individual-read path for the
rest of the session.

Inspect affected registers with:

```python
diag = client.get_diagnostics()
print(diag.batch_unsafe_registers)
```

If an external plausibility check detects a grouped value that is syntactically
valid but wrong, quarantine the register:

```python
client.mark_batch_unsafe("humidity_sensor")
```

See [Data Polling](Data-Update) for the full recovery model.

---

## Wrong PIN / web supplement does not start

The local web supplement requires a configured local network PIN. The factory
helpers return `None` when no PIN is set, so Modbus-only operation continues:

```python
from idm_heatpump import web_pin_configured, create_optional_navigator10_web_client

print(web_pin_configured(None))   # False
web = create_optional_navigator10_web_client("192.168.1.100", None)  # returns None
```

A wrong PIN is raised as `IdmWebPinRejectedError` (subclass of
`IdmWebAuthenticationError`). Catch `IdmWebError` to cover the full web failure
surface:

```python
from idm_heatpump import IdmWebError, IdmWebAuthenticationError

try:
    data = await web.read_data()
except IdmWebAuthenticationError:
    print("PIN rejected")
except IdmWebError as exc:
    print("Web error:", exc)
```

See [Navigator Protocol Analysis](Navigator-Protocol-Analysis) for the
device-specific transport boundary.

---

## Collecting diagnostics for a bug report

Always attach a diagnostics snapshot and the last error context when reporting
an issue:

```python
diag = client.get_diagnostics()
ctx = client.get_last_error_context()

print(diag)
# IdmClientDiagnostics(navigator_type=..., modbus_connected=...,
#   firmware=..., last_error=..., permanently_failed_registers=...,
#   batch_unsafe_registers=..., connection_suspect=...)

print(ctx)
# ModbusErrorContext(operation=..., address=..., count=...,
#   register_type=..., error_type=..., message=..., attempt=...)
```

For model detection issues, also include the `IdmModelInfo`:

```python
model_info = await client.detect_model()
print(model_info)
```

---

## "It works in one tool but not here"

If another Modbus client (e.g. a phone app) holds the single TCP connection the
Navigator accepts, this library's requests will fail. Stop the other client and
retry. If problems persist, confirm the port (`502`) and slave ID (`1`) match
the controller settings.
