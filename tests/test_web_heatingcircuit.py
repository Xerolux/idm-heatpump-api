"""Tests for the heating-circuit read/write paths (Phase 4 slice 3)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from idm_heatpump import (
    IdmNavigator10WebClient,
    IdmWebResponseError,
    parse_navigator_heatingcircuit_response,
)

HC_DETAIL = json.dumps(
    {
        "remoteSessionId": "x",
        "heatingcircuitDetail": {
            "id": "D",
            "displayName": "D EG",
            "pumpActive": False,
            "mode": {
                "id": "HKD01",
                "type": "chooselist",
                "types": [
                    {"key": 0, "name": "N2_OFF"},
                    {"key": 1, "name": "N2_TIMETABLE"},
                    {"key": 2, "name": "N2_NORMAL"},
                ],
                "value": 0,
            },
            "temperatures": {
                "heating": {
                    "eco": {
                        "id": "HKD05",
                        "increment": "0.1",
                        "max": 25,
                        "min": 10,
                        "type": "float",
                        "value": 19,
                    },
                    "normal": {
                        "id": "HKD04",
                        "increment": "0.1",
                        "max": 30,
                        "min": 15,
                        "type": "float",
                        "value": 22,
                    },
                }
            },
            "room": {"temperatures": {"actual": "21.4", "set": "0.0"}},
            "availableHeatingCircuits": [
                {"displayName": "A OG", "id": "A", "mode": 1},
                {"displayName": "D EG", "id": "D", "mode": 1},
            ],
        },
    }
)

HC_SAVE_SUCCESS = json.dumps(
    {
        "remoteSessionId": "x",
        "heatingcircuitSave": {
            "note": {"text": "value has been saved successfully!", "type": "success"}
        },
    }
)
HC_SAVE_DANGER = json.dumps(
    {
        "remoteSessionId": "x",
        "heatingcircuitSave": {"note": {"text": "value out of range!", "type": "danger"}},
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


class TestHeatingCircuitParsing:
    def test_extracts_the_live_confirmed_state(self) -> None:
        circuit = parse_navigator_heatingcircuit_response(HC_DETAIL)

        assert circuit.hc_id == "D"
        assert circuit.display_name == "D EG"
        assert circuit.mode_value == 0
        assert circuit.mode_parameter_id == "HKD01"
        assert [o.key for o in circuit.mode_options] == [0, 1, 2]
        assert circuit.setpoint_normal is not None
        assert circuit.setpoint_normal.parameter_id == "HKD04"
        assert circuit.setpoint_normal.value == 22
        assert circuit.setpoint_normal.min_value == 15
        assert circuit.setpoint_normal.max_value == 30
        assert circuit.setpoint_eco is not None
        assert circuit.setpoint_eco.parameter_id == "HKD05"
        assert circuit.room_temperature == pytest.approx(21.4)
        assert circuit.pump_active is False
        assert [ref.hc_id for ref in circuit.available_circuits] == ["A", "D"]

    def test_missing_detail_raises(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator_heatingcircuit_response(json.dumps({"setting": {}}))


class TestReadHeatingCircuit:
    @pytest.mark.asyncio
    async def test_sends_the_documented_frame(self) -> None:
        client = _StubClient([HC_DETAIL])

        circuit = await client.read_heatingcircuit("a")

        assert client.captured == [
            {"controller": "system.heatingcircuit", "command": "detail", "data": {"hcId": "A"}}
        ]
        assert circuit.hc_id == "D"

    @pytest.mark.asyncio
    async def test_empty_id_is_rejected(self) -> None:
        client = _StubClient([])
        with pytest.raises(ValueError):
            await client.read_heatingcircuit(" ")


class TestSaveHeatingCircuitParameter:
    @pytest.mark.asyncio
    async def test_write_is_range_validated_and_capture_confirmed(self) -> None:
        client = _StubClient([HC_SAVE_SUCCESS])

        await client.save_heatingcircuit_parameter("HKA04", 21.6, min_value=15, max_value=30)

        assert client.captured == [
            {
                "controller": "system.heatingcircuit",
                "command": "save",
                "data": {"parameterId": "HKA04", "value": 21.6},
            }
        ]

    @pytest.mark.asyncio
    async def test_out_of_range_is_rejected_before_sending(self) -> None:
        client = _StubClient([])

        with pytest.raises(ValueError, match="minimum"):
            await client.save_heatingcircuit_parameter("HKA04", 10, min_value=15, max_value=30)
        with pytest.raises(ValueError, match="maximum"):
            await client.save_heatingcircuit_parameter("HKA04", 40, min_value=15, max_value=30)
        assert client.captured == []

    @pytest.mark.asyncio
    async def test_rejected_write_raises(self) -> None:
        client = _StubClient([HC_SAVE_DANGER])

        with pytest.raises(IdmWebResponseError, match="rejected the write"):
            await client.save_heatingcircuit_parameter("HKA04", 21.6, min_value=15, max_value=30)
