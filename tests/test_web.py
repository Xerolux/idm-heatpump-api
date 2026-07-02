"""Tests for optional IDM local web interface parsing."""

from __future__ import annotations

import json

import pytest

from idm_heatpump.web import (
    IdmNavigator10WebClient,
    IdmNavigator20WebClient,
    IdmWebAuthenticationError,
    IdmWebResponseError,
    create_optional_navigator10_web_client,
    create_optional_navigator20_web_client,
    parse_idm_html_table_values,
    parse_navigator_notifications_response,
    parse_navigator_setting_response,
    parse_navigator_statistic_response,
    web_pin_configured,
)

NAV10_SENSOR_HTML = """
<table>
<tr><td>B32</td><td>Außentemperatur</td><td>21.7°C</td></tr>
<tr><td>B71</td><td>Heißgastemperatur</td><td>31.0°C</td></tr>
<tr><td>B78</td><td>Verdampferdruck</td><td>7.9bar</td></tr>
<tr><td>B86</td><td>Kondensatordruck</td><td>7.9bar</td></tr>
<tr><td> </td><td>Platinentemperatur</td><td>28.7°C</td></tr>
<tr><td> </td><td>Batteriespannung Zentraleinheit</td><td>3.00V</td></tr>
<tr><td>B2</td><td>Durchfluss</td><td>0.0l/min</td></tr>
<tr><td>B5</td><td>Taupunktwächter Heizkreis A</td><td>1</td><td></td></tr>
<tr><td>Modell</td><td></td><td>iDM ALM 6-15</td></tr>
<tr><td>Laufzeit Stufe&nbsp;1</td><td>24.5h</td></tr>
<tr><td>myIDMID</td><td>m123@example</td></tr>
<tr><td></td><td>Wärmemenge Zapfung</td><td>1653.1</td><td>kWh</td></tr>
<tr><td></td><td>Wärmemenge Zirkulation</td><td>4384.7</td><td>kWh</td></tr>
<tr><td>M124</td><td>Zwischenkreispumpe</td><td>Unterbrechung</td><td>V</td></tr>
</table>
"""


def test_parse_idm_html_table_values_maps_known_values() -> None:
    values = parse_idm_html_table_values(NAV10_SENSOR_HTML)

    assert values["outside_air_temperature"].numeric_value == 21.7
    assert values["outside_air_temperature"].unit == "°C"
    assert values["hotgas_temperature"].value == "31.0°C"
    assert values["verdamper_pressure"].value == "7.9bar"
    assert values["condenser_pressure"].value == "7.9bar"
    assert values["board_temperature"].value == "28.7°C"
    assert values["battery_voltage_central_unit"].numeric_value == 3.0
    assert values["flowmeter"].unit == "l/min"
    assert values["dewpoint_humidity_alarm"].value == "1"
    assert values["heatpump_model"].value == "iDM ALM 6-15"
    assert values["runtime_stage_1_hours"].value == "24.5h"
    assert values["myidm_id"].value == "m123@example"
    assert values["hotwater_tapping_heat_quantity"].value == "1653.1kWh"
    assert values["hotwater_tapping_heat_quantity"].numeric_value == 1653.1
    assert values["hotwater_tapping_heat_quantity"].unit == "kWh"
    assert values["hotwater_circulation_heat_quantity"].value == "4384.7kWh"


def test_parse_navigator_setting_response_extracts_setting_detail_value() -> None:
    raw = json.dumps(
        {
            "settingDetail": {
                "id": "4768",
                "name": "N2_SENSORS",
                "value": NAV10_SENSOR_HTML,
            }
        }
    )

    values = parse_navigator_setting_response(raw)

    assert values["flowmeter"].value == "0.0l/min"


def test_parse_navigator_setting_response_uses_setting_specific_names() -> None:
    raw = json.dumps(
        {
            "settingDetail": {
                "id": "4789",
                "name": "N2_DIGITAL_OUTPUTS",
                "value": """
                <table>
                <tr><td>M1</td><td>Verdichter 1</td><td>0</td><td></td></tr>
                <tr><td>M73</td><td>Ladepumpe</td><td>100</td><td></td></tr>
                <tr><td>M64</td><td>Zirkulationspumpe</td><td>Aus</td><td></td></tr>
                </table>
                """,
            }
        }
    )

    values = parse_navigator_setting_response(raw)

    assert values["compressor_1"].value == "0"
    assert values["flow_pump_output"].value == "100"
    assert values["hotwater_circulation_pump"].value == "Aus"

    raw_analogue = json.dumps(
        {
            "settingDetail": {
                "id": "4782",
                "name": "N2_ANALOGUE_OUTPUTS",
                "value": """
                <table>
                <tr><td>M124</td><td>Zwischenkreispumpe</td><td>Unterbrechung</td><td>V</td></tr>
                </table>
                """,
            }
        }
    )

    analogue_values = parse_navigator_setting_response(raw_analogue)

    assert analogue_values["heat_sink_intermediate_circuit_pump_signal"].value == "Unterbrechung"


def test_parse_navigator_setting_response_rejects_invalid_json() -> None:
    with pytest.raises(IdmWebResponseError):
        parse_navigator_setting_response("not json")


def test_parse_navigator_statistic_response_extracts_total_and_latest_year() -> None:
    raw = json.dumps(
        {
            "statisticDetail": {
                "data": {
                    "total": {"heating": 142.98, "priority": 46.5},
                    "yearly": [{"date": "2026-05-04", "idx": 1, "heating": 12.0, "priority": 3.0}],
                },
                "name": "N2_RUNTIMEHEATPUMP",
                "type": 0,
            }
        }
    )

    values = parse_navigator_statistic_response(raw, "stat_runtime")

    assert values["stat_runtime_total_heating"].value == "142.98"
    assert values["stat_runtime_current_year_priority"].value == "3.0"


def test_parse_navigator_notifications_response_handles_empty_current_list() -> None:
    notifications = parse_navigator_notifications_response(
        '{"notification":{"current":[]},"remoteSessionId":"abc"}'
    )

    assert notifications.count == 0
    assert notifications.summary == "Keine aktiven Meldungen"


def test_parse_navigator_notifications_response_extracts_current_messages() -> None:
    raw = json.dumps(
        {
            "notification": {
                "current": [
                    {
                        "code": "E123",
                        "textEnum": "RD_EXAMPLE_ERROR",
                        "dateTime": 1783032856000,
                        "type": "danger",
                        "quitType": 1,
                        "deferrable": True,
                    },
                    {
                        "code": "W456",
                        "description": "Filter pruefen",
                    },
                ]
            },
            "remoteSessionId": "abc",
        }
    )

    notifications = parse_navigator_notifications_response(raw, include_raw=True)

    assert notifications.count == 2
    assert notifications.current[0].code == "E123"
    assert notifications.current[0].message == "RD_EXAMPLE_ERROR"
    assert notifications.current[0].timestamp == 1783032856000
    assert notifications.current[0].severity == "danger"
    assert notifications.current[0].quit_type == 1
    assert notifications.current[0].deferrable is True
    assert notifications.current[0].raw["code"] == "E123"
    assert notifications.current[1].message == "Filter pruefen"
    assert notifications.summary == "E123: RD_EXAMPLE_ERROR | W456: Filter pruefen"


@pytest.mark.parametrize("pin", [None, "", "   "])
def test_optional_web_client_factories_return_none_without_pin(pin: str | None) -> None:
    assert not web_pin_configured(pin)
    assert create_optional_navigator10_web_client("192.0.2.10", pin) is None
    assert create_optional_navigator20_web_client("192.0.2.10", pin) is None


def test_optional_web_client_factories_create_clients_with_pin() -> None:
    nav10 = create_optional_navigator10_web_client("192.0.2.10", " 1234 ")
    nav20 = create_optional_navigator20_web_client("192.0.2.10", " 1234 ")

    assert web_pin_configured(" 1234 ")
    assert isinstance(nav10, IdmNavigator10WebClient)
    assert isinstance(nav20, IdmNavigator20WebClient)


class FakeWsMessage:
    def __init__(self, data: str) -> None:
        from aiohttp import WSMsgType

        self.type = WSMsgType.TEXT
        self.data = data


class FakeWs:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.sent: list[dict[str, object]] = []
        self.closed = False

    async def receive(self, timeout: float) -> FakeWsMessage:
        return FakeWsMessage(self.responses.pop(0))

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed = True

    def exception(self) -> None:
        return None


class FakeSession:
    def __init__(self, ws: FakeWs) -> None:
        self.ws = ws
        self.urls: list[str] = []

    async def ws_connect(self, url: str, timeout: float) -> FakeWs:
        self.urls.append(url)
        return self.ws


@pytest.mark.asyncio
async def test_navigator10_client_reads_setting_details() -> None:
    setting_raw = json.dumps(
        {"settingDetail": {"id": "4768", "name": "N2_SENSORS", "value": NAV10_SENSOR_HTML}}
    )
    ws = FakeWs(['{"authorized":true}', setting_raw])
    session = FakeSession(ws)
    client = IdmNavigator10WebClient(
        "192.0.2.10",
        "1234",
        timeout=1,
        session=session,
    )

    data = await client.read_data(("4768",))

    assert data.model == "Navigator 10 Web"
    assert data.navigator_version == "Navigator 10"
    assert data.heatpump_model == "iDM ALM 6-15"
    assert data.simple_values["hotgas_temperature"] == "31.0°C"
    assert ws.sent == [
        {
            "controller": "setting",
            "command": "detail",
            "data": {"settingId": "4768"},
        }
    ]
    assert session.urls == ["ws://192.0.2.10:61220/?auth_code=1234"]


@pytest.mark.asyncio
async def test_navigator10_client_reads_notifications() -> None:
    ws = FakeWs(
        [
            '{"authorized":true}',
            '{"notification":{"current":[{"code":"E123","textEnum":"RD_EXAMPLE_ERROR"}]}}',
        ]
    )
    client = IdmNavigator10WebClient("192.0.2.10", "1234", timeout=1, session=FakeSession(ws))

    notifications = await client.read_notifications()

    assert notifications.count == 1
    assert notifications.summary == "E123: RD_EXAMPLE_ERROR"
    assert ws.sent == [{"controller": "notification", "command": "overview"}]


@pytest.mark.asyncio
async def test_navigator10_client_rejects_invalid_pin() -> None:
    ws = FakeWs(['{"authorized":false}'])
    client = IdmNavigator10WebClient("192.0.2.10", "1234", timeout=1, session=FakeSession(ws))

    with pytest.raises(IdmWebAuthenticationError):
        await client.connect()

    assert ws.closed
