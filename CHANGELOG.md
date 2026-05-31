name: Status check labels

on:
  pull_request:
    types: [labeled, unlabeled]

jobs:
  check:
    name: Check ${{ matrix.label }}
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        label:
          - needs-docs
          - merge-after-release
          - chained-pr
    steps:
      - uses: actions/github-script@v7
        env:
          LABEL: ${{ matrix.label }}
        with:
          script: |
            const labelToCheck = process.env.LABEL;
            const { data: labels } = await github.rest.issues.listLabelsOnIssue({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number
            });
            const hasLabel = labels.find(label => label.name === labelToCheck);
            if (hasLabel) {
              core.setFailed(`Pull request cannot be merged, it is labeled as ${labelToCheck}`);
            }


## [0.2.0] - 2026-05

### Breaking / Important
- Restructured package for clean PyPI distribution (`import idm_heatpump`).
- The library is now the official core for the Home Assistant integration (migration Option B).

### Features
- Full Navigator 10 support (heat sink flow rate 1072, boosters, power limitation, etc.).
- Improved model detection for Navigator 10.

### Packaging
- Added proper release workflow for PyPI (modeled after violet-poolController-api).
- Clean top-level package layout.


