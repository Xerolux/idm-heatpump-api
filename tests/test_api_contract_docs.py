"""Tests for the documented API release contract."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_CONTRACT = ROOT / "docs" / "API-Contract.md"


def test_api_contract_documents_versioning_and_deprecation_policy() -> None:
    text = API_CONTRACT.read_text(encoding="utf-8")

    for heading in [
        "## Public Import Surface",
        "## Versioning Rules",
        "### Patch Releases",
        "### Minor Releases",
        "### Major Releases",
        "## Deprecation Policy",
        "## Register Compatibility Rules",
        "## Home Assistant Compatibility",
    ]:
        assert heading in text


def test_readme_links_api_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/API-Contract.md" in readme
