"""Tests for optional IDM local web interface parsing."""

from __future__ import annotations

import json

import pytest

from idm_heatpump.web import (
    DEFAULT_NAVIGATOR10_REQUEST_DELAY,
    WEB_VALUE_DESCRIPTIONS,
    IdmNavigator10WebClient,
    IdmNavigator20WebClient,
    IdmWebAuthenticationError,
    IdmWebConnectionError,
    IdmWebData,
    IdmWebResponseError,
    IdmWebValue,
    _extract_csrf_token,
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


def test_web_data_helpers_return_defaults_and_numeric_values() -> None:
    data = IdmWebData(
        model="Navigator 10 Web",
        values={"flowmeter": IdmWebValue("flowmeter", "12.5l/min", "B2", numeric_value=12.5)},
    )

    assert data.get_value("flowmeter") == "12.5l/min"
    assert data.get_value("missing", "fallback") == "fallback"
    assert data.get_numeric("flowmeter") == 12.5
    assert data.get_numeric("missing", 0.0) == 0.0
    assert WEB_VALUE_DESCRIPTIONS["flowmeter"].preferred_unit == "l/min"


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
    assert nav10._request_delay == DEFAULT_NAVIGATOR10_REQUEST_DELAY
    assert nav10._pin == "1234"
    assert nav20._pin == "1234"


class FakeWsMessage:
    def __init__(self, data: str) -> None:
        self.type = "TEXT"
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


class FailingSendWs(FakeWs):
    async def send_json(self, payload: dict[str, object]) -> None:
        self.closed = True
        raise OSError("drop")


class FakeSession:
    def __init__(self, ws: FakeWs | list[FakeWs]) -> None:
        self.ws = ws
        self.urls: list[str] = []
        self.closed = False

    async def ws_connect(self, url: str, timeout: float) -> FakeWs:
        self.urls.append(url)
        if isinstance(self.ws, list):
            return self.ws.pop(0)
        return self.ws

    async def close(self) -> None:
        self.closed = True


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
async def test_navigator10_client_reconnects_once_after_stale_websocket() -> None:
    setting_raw = json.dumps(
        {"settingDetail": {"id": "4768", "name": "N2_SENSORS", "value": NAV10_SENSOR_HTML}}
    )
    stale_ws = FakeWs(['{"authorized":true}'])
    fresh_ws = FakeWs(['{"authorized":true}', setting_raw])
    session = FakeSession([stale_ws, fresh_ws])
    client = IdmNavigator10WebClient("192.0.2.10", "1234", timeout=1, session=session)

    await client.connect()
    stale_ws.closed = True

    data = await client.read_data(("4768",))

    assert data.get_value("flowmeter") == "0.0l/min"
    assert len(session.urls) == 2
    assert fresh_ws.sent == [
        {
            "controller": "setting",
            "command": "detail",
            "data": {"settingId": "4768"},
        }
    ]


@pytest.mark.asyncio
async def test_navigator10_client_can_skip_inter_setting_delay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    setting_raw = json.dumps(
        {"settingDetail": {"id": "4768", "name": "N2_SENSORS", "value": NAV10_SENSOR_HTML}}
    )
    ws = FakeWs(['{"authorized":true}', setting_raw, setting_raw])
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("idm_heatpump.web.asyncio.sleep", fake_sleep)
    client = IdmNavigator10WebClient(
        "192.0.2.10",
        "1234",
        timeout=1,
        request_delay=0,
        session=FakeSession(ws),
    )

    await client.read_data(("4768", "4775"))

    assert sleeps == []


@pytest.mark.asyncio
async def test_navigator10_client_closes_owned_session_on_connect_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingSession:
        def __init__(self) -> None:
            self.closed = False

        async def ws_connect(self, url: str, timeout: float) -> FakeWs:
            raise OSError("connection refused")

        async def close(self) -> None:
            self.closed = True

    session = FailingSession()
    monkeypatch.setattr("aiohttp.ClientSession", lambda: session)
    client = IdmNavigator10WebClient("192.0.2.10", "1234", timeout=1)

    with pytest.raises(IdmWebConnectionError, match="connection failed"):
        await client.connect()

    assert session.closed is True
    assert client._session is None
    assert client._own_session is False


@pytest.mark.asyncio
async def test_navigator10_client_parses_pretty_printed_auth_response() -> None:
    ws = FakeWs(['{\n  "authorized": true\n}'])
    client = IdmNavigator10WebClient("192.0.2.10", "1234", timeout=1, session=FakeSession(ws))

    await client.connect()

    assert client._ws is ws


@pytest.mark.asyncio
async def test_navigator10_client_does_not_retry_authentication_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ws = FakeWs(['{"authorized":true}'])
    session = FakeSession(ws)
    client = IdmNavigator10WebClient("192.0.2.10", "1234", timeout=1, session=session)
    await client.connect()

    async def raise_auth(payload: dict[str, object]) -> str:
        raise IdmWebAuthenticationError("auth failed")

    monkeypatch.setattr(client, "_send_json_and_receive_text_once", raise_auth)

    with pytest.raises(IdmWebAuthenticationError):
        await client._send_json_and_receive_text({"controller": "test"})

    assert session.urls == ["ws://192.0.2.10:61220/?auth_code=1234"]




@pytest.mark.asyncio
async def test_navigator10_diagnostics_and_cache_track_success() -> None:
    setting_raw = json.dumps(
        {"settingDetail": {"id": "4768", "name": "N2_SENSORS", "value": NAV10_SENSOR_HTML}}
    )
    ws = FakeWs(['{"authorized":true}', setting_raw])
    client = IdmNavigator10WebClient("192.0.2.10", "1234", timeout=1, session=FakeSession(ws))

    data = await client.read_data(("4768",))
    diagnostics = client.diagnostics()

    assert client.get_cached_data() is data
    assert diagnostics.navigator_type == "nav10"
    assert diagnostics.websocket_connected is True
    assert diagnostics.cached is True
    assert diagnostics.last_success_monotonic is not None


@pytest.mark.asyncio
async def test_navigator10_reconnect_uses_bounded_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stale_ws = FakeWs(['{"authorized":true}'])
    failing_ws = FailingSendWs(['{"authorized":true}'])
    fresh_ws = FakeWs(['{"authorized":true}', '{"notification":{"current":[]}}'])
    session = FakeSession([stale_ws, failing_ws, fresh_ws])
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("idm_heatpump.web.asyncio.sleep", fake_sleep)
    client = IdmNavigator10WebClient(
        "192.0.2.10",
        "1234",
        timeout=1,
        reconnect_base_delay=0.5,
        reconnect_max_delay=1.0,
        max_reconnect_attempts=2,
        session=session,
    )
    await client.connect()
    stale_ws.closed = True

    notifications = await client.read_notifications()

    assert notifications.count == 0
    assert sleeps == [0.5]
    assert len(session.urls) == 3


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



@pytest.mark.parametrize(
    "html",
    [
        'csrf_token="abc123"',
        '<input type="hidden" name="csrf_token" value="abc123">',
        '<meta name="csrf-token" content="abc123">',
        '<script>var csrfToken = "abc123";</script>',
        "<script>var csrf_token = 'abc123';</script>",
    ],
)
def test_extract_csrf_token_supports_common_nav2_variants(html: str) -> None:
    assert _extract_csrf_token(html) == "abc123"


def test_extract_csrf_token_returns_none_without_token() -> None:
    assert _extract_csrf_token("<html><body>No token</body></html>") is None


class FakeHttpResponse:
    def __init__(self, status: int, text: str, cookies: dict[str, str] | None = None) -> None:
        self.status = status
        self._text = text
        self.cookies = cookies or {}

    async def __aenter__(self) -> "FakeHttpResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def text(self) -> str:
        return self._text


class FakeHttpSession:
    def __init__(self, responses: dict[tuple[str, str], list[FakeHttpResponse]]) -> None:
        self.responses = responses
        self.cookies: dict[str, str] = {}
        self.requests: list[tuple[str, str, dict[str, str] | None]] = []
        self.closed = False

    def request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> FakeHttpResponse:
        del headers, timeout
        path = "/" + url.split("/", 3)[3] if "/" in url[7:] else "/"
        key = (method, path)
        self.requests.append((method, path, data))
        response = self.responses.get(key, [FakeHttpResponse(404, "")]).pop(0)
        self.cookies.update(response.cookies)
        return response

    async def close(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_navigator20_login_fallback_without_csrf_uses_cookie_only_session() -> None:
    session = FakeHttpSession(
        {
            ("GET", "/"): [FakeHttpResponse(404, "")],
            ("GET", "/index.php"): [
                FakeHttpResponse(200, '<html><form><input name="pin"></form></html>')
            ],
            ("POST", "/index.php"): [
                FakeHttpResponse(
                    200,
                    '<html><form><input name="pin"></form></html>',
                    cookies={"sid": "ok"},
                )
            ],
            ("GET", "/data/info.php"): [FakeHttpResponse(200, '{"heatpump":"ok","value":1}')],
        }
    )
    client = IdmNavigator20WebClient("192.0.2.10", "1234", timeout=1, session=session)

    assert await client.detect() is True
    assert client._data_paths == ("/data/info.php",)


@pytest.mark.asyncio
async def test_navigator20_login_rejected_raises_authentication_error() -> None:
    login = '<html><form><input name="pin"></form></html>'
    session = FakeHttpSession(
        {
            ("GET", "/"): [FakeHttpResponse(404, "")],
            ("GET", "/index.php"): [FakeHttpResponse(200, login)],
            ("POST", "/index.php"): [FakeHttpResponse(200, login)],
        }
    )
    client = IdmNavigator20WebClient("192.0.2.10", "bad", timeout=1, session=session)

    with pytest.raises(IdmWebAuthenticationError, match="PIN rejected"):
        await client.connect()


@pytest.mark.asyncio
async def test_navigator20_skips_missing_endpoint_and_uses_working_endpoint() -> None:
    session = FakeHttpSession(
        {
            ("GET", "/"): [FakeHttpResponse(404, "")],
            ("GET", "/index.php"): [FakeHttpResponse(200, "OK")],
            ("POST", "/"): [FakeHttpResponse(200, "OK")],
            ("GET", "/data/heatpump.php"): [FakeHttpResponse(200, '{"heatpump":"ok"}')],
        }
    )
    client = IdmNavigator20WebClient("192.0.2.10", "1234", timeout=1, session=session)

    await client.connect()

    assert client._data_paths == ("/data/heatpump.php",)


@pytest.mark.asyncio
async def test_navigator20_rejects_login_page_as_data_endpoint() -> None:
    session = FakeHttpSession(
        {
            ("GET", "/"): [FakeHttpResponse(404, "")],
            ("GET", "/index.php"): [FakeHttpResponse(200, "OK")],
            ("POST", "/"): [FakeHttpResponse(200, "OK")],
            ("GET", "/data/heatpump.php"): [
                FakeHttpResponse(200, '<html><form><input name="pin"></form></html>')
            ],
        }
    )
    client = IdmNavigator20WebClient("192.0.2.10", "1234", timeout=1, session=session)

    with pytest.raises(IdmWebResponseError, match="endpoint candidates"):
        await client.connect()
