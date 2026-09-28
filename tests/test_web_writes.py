"""Tests for the Navigator 10 WebSocket write methods (Phase 4 slice 1).

Frame and response shapes are taken from the 2026-09-28 capture session
(read-only analysis plus harmless reversible actions).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from idm_heatpump import (
    NAVIGATOR10_SYSTEM_MODE_AUTOMATIC,
    NAVIGATOR10_SYSTEM_MODE_HOT_WATER_ONLY,
    NAVIGATOR10_WRITABLE_SYSTEM_MODES,
    IdmNavigator10WebClient,
    IdmWebResponseError,
    parse_navigator_home_overview_response,
    parse_navigator_save_response,
)

HOME_SAVE_SUCCESS = json.dumps(
    {
        "remoteSessionId": "x",
        "homeSave": {"note": {"text": "value has been saved successfully!", "type": "success"}},
    }
)
NOTIFICATION_SAVE_SUCCESS = json.dumps(
    {
        "remoteSessionId": "x",
        "notificationSave": {
            "note": {"text": "cancellation has been executed successfully!", "type": "success"}
        },
    }
)
SAVE_DANGER = json.dumps(
    {
        "remoteSessionId": "x",
        "homeSave": {"note": {"text": "value is out of range!", "type": "danger"}},
    }
)

HOME_OVERVIEW_FRAME = json.dumps(
    {
        "remoteSessionId": "x",
        "home": {
            "7": {
                "1x2": {
                    "systemMode": {
                        "coolingConfigured": False,
                        "options": [
                            {"value": -1},
                            {"value": 0},
                            {"value": 1},
                            {"value": 2},
                            {"value": 3},
                            {"value": 5},
                            {"value": 4},
                        ],
                        "value": 1,
                    }
                }
            }
        },
    }
)


class _StubClient(IdmNavigator10WebClient):
    def __init__(self, response: str) -> None:
        super().__init__(host="192.0.2.10", pin="1234")
        self.response = response
        self.captured: list[dict[str, Any]] = []

    async def connect(self) -> None:
        return None

    async def _send_json_and_receive_text(self, payload: dict[str, Any]) -> str:
        self.captured.append(payload)
        return self.response


class TestSaveResponseParsing:
    def test_success_note_is_returned(self) -> None:
        assert (
            parse_navigator_save_response(HOME_SAVE_SUCCESS, "homeSave")
            == "value has been saved successfully!"
        )

    def test_danger_note_raises(self) -> None:
        with pytest.raises(IdmWebResponseError, match="out of range"):
            parse_navigator_save_response(SAVE_DANGER, "homeSave")

    def test_missing_key_raises(self) -> None:
        with pytest.raises(IdmWebResponseError, match="homeSave"):
            parse_navigator_save_response(json.dumps({"remoteSessionId": "x"}), "homeSave")

    def test_non_json_raises(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator_save_response("not json", "homeSave")


class TestHomeOverviewParsing:
    def test_extracts_system_mode_from_live_shape(self) -> None:
        overview = parse_navigator_home_overview_response(HOME_OVERVIEW_FRAME)

        assert overview.system_mode is not None
        assert overview.system_mode.value == 1
        assert overview.system_mode.options == (-1, 0, 1, 2, 3, 5, 4)
        assert overview.system_mode.cooling_configured is False

    def test_missing_tile_yields_none(self) -> None:
        overview = parse_navigator_home_overview_response(json.dumps({"home": {"1": {}}}))

        assert overview.system_mode is None


class TestSetSystemMode:
    def test_sends_the_capture_confirmed_frame(self) -> None:
        client = _StubClient(HOME_SAVE_SUCCESS)

        asyncio.run(client.set_system_mode(NAVIGATOR10_SYSTEM_MODE_HOT_WATER_ONLY))

        assert client.captured == [
            {
                "controller": "home",
                "command": "save",
                "data": {"systemMode": {"value": NAVIGATOR10_SYSTEM_MODE_HOT_WATER_ONLY}},
            }
        ]

    def test_rejects_invalid_modes_before_sending(self) -> None:
        client = _StubClient(HOME_SAVE_SUCCESS)

        for bad in (-1, 6, 99, True, "1", 1.5, None):
            with pytest.raises(ValueError):
                asyncio.run(client.set_system_mode(bad))  # type: ignore[arg-type]

        assert client.captured == []

    def test_writable_modes_are_the_modbus_numbering(self) -> None:
        assert NAVIGATOR10_WRITABLE_SYSTEM_MODES == frozenset({0, 1, 2, 3, 4, 5})
        assert NAVIGATOR10_SYSTEM_MODE_AUTOMATIC == 1
        assert NAVIGATOR10_SYSTEM_MODE_HOT_WATER_ONLY == 4

    def test_rejected_write_raises(self) -> None:
        client = _StubClient(SAVE_DANGER)

        with pytest.raises(IdmWebResponseError, match="rejected the write"):
            asyncio.run(client.set_system_mode(0))


class TestNotificationAcknowledgement:
    def test_quit_all_sends_the_capture_confirmed_frame(self) -> None:
        client = _StubClient(NOTIFICATION_SAVE_SUCCESS)

        asyncio.run(client.acknowledge_all_notifications())

        assert client.captured == [
            {"controller": "notification", "command": "save", "data": {"quitAll": True}}
        ]

    def test_single_acknowledgement_sends_code_and_remind_flag(self) -> None:
        client = _StubClient(NOTIFICATION_SAVE_SUCCESS)

        asyncio.run(client.acknowledge_notification("20005", remind_me_later=True))

        assert client.captured == [
            {
                "controller": "notification",
                "command": "save",
                "data": {"code": "20005", "remindMeLater": True},
            }
        ]

    def test_empty_code_is_rejected_before_sending(self) -> None:
        client = _StubClient(NOTIFICATION_SAVE_SUCCESS)

        with pytest.raises(ValueError):
            asyncio.run(client.acknowledge_notification("  "))

        assert client.captured == []


class TestReadHomeOverview:
    def test_sends_the_documented_frame(self) -> None:
        client = _StubClient(HOME_OVERVIEW_FRAME)

        overview = asyncio.run(client.read_home_overview())

        assert client.captured == [{"controller": "home", "command": "overview"}]
        assert overview.system_mode is not None
        assert overview.system_mode.value == 1
