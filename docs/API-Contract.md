# API Contract

This document defines the public compatibility contract for
`idm-heatpump-api`. It is intended for consumers such as the IDM Heatpump Home
Assistant custom integration and for maintainers preparing releases.

## Public Import Surface

Supported consumers should import from the package root:

```python
from idm_heatpump import IdmModbusClient, build_register_map
```

The package root `__all__` list is the public import contract. It is protected
by `tests/test_public_api.py`.

Imports from implementation modules such as `idm_heatpump.client` and
`idm_heatpump.registers` are tolerated for internal tests and local debugging,
but they are not the preferred consumer contract.

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

Register changes must include:

- source or verification note;
- model availability gate when the register is not universal;
- datatype, size, unit, min/max, writable, write-only, and sentinel behavior;
- test coverage for address, datatype, and model inclusion/exclusion.

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
| 0.3.7 | 0.7.3 | Tested baseline for Navigator 2.0 filtering and Navigator 10 register map |
