"""Tests for the Navigator 10 home/detail demand-reason decoding."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from idm_heatpump import (
    NAVIGATOR10_DHW_DEMAND_REASON_BITS,
    NAVIGATOR10_HEATING_DEMAND_REASON_BITS,
    IdmNavigator10WebClient,
    IdmWebResponseError,
    decode_navigator10_demand_reason,
    parse_navigator_home_response,
)


def test_heating_table_decodes_every_documented_bit() -> None:
    expected = {
        2: "no_info",
        4: "external_input",
        8: "external_bus",
        16: "isc",
        32: "pv",
        64: "frost_protection",
        128: "hc_a",
        256: "hc_b",
        512: "hc_c",
        1024: "hc_d",
        2048: "hc_e",
        4096: "hc_f",
        8192: "hc_g",
        16384: "system_off",
        32768: "ion",
    }
    assert expected == dict(NAVIGATOR10_HEATING_DEMAND_REASON_BITS)
    for bit, reason in expected.items():
        assert decode_navigator10_demand_reason(1, bit) == reason


def test_dhw_table_decodes_every_documented_bit() -> None:
    expected = {
        2: "single_loading",
        4: "single_loading_boost",
        8: "external_input",
        16: "external_bus",
        32: "pv",
        64: "isc",
        128: "schedule",
        256: "schedule_boost",
        512: "system_off",
        1024: "dhw_comfort",
        2048: "ion",
        4096: "cascade",
        8192: "dhw_booster",
    }
    assert expected == dict(NAVIGATOR10_DHW_DEMAND_REASON_BITS)
    for bit, reason in expected.items():
        assert decode_navigator10_demand_reason(4, bit) == reason


def test_bit_32_means_pv_in_both_tables() -> None:
    assert decode_navigator10_demand_reason(1, 32) == "pv"
    assert decode_navigator10_demand_reason(4, 32) == "pv"


def test_multiple_bits_mean_more_demands_ignoring_bit_zero() -> None:
    assert decode_navigator10_demand_reason(1, 4 | 8) == "more_demands"
    assert decode_navigator10_demand_reason(4, 64 | 128) == "more_demands"
    assert decode_navigator10_demand_reason(1, 32 | 1) == "pv"


def test_operation_modes_without_active_demand() -> None:
    assert decode_navigator10_demand_reason(0, 32) == "no_info"
    assert decode_navigator10_demand_reason(8, 32) == "off"


def test_undecodable_inputs_return_none() -> None:
    assert decode_navigator10_demand_reason(1, None) is None
    assert decode_navigator10_demand_reason(None, 32) is None
    assert decode_navigator10_demand_reason(3, 32) is None
    assert decode_navigator10_demand_reason(1, 1 << 20) is None


def test_parse_walks_home_push_envelope() -> None:
    payload: dict[str, Any] = {
        "home": {
            "1": {
                "3x2": {
                    "grid": {"value": "11.8460"},
                    "pv": {"value": "5.5030"},
                    "signal": 16,
                    "type": 4,
                },
            },
            "10": {"1x2": {"operationMode": 0}},
            "17": {"1x1": {"operationMode": 0}},
            "18": {"1x1": {"activeMode": 1, "displayName": "A OG", "pumpActive": False}},
        },
        "remoteSessionId": "session",
    }
    detail = parse_navigator_home_response(json.dumps(payload))

    assert [node.operation_mode for node in detail.demand_reasons] == [0, 0]
    assert all(node.reason == "no_info" for node in detail.demand_reasons)
    assert detail.pv_power is not None
    assert detail.pv_power.numeric_value == pytest.approx(5.503)
    assert detail.grid_power is not None
    assert detail.grid_power.numeric_value == pytest.approx(11.846)
    assert detail.pv_demand_active is False
    assert detail.raw_response is None


def test_parse_walks_home_detail_envelope_with_active_pv_demand() -> None:
    payload: dict[str, Any] = {
        "homeDetail": {
            "data": {
                "10": {"operationMode": 1, "info": 32},
                "17": {"operationMode": 0},
            }
        }
    }
    detail = parse_navigator_home_response(json.dumps(payload), include_raw=True)

    assert detail.pv_demand_active is True
    reasons = [node.reason for node in detail.demand_reasons]
    assert reasons == ["pv", "no_info"]
    assert detail.raw_response is not None


def test_parse_tolerates_missing_energy_flow_and_info() -> None:
    detail = parse_navigator_home_response(json.dumps({"home": {}}))
    assert detail.demand_reasons == ()
    assert detail.pv_power is None
    assert detail.grid_power is None
    assert detail.pv_demand_active is False


def test_parse_rejects_malformed_responses() -> None:
    with pytest.raises(IdmWebResponseError):
        parse_navigator_home_response("not json")
    with pytest.raises(IdmWebResponseError):
        parse_navigator_home_response("[1, 2, 3]")


def test_client_read_home_detail_sends_the_documented_frame() -> None:
    frame = json.dumps({"homeDetail": {"data": {"10": {"operationMode": 4, "info": 32}}}})
    captured: list[dict[str, Any]] = []

    class _StubClient(IdmNavigator10WebClient):
        async def connect(self) -> None:
            return None

        async def _send_json_and_receive_text(self, payload: dict[str, Any]) -> str:
            captured.append(payload)
            return frame

    client = _StubClient(host="192.168.178.103", pin="0000")
    detail = asyncio.run(client.read_home_detail())

    assert captured == [{"controller": "home", "command": "detail"}]
    assert detail.pv_demand_active is True
