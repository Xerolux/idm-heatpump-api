"""Tests for the Navigator 2.0 statistics pages and the clock setting (2.11.0)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest

from idm_heatpump import (
    IdmNavigator10WebClient,
    IdmNavigator20WebClient,
    IdmWebResponseError,
    parse_navigator20_statistics_response,
)

RUNTIME_JSON = json.dumps(
    {
        "unitTotal": "h",
        "total": [
            {"name": "Heizen", "value": 3379.48},
            {"name": "Warmwasser", "value": 319.77},
            {"name": "Abtauung", "value": 59.72},
        ],
    }
)
GENHEAT_JSON = json.dumps(
    {
        "unitTotal": "kWh",
        "total": [
            {"name": "Heizen", "value": 27316.22},
            {"name": "Warmwasser", "value": 3587.84},
        ],
    }
)
ELCONS_WH_JSON = json.dumps(
    {
        "unitTotal": "Wh",
        "total": [
            {"name": "Heating", "value": 5000},
            {"name": "Domestic Hot Water", "value": 1500},
        ],
    }
)


class TestStatisticsParsing:
    def test_runtime_categories_in_hours(self) -> None:
        values = parse_navigator20_statistics_response(RUNTIME_JSON, "runtime")

        assert values["stat_runtime_total_heating"].numeric_value == pytest.approx(3379.48)
        assert values["stat_runtime_total_heating"].unit == "h"
        assert values["stat_runtime_total_hotwater"].numeric_value == pytest.approx(319.77)
        assert values["stat_runtime_total_defrost"].numeric_value == pytest.approx(59.72)

    def test_energy_categories_in_kwh(self) -> None:
        values = parse_navigator20_statistics_response(GENHEAT_JSON, "genheat")

        assert values["stat_genheat_total_heating"].numeric_value == pytest.approx(27316.22)
        assert values["stat_genheat_total_heating"].unit == "kWh"

    def test_unit_scaling_normalizes_to_kwh(self) -> None:
        values = parse_navigator20_statistics_response(ELCONS_WH_JSON, "elcons")

        assert values["stat_elcons_total_heating"].numeric_value == pytest.approx(5.0)
        assert values["stat_elcons_total_hotwater"].numeric_value == pytest.approx(1.5)

    def test_unknown_categories_are_skipped(self) -> None:
        raw = json.dumps({"unitTotal": "kWh", "total": [{"name": "Zukunft", "value": 1}]})
        assert parse_navigator20_statistics_response(raw, "genheat") == {}

    def test_non_json_raises(self) -> None:
        with pytest.raises(IdmWebResponseError):
            parse_navigator20_statistics_response("nope", "runtime")


class _StubNav20(IdmNavigator20WebClient):
    def __init__(self, responses: dict[str, str]) -> None:
        super().__init__(host="192.0.2.10", pin="1234")
        self.responses = responses
        self.requests: list[tuple[str, str]] = []

    async def login(self) -> None:
        return None

    async def _request_text(self, method: str, path: str, **kwargs: Any) -> str:
        self.requests.append((method, path))
        if path not in self.responses:
            raise IdmWebResponseError(f"404 {path}")
        return self.responses[path]


class TestReadStatistics:
    @pytest.mark.asyncio
    async def test_reads_all_three_pages_and_merges(self) -> None:
        client = _StubNav20(
            {
                "/data/statistics.php?type=heatpump": RUNTIME_JSON,
                "/data/statistics.php?type=amountofheat": GENHEAT_JSON,
                "/data/statistics.php?type=baenergyhp": ELCONS_WH_JSON,
            }
        )

        data = await client.read_statistics()

        assert data.values["stat_runtime_total_heating"].numeric_value == pytest.approx(3379.48)
        assert data.values["stat_genheat_total_heating"].numeric_value == pytest.approx(27316.22)
        assert data.values["stat_elcons_total_heating"].numeric_value == pytest.approx(5.0)

    @pytest.mark.asyncio
    async def test_missing_pages_are_skipped(self) -> None:
        client = _StubNav20({"/data/statistics.php?type=heatpump": RUNTIME_JSON})

        data = await client.read_statistics()

        assert "stat_runtime_total_heating" in data.values
        assert "stat_genheat_total_heating" not in data.values

    @pytest.mark.asyncio
    async def test_no_page_answered_raises(self) -> None:
        client = _StubNav20({})

        with pytest.raises(IdmWebResponseError, match="none of the statistics"):
            await client.read_statistics()


class TestSetDatetime:
    @pytest.mark.asyncio
    async def test_nav10_sends_the_capture_confirmed_frame(self) -> None:
        class _Stub10(IdmNavigator10WebClient):
            def __init__(self) -> None:
                super().__init__(host="192.0.2.10", pin="1234")
                self.captured: list[dict[str, Any]] = []

            async def connect(self) -> None:
                return None

            async def _send_json_and_receive_text(self, payload: dict[str, Any]) -> str:
                self.captured.append(payload)
                return json.dumps(
                    {
                        "settingSave": {
                            "note": {
                                "text": "value has been saved successfully!",
                                "type": "success",
                            },
                            "redirect": {"command": "overview", "controller": "setting"},
                        }
                    }
                )

        client = _Stub10()
        moment = datetime(2026, 9, 29, 12, 30, 0, tzinfo=UTC)

        await client.set_datetime(moment)

        assert client.captured == [
            {
                "controller": "setting",
                "command": "save",
                "data": {"settingId": "4537", "value": "2026-09-29T12:30:00+00:00"},
            }
        ]

    @pytest.mark.asyncio
    async def test_non_datetime_is_rejected(self) -> None:
        class _Stub10(IdmNavigator10WebClient):
            async def connect(self) -> None:
                return None

        client = _Stub10(host="192.0.2.10", pin="1234")
        with pytest.raises(ValueError):
            await client.set_datetime("2026-09-29")  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_nav20_builds_the_setdt_payload(self) -> None:
        class _Stub20(_StubNav20):
            def __init__(self) -> None:
                super().__init__({})
                self.put_calls: list[tuple[str, bytes]] = []

            class _PutResponse:
                status = 200

                async def text(self) -> str:
                    return "OK"

            class _PutCtx:
                def __init__(self, outer: "_Stub20") -> None:
                    self._outer = outer

                async def __aenter__(self) -> "_Stub20._PutResponse":
                    return _Stub20._PutResponse()

                async def __aexit__(self, *args: Any) -> None:
                    return None

            def put(self, url: str, data: bytes | None = None, **kwargs: Any) -> "_Stub20._PutCtx":
                self.put_calls.append((url, data or b""))
                return _Stub20._PutCtx(self)

        class _Session:
            def __init__(self, stub: _Stub20) -> None:
                self._stub = stub

            def put(self, url: str, **kwargs: Any) -> _Stub20._PutCtx:
                return self._stub.put(url, **kwargs)

        client = _Stub20()
        client._session = _Session(client)  # type: ignore[assignment]
        moment = datetime(2026, 9, 29, 12, 30, 0)

        await client.set_datetime(moment)

        url, body = client.put_calls[0]
        assert url.endswith("/index.php")
        assert b"SSETDATETIME" in body
        assert b"2026-09-29T12:30:00" in body
