"""Tests for the status/overview and system.freshwater/overview read paths.

Response shapes are taken from a live Navigator 10 capture (jsonVersion 11,
September 2026) with private data removed.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from idm_heatpump import (
    NAVIGATOR10_STATISTIC_EMEH,
    NAVIGATOR10_STATISTIC_EMHP,
    NAVIGATOR10_STATISTIC_ENERGY_FLOW,
    NAVIGATOR10_STATISTIC_HEAT_QUANTITIES,
    NAVIGATOR10_STATISTIC_PERIOD_DAILY,
    NAVIGATOR10_STATISTIC_PERIOD_TODAY,
    NAVIGATOR10_STATISTIC_PERIOD_TOTAL,
    NAVIGATOR10_STATISTIC_RUNTIME_BIVALENCE,
    NAVIGATOR10_STATISTIC_RUNTIME_HEATPUMP,
    IdmNavigator10WebClient,
    IdmWebResponseError,
    parse_navigator_freshwater_response,
    parse_navigator_status_response,
)

STATUS_FRAME = json.dumps(
    {
        "remoteSessionId": "0123456789abcdef0123456789abcdef",
        "status": {
            "authenticationEnabled": True,
            "demoModeActive": False,
            "frostProtectionInfo": {"active": False, "display": False},
            "header": {},
            "jsonVersion": 11,
            "language": "de",
            "network": True,
            "notificationCount": 0,
            "timestamp": 1790576788000,
            "userlevel": 0,
        },
    }
)

FRESHWATER_FRAME = json.dumps(
    {
        "remoteSessionId": "0123456789abcdef0123456789abcdef",
        "freshwater": {
            "circulation": {"active": False},
            "statusInfo": {"status": 16},
            "systemMode": 1,
            "temperatures": {"bottom": "52.6", "top": "56.3"},
        },
    }
)


class TestParseNavigatorStatusResponse:
    def test_extracts_every_live_confirmed_field(self) -> None:
        status = parse_navigator_status_response(STATUS_FRAME)

        assert status.json_version == 11
        assert status.userlevel == 0
        assert status.language == "de"
        assert status.notification_count == 0
        assert status.timestamp_ms == 1790576788000
        assert status.frost_protection_active is False
        assert status.network is True
        assert status.authentication_enabled is True
        assert status.raw_response is None

    def test_include_raw_keeps_the_frame(self) -> None:
        status = parse_navigator_status_response(STATUS_FRAME, include_raw=True)
        assert status.raw_response == STATUS_FRAME

    def test_missing_fields_stay_none_instead_of_failing(self) -> None:
        status = parse_navigator_status_response(json.dumps({"status": {"jsonVersion": 10}}))

        assert status.json_version == 10
        assert status.userlevel is None
        assert status.frost_protection_active is None
        assert status.language is None

    def test_rejects_malformed_responses(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator_status_response("not json")
        with pytest.raises(IdmWebResponseError):
            parse_navigator_status_response("[1, 2, 3]")
        with pytest.raises(IdmWebResponseError):
            parse_navigator_status_response(json.dumps({"home": {}}))


class TestParseNavigatorFreshwaterResponse:
    def test_extracts_every_live_confirmed_field(self) -> None:
        freshwater = parse_navigator_freshwater_response(FRESHWATER_FRAME)

        assert freshwater.circulation_active is False
        assert freshwater.status == 16
        assert freshwater.system_mode == 1
        assert freshwater.temperature_top is not None
        assert freshwater.temperature_top.value == "56.3"
        assert freshwater.temperature_top.numeric_value == pytest.approx(56.3)
        assert freshwater.temperature_top.unit == "°C"
        assert freshwater.temperature_bottom is not None
        assert freshwater.temperature_bottom.numeric_value == pytest.approx(52.6)
        assert freshwater.raw_response is None

    def test_include_raw_keeps_the_frame(self) -> None:
        freshwater = parse_navigator_freshwater_response(FRESHWATER_FRAME, include_raw=True)
        assert freshwater.raw_response == FRESHWATER_FRAME

    def test_missing_blocks_stay_none(self) -> None:
        freshwater = parse_navigator_freshwater_response(
            json.dumps({"freshwater": {"systemMode": 2}})
        )

        assert freshwater.system_mode == 2
        assert freshwater.circulation_active is None
        assert freshwater.status is None
        assert freshwater.temperature_top is None
        assert freshwater.temperature_bottom is None

    def test_non_numeric_temperature_is_kept_as_text(self) -> None:
        freshwater = parse_navigator_freshwater_response(
            json.dumps({"freshwater": {"temperatures": {"top": "--"}}})
        )

        assert freshwater.temperature_top is not None
        assert freshwater.temperature_top.value == "--"
        assert freshwater.temperature_top.numeric_value is None

    def test_rejects_malformed_responses(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator_freshwater_response("not json")
        with pytest.raises(IdmWebResponseError):
            parse_navigator_freshwater_response(json.dumps({"status": {}}))


class _StubClient(IdmNavigator10WebClient):
    """Record sent frames and answer with a fixed response."""

    def __init__(self, frame: str) -> None:
        super().__init__(host="192.0.2.10", pin="1234")
        self.frame = frame
        self.captured: list[dict[str, Any]] = []

    async def connect(self) -> None:
        return None

    async def _send_json_and_receive_text(self, payload: dict[str, Any]) -> str:
        self.captured.append(payload)
        return self.frame


class TestClientReadMethods:
    def test_read_status_overview_sends_the_documented_frame(self) -> None:
        client = _StubClient(STATUS_FRAME)

        status = asyncio.run(client.read_status_overview())

        assert client.captured == [{"controller": "status", "command": "overview"}]
        assert status.json_version == 11

    def test_read_freshwater_overview_sends_the_documented_frame(self) -> None:
        client = _StubClient(FRESHWATER_FRAME)

        freshwater = asyncio.run(client.read_freshwater_overview())

        assert client.captured == [{"controller": "system.freshwater", "command": "overview"}]
        assert freshwater.status == 16


class TestStatisticConstants:
    def test_values_match_the_live_verified_catalog(self) -> None:
        """The values were confirmed frame by frame on a live controller.

        statisticType 1 is deliberately absent: the controller answers
        "specified statistic type [1] is not avaiable!" for it.
        """
        assert NAVIGATOR10_STATISTIC_RUNTIME_HEATPUMP == 0
        assert NAVIGATOR10_STATISTIC_RUNTIME_BIVALENCE == 2
        assert NAVIGATOR10_STATISTIC_EMHP == 3
        assert NAVIGATOR10_STATISTIC_EMEH == 4
        assert NAVIGATOR10_STATISTIC_ENERGY_FLOW == 5
        assert NAVIGATOR10_STATISTIC_HEAT_QUANTITIES == 6

    def test_period_values_match_the_live_verified_aggregations(self) -> None:
        assert NAVIGATOR10_STATISTIC_PERIOD_DAILY == 0
        assert NAVIGATOR10_STATISTIC_PERIOD_TODAY == 1
        assert NAVIGATOR10_STATISTIC_PERIOD_TOTAL == 7
