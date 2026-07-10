# API Contract

This document defines the public compatibility contract for
`idm-heatpump-api`. It is intended for consumers such as the IDM Heatpump Home
Assistant custom integration and for maintainers preparing releases.

## Public Import Surface

Supported consumers should import from the package root:

```python
from idm_heatpump import IdmModbusClient, build_register_map
```

Optional local web supplement consumers should also import from the package root:

```python
from idm_heatpump import create_optional_navigator10_web_client
```

Consumers that create entities from local web supplement values can use
`WEB_VALUE_DESCRIPTIONS` for stable key metadata and `IdmWebData.get_value()` /
`IdmWebData.get_numeric()` for defensive value access.

The package root `__all__` list is the public import contract. It is protected
by `tests/test_public_api.py`.

### Unsupported-register query

`IdmModbusClient.get_unsupported_registers()` is a supported public method for
polling consumers. It returns a sorted tuple of register names for which the
controller returned Modbus exception code 2 ("Illegal Data Address") during a
batch fallback. It excludes registers that became permanently failed only after
repeated transient errors. The result is retained for the lifetime of the
client and is cleared by `reset_failed_registers()`.

### Batch-read safety query

`IdmModbusClient.get_batch_unsafe_registers()` returns a sorted tuple of
register names whose grouped response violated declared enum or numeric-range
metadata. Those registers remain readable, but the client fetches them
individually for the rest of its lifetime. `IdmClientDiagnostics` exposes the
same names as `batch_unsafe_registers`.

Grouped reads only combine register definitions whose address ranges touch;
they never span unrequested address gaps. A suspect grouped value is recovered
with an individual read, and that recovery value is validated again before it
is returned to the consumer. Documented `sentinel_values` remain valid during
both checks.

Imports from implementation modules such as `idm_heatpump.client` and
`idm_heatpump.registers` are tolerated for internal tests and local debugging,
but they are not the preferred consumer contract.

The optional local web supplement is read-only and additive. Consumers must keep
Modbus as the baseline data path and treat web data as optional enrichment. If no
local network PIN is configured, consumers should not create a web client and
must continue Modbus-only operation without surfacing a web error.

## Versioning Rules

### Patch Releases

Patch releases may include:

- bug fixes that preserve public imports and call signatures;
- register corrections that make metadata match documented or verified device
  behavior;
- model gates that remove unsupported registers from affected models;
- stricter validation when it prevents unsafe writes or protocol misuse;
- documentation and test updates.

Patch releases must not silently rename public symbols or change the meaning of
existing public option values.

### Minor Releases

Minor releases may include:

- new public symbols;
- additive registers, metadata fields, model capabilities, or helper APIs;
- new optional validation helpers;
- deprecation warnings for APIs planned for removal or behavioral change.

Minor releases must remain compatible for existing correct consumer code.

### Major Releases

Major releases are required for:

- removing public symbols from package root `__all__`;
- changing public function signatures in incompatible ways;
- renaming register keys without a compatibility alias;
- changing encode/decode behavior in a way that alters existing valid values;
- changing write-safety behavior that requires consumer migration.

Major releases must include migration notes in the changelog.

## Deprecation Policy

When a public symbol, register key, or behavior needs to be replaced:

1. Add the replacement first.
2. Keep the old path working for at least one minor release.
3. Emit a `DeprecationWarning` when practical and safe for consumers.
4. Document the old path, replacement path, and earliest removal version in the
   changelog.
5. Remove only in a major release unless the old behavior is unsafe.

Unsafe write behavior can be blocked sooner, but the changelog must explain the
reason and the safe replacement.

## Register Compatibility Rules

The protocol rules, reviewed source documents, documented logical overlaps,
and model-family boundaries in
[`Register-Map-Invariants.md`](Register-Map-Invariants.md) are mandatory for all
register-map changes.

Register changes must include:

- source or verification note;
- model availability gate when the register is not universal;
- datatype, size, unit, min/max, writable, write-only, and sentinel behavior;
- test coverage for address, datatype, and model inclusion/exclusion.

Every `RegisterDef` exposes machine-readable quality metadata:

- `source`: source family for the register definition;
- `source_version`: document or verification version;
- `supported_models`: controller models where the register is expected;
- `sentinel_values`: values that need context-specific unavailable handling;
- `last_verified`: optional date or verification label for hardware checks.

The versioned schema snapshot in `tests/fixtures/register_schema_v1.json`
serializes these fields for every generated register map.

Registers observed in a device UI but not confirmed over Modbus must not be
added as supported Modbus registers.

## Runtime Dependency Compatibility

The package supports `pymodbus>=3.12.1,<4.0`. CI tests the version pinned by
the Home Assistant integration and the latest installable 3.x release. A future
`pymodbus` major version must be validated before the upper bound is raised.

## Home Assistant Compatibility

Each API release consumed by the Home Assistant custom integration should have
an explicit integration compatibility entry in
`docs/compatibility-matrix.json`.

| API version | HASS integration version | Compatibility |
|-------------|--------------------------|---------------|
| 0.5.1 | 0.8.0-beta.11 | Fixes Navigator 2.0 misdetection caused by address 1072; first-setup stable on Terra SWM / Navigator 2.0 |
| 0.5.0 | pending | Adds stable web supplement metadata/helpers, optional firmware probing and Navigator 10 WebSocket reconnect hardening |
| 0.4.0 | pending | API prepared with optional local web supplement and default-safe Navigator 10 firmware register polling |
| 0.4.1 | 0.8.0-beta.7 | Beta integration line consumes optional web supplement and faster model detection |
| 0.3.7 | 0.7.3 | Tested baseline for Navigator 2.0 filtering and Navigator 10 register map |
| 0.7.0 | pending | Adds the stable unsupported-register query for consumers that maintain their own polling skip-list. |
| 0.7.2 | 0.8.1-beta.23 | Hardens batch reads and validates suspect register values. |
| 0.7.3 | 0.8.1-beta.23 | Ignores unavailable heating-circuit slot sentinels during model detection. |
| 0.7.4 | Pending | Restores documented Navigator register addresses and reconnects after pymodbus no-response errors. |
