"""Synthetic schema regressions; no donated plant identifiers or readings."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from idm_heatpump.web import (
    IdmNavigator20WebClient,
    _looks_like_data_response,
    parse_navigator20_response,
    parse_navigator20_statistics_response,
)


def test_structured_temperatures_use_existing_sensor_names() -> None:
    payload = {
        "system": {"temperatures": {"hpout": "37.5", "hpin": "31.25"}},
        "out": -4.5,
        "header": {"myIDMID": "PRIVATE-EXAMPLE"},
        "hk": [
            {
                "hk": "B",
                "name": "Custom room title",
                "flow": {"temperatures": {"act": "28.75", "set": 35}},
                "room": {"temperatures": {"act": "19.25"}},
            }
        ],
    }
    values = parse_navigator20_response(json.dumps(payload))
    assert {name: value.numeric_value for name, value in values.items()} == {
        "flow_temperature": 37.5,
        "return_temperature": 31.25,
        "outside_air_temperature": -4.5,
        "flow_temp_HK_B": 28.75,
        "room_temperature_HK_B": 19.25,
    }
    assert all(value.unit == "°C" for value in values.values())
    assert "PRIVATE-EXAMPLE" not in str(values)
    assert "Custom room title" not in str(values)
    assert _looks_like_data_response('{"system":{"temperatures":{"hpout":"37.5"}}}')


@pytest.mark.parametrize("value", [None, True, False, "---", "nan", "inf", [], {}])
def test_missing_and_nonfinite_temperatures_are_not_zero(value: object) -> None:
    assert parse_navigator20_response(json.dumps({"out": value})) == {}
    assert parse_navigator20_response('{"out":0}')["outside_air_temperature"].numeric_value == 0


def test_ambiguous_or_unknown_circuit_ids_are_not_assigned() -> None:
    entries = [
        {"hk": key, "flow": {"temperatures": {"act": 28}}}
        for key in ("A", "A", "A", "unknown", "AA", "a")
    ]
    assert parse_navigator20_response(json.dumps({"hk": entries})) == {}


def test_legacy_html_and_json_embedded_html_remain_supported() -> None:
    table = "<table><tr><td>B33</td><td>37.5 °C</td></tr></table>"
    for text in (table, json.dumps({"settings": table})):
        value = parse_navigator20_response(text)["flow_temperature"]
        assert value.numeric_value == 37.5
        assert value.unit == "°C"


@pytest.mark.parametrize(
    "unit,factor", [("h", 1), ("min", 1 / 60), ("Wh", 0.001), ("kWh", 1), ("MWh", 1000)]
)
def test_version_two_statistics_keep_scaling_and_legacy_keys(unit: str, factor: float) -> None:
    body = {
        "unitTotal": unit,
        "total": [
            {"name": "Heizen", "value": 120},
            {"name": "Kühlen", "value": 0},
            {"name": "Warmwasser", "value": 30},
        ],
    }
    kind = "runtime" if unit in ("h", "min") else "genheat"
    old = parse_navigator20_statistics_response(json.dumps(body), kind)
    new = parse_navigator20_statistics_response(json.dumps({"version": 2, "data": body}), kind)
    assert new == old
    assert new[f"stat_{kind}_total_heating"].numeric_value == 120 * factor
    assert new[f"stat_{kind}_total_cooling"].numeric_value == 0


@pytest.mark.asyncio
async def test_read_data_uses_the_json_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    client = IdmNavigator20WebClient("192.0.2.10", "example-pin", session=object())
    client._data_paths = ("/data/heatpump.php",)
    request = AsyncMock(return_value='{"system":{"temperatures":{"hpout":"37.5"}}}')
    monkeypatch.setattr(client, "_request_text", request)
    result = await client.read_data(include_raw=True)
    assert result.values["flow_temperature"].numeric_value == 37.5
    assert "/data/heatpump.php" in result.raw_responses
    request.assert_awaited_once_with("GET", "/data/heatpump.php")
