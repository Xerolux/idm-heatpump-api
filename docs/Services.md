# Client Methods

This page is the structured reference for the public methods of
`IdmModbusClient` and the optional web clients. The name "Services" is kept
only for stable wiki links — the content describes the **library API**, not
Home Assistant services.

For copy-paste examples, see [Examples](Examples). For the polling model
behind batch reads and fallbacks, see [Data Polling](Data-Update).

## IdmModbusClient

### Construction

```python
IdmModbusClient(
    host: str,
    port: int = 502,           # DEFAULT_PORT
    slave_id: int = 1,         # DEFAULT_SLAVE_ID
    timeout: float = 10.0,     # DEFAULT_TIMEOUT
    max_retries: int = 3,      # MAX_RETRIES
    *,
    pymodbus_retries: int = 0,
    max_group_size: int = 40,
)
```

Validates a non-empty `host`, `port` in 1–65535, `slave_id` in 1–247,
`max_retries >= 1`, `pymodbus_retries >= 0`, and `max_group_size >= 1`.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `host` | `str` | Configured host. |
| `port` | `int` | Configured port. |
| `is_connected` | `bool` | Whether the underlying TCP client is connected. |
| `model_info` | `IdmModelInfo \| None` | Result of the last `detect_model()`, if any. |
| `model_name` | `str` | Navigator model name; falls back to `MODEL_NAVIGATOR_20` when unknown. |

### Connection

| Method | Description |
|--------|-------------|
| `async connect() -> None` | Open the TCP connection. |
| `async disconnect() -> None` | Close the TCP connection. |
| `async force_reconnect() -> None` | Hard-close the current connection and open a fresh one. Public hook for consumers to trigger an immediate reconnect after repeated failures. Safe to call when no connection exists yet; clears the connection-suspect flag. |

### Model detection and probing

| Method | Description |
|--------|-------------|
| `async detect_model(*, read_firmware: bool = True) -> IdmModelInfo` | Probe registers to detect the model, active heating circuits, zone modules, solar, ISC, PV, and cascade. Optionally reads the firmware version. |
| `async probe_register(address: int, count: int = 1, *, max_retries: int \| None = None, timeout: float \| None = None) -> list[int] \| None` | Read raw register words without affecting failure tracking. Returns `None` when the controller rejects the address. |

### Reading

| Method | Description |
|--------|-------------|
| `async read_register(reg: RegisterDef) -> Any` | Read and decode a single register. Respects the permanently-failed set. |
| `async read_value(key: str) -> Any` | Read and decode a single register by registry key/name. |
| `async read_batch(register_list: list[RegisterDef]) -> dict[str, Any]` | Read many registers in efficient grouped batches (up to `max_group_size` adjacent registers). Implausible grouped values are re-read individually and validated. |

### Writing

| Method | Description |
|--------|-------------|
| `async write_register(reg: RegisterDef, value: Any, *, allow_custom_register: bool = False) -> None` | Validate, encode, and write a single register. `allow_custom_register=True` skips detected-model map membership for an explicitly constructed register; datatype, numeric, and write-metadata validation still apply. Expose this only behind an explicit advanced-user risk acknowledgement. |
| `async set_value(key: str, value: Any, *, dry_run: bool = False) -> WriteSafetyResult` | Safe key-based write. `dry_run=True` validates and encodes without sending. |
| `simulate_write(reg: RegisterDef \| str, value: Any, *, dry_run: bool = True, allow_custom_register: bool = False) -> WriteSafetyResult` | Validate and encode a write without necessarily sending it. `reg` may be a `RegisterDef` or a registry key. |

### Codec

| Method | Description |
|--------|-------------|
| `decode_value(registers: list[int], reg: RegisterDef) -> Any` | Decode raw words to a Python value for the given register datatype. |
| `encode_value(value: Any, reg: RegisterDef) -> list[int]` | Encode a Python value to raw words for the given register datatype. |

### Diagnostics and state

| Method | Description |
|--------|-------------|
| `get_diagnostics() -> IdmClientDiagnostics` | Snapshot: `navigator_type`, `modbus_connected`, `firmware`, `last_error`, `permanently_failed_registers`, `batch_unsafe_registers`, `connection_suspect`. |
| `get_last_error_context() -> ModbusErrorContext \| None` | Last structured error: `operation`, `address`, `count`, `register_type`, `error_type`, `message`, `attempt`. |
| `clear_last_error_context() -> None` | Clear the last error context. |
| `get_unsupported_registers() -> tuple[str, ...]` | Sorted register names explicitly rejected by the controller with Modbus exception code 2 ("Illegal Data Address"). Never includes registers that only failed transiently. |
| `get_batch_unsafe_registers() -> tuple[str, ...]` | Sorted register names whose grouped response violated declared metadata; these are read individually for the rest of the session. |
| `mark_batch_unsafe(*registers: RegisterDef \| str) -> None` | Consumer-driven quarantine for device-specific registers whose grouped value is syntactically valid but wrong. Session-local; does not persist across client instances. |
| `reset_failed_registers() -> None` | Retry permanently failed registers. |

### Cyclic-write heartbeat

| Method | Description |
|--------|-------------|
| `get_active_cyclic_writes() -> dict[str, float]` | Map of cyclic-register name to its next deadline monotonic timestamp. |
| `get_expired_cyclic_writes() -> set[str]` | Cyclic registers whose deadline has passed. |
| `reset_cyclic_write_state(reg: RegisterDef \| None = None) -> None` | Clear cyclic-write state for one register or all. Call on reload or shutdown. |
| `reset_write_throttle(reg: RegisterDef \| None = None) -> None` | Clear the EEPROM throttle for one register or all. |

## Supporting types

### `IdmModelInfo`

Mutable dataclass returned by `detect_model()`.

| Field | Type |
|-------|------|
| `model_name` | `str` |
| `active_heating_circuits` | `list[str]` |
| `zone_modules` | `int` |
| `has_solar` | `bool` |
| `has_isc` | `bool` |
| `has_pv` | `bool` |
| `has_cascade` | `bool` |
| `features` | `set[str]` |
| `firmware_version` | `float \| None` |

Property `is_pro` returns `True` when `zone_modules > 0`.

### `RegisterDef`

Mutable dataclass describing one register. See [Register Metadata](Register-Metadata)
for the full field list and HA-mapping notes. Key fields: `address`,
`datatype`, `name`, `unit`, `writable`, `min_val`, `max_val`, `enum_options`,
`multiplier`, `register_type`, `eeprom_sensitive`, `cyclic_required`,
`binary`, `enabled_by_default`, `state_class`, `icon`, `write_only`,
`exclude_from_write`, `source`, `source_version`, `supported_models`,
`sentinel_values`, `last_verified`, computed `size`, and derived `write_class`.

### Enums

- `DataType`: `FLOAT`, `UCHAR`, `INT8`, `INT16`, `UINT16`, `BOOL`, `BITFLAG`
- `RegisterType`: `INPUT`, `HOLDING`
- `WriteClass`: `FORBIDDEN`, `VOLATILE`, `CYCLIC`, `EEPROM`, `WRITE_ONLY`
  (derived from `writable` / `write_only` / `cyclic_required` / `eeprom_sensitive`).

### Result / context dataclasses

- `WriteSafetyResult` (frozen): `register`, `requested_value`, `encoded_registers: tuple[int, ...]`, `dry_run`.
- `IdmClientDiagnostics` (frozen): see `get_diagnostics()` above.
- `ModbusErrorContext` (frozen): see `get_last_error_context()` above.

## Register builders

These live in the package root and are re-exported for consumers.

| Function | Description |
|----------|-------------|
| `build_register_map(model_info=None, circuits=None, zone_modules=0, rooms_per_zone=6) -> dict[str, RegisterDef]` | Compose a register map for a detected model or a manual configuration. Cached. Raises `ValueError` on invalid circuits, `zone_modules` outside 0–10, or `rooms_per_zone` outside 1–8. |
| `get_all_registers(*, model_info=None) -> list[RegisterDef]` | All registers (model-aware) or just `CORE_REGISTERS`. |
| `get_register(name, *, model_info=None) -> RegisterDef` | Look up one register by name. Raises `ValueError` if not found. |
| `get_register_registry(*, model_info=None) -> RegisterRegistry` | Wrap the map in a `RegisterRegistry`. |
| `get_detection_registers() -> list[RegisterDef]` | Registers used for model/capability probing. |
| `get_heating_circuit_registers(circuit_letter) -> dict[str, RegisterDef]` | Registers for one circuit (A–G). |
| `get_zone_module_registers(zone_index, room_count=6) -> dict[str, RegisterDef]` | Registers for one zone module (`zone_index` 1–10, `room_count` 1–8). |

### `RegisterRegistry`

Frozen dataclass wrapping `registers: dict[str, RegisterDef]` with:
`get(key)`, `require(key)`, `by_address(address, register_type="input")`,
`writable()`, and `to_schema()` (export list of dicts).

## Optional web clients

Both web clients are **read-only** and require a configured local network PIN.

### Factories

| Function | Description |
|----------|-------------|
| `web_pin_configured(pin: str \| None) -> bool` | `True` when a non-empty (stripped) PIN is provided. |
| `create_optional_navigator10_web_client(host, pin, *, port=61220, timeout=8.0, request_delay=0.05, session=None) -> IdmNavigator10WebClient \| None` | Returns `None` when PIN not configured. |
| `create_optional_navigator20_web_client(host, pin, *, timeout=8.0, session=None) -> IdmNavigator20WebClient \| None` | Returns `None` when PIN not configured. |

### `IdmNavigator10WebClient` (WebSocket, port 61220)

| Member | Description |
|--------|-------------|
| `model_name` (property) | Always `MODEL_NAVIGATOR_10`. |
| `async connect()` / `async close()` | Lifecycle. Also usable as `async with`. |
| `async read_data(setting_ids=DEFAULT_NAVIGATOR10_SETTING_IDS, *, include_raw=False) -> IdmWebData` | Read the configured values. |
| `async read_statistics(statistic_type, period_type, prefix, *, include_raw=False) -> IdmWebData` | Read a statistics block. |
| `async read_notifications(*, include_raw=False) -> IdmWebNotifications` | Read active controller notifications (Navigator 10 only). |
| `get_cached_data() -> IdmWebData \| None` | Last successful `read_data()` result, if any. |
| `diagnostics() -> IdmWebDiagnostics` | Web-client diagnostics snapshot. |

### `IdmNavigator20WebClient` (HTTP + CSRF)

| Member | Description |
|--------|-------------|
| `model_name` (property) | Always `MODEL_NAVIGATOR_20`. |
| `async connect()` / `async login()` / `async close()` | Lifecycle (`connect` delegates to `login`). Also usable as `async with`. |
| `async detect() -> bool` | `True` when data endpoints were found. |
| `async read_data(paths=DEFAULT_NAVIGATOR20_PATHS, *, include_raw=False) -> IdmWebData` | Read the configured pages. |
| `async read_extra_data() -> dict[str, Any]` | Convenience wrapper returning `IdmWebData.simple_values`. |
| `get_cached_data() -> IdmWebData \| None` | Last successful `read_data()` result, if any. |
| `capabilities() -> dict[str, bool]` | Keys: `web_data`, `settings`, `heatpump`, `rooms`, `zones`, `pv`, `smart_grid`. |
| `diagnostics() -> IdmWebDiagnostics` | Web-client diagnostics snapshot. |

### Web data types

- `IdmWebData` (frozen): `model`, `values: dict[str, IdmWebValue]`, `raw_responses`. Properties `simple_values`, `navigator_version`, `software_version`, `heatpump_model`. Methods `get_value(name, default=None)` and `get_numeric(name, default=None)`.
- `IdmWebValue` (frozen): `name`, `value`, `raw_key`, `raw_description`, `unit`, `numeric_value`.
- `IdmWebNotifications` (frozen): `current: tuple[IdmWebNotification, ...]`, `raw_response`. Properties `count`, `summary`.
- `IdmWebNotification` (frozen): `code`, `message`, `timestamp`, `severity`, `quit_type`, `deferrable`, `raw`.
- `IdmWebDiagnostics` (frozen): `navigator_type`, `websocket_connected`, `web_data_enabled`, `firmware`, `api_version`, `model`, `serial_number`, `last_success_monotonic`, `last_error`, `last_reconnect_monotonic`, `reconnect_attempts`, `used_endpoints`, `cached`.
- `WEB_VALUE_DESCRIPTIONS`: stable key metadata for entity creation.
- `RECOMMENDED_WEB_SCAN_INTERVAL`: `30.0` seconds.

### Web exception hierarchy

Base: `IdmWebError`. Subclasses: `IdmWebDependencyError`,
`IdmWebConnectionError` → `IdmWebTimeoutError`,
`IdmWebAuthenticationError` → `IdmWebPinRejectedError` / `IdmWebCsrfError`,
`IdmWebProtocolError` → `IdmWebWebSocketError` / `IdmWebResponseError`.

Legacy short aliases remain available but the `IdmWeb*` names are preferred:
`AuthenticationError`, `PinRejectedError`, `CsrfError`, `ConnectionError`,
`TimeoutError`, `WebSocketError`, `ProtocolError`.

## Option maps and constants

The package root exports option-map dicts useful for translating raw register
values to labels:

`SYSTEM_MODE_OPTIONS`, `CIRCUIT_MODE_OPTIONS`, `ROOM_MODE_OPTIONS`,
`ZONE_MODULE_MODE_OPTIONS`, `ACTIVE_HC_MODE_OPTIONS`, `SOLAR_MODE_OPTIONS`,
`SMART_GRID_OPTIONS`, `ISC_MODE_OPTIONS`, `HP_OPERATING_MODE_OPTIONS`,
`BIVALENCE_STATE_OPTIONS`, `BOOSTER_FAULT_OPTIONS`, `EVU_LOCK_OPTIONS`,
`VARIABLE_INPUT_OPTIONS`.

Model, feature, and connection constants: `MODEL_NAVIGATOR_20`,
`MODEL_NAVIGATOR_PRO`, `MODEL_NAVIGATOR_10`, `MODEL_UNKNOWN`,
`MODEL_DETECTION_TIMEOUT`, `MODEL_DETECTION_MAX_RETRIES`,
`FEATURE_HEATING_CIRCUITS`, `FEATURE_ZONE_MODULES`, `FEATURE_SOLAR`,
`FEATURE_ISC`, `FEATURE_PV`, `FEATURE_CASCADE`, `HEATING_CIRCUIT_LETTERS`,
`MAX_HEATING_CIRCUITS`, `MAX_ZONE_MODULES`, `MAX_ROOMS_PER_ZONE`,
`DEFAULT_PORT`, `DEFAULT_SLAVE_ID`, `DEFAULT_TIMEOUT`, `MAX_RETRIES`,
`RETRY_BACKOFF_BASE`, `EEPROM_SENSITIVE_ADDRESSES`.
