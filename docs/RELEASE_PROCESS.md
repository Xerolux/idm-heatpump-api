# Release Process

`idm-heatpump-api` is released before the Home Assistant integration when both
repositories change.

## API Checklist

- `pytest tests/ -v --tb=short --cov=idm_heatpump --cov-report=term-missing --cov-fail-under=75`
- `ruff check idm_heatpump tests`
- `ruff format idm_heatpump tests --check`
- `mypy idm_heatpump`
- `python -m build`
- `twine check dist/*`
- Install the built wheel into a clean virtual environment and import the public
  package root.
- Run the Home Assistant integration contract tests against the target
  integration branch.
- Confirm `pyproject.toml` version and Git tag match exactly.
- Confirm release notes are curated by a maintainer.

## Release Order

1. Merge the API change.
2. Verify CI and security checks.
3. Publish the API package.
4. Open the integration pin PR.
5. Run integration CI and smoke tests.
6. Publish the integration release.

## Pre-Releases

Use alpha, beta, or release-candidate releases when changing:

- register model gates;
- decode or encode behavior;
- write validation;
- connection retry behavior;
- public APIs used by the Home Assistant integration.

### Naming

**PEP 440, not SemVer: `2.0.0b1`, `2.0.0a1`, `2.0.0rc1`.** No hyphen, no dot
before the number.

This is a PyPI package, so the version has to be a PEP 440 version. pip and PyPI
normalise `2.0.0-beta.1` to `2.0.0b1` on the way in — the wheel is named
`idm_heatpump_api-2.0.0b1-py3-none-any.whl` whatever the tag said, and the
Home Assistant manifest has to pin `idm-heatpump-api[web]==2.0.0b1` to resolve
it. Writing the normalised form everywhere is the only way the `pyproject.toml`
version, the git tag, the PyPI filename and the consumer pin all read the same.

`release.yml` enforces it: `version_mode=custom` accepts `1.2.3` or a PEP 440
prerelease and rejects anything else, naming the accepted forms. The tag is
`v` plus that version (`v2.0.0b1`). The integration repository keeps SemVer tags
(`v0.16.0-beta.1`) because HACS reads those, so the two repositories deliberately
differ here.

### What the workflow does with a prerelease

- **It never auto-bumps off one.** With a prerelease in `pyproject.toml`,
  `auto-minor` and `auto-patch` fail and ask for `version_mode=custom`: only a
  maintainer knows whether the next version is `2.0.0b2` or `2.0.0`.
- **The GitHub release is marked as a prerelease** and does not become the
  repository's latest release.
- **Release notes compare against the newest tag of any kind**, so `2.0.0b2`
  documents what changed since `2.0.0b1`. A stable release still compares against
  the previous stable, so its notes are not a diff against its own beta.
- **The install snippet names the exact version**, because a bare
  `pip install idm-heatpump-api` resolves to the newest stable release and would
  silently skip the prerelease.

## Rollback

1. Avoid deleting tags after users may have installed them.
2. Yank a PyPI release only when installation is actively harmful.
3. Prefer publishing a fixed patch release.
4. Update the integration pin to the fixed version.
5. Document affected versions and required user action in release notes.
