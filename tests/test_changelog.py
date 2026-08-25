"""Changelog consistency checks."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from packaging.version import Version

ROOT = Path(__file__).resolve().parents[1]

# PEP 440, matching what release.yml accepts: "1.2.3" or a prerelease such as
# "2.0.0b1".  A prerelease heading documents a patch that is not released yet.
_VERSION_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+(?:(?:a|b|rc)\d+)?)\]", re.MULTILINE)


def _changelog_versions() -> list[str]:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return _VERSION_HEADING.findall(changelog)


def _current_version() -> Version:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return Version(pyproject["project"]["version"])


def test_changelog_versions_are_sorted_newest_first() -> None:
    versions = _changelog_versions()

    assert versions == sorted(versions, key=Version, reverse=True)


def test_changelog_headings_are_pep440() -> None:
    """A heading written as "2.0.0-beta.1" is not the version pip resolves."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    headings = re.findall(r"^## \[([^\]]+)\]", changelog, flags=re.MULTILINE)
    unparsed = [
        heading
        for heading in headings
        if heading != "Unreleased" and not _VERSION_HEADING.match(f"## [{heading}]")
    ]

    assert not unparsed, f"non-PEP 440 changelog headings: {unparsed}"


def test_changelog_covers_current_version() -> None:
    current = _current_version()

    assert str(current) in {str(Version(version)) for version in _changelog_versions()}


def test_changelog_covers_current_minor_without_patch_gaps() -> None:
    current = _current_version()
    major, minor, patch = current.release

    released_patches = {
        Version(version).release[2]
        for version in _changelog_versions()
        if not Version(version).is_prerelease and Version(version).release[:2] == (major, minor)
    }

    # A prerelease documents a patch that has not shipped, so the run of
    # released patches in this minor stops one below it.
    ceiling = patch - 1 if current.is_prerelease else patch

    if not released_patches:
        assert ceiling < 0, f"{current} has no released predecessor in {major}.{minor}"
        return

    highest = max(released_patches)
    # The changelog may lead pyproject.toml by one: release.yml writes the
    # section first and bumps the version during the release run.
    assert highest <= ceiling + 1
    assert released_patches == set(range(highest + 1))
