"""Tests for the range-validated web setpoint writes (Phase 4 slice 2)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from idm_heatpump import (
    NAVIGATOR10_DHW_SETPOINT_PARAM,
    NAVIGATOR10_DHW_SETPOINT_SETTING_ID,
    IdmNavigator10WebClient,
    IdmWebResponseError,
    parse_navigator_setting_parameter,
)

SETTING_DETAIL = json.dumps(
    {
        "remoteSessionId": "x",
        "settingDetail": {
            "def": 46,
            "description": "N2D_HOT_WATER_DESIRED_TEMP",
            "id": "13256",
            "increment": "0.5",
            "max": 60,
            "min": 30,
            "name": "N2_HOT_WATER_DESIRED_TEMP",
            "param": "FW030",
            "redirectId": "13231",
            "type": "float",
            "unit": "N2_GRAD",
            "value": 48,
        },
    }
)

FRESHWATER_SAVE_SUCCESS = json.dumps(
    {
        "remoteSessionId": "x",
        "freshwaterSave": {
            "note": {"text": "value has been saved successfully!", "type": "success"}
        },
    }
)
FRESHWATER_SAVE_DANGER = json.dumps(
    {
        "remoteSessionId": "x",
        "freshwaterSave": {"note": {"text": "value out of range!", "type": "danger"}},
    }
)


class _StubClient(IdmNavigator10WebClient):
    def __init__(self, responses: list[str]) -> None:
        super().__init__(host="192.0.2.10", pin="1234")
        self.responses = list(responses)
        self.captured: list[dict[str, Any]] = []

    async def connect(self) -> None:
        return None

    async def _send_json_and_receive_text(self, payload: dict[str, Any]) -> str:
        self.captured.append(payload)
        return self.responses.pop(0)


class TestSettingParameterParsing:
    def test_extracts_the_live_confirmed_definition(self) -> None:
        parameter = parse_navigator_setting_parameter(SETTING_DETAIL)

        assert parameter.setting_id == "13256"
        assert parameter.name == "N2_HOT_WATER_DESIRED_TEMP"
        assert parameter.param == "FW030"
        assert parameter.type == "float"
        assert parameter.value == 48
        assert parameter.min_value == 30
        assert parameter.max_value == 60
        assert parameter.increment == "0.5"
        assert parameter.default == 46

    def test_missing_detail_raises(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator_setting_parameter(json.dumps({"setting": {}}))

    def test_non_json_raises(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator_setting_parameter("nope")


class TestSaveFreshwaterParameter:
    @pytest.mark.asyncio
    async def test_validates_against_the_device_declared_range(self) -> None:
        client = _StubClient([SETTING_DETAIL, FRESHWATER_SAVE_SUCCESS])

        await client.save_freshwater_parameter("FW030", 49, setting_id="13256")

        assert client.captured[0] == {
            "controller": "setting",
            "command": "detail",
            "data": {"settingId": "13256"},
        }
        assert client.captured[1] == {
            "controller": "system.freshwater",
            "command": "save",
            "data": {"parameterId": "FW030", "value": 49},
        }

    @pytest.mark.asyncio
    async def test_below_minimum_is_rejected_before_sending(self) -> None:
        client = _StubClient([SETTING_DETAIL])

        with pytest.raises(ValueError, match="minimum"):
            await client.save_freshwater_parameter("FW030", 25, setting_id="13256")

        assert len(client.captured) == 1

    @pytest.mark.asyncio
    async def test_above_maximum_is_rejected_before_sending(self) -> None:
        client = _StubClient([SETTING_DETAIL])

        with pytest.raises(ValueError, match="maximum"):
            await client.save_freshwater_parameter("FW030", 65, setting_id="13256")

    @pytest.mark.asyncio
    async def test_mismatched_setting_param_is_rejected(self) -> None:
        client = _StubClient([SETTING_DETAIL])

        with pytest.raises(ValueError, match="is parameter FW030"):
            await client.save_freshwater_parameter("FW999", 49, setting_id="13256")

    @pytest.mark.asyncio
    async def test_non_numeric_value_is_rejected(self) -> None:
        client = _StubClient([])

        with pytest.raises(ValueError):
            await client.save_freshwater_parameter("FW030", "49")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_rejected_write_raises(self) -> None:
        client = _StubClient([SETTING_DETAIL, FRESHWATER_SAVE_DANGER])

        with pytest.raises(IdmWebResponseError, match="rejected the write"):
            await client.save_freshwater_parameter("FW030", 49, setting_id="13256")


class TestSaveDhwSetpoint:
    @pytest.mark.asyncio
    async def test_uses_the_capture_confirmed_ids(self) -> None:
        assert NAVIGATOR10_DHW_SETPOINT_SETTING_ID == "13256"
        assert NAVIGATOR10_DHW_SETPOINT_PARAM == "FW030"

    @pytest.mark.asyncio
    async def test_round_trip_frame_sequence(self) -> None:
        client = _StubClient([SETTING_DETAIL, FRESHWATER_SAVE_SUCCESS])

        await client.save_dhw_setpoint(47.5)

        assert client.captured[0]["data"] == {"settingId": "13256"}
        assert client.captured[1]["data"] == {"parameterId": "FW030", "value": 47.5}
