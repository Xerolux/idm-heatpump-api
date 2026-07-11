# Examples

Python usage patterns for `idm-heatpump-api`. See [Installation and Setup](Installation-and-Setup)
for install instructions and [Client Methods](Services) for the full method
reference.

## Connect, detect, and read

```python
import asyncio
from idm_heatpump import IdmModbusClient, build_register_map

async def main():
    client = IdmModbusClient("192.168.1.100")
    try:
        await client.connect()
        model_info = await client.detect_model()
        print(f"Detected: {model_info.model_name} (firmware {model_info.firmware_version})")
        print(f"Circuits: {model_info.active_heating_circuits}")
        print(f"Zone modules: {model_info.zone_modules}")
        print(f"Solar={model_info.has_solar} ISC={model_info.has_isc} "
              f"PV={model_info.has_pv} Cascade={model_info.has_cascade}")

        registers = build_register_map(model_info=model_info)
        values = await client.read_batch(list(registers.values()))
        for name, value in sorted(values.items()):
            reg = registers[name]
            unit = f" {reg.unit}" if reg.unit else ""
            print(f"  {name}: {value}{unit}")
    finally:
        await client.disconnect()

asyncio.run(main())
```

## Manual register map (no auto-detection)

If you know the active configuration up front, skip detection:

```python
from idm_heatpump import build_register_map

registers = build_register_map(
    circuits=["A", "B"],
    zone_modules=2,
    rooms_per_zone=4,
)
```

`circuits` must be letters A–G, `zone_modules` 0–10, `rooms_per_zone` 1–8.
Invalid values raise `ValueError`.

## Single register read / write

```python
from idm_heatpump import IdmModbusClient, get_register

client = IdmModbusClient("192.168.1.100")
await client.connect()

reg = get_register("dhw_setpoint", model_info=await client.detect_model())
current = await client.read_register(reg)
print("DHW setpoint:", current)

await client.write_register(reg, 48)
```

Key-based helpers resolve the register through the registry:

```python
await client.read_value("outdoor_temp")
await client.set_value("dhw_setpoint", 48)
```

## Validate a write without sending it

`set_value(..., dry_run=True)` and `simulate_write(...)` validate and encode a
write and return a `WriteSafetyResult` without touching the hardware. This is
useful for pre-flight checks and for showing users exactly what would be sent.

```python
plan = await client.set_value("dhw_setpoint", 48, dry_run=True)
print(plan.requested_value)      # 48
print(plan.encoded_registers)    # e.g. (48,)
print(plan.dry_run)              # True
print(plan.register.name)        # dhw_setpoint
```

## Advanced raw write escape hatch

`write_register(..., allow_custom_register=True)` skips detected-model map
membership for an explicitly constructed `RegisterDef`, but datatype, numeric,
and write-metadata validation still apply. Expose this only behind an explicit
advanced-user risk acknowledgement.

```python
from idm_heatpump import IdmModbusClient, RegisterDef, DataType, RegisterType

custom = RegisterDef(
    address=9999,
    datatype=DataType.UCHAR,
    name="custom_user_register",
    register_type=RegisterType.HOLDING,
    writable=True,
)
await client.write_register(custom, 1, allow_custom_register=True)
```

## Inspect model detection details

```python
model_info = await client.detect_model()
print(model_info.active_heating_circuits)   # e.g. ['A', 'B']
print(model_info.features)                  # {'heating_circuits', 'zone_modules', ...}
print(model_info.is_pro)                    # True when zone_modules > 0
print(model_info.firmware_version)          # e.g. 20.23
```

## Parallel Modbus + web polling

The web supplement is read-only and runs alongside the Modbus client. Poll
them in parallel, or start the web task a few milliseconds later if the
controller needs gentler pacing.

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
        modbus_values, web_data = await asyncio.gather(
            modbus.read_batch(list(registers.values())),
            web.read_data(),
        )

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

## Navigator 10 notifications and statistics

```python
from idm_heatpump import create_optional_navigator10_web_client

web = create_optional_navigator10_web_client("192.168.1.100", pin="1234")
if web is not None:
    await web.connect()
    notifications = await web.read_notifications()
    print(notifications.count)
    print(notifications.summary)

    stats = await web.read_statistics(statistic_type=1, period_type=2, prefix="heating")
    print(stats.simple_values)
    await web.close()
```

## Navigator 2.0 capabilities

```python
from idm_heatpump import create_optional_navigator20_web_client

web = create_optional_navigator20_web_client("192.168.1.100", pin="1234")
if web is not None:
    await web.connect()
    caps = web.capabilities()
    print(caps)   # {'web_data': ..., 'pv': ..., 'zones': ...}
    await web.close()
```

## Diagnostics and error context

```python
diag = client.get_diagnostics()
print(diag.navigator_type)
print(diag.modbus_connected)
print(diag.connection_suspect)
print(diag.permanently_failed_registers)
print(diag.batch_unsafe_registers)

ctx = client.get_last_error_context()
if ctx is not None:
    print(ctx.operation, ctx.address, ctx.error_type, ctx.message)
```

## Batch-safety quarantine

If an external plausibility check detects a grouped value that is syntactically
valid but wrong, quarantine the register so it is read individually for the
rest of the session:

```python
client.mark_batch_unsafe("humidity_sensor")
# or with a RegisterDef:
# client.mark_batch_unsafe(registers["humidity_sensor"])

print(client.get_batch_unsafe_registers())
```

## Cyclic GLT writes

Cyclic GLT demand registers must be refreshed periodically to stay active.
Successful writes update an in-memory heartbeat; consumers can detect stale
demands and clear state on reload or shutdown.

```python
print(client.get_active_cyclic_writes())    # name -> deadline monotonic ts
print(client.get_expired_cyclic_writes())   # names whose deadline passed
client.reset_cyclic_write_state()           # clear on shutdown/reload
```

## Error handling

```python
from idm_heatpump import (
    IdmModbusClient,
    IllegalAddressError,
    IdmWebError,
    IdmWebAuthenticationError,
)

try:
    await client.write_register(reg, 48)
except IllegalAddressError:
    print("Controller rejected the address")
except ValueError as exc:
    print("Validation rejected the value:", exc)
```

For the web clients, catch `IdmWebError` (or a specific subclass such as
`IdmWebAuthenticationError` / `IdmWebPinRejectedError` for a wrong PIN):

```python
try:
    web_data = await web.read_data()
except IdmWebAuthenticationError:
    print("PIN rejected")
except IdmWebError as exc:
    print("Web error:", exc)
```
