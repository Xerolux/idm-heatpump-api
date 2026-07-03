"""Tests for the documented API release contract."""

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_CONTRACT = ROOT / "docs" / "API-Contract.md"
COMPATIBILITY_MATRIX = ROOT / "docs" / "compatibility-matrix.json"


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


def test_api_contract_documents_register_quality_metadata() -> None:
    text = API_CONTRACT.read_text(encoding="utf-8")

    for field in [
        "`source`",
        "`source_version`",
        "`supported_models`",
        "`sentinel_values`",
        "`last_verified`",
        "tests/fixtures/register_schema_v1.json",
    ]:
        assert field in text


def test_readme_links_api_contract() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "docs/API-Contract.md" in readme


def test_typed_package_marker_is_shipped() -> None:
    assert (ROOT / "idm_heatpump" / "py.typed").is_file()

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'idm_heatpump = ["py.typed"]' in pyproject


def test_mypy_configuration_is_strict() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "strict = true" in pyproject
    assert "disallow_untyped_defs = false" not in pyproject


def test_pymodbus_compatibility_is_bounded_and_matrix_tested() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    contract = API_CONTRACT.read_text(encoding="utf-8")

    assert '"pymodbus>=3.12.1,<4.0"' in pyproject
    assert "pymodbus==3.12.1" in workflow
    assert "pymodbus>=3.12.1,<4.0" in workflow
    assert "Runtime Dependency Compatibility" in contract


def test_ci_builds_and_import_checks_distribution_artifacts() -> None:
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    assert "python -m build" in workflow
    assert "twine check dist/*" in workflow
    assert "python -m venv /tmp/idm_heatpump_api_import" in workflow
    assert "python -m pip install dist/*.whl" in workflow


def test_ci_enforces_coverage_floor() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    assert "pytest-cov>=7.1.0" in pyproject
    assert "fail_under = 75" in pyproject
    assert "--cov=idm_heatpump" in workflow
    assert "--cov-fail-under=75" in workflow


def test_hass_compatibility_matrix_covers_current_api_version() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    current_version = pyproject["project"]["version"]
    matrix = json.loads(COMPATIBILITY_MATRIX.read_text(encoding="utf-8"))
    entries = matrix["entries"]

    assert matrix["schema_version"] == 1
    assert {
        "api_version": "0.3.7",
        "hass_integration_version": "0.7.3",
        "status": "tested",
        "notes": "Baseline for Navigator 2.0 filtering and Navigator 10 register map.",
    } in entries
    assert any(entry["api_version"] == current_version for entry in entries)
    assert "docs/compatibility-matrix.json" in API_CONTRACT.read_text(encoding="utf-8")


def test_ci_runs_home_assistant_integration_contract_tests() -> None:
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    assert "repository: Xerolux/idm-heatpump-hass" in workflow
    assert "integration-contract/tests/test_library_client.py" in workflow
    assert "integration-contract/tests/test_adapter_helpers.py" in workflow
    assert 'PYTHONPATH="$PWD:$PWD/integration-contract"' in workflow
