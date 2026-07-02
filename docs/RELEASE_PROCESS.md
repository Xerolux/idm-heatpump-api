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

## Rollback

1. Avoid deleting tags after users may have installed them.
2. Yank a PyPI release only when installation is actively harmful.
3. Prefer publishing a fixed patch release.
4. Update the integration pin to the fixed version.
5. Document affected versions and required user action in release notes.
