"""Changelog consistency checks."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _version_tuple(version: str) -> tuple[int, int, int]:
    major, minor, patch = version.split(".")
    return int(major), int(minor), int(patch)


def _changelog_versions() -> list[str]:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return re.findall(r"^## \[(\d+\.\d+\.\d+)\]", changelog, flags=re.MULTILINE)


def test_changelog_versions_are_sorted_newest_first() -> None:
    versions = _changelog_versions()

    assert versions == sorted(versions, key=_version_tuple, reverse=True)


def test_changelog_covers_current_minor_without_patch_gaps() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    current_version = pyproject["project"]["version"]
    major, minor, patch = _version_tuple(current_version)
    actual = {
        version
        for version in _changelog_versions()
        if _version_tuple(version)[:2] == (major, minor)
    }

    assert current_version in actual

    highest_patch = max(_version_tuple(version)[2] for version in actual)
    assert highest_patch <= patch + 1

    expected = {f"{major}.{minor}.{candidate}" for candidate in range(highest_patch + 1)}
    assert actual == expected
