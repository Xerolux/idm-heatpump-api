# AGENTS.md — IDM Heatpump API

This file contains mandatory guidance for AI assistants and maintainers working
on this repository.

## Register map authority

Before changing register addresses, datatypes, sizes, function codes, model
gates, batching, or write behavior, read
[`docs/Register-Map-Invariants.md`](docs/Register-Map-Invariants.md) completely.

The official IDM Modbus documents are the primary source. Community reports,
generated templates, inferred address patterns, and a desire for a
non-overlapping map must never override the official tables without an exact
hardware capture proving a firmware-specific exception.

## Non-negotiable protocol rules

- Never shift an official address merely to eliminate a logical range overlap.
- Never change a documented datatype to make every address occupy one unique
  16-bit slot.
- IDM `FLOAT` values are IEEE-754 32-bit values occupying two 16-bit registers,
  transferred low word first (`Reg_L`, then `Reg_H`).
- Batch only exactly adjacent, non-overlapping ranges of the same register
  type. Never span gaps and never combine overlapping logical data points.
- Read an overlapping data point using its exact documented start address and
  size. For example, humidity is `1392/count=2`, while heating-circuit A mode is
  a separate `1393/count=1` request.
- Validate physical ranges only after decoding the documented datatype. Do not
  clamp or discard a raw byte to hide a datatype/address error.
- Treat Navigator 1.0/1.7 as a separate protocol family. Its addresses must not
  be copied into the Navigator 2.0/10/Pro map. It is not currently supported.
- Treat writes as safety-sensitive. Preserve EEPROM guards, cyclic-write rules,
  exact function codes, and documented sentinels.

## Required change set for register edits

Any register change must include all of the following:

1. A source or hardware-verification note.
2. Focused tests for address, datatype, size, model inclusion, and exact Modbus
   request shape.
3. An updated `tests/fixtures/register_schema_v1.json` snapshot.
4. A changelog entry.
5. Successful pytest, Ruff, strict mypy, and Home Assistant cross-repository
   contract tests.

Do not add a no-overlap invariant. The official Navigator 2.0/10 map contains
documented logical range overlaps at block boundaries.
