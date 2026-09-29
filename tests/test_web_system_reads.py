"""Tests for the system-level read controllers (performance, weather, iON, energyflow).

Fixture frames are the live responses of a Navigator 10 (jsonVersion 11,
firmware T_NAV10_20.24-1580, captured 2026-09-29).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from idm_heatpump import (
    IdmNavigator10WebClient,
    IdmWebResponseError,
    parse_navigator_energyflow_response,
    parse_navigator_ion_response,
    parse_navigator_performance_response,
    parse_navigator_weather_response,
)

PERFORMANCE_DETAIL = json.dumps(
    {
        "remoteSessionId": "dfe17e1c97b14ae5883af3b3ea59bf64",
        "performanceDetail": {
            "consumption": {"battery": False, "power": "1.45", "source": 2},
            "environment": {
                "power": "0.0",
                "source": 2,
                "temperatures": {"in": "17.5"},
            },
            "heatingRod": False,
            "mode": 0,
            "production": {"temperatures": {"flow": "52.3"}},
            "systemMode": 1,
        },
    }
)

WEATHER_DETAIL = json.dumps(
    {
        "remoteSessionId": "dfe17e1c97b14ae5883af3b3ea59bf64",
        "weatherDetail": {
            "forecast1": {
                "cloudCover": 5.940800189971924,
                "date": "30.09.2026",
                "dayofweek": "N2_WE",
                "rainProbability": 0,
                "sun": 33836,
                "sym_w50": 2,
                "temperature": {"act": 17, "max": 25, "min": 10},
                "windSpeed": {"max": 1.8559999465942383, "min": 0.6269000172615051},
            },
            "forecast3": {
                "date": "02.10.2026",
                "dayofweek": "N2_FR",
                "sun": 5539,
                "sym_w50": 5,
                "temperature": {"act": 17, "max": 21, "min": 14},
            },
            "today": {
                "cloudCover": 0.4740999937057495,
                "date": "29.09.2026",
                "dayofweek": "N2_TODAY",
                "rainProbability": 0,
                "sun": 40991,
                "sym_w50": 1,
                "temperature": {"act": 18, "avg": "14°C/16.0h", "max": 25, "min": 9},
                "windSpeed": {"max": 2.7960000038146973, "min": 0.6996999975019213},
            },
        },
    }
)

ION_OVERVIEW = json.dumps(
    {
        "remoteSessionId": "dfe17e1c97b14ae5883af3b3ea59bf64",
        "ion": {
            "active": False,
            "enabled": {
                "id": "CE001",
                "increment": "1",
                "type": "chooselist",
                "types": [{"0": "N2_NO"}, {"1": "N2_YES"}],
                "value": 0,
            },
            "ionSubscriptionStatus": -1,
        },
    }
)

ENERGYFLOW_OVERVIEW = json.dumps(
    {
        "remoteSessionId": "dfe17e1c97b14ae5883af3b3ea59bf64",
        "energyflow": {
            "grid": {"value": "12.9970"},
            "pv": {"value": "5.6940"},
            "signal": 16,
            "type": 4,
        },
    }
)

ENERGYFLOW_WITH_HOUSE = json.dumps(
    {
        "energyflow": {"grid": {"value": "0.0240"}, "house": {"value": "0.4690"}, "pv": {"value": "0.4930"}},
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


class TestPerformanceParsing:
    def test_extracts_the_live_confirmed_state(self) -> None:
        performance = parse_navigator_performance_response(PERFORMANCE_DETAIL)

        assert performance.consumption_power == pytest.approx(1.45)
        assert performance.consumption_source == 2
        assert performance.consumption_battery is False
        assert performance.environment_power == pytest.approx(0.0)
        assert performance.environment_temperature_in == pytest.approx(17.5)
        assert performance.production_flow_temperature == pytest.approx(52.3)
        assert performance.heating_rod is False
        assert performance.mode == 0
        assert performance.system_mode == 1

    def test_missing_detail_raises(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator_performance_response(json.dumps({"performance": {}}))

    @pytest.mark.asyncio
    async def test_client_sends_the_documented_frame(self) -> None:
        client = _StubClient([PERFORMANCE_DETAIL])

        performance = await client.read_performance()

        assert client.captured == [
            {"controller": "system.heatpump.performance", "command": "detail"}
        ]
        assert performance.consumption_power == pytest.approx(1.45)


class TestWeatherParsing:
    def test_extracts_today_and_forecasts_in_order(self) -> None:
        weather = parse_navigator_weather_response(WEATHER_DETAIL)

        assert weather.today is not None
        assert weather.today.date == "29.09.2026"
        assert weather.today.day_of_week == "N2_TODAY"
        assert weather.today.sun_seconds == 40991
        assert weather.today.symbol == 1
        assert weather.today.temperature == 18
        assert weather.today.temperature_min == 9
        assert weather.today.temperature_max == 25
        assert weather.today.temperature_avg_label == "14°C/16.0h"
        assert weather.today.cloud_cover == pytest.approx(0.4741)
        assert weather.today.wind_speed_max == pytest.approx(2.796)

        assert [day.date for day in weather.forecasts] == ["30.09.2026", "02.10.2026"]
        first = weather.forecasts[0]
        assert first.rain_probability == 0
        assert first.wind_speed_min == pytest.approx(0.6269)
        assert weather.forecasts[1].cloud_cover is None  # firmware omitted it

    def test_missing_detail_raises(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator_weather_response(json.dumps({"weather": {}}))

    @pytest.mark.asyncio
    async def test_client_sends_the_documented_frame(self) -> None:
        client = _StubClient([WEATHER_DETAIL])

        weather = await client.read_weather()

        assert client.captured == [{"controller": "weather", "command": "detail"}]
        assert weather.today is not None


class TestIonParsing:
    def test_extracts_the_live_confirmed_state(self) -> None:
        ion = parse_navigator_ion_response(ION_OVERVIEW)

        assert ion.active is False
        assert ion.enabled_setting_id == "CE001"
        assert ion.enabled_value == 0
        assert ion.subscription_status == -1

    def test_missing_ion_raises(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator_ion_response(json.dumps({"status": {}}))

    @pytest.mark.asyncio
    async def test_client_sends_the_documented_frame(self) -> None:
        client = _StubClient([ION_OVERVIEW])

        ion = await client.read_ion()

        assert client.captured == [{"controller": "ion", "command": "overview"}]
        assert ion.active is False


class TestEnergyflowParsing:
    def test_extracts_the_live_confirmed_state_without_house(self) -> None:
        flow = parse_navigator_energyflow_response(ENERGYFLOW_OVERVIEW)

        assert flow.grid_power == pytest.approx(12.997)
        assert flow.pv_power == pytest.approx(5.694)
        assert flow.house_power is None  # removed in firmware 20.24-1580
        assert flow.signal == 16
        assert flow.type == 4

    def test_older_firmware_house_channel_still_parses(self) -> None:
        flow = parse_navigator_energyflow_response(ENERGYFLOW_WITH_HOUSE)

        assert flow.house_power == pytest.approx(0.469)
        assert flow.grid_power == pytest.approx(0.024)

    def test_missing_energyflow_raises(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator_energyflow_response(json.dumps({"home": {}}))

    @pytest.mark.asyncio
    async def test_client_sends_the_documented_frame(self) -> None:
        client = _StubClient([ENERGYFLOW_OVERVIEW])

        flow = await client.read_energyflow()

        assert client.captured == [{"controller": "energyflow", "command": "overview"}]
        assert flow.pv_power == pytest.approx(5.694)
