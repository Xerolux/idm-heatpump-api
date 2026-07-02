"""Register map contract tests against a versioned machine-readable schema."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from idm_heatpump.client import IdmModelInfo, RegisterDef
from idm_heatpump.const import MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_20
from idm_heatpump.registers import build_register_map

ROOT = Path(__file__).resolve().parents[1]
REGISTER_SCHEMA = ROOT / "tests" / "fixtures" / "register_schema_v1.json"


def _serialize_register(reg: RegisterDef) -> dict[str, Any]:
    return {
        "address": reg.address,
        "datatype": reg.datatype.value,
        "name": reg.name,
        "unit": reg.unit,
        "writable": reg.writable,
        "min_val": reg.min_val,
        "max_val": reg.max_val,
        "enum_options": {str(key): value for key, value in sorted((reg.enum_options or {}).items())},
        "multiplier": reg.multiplier,
        "register_type": reg.register_type.value,
        "eeprom_sensitive": reg.eeprom_sensitive,
        "cyclic_required": reg.cyclic_required,
        "cyclic_write_ttl": reg.cyclic_write_ttl,
        "binary": reg.binary,
        "enabled_by_default": reg.enabled_by_default,
        "state_class": reg.state_class,
        "icon": reg.icon,
        "write_only": reg.write_only,
        "write_class": reg.write_class.value,
        "exclude_from_write": sorted(reg.exclude_from_write or []),
        "source": reg.source,
        "source_version": reg.source_version,
        "supported_models": list(reg.supported_models),
        "sentinel_values": list(reg.sentinel_values),
        "last_verified": reg.last_verified,
        "size": reg.size,
    }


def _serialize_map(registers: dict[str, RegisterDef]) -> dict[str, Any]:
    return {key: _serialize_register(registers[key]) for key in sorted(registers)}


def _current_schema() -> dict[str, Any]:
    navigator_20 = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_20,
        active_heating_circuits=["A"],
        zone_modules=0,
        has_solar=False,
        has_isc=False,
        has_pv=False,
        has_cascade=False,
    )
    navigator_10 = IdmModelInfo(
        model_name=MODEL_NAVIGATOR_10,
        active_heating_circuits=list("ABCDEFG"),
        zone_modules=10,
        has_solar=True,
        has_isc=True,
        has_pv=True,
        has_cascade=True,
    )

    return {
        "schema_version": 1,
        "maps": {
            "default": _serialize_map(build_register_map()),
            "navigator_10_full": _serialize_map(build_register_map(model_info=navigator_10)),
            "navigator_20_circuit_a": _serialize_map(build_register_map(model_info=navigator_20)),
        },
    }


def test_register_maps_match_versioned_reference_schema() -> None:
    expected = json.loads(REGISTER_SCHEMA.read_text(encoding="utf-8"))

    assert expected["schema_version"] == 1
    assert _current_schema() == expected
