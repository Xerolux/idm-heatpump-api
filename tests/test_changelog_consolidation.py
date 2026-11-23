"""Contract tests for the version-to-version changelog workflow.

From 2.1.1 on the changelog is kept between released versions: when a stable
section exists, the prerelease sections of that version must have been folded
into it. Individual prereleases need not be named in the stable section, but
the fold is expected to lose nothing — that is what
``scripts/consolidate_changelog.py`` guarantees mechanically, and what the
editorial pass keeps true afterwards. The ``2.0.0b1`` history below the
baseline keeps the shape it was published with.
"""

from __future__ import annotations

import re
from pathlib import Path

from packaging.version import Version

from scripts import consolidate_changelog as fold_module

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"

#: The workflow starts here; the 2.0.0b1 history keeps its published shape.
CONSOLIDATION_BASELINE = Version("2.1.1")

_HEADING_RE = re.compile(r"^## \[([^\]]+)\]", re.MULTILINE)


def _headings() -> list[str]:
    return _HEADING_RE.findall(CHANGELOG.read_text(encoding="utf-8"))


def _version(label: str) -> Version | None:
    """Parse a heading label, returning None for Unreleased/malformed ones."""
    if label == "Unreleased":
        return None
    try:
        return Version(label)
    except Exception:  # noqa: BLE001 - malformed labels are the point here
        return None


def _is_prerelease(label: str) -> bool:
    version = _version(label)
    return version is not None and version.is_prerelease


def _stable_labels() -> set[str]:
    labels = set()
    for label in _headings():
        version = _version(label)
        if version is not None and not version.is_prerelease and version >= CONSOLIDATION_BASELINE:
            labels.add(str(version))
    return labels


def test_stable_sections_have_no_leftover_prerelease_headings() -> None:
    """Every stable cut from 0.17.0 on folds its prerelease sections away."""
    stables = _stable_labels()
    problems = [
        label
        for label in _headings()
        if (version := _version(label)) is not None
        and version.is_prerelease
        and str(version) in stables
    ]
    assert not problems, (
        "prerelease sections still present after their stable cut: "
        f"{problems}; fold them with scripts/consolidate_changelog.py"
    )


SAMPLE = """# Changelog

## [Unreleased]

## [2.2.0b2] - 2026-10-02

Second beta intro.

### Fixed

- Bug A fix improved.
- Bug B.

## [2.2.0b1] - 2026-10-01

First beta intro.

### Added

- Feature X.

### Fixed

- Bug A initial fix.

## [2.1.1] - 2026-09-13

Older release.

### Fixed

- Compressor names.

## [2.1.0] - 2026-09-13

Even older.
"""


def test_fold_merges_prereleases_without_losing_bullets() -> None:
    result = fold_module.fold(SAMPLE, "2.2.0", "2026-10-03")

    assert "## [2.2.0] - 2026-10-03" in result
    assert "## [2.2.0b" not in result
    # Both betas' bullets survive; the superseded wording stays for the editor.
    assert "Feature X." in result
    assert "Bug A initial fix." in result
    assert "Bug A fix improved." in result
    assert "Bug B." in result
    # The older sections are untouched.
    assert "## [2.1.1] - 2026-09-13" in result
    assert "## [2.1.0] - 2026-09-13" in result
    # Intros are marked with the beta they came from.
    assert "**From `[2.2.0b1]`:** First beta intro." in result


def test_fold_deduplicates_identical_bullets() -> None:
    sample = SAMPLE.replace("- Bug A fix improved.\n", "- Bug A initial fix.\n")
    result = fold_module.fold(sample, "2.2.0", "2026-10-03")

    assert result.count("- Bug A initial fix.") == 1


def test_fold_refuses_when_the_stable_already_exists() -> None:
    try:
        fold_module.fold(SAMPLE, "2.1.1", "2026-10-03")
    except SystemExit as err:
        assert "already exists" in str(err)
    else:
        raise AssertionError("folding a released stable must refuse")


def test_fold_refuses_without_prereleases() -> None:
    try:
        fold_module.fold(SAMPLE, "2.3.0", "2026-10-03")
    except SystemExit as err:
        assert "no prerelease sections" in str(err)
    else:
        raise AssertionError("folding a version without prereleases must refuse")


HOTFIX_BETWEEN_BETAS = SAMPLE.replace(
    "## [2.2.0b1] - 2026-10-01\n",
    "## [2.1.2] - 2026-09-20\n"
    "\n"
    "### Fixed\n"
    "\n"
    "- Hotfix released while the betas were open.\n"
    "\n"
    "## [2.2.0b1] - 2026-10-01\n",
)


def test_fold_keeps_a_release_published_between_prereleases() -> None:
    """A patch cut while the beta cycle was running sits between the betas in the file.

    The fold used to replace everything from the newest to the oldest
    prerelease section, which deleted that release's section with it - the
    one thing the mechanical fold exists to prevent.
    """
    result = fold_module.fold(HOTFIX_BETWEEN_BETAS, "2.2.0", "2026-10-03")

    assert "## [2.1.2] - 2026-09-20" in result
    assert "- Hotfix released while the betas were open." in result
    # Both betas still fold into the stable section, and the hotfix keeps its
    # chronological place: below the new stable section, above the older release.
    assert "## [2.2.0b" not in result
    assert "Feature X." in result and "Bug B." in result
    assert (
        result.index("## [2.2.0] - 2026-10-03")
        < result.index("## [2.1.2] - 2026-09-20")
        < result.index("## [2.1.1] - 2026-09-13")
    )
