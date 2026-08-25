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

## Versioning and releases

- **Versions are PEP 440.** A prerelease is `2.0.0b1`, `2.0.0a1`, `2.0.0rc1` —
  no hyphen, no dot before the number. pip and PyPI normalise `2.0.0-beta.1` to
  `2.0.0b1` anyway, and the Home Assistant manifest has to pin the normalised
  form, so writing it everywhere keeps `pyproject.toml`, the tag, the PyPI
  filename and the consumer pin identical. The tag is `v` plus the version
  (`v2.0.0b1`). The integration repository keeps SemVer tags
  (`v0.16.0-beta.1`) for HACS; the two repositories differ here on purpose.
- **`release.yml` enforces the format** and refuses to auto-bump off a
  prerelease — only a maintainer knows whether the next one is `2.0.0b2` or
  `2.0.0`. Use `version_mode=custom` and name it.
- **Releasing takes two dispatches.** `release.yml` tags with `GITHUB_TOKEN`,
  and GitHub does not start workflows for events that token creates, so the
  `push: tags` trigger in `publish.yml` never fires. Run **Release** first, then
  **Publish** with the tag. A GitHub release with assets is not proof the
  package is on PyPI — check PyPI itself.
- **Every release carries the support links.** They are part of the release body
  in `release.yml`; keep them in step with `.github/FUNDING.yml`.
- **Write in English** — changelog, release notes, docs, commit messages, pull
  request text, comments and docstrings, including the prose baked into
  workflows and scripts.

See `docs/RELEASE_PROCESS.md` for the full procedure.
