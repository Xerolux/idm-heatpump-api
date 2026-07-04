"""Optional read-only web clients for IDM Navigator local web interfaces."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from types import TracebackType
from typing import Any, Literal

from .const import MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_20

NavigatorWebModel = Literal["Navigator 2.0 Web", "Navigator 10 Web"]

DEFAULT_NAVIGATOR10_PORT = 61220
DEFAULT_NAVIGATOR10_REQUEST_DELAY = 0.05
RECOMMENDED_WEB_SCAN_INTERVAL = 30.0
DEFAULT_NAVIGATOR10_SETTING_IDS = ("4768", "4775", "4782", "4789", "4754", "13259")
DEFAULT_NAVIGATOR20_PATHS = ("/data/settings.php", "/data/heatpump.php", "/data/info.php")

_NAVIGATOR10_SETTING_REQUEST = {
    "controller": "setting",
    "command": "detail",
    "data": {"settingId": ""},
}

_NAVIGATOR10_STATISTIC_REQUEST = {
    "controller": "statistic",
    "command": "detail",
    "data": {"statisticType": 0, "periodType": 7, "statisticSubType": None},
}

_NAVIGATOR10_NOTIFICATION_REQUEST = {
    "controller": "notification",
    "command": "overview",
}

SENSOR_NAME_MAP: dict[str, str] = {
    "B2": "flowmeter",
    "B5": "dewpoint_humidity_alarm",
    "B10": "high_pressure_error",
    "B15": "failure_eheating",
    "B32": "outside_air_temperature",
    "B33": "flow_temperature",
    "B34": "return_temperature",
    "B37": "airsource_temperature",
    "B38": "heatstore_temperature",
    "B41": "water_temp_bottom",
    "B45": "loading_temperature",
    "B48": "water_temp_top",
    "B51": "flow_temp_HK_A",
    "B53": "flow_temp_HK_C",
    "B61": "room_temperature_HK_A",
    "B71": "hotgas_temperature",
    "B78": "verdamper_pressure",
    "B78v": "evaporation_temperature",
    "B79": "evaporator_outlet_temperature",
    "B86": "condenser_pressure",
    "B86v": "condenser_temperature",
    "B87": "liquid_line_temperature",
    "B42": "hotwater_temperature",
    "B108": "hotwater_station_flowmeter",
    "B110": "heating_water_outlet_temperature",
    "B121": "cold_water_temperature",
    "Platinentemperatur": "board_temperature",
    "board temperature": "board_temperature",
    "Batteriespannung Zentraleinheit": "battery_voltage_central_unit",
    "Battery voltage central unit": "battery_voltage_central_unit",
    "Software Version": "software_version",
    "myIDMID": "myidm_id",
    "Modell": "heatpump_model",
    "Model": "heatpump_model",
    "Gerätetyp": "heatpump_model",
    "Geraetetyp": "heatpump_model",
    "Device type": "heatpump_model",
    "Wärmepumpe": "heatpump_model",
    "Waermepumpe": "heatpump_model",
    "Heat pump": "heatpump_model",
    "Typ": "heatpump_model",
    "Type": "heatpump_model",
    "Regler Online": "controller_online_hours",
    "Controller Online": "controller_online_hours",
    "Laufzeit Stufe&nbsp1": "runtime_stage_1_hours",
    "Laufzeit Stufe 1": "runtime_stage_1_hours",
    "Runtime Stage&nbsp1": "runtime_stage_1_hours",
    "Runtime Stage 1": "runtime_stage_1_hours",
    "Schaltzyklen Stufe&nbsp1": "switch_cycles_stage_1",
    "Schaltzyklen Stufe 1": "switch_cycles_stage_1",
    "Starts Stage&nbsp1": "switch_cycles_stage_1",
    "Starts Stage 1": "switch_cycles_stage_1",
    "Laufzeit 2.Wärmeerzeuger": "runtime_second_heat_generator_hours",
    "Runtime 2nd Stage": "runtime_second_heat_generator_hours",
    "Schaltzyklen 2.Wärmeerzeuger": "switch_cycles_second_heat_generator",
    "Starts 2nd Stage": "switch_cycles_second_heat_generator",
    "Laufzeit Heizen": "runtime_heating_hours",
    "Runtime Heating": "runtime_heating_hours",
    "Laufzeit Kühlen": "runtime_cooling_hours",
    "Runtime Cooling": "runtime_cooling_hours",
    "Laufzeit Warmwasser": "runtime_hotwater_hours",
    "Runtime Domestic Hot Water": "runtime_hotwater_hours",
    "Laufzeit Abtauen": "runtime_defrosting_hours",
    "Runtime Defrost": "runtime_defrosting_hours",
    "mom./prog. Leistung Heizen": "current_expected_power_heating",
    "mom./prog. Leistung Kühlen": "current_expected_power_cooling",
    "mom./prog. Leistung Vorrang": "current_expected_power_hotwater",
    "Wärmepumpe Aufnahmeleistung": "current_electrical_power",
    "Wärmemenge Zapfung": "hotwater_tapping_heat_quantity",
    "Heat quantity tapping": "hotwater_tapping_heat_quantity",
    "Wärmemenge Zirkulation": "hotwater_circulation_heat_quantity",
    "Heat quantity circulation": "hotwater_circulation_heat_quantity",
}

NAVIGATOR10_SETTING_NAME_MAP: dict[tuple[str, str], str] = {
    ("4775", "Externe Anforderung"): "external_request",
    ("4775", "external request"): "external_request",
    ("4775", "Ext. Umschaltung H/K"): "ext_switch_heating_cooling",
    ("4775", "ext. heat/cool switch"): "ext_switch_heating_cooling",
    ("4775", "EW/EVU Sperrkontakt"): "ew_evu_lock_contact",
    ("4775", "EW/EVU blocking"): "ew_evu_lock_contact",
    ("4775", "ext. Vorrangladung"): "ext_hotwater_signal",
    ("4775", "ext. priority request"): "ext_hotwater_signal",
    ("4775", "B1"): "hotwater_station_flow_switch",
    ("4775", "M73"): "flow_pump_on",
    ("4782", "M73"): "flow_pump_percentage",
    ("4782", "M13"): "ventilator_voltage",
    ("4782", "M22"): "hotwater_station_pump_percentage",
    ("4782", "M124"): "heat_sink_intermediate_circuit_pump_signal",
    ("4789", "M1"): "compressor_1",
    ("4789", "M51"): "4way_valve_circuit1",
    ("4789", "E32.1"): "siphon_heating",
    ("4789", "M13"): "ventilator_direction_1",
    ("4789", "E1"): "compressor_heating",
    ("4789", "M73"): "flow_pump_output",
    ("4789", "M31"): "pump_heating_circuitA",
    ("4789", "M41"): "mixer_heating_circuitA",
    ("4789", "2./3. Wärmeerzeuger"): "heat_generator_2nd_3rd",
    ("4789", "2. Wärmeerzeuger"): "heat_generator_2nd",
    ("4789", "M63"): "valve_heating_hotwater",
    ("4789", "M64"): "hotwater_circulation_pump",
}

_NUMBER_RE = re.compile(r"^\s*-?\d+(?:[.,]\d+)?\s*$")
_UNIT_SUFFIX_RE = re.compile(r"^\s*(-?\d+(?:[.,]\d+)?)\s*([A-Za-z°/%]+(?:/[A-Za-z]+)?)?\s*$")


class IdmWebError(Exception):
    """Base exception for IDM local web interface errors."""


class IdmWebDependencyError(IdmWebError):
    """Raised when optional web client dependencies are missing."""


class IdmWebAuthenticationError(IdmWebError):
    """Raised when the local web interface rejects the PIN."""


class IdmWebResponseError(IdmWebError):
    """Raised when the local web interface returns an unexpected response."""


@dataclass(frozen=True)
class IdmWebValue:
    """One parsed local web interface value."""

    name: str
    value: str
    raw_key: str
    raw_description: str = ""
    unit: str | None = None
    numeric_value: float | None = None


@dataclass(frozen=True)
class IdmWebValueDescription:
    """Stable metadata for a known local web interface value."""

    key: str
    preferred_unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    enabled_by_default: bool = True


WEB_VALUE_DESCRIPTIONS: dict[str, IdmWebValueDescription] = {
    "flowmeter": IdmWebValueDescription("flowmeter", "l/min", state_class="measurement"),
    "hotgas_temperature": IdmWebValueDescription(
        "hotgas_temperature", "°C", device_class="temperature", state_class="measurement"
    ),
    "verdamper_pressure": IdmWebValueDescription(
        "verdamper_pressure", "bar", device_class="pressure", state_class="measurement"
    ),
    "condenser_pressure": IdmWebValueDescription(
        "condenser_pressure", "bar", device_class="pressure", state_class="measurement"
    ),
    "board_temperature": IdmWebValueDescription(
        "board_temperature", "°C", device_class="temperature", state_class="measurement"
    ),
    "battery_voltage_central_unit": IdmWebValueDescription(
        "battery_voltage_central_unit", "V", device_class="voltage", state_class="measurement"
    ),
    "software_version": IdmWebValueDescription("software_version"),
    "heatpump_model": IdmWebValueDescription("heatpump_model"),
    "myidm_id": IdmWebValueDescription("myidm_id", enabled_by_default=False),
    "hotwater_tapping_heat_quantity": IdmWebValueDescription(
        "hotwater_tapping_heat_quantity", "kWh", device_class="energy", state_class="total"
    ),
    "hotwater_circulation_heat_quantity": IdmWebValueDescription(
        "hotwater_circulation_heat_quantity", "kWh", device_class="energy", state_class="total"
    ),
}


@dataclass(frozen=True)
class IdmWebData:
    """A read-only local web interface snapshot."""

    model: NavigatorWebModel
    values: dict[str, IdmWebValue]
    raw_responses: dict[str, str] = field(default_factory=dict)

    @property
    def simple_values(self) -> dict[str, str]:
        """Return a compact name-to-string-value mapping for consumers."""
        return {name: value.value for name, value in self.values.items()}

    def get_value(self, name: str, default: str | None = None) -> str | None:
        """Return a parsed string value by stable name."""
        value = self.values.get(name)
        return value.value if value is not None else default

    def get_numeric(self, name: str, default: float | None = None) -> float | None:
        """Return a parsed numeric value by stable name."""
        value = self.values.get(name)
        return value.numeric_value if value is not None else default

    @property
    def navigator_version(self) -> str:
        """Return the local web interface navigator version."""
        return self.model.removesuffix(" Web")

    @property
    def software_version(self) -> str | None:
        """Return the controller software version when the web interface reports it."""
        value = self.values.get("software_version")
        return value.value if value is not None else None

    @property
    def heatpump_model(self) -> str | None:
        """Return the heat pump model/type when the web interface reports it."""
        value = self.values.get("heatpump_model")
        return value.value if value is not None else None


@dataclass(frozen=True)
class IdmWebNotification:
    """One active Navigator 10 infosystem notification."""

    code: str
    message: str
    timestamp: int | None = None
    severity: str | None = None
    quit_type: int | None = None
    deferrable: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IdmWebNotifications:
    """Read-only Navigator 10 infosystem notification snapshot."""

    current: tuple[IdmWebNotification, ...]
    raw_response: str | None = None

    @property
    def count(self) -> int:
        return len(self.current)

    @property
    def summary(self) -> str:
        if not self.current:
            return "Keine aktiven Meldungen"
        return " | ".join(
            f"{notification.code}: {notification.message}"
            if notification.code
            else notification.message
            for notification in self.current
        )


def web_pin_configured(pin: str | None) -> bool:
    """Return whether optional web access should be enabled."""
    return bool(pin and pin.strip())


def create_optional_navigator10_web_client(
    host: str,
    pin: str | None,
    *,
    port: int = DEFAULT_NAVIGATOR10_PORT,
    timeout: float = 8.0,
    request_delay: float = DEFAULT_NAVIGATOR10_REQUEST_DELAY,
    session: Any | None = None,
) -> IdmNavigator10WebClient | None:
    """Create a Navigator 10 web client only when a PIN is configured."""
    if not web_pin_configured(pin):
        return None
    return IdmNavigator10WebClient(
        host,
        pin.strip() if pin is not None else "",
        port=port,
        timeout=timeout,
        request_delay=request_delay,
        session=session,
    )


def create_optional_navigator20_web_client(
    host: str,
    pin: str | None,
    *,
    timeout: float = 8.0,
    session: Any | None = None,
) -> IdmNavigator20WebClient | None:
    """Create a Navigator 2.0 web client only when a PIN is configured."""
    if not web_pin_configured(pin):
        return None
    return IdmNavigator20WebClient(
        host,
        pin.strip() if pin is not None else "",
        timeout=timeout,
        session=session,
    )


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._current_cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._current_row = []
        elif tag == "td" and self._current_row is not None:
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._current_cell is not None:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._current_row is not None and self._current_cell is not None:
            self._current_row.append("".join(self._current_cell).strip())
            self._current_cell = None
        elif tag == "tr" and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None
            self._current_cell = None


def _require_aiohttp() -> Any:
    try:
        import aiohttp
    except ModuleNotFoundError as exc:
        raise IdmWebDependencyError(
            "aiohttp is required for IDM web clients. Install idm-heatpump-api[web]."
        ) from exc
    return aiohttp


def _normalize_label(value: str) -> str:
    return " ".join(unescape(value).replace("\xa0", " ").split())


def _parse_value(raw_value: str) -> tuple[str, float | None, str | None]:
    normalized = _normalize_label(raw_value)
    match = _UNIT_SUFFIX_RE.match(normalized)
    if match is None:
        return normalized, None, None
    numeric_text = match.group(1).replace(",", ".")
    unit = match.group(2)
    try:
        numeric_value = float(numeric_text)
    except ValueError:
        numeric_value = None
    return normalized, numeric_value, unit


def parse_idm_html_table_values(
    html: str,
    name_map: dict[str, str] | None = None,
    section_name_map: dict[tuple[str, str], str] | None = None,
    section_id: str | None = None,
) -> dict[str, IdmWebValue]:
    """Parse IDM HTML table rows into stable value names."""
    parser = _TableParser()
    parser.feed(html)
    mapping = name_map or SENSOR_NAME_MAP
    values: dict[str, IdmWebValue] = {}

    for row in parser.rows:
        if len(row) < 2:
            continue
        raw_key = _normalize_label(row[0])
        raw_description = _normalize_label(row[1]) if len(row) > 2 else ""
        raw_value = row[2] if len(row) > 2 else row[1]
        raw_unit = _normalize_label(row[3]) if len(row) > 3 else ""
        if raw_unit and _NUMBER_RE.match(raw_value):
            raw_value = f"{raw_value}{raw_unit}"
        lookup_key = raw_key or raw_description
        lookup_key = _normalize_label(lookup_key)
        name = None
        if section_id is not None and section_name_map is not None:
            name = section_name_map.get((section_id, lookup_key))
        if name is None:
            name = mapping.get(lookup_key)
        if name is None:
            continue
        value, numeric_value, unit = _parse_value(raw_value)
        values[name] = IdmWebValue(
            name=name,
            value=value,
            raw_key=lookup_key,
            raw_description=raw_description,
            unit=unit,
            numeric_value=numeric_value,
        )

    return values


def parse_navigator_setting_response(raw_response: str) -> dict[str, IdmWebValue]:
    """Parse a Navigator 10 setting/detail response."""
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 setting response is not valid JSON") from exc

    detail = payload.get("settingDetail")
    if not isinstance(detail, dict):
        raise IdmWebResponseError("Navigator 10 response does not contain settingDetail")
    value = detail.get("value")
    if not isinstance(value, str):
        raise IdmWebResponseError("Navigator 10 settingDetail.value is not HTML text")
    setting_id = detail.get("id")
    return parse_idm_html_table_values(
        value,
        section_name_map=NAVIGATOR10_SETTING_NAME_MAP,
        section_id=str(setting_id) if setting_id is not None else None,
    )


def parse_navigator_statistic_response(
    raw_response: str,
    prefix: str,
) -> dict[str, IdmWebValue]:
    """Parse a Navigator 10 statistic/detail response."""
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 statistic response is not valid JSON") from exc

    detail = payload.get("statisticDetail")
    if not isinstance(detail, dict):
        raise IdmWebResponseError("Navigator 10 response does not contain statisticDetail")
    data = detail.get("data")
    if not isinstance(data, dict):
        return {}

    values: dict[str, IdmWebValue] = {}
    total = data.get("total")
    if isinstance(total, dict):
        for key, value in total.items():
            name = f"{prefix}_total_{key}"
            values[name] = IdmWebValue(name=name, value=str(value), raw_key=key)

    yearly = data.get("yearly")
    if isinstance(yearly, list) and yearly:
        latest = yearly[-1]
        if isinstance(latest, dict):
            for key, value in latest.items():
                if key in {"date", "idx"}:
                    continue
                name = f"{prefix}_current_year_{key}"
                values[name] = IdmWebValue(name=name, value=str(value), raw_key=key)

    return values


def parse_navigator_notifications_response(
    raw_response: str,
    *,
    include_raw: bool = False,
) -> IdmWebNotifications:
    """Parse a Navigator 10 notification/overview response."""
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 notification response is not valid JSON") from exc

    notification = payload.get("notification")
    if not isinstance(notification, dict):
        raise IdmWebResponseError("Navigator 10 response does not contain notification")

    current = notification.get("current", [])
    if not isinstance(current, list):
        raise IdmWebResponseError("Navigator 10 notification.current is not a list")

    parsed: list[IdmWebNotification] = []
    for item in current:
        if not isinstance(item, dict):
            continue
        code = item.get("code", "")
        text = (
            item.get("text")
            or item.get("textEnum")
            or item.get("description")
            or item.get("descEnum")
            or item.get("descEnumService")
            or item.get("title")
            or ""
        )
        timestamp = item.get("timestamp", item.get("dateTime"))
        parsed.append(
            IdmWebNotification(
                code=str(code) if code is not None else "",
                message=str(text) if text is not None else "",
                timestamp=timestamp if isinstance(timestamp, int) else None,
                severity=str(item["type"]) if "type" in item else None,
                quit_type=item.get("quitType") if isinstance(item.get("quitType"), int) else None,
                deferrable=item.get("deferrable")
                if isinstance(item.get("deferrable"), bool)
                else None,
                raw=dict(item) if include_raw else {},
            )
        )

    return IdmWebNotifications(
        current=tuple(parsed),
        raw_response=raw_response if include_raw else None,
    )


class IdmNavigator10WebClient:
    """Read-only async client for the Navigator 10 local WebSocket interface."""

    def __init__(
        self,
        host: str,
        pin: str,
        *,
        port: int = DEFAULT_NAVIGATOR10_PORT,
        timeout: float = 8.0,
        request_delay: float = DEFAULT_NAVIGATOR10_REQUEST_DELAY,
        session: Any | None = None,
    ) -> None:
        if not host:
            raise ValueError("Host must not be empty")
        if not pin:
            raise ValueError("PIN must not be empty")
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")
        self._host = host
        self._pin = pin
        self._port = int(port)
        self._timeout = float(timeout)
        self._request_delay = max(0.0, float(request_delay))
        self._session = session
        self._own_session = False
        self._ws: Any | None = None

    @property
    def model_name(self) -> str:
        return MODEL_NAVIGATOR_10

    async def __aenter__(self) -> IdmNavigator10WebClient:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def connect(self) -> None:
        if self._ws is not None:
            if not self._websocket_closed(self._ws):
                return
            self._ws = None
        if self._session is None:
            aiohttp = _require_aiohttp()
            self._session = aiohttp.ClientSession()
            self._own_session = True

        url = f"ws://{self._host}:{self._port}/?auth_code={self._pin}"
        self._ws = await self._session.ws_connect(url, timeout=self._timeout)
        auth = await self._receive_text()
        if '"authorized":true' not in auth.replace(" ", ""):
            await self.close()
            if '"authorized":false' in auth.replace(" ", ""):
                raise IdmWebAuthenticationError("Navigator 10 rejected the PIN")
            raise IdmWebResponseError("Navigator 10 authorization response was not recognized")

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        if self._own_session and self._session is not None:
            await self._session.close()
            self._session = None
            self._own_session = False

    async def read_data(
        self,
        setting_ids: tuple[str, ...] = DEFAULT_NAVIGATOR10_SETTING_IDS,
        *,
        include_raw: bool = False,
    ) -> IdmWebData:
        await self.connect()
        values: dict[str, IdmWebValue] = {}
        raw_responses: dict[str, str] = {}

        for setting_id in setting_ids:
            request = dict(_NAVIGATOR10_SETTING_REQUEST)
            request["data"] = {"settingId": setting_id}
            raw = await self._send_json_and_receive_text(request)
            if include_raw:
                raw_responses[f"setting:{setting_id}"] = raw
            values.update(parse_navigator_setting_response(raw))
            if self._request_delay:
                await asyncio.sleep(self._request_delay)

        return IdmWebData(model="Navigator 10 Web", values=values, raw_responses=raw_responses)

    async def read_statistics(
        self,
        statistic_type: int,
        period_type: int,
        prefix: str,
        *,
        include_raw: bool = False,
    ) -> IdmWebData:
        await self.connect()
        request = dict(_NAVIGATOR10_STATISTIC_REQUEST)
        request["data"] = {
            "statisticType": statistic_type,
            "periodType": period_type,
            "statisticSubType": None,
        }
        raw = await self._send_json_and_receive_text(request)
        return IdmWebData(
            model="Navigator 10 Web",
            values=parse_navigator_statistic_response(raw, prefix),
            raw_responses={f"statistic:{statistic_type}:{period_type}": raw} if include_raw else {},
        )

    async def read_notifications(self, *, include_raw: bool = False) -> IdmWebNotifications:
        await self.connect()
        raw = await self._send_json_and_receive_text(_NAVIGATOR10_NOTIFICATION_REQUEST)
        return parse_navigator_notifications_response(raw, include_raw=include_raw)

    async def _send_json_and_receive_text(self, payload: dict[str, Any]) -> str:
        try:
            return await self._send_json_and_receive_text_once(payload)
        except (IdmWebResponseError, OSError, TimeoutError):
            await self.close()
            await self.connect()
            return await self._send_json_and_receive_text_once(payload)

    async def _send_json_and_receive_text_once(self, payload: dict[str, Any]) -> str:
        if self._ws is None:
            raise IdmWebResponseError("Navigator 10 websocket is not connected")
        if self._websocket_closed(self._ws):
            raise IdmWebResponseError("Navigator 10 websocket is closed")
        await self._ws.send_json(payload)
        return await self._receive_text()

    async def _receive_text(self) -> str:
        if self._ws is None:
            raise IdmWebResponseError("Navigator 10 websocket is not connected")
        message = await self._ws.receive(timeout=self._timeout)
        message_type = getattr(message, "type", None)
        if self._is_ws_text_message(message_type):
            return str(message.data)
        if self._is_ws_error_message(message_type):
            raise IdmWebResponseError(f"Navigator 10 websocket error: {self._ws.exception()}")
        raise IdmWebResponseError(
            f"Navigator 10 websocket returned unexpected frame: {message_type}"
        )

    @staticmethod
    def _websocket_closed(ws: Any) -> bool:
        return bool(getattr(ws, "closed", False))

    @staticmethod
    def _is_ws_text_message(message_type: Any) -> bool:
        if str(message_type) in {"1", "TEXT", "WSMsgType.TEXT"}:
            return True
        try:
            import aiohttp
        except ModuleNotFoundError:
            return False
        return bool(message_type == aiohttp.WSMsgType.TEXT)

    @staticmethod
    def _is_ws_error_message(message_type: Any) -> bool:
        if str(message_type) in {"258", "ERROR", "WSMsgType.ERROR"}:
            return True
        try:
            import aiohttp
        except ModuleNotFoundError:
            return False
        return bool(message_type == aiohttp.WSMsgType.ERROR)


class IdmNavigator20WebClient:
    """Read-only async client for the Navigator 2.0 local HTTP interface."""

    def __init__(
        self,
        host: str,
        pin: str,
        *,
        timeout: float = 8.0,
        session: Any | None = None,
    ) -> None:
        if not host:
            raise ValueError("Host must not be empty")
        if not pin:
            raise ValueError("PIN must not be empty")
        self._host = host
        self._pin = pin
        self._timeout = float(timeout)
        self._session = session
        self._own_session = False
        self._csrf_token: str | None = None

    @property
    def model_name(self) -> str:
        return MODEL_NAVIGATOR_20

    async def __aenter__(self) -> IdmNavigator20WebClient:
        await self.login()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def login(self) -> None:
        aiohttp = _require_aiohttp()
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        url = f"http://{self._host}/index.php"
        async with self._session.post(
            url, data={"pin": self._pin}, timeout=self._timeout
        ) as response:
            text = await response.text()
            if response.status != 200:
                raise IdmWebResponseError(f"Navigator 2.0 login returned HTTP {response.status}")
            if "Authorization Required" in text:
                raise IdmWebAuthenticationError("Navigator 2.0 rejected the PIN")
            match = re.search(r'csrf_token="([^"]+)"', text)
            if match is None:
                raise IdmWebResponseError("Navigator 2.0 login did not return a CSRF token")
            self._csrf_token = match.group(1)

    async def close(self) -> None:
        if self._own_session and self._session is not None:
            await self._session.close()
            self._session = None
            self._own_session = False

    async def read_data(
        self,
        paths: tuple[str, ...] = DEFAULT_NAVIGATOR20_PATHS,
        *,
        include_raw: bool = False,
    ) -> IdmWebData:
        if self._csrf_token is None:
            await self.login()
        if self._session is None or self._csrf_token is None:
            raise IdmWebResponseError("Navigator 2.0 HTTP session is not connected")

        values: dict[str, IdmWebValue] = {}
        raw_responses: dict[str, str] = {}
        headers = {"CSRF-Token": self._csrf_token}
        for path in paths:
            url = f"http://{self._host}{path}"
            async with self._session.get(url, headers=headers, timeout=self._timeout) as response:
                text = await response.text()
                if response.status != 200:
                    raise IdmWebResponseError(
                        f"Navigator 2.0 {path} returned HTTP {response.status}"
                    )
                if "invalid csrf token" in text.lower():
                    self._csrf_token = None
                    raise IdmWebAuthenticationError("Navigator 2.0 CSRF token was rejected")
                if include_raw:
                    raw_responses[path] = text
                values.update(parse_idm_html_table_values(text))

        return IdmWebData(model="Navigator 2.0 Web", values=values, raw_responses=raw_responses)
