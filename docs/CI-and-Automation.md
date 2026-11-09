# CI and Automation

This page documents the continuous-integration setup of `idm-heatpump-api`:
the workflows, the branch protection on `main`, and how Dependabot pull
requests are merged automatically. For release mechanics see
[RELEASE_PROCESS](RELEASE_PROCESS); for the maintenance policy see
[MAINTENANCE](MAINTENANCE).

## Branch protection on `main`

- Pull requests are required; direct pushes are refused (admins included).
- Required status check: **Scan for credentials and personal data**.
- No force pushes, no branch deletion.
- Merged branches are deleted automatically (`delete_branch_on_merge`).

The required check is deliberately only the sensitive-data scan: the
Dependabot auto-merge below waits for **all** checks of a pull request, not
just the required ones, so making the whole matrix required would add review
noise without adding safety.

## Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `tests.yml` | push/PR to `main`, `develop` | Test matrix (Python 3.12–3.14 × pinned and bounded `pymodbus`), `no-pymodbus` install check, package build + `twine check` + wheel import, Home Assistant cross-repo contract tests |
| `security.yml` | push/PR, weekly schedule | CodeQL analysis and `pip-audit` dependency scanning |
| `sensitive-data-guard.yml` | every push and PR | Scans diffs for credentials and personal data; the only required check |
| `dependabot-auto-merge.yml` | Dependabot PR events | Merges Dependabot pull requests once their checks are green (see below) |
| `release.yml` | manual dispatch | Validates the version, bumps `pyproject.toml`, tags, creates the GitHub release, and dispatches `publish.yml` |
| `publish.yml` | tag push `v*`, manual dispatch | Builds the tagged tree and publishes to PyPI (trusted publishing, protected `pypi` environment) |
| `pages.yml` | push to `main` touching `docs/**` or `README.md` | Copies `docs/` to GitHub Pages |
| `wiki-sync.yml` | push to `main` touching `docs/**` | `rsync --delete` `docs/` into the GitHub Wiki |

Actions are pinned by SHA. The pins are owned by Dependabot — see below.

## Dependabot configuration

`.github/dependabot.yml` schedules weekly updates (Monday mornings,
Europe/Berlin):

- **github-actions** ecosystem, grouped CodeQL updates, labeled
  `dependencies` + `ci`
- **pip** ecosystem, up to 5 open pull requests, labeled `dependencies` +
  `python`

The labels are repository labels; Dependabot refuses to open labeled pull
requests while a label is missing, so deleting them reverts to the default
`dependabot` labeling and posts a warning comment.

## Dependabot auto-merge

Dependabot owns the action pins, and its pull requests used to wait days for
a manual merge (#107 sat four days fully green). `dependabot-auto-merge.yml`
merges them as soon as their checks pass. The design has three deliberate
properties:

1. **It runs on `pull_request_target`** with `contents: write` — a normal
   `pull_request` event would give Dependabot's pull request only a read-only
   token that cannot merge. The pull request's code is never checked out, so
   nothing from the branch runs with the write-capable token; the job only
   talks to the GitHub API.
2. **Repository-level auto-merge stays disabled.** GitHub's native auto-merge
   waits only for the *required* checks, which here is a single scan job. The
   workflow instead waits for every check on the pull request — the full test
   matrix, CodeQL, pip-audit — before merging.
3. **The wait must not watch itself.** The workflow's own job appears as a
   pending check run on the pull request it is watching. An earlier version
   used `gh pr checks --watch`, which therefore waited for its own job to
   finish — a deadlock that only the 90-minute job timeout resolved; pull
   requests #163 and #164 each burned the full timeout while every real
   check was green after one minute. The job now polls the Checks API for
   the pull-request head, skips the check runs of its own workflow run, and
   merges only when every other check completed successfully. A red check
   fails the job and leaves the pull request open.

A merge performed with `GITHUB_TOKEN` does not trigger further workflow
runs, so the merge of a Dependabot pull request does not re-run CI on `main`
by itself; the next push or scheduled run covers it.

## Documentation publishing

The `docs/` directory is the single source of truth for both documentation
surfaces:

- **GitHub Wiki** — `wiki-sync.yml` mirrors `docs/` into the wiki with
  `rsync --delete`: pages removed from `docs/` disappear from the wiki.
- **GitHub Pages** — `pages.yml` deploys `docs/` (including `index.html`,
  `faq.html`, and the compatibility matrix) to
  <https://xerolux.github.io/idm-heatpump-api/>.

Wiki edits made directly in GitHub are overwritten by the next sync — always
edit `docs/` in a pull request instead.
