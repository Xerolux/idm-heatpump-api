# Maintenance Policy

This library is maintained together with the IDM Heatpump Home Assistant
integration.

## Support Window

- The latest stable API release is supported.
- The API version pinned by the latest stable integration release is supported.
- Older releases may receive guidance, but fixes are normally released forward.
- Unsafe write behavior and security defects can be patched outside the normal
  roadmap.

## Review Areas

Maintainer review is required for:

- register addresses, datatypes, sizes, units, and model gates;
- write validation and EEPROM-sensitive behavior;
- public package-root exports;
- dependency bounds;
- release and publishing workflows;
- generated register schema snapshots.

## Repository Settings

Maintain these settings:

- Protect `main`: require pull requests, required CI checks, linear history, and
  no force-pushes.
- Treat tests, lint, format, type checks, package build, security checks, and
  Home Assistant contract tests as required checks once green on the default
  branch.
- Use a protected `pypi` environment for publishing.
- Delete merged branches automatically after merge.
- Enable Dependabot security and version updates.
- Keep secrets only in GitHub Environments or repository secrets.

## Roadmap Review

Review API and integration roadmap items together at least once per quarter.
Register changes should link to release notes, issues, or compatibility matrix
entries instead of relying only on commit history.
