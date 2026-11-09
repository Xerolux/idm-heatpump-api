# Contributing to idm-heatpump-api

Thanks for your interest in improving the library. This project is an
unofficial community effort for IDM Navigator heat pumps, and contributions —
bug reports, register-map corrections with evidence, documentation, and code —
are welcome.

## Writing conventions

All changelog entries, release notes, documentation, commit messages, pull
request text, comments, and docstrings are written in **English**.

## Getting started

```bash
git clone https://github.com/Xerolux/idm-heatpump-api.git
cd idm-heatpump-api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,test]"
```

See [Installation and Setup](docs/Installation-and-Setup.md) for the full
developer walkthrough.

## Quality gate

Run the full local gate before pushing; CI runs the same commands and the
pull request will not merge while any of them is red:

```bash
pytest                       # tests + coverage (fail-under 75)
ruff check .                 # lint
mypy                         # strict type checking
```

Home Assistant cross-repository contract tests run in CI as well; if you
change the public API or client behavior, expect them to pin your change.

## Changing the register map

Register addresses, datatypes, sizes, function codes, model gates, batching,
and write behavior are protocol facts, not style choices. Before touching
them, read
[docs/Register-Map-Invariants.md](docs/Register-Map-Invariants.md) completely.
The official IDM Modbus documents are the primary source; community reports
and inferred address patterns never override them without exact hardware
evidence.

Every register change must include:

1. a source or hardware-verification note,
2. focused tests for address, datatype, size, model inclusion, and exact
   Modbus request shape,
3. an updated `tests/fixtures/register_schema_v1.json` snapshot,
4. a changelog entry.

## Documentation

The `docs/` directory is the single source of truth. It is published to the
GitHub Wiki (via `wiki-sync.yml`) and to GitHub Pages (via `pages.yml`).
Edit files there — never edit the wiki directly, the next sync would
overwrite it.

See [CI and Automation](docs/CI-and-Automation.md) for how the workflows,
branch protection, and Dependabot auto-merge operate.

## Pull requests

- Keep pull requests focused; one topic per pull request.
- Write the changelog entry under `[Unreleased]` in `CHANGELOG.md`.
- Merged branches are deleted automatically.
- If you cannot finish a change, open a draft pull request and describe what
  is missing.

## Reporting bugs

Open an issue with the controller model (Navigator 2.0 / Pro / 10), the
firmware version if known, the library version, and — for register problems —
the raw Modbus request/response. Never post credentials or personal data;
a CI job scans for them.
