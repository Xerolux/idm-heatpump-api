"""Optional read-only web clients for IDM Navigator local web interfaces."""

from __future__ import annotations

import asyncio
import builtins
import ipaddress
import json
import logging
import re
import time
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from types import TracebackType
from typing import Any, Literal
from urllib.parse import quote

from .const import MODEL_NAVIGATOR_10, MODEL_NAVIGATOR_20

NavigatorWebModel = Literal["Navigator 2.0 Web", "Navigator 10 Web"]

try:
    import aiohttp

    _AIOHTTP_WS_TEXT: Any = aiohttp.WSMsgType.TEXT
    _AIOHTTP_WS_CLOSED: Any = aiohttp.WSMsgType.CLOSED
    _AIOHTTP_WS_ERROR: Any = aiohttp.WSMsgType.ERROR
    _AIOHTTP_CLIENT_ERROR: tuple[type[BaseException], ...] = (aiohttp.ClientError,)
    _AIOHTTP_CLIENT_ERROR_CLS: type[BaseException] | None = aiohttp.ClientError
except ModuleNotFoundError:
    _AIOHTTP_WS_TEXT = None
    _AIOHTTP_WS_CLOSED = None
    _AIOHTTP_WS_ERROR = None
    _AIOHTTP_CLIENT_ERROR = ()
    _AIOHTTP_CLIENT_ERROR_CLS = None

DEFAULT_NAVIGATOR10_PORT = 61220
DEFAULT_NAVIGATOR10_REQUEST_DELAY = 0.05
RECOMMENDED_WEB_SCAN_INTERVAL = 30.0
DEFAULT_NAVIGATOR10_SETTING_IDS = ("4768", "4775", "4782", "4789", "4754", "13259")
DEFAULT_NAVIGATOR20_PATHS = (
    "/data/settings.php",
    "/data/heatpump.php",
    "/data/info.php",
    "/data/state.php",
    "/data/status.php",
    "/data/values.php",
)

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


def _parse_auth_response(text: str) -> tuple[bool, bool | None]:
    """Parse a Navigator 10 auth response once.

    Returns a ``(has_key, authorized)`` tuple where ``has_key`` indicates that
    an ``authorized`` field was present at all and ``authorized`` is its boolean
    value (or ``None`` when the key is absent / the payload is not JSON). This
    avoids re-parsing the same websocket frame multiple times during connect.
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return False, None
    if not isinstance(data, dict):
        return False, None
    if "authorized" not in data:
        return False, None
    authorized = data.get("authorized")
    return True, authorized if isinstance(authorized, bool) else None


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
_LOGIN_FORM_RE = re.compile(r"<form\b", re.IGNORECASE)
_PASSWORD_INPUT_RE = re.compile(
    r'<input\b[^>]*(?:type=["\']password["\']|name=["\'](?:pin|password|pass)["\'])',
    re.IGNORECASE,
)
_LOGGER = logging.getLogger(__name__)


def _is_ip_literal(host: str) -> bool:
    """Return whether a configured host string is an IPv4 or IPv6 literal.

    Accepts plain IPv4/IPv6 literals, IPv4/hostname-style values with a
    single port separator, and bracketed IPv6 literals such as
    ``[2001:db8::1]`` or ``[2001:db8::1]:80``. Hostnames intentionally return
    ``False`` so they keep aiohttp's safe default cookie handling.
    """
    candidate = host.strip()
    if not candidate:
        return False

    if candidate.startswith("[") and "]" in candidate:
        candidate = candidate[1 : candidate.index("]")]
    elif candidate.count(":") == 1:
        candidate = candidate.rsplit(":", 1)[0]

    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return False
    return True


def _format_url_host(host: str) -> str:
    """Validate a configured host and format IPv6 literals for URL authorities."""
    if not host or host != host.strip():
        raise ValueError("Host must not be empty or contain surrounding whitespace")

    bracketed = host.startswith("[") and host.endswith("]")
    candidate = host[1:-1] if bracketed else host
    if not candidate or "%" in candidate:
        raise ValueError(f"Invalid host: {host!r}")

    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        if bracketed or len(candidate) > 253:
            raise ValueError(f"Invalid host: {host!r}") from None
        labels = candidate.rstrip(".").split(".")
        if any(
            not label
            or len(label) > 63
            or re.fullmatch(r"[A-Za-z0-9_](?:[A-Za-z0-9_-]*[A-Za-z0-9_])?", label) is None
            for label in labels
        ):
            raise ValueError(f"Invalid host: {host!r}")
        return candidate

    if bracketed and address.version != 6:
        raise ValueError(f"Only IPv6 literals may use brackets: {host!r}")
    return f"[{candidate}]" if address.version == 6 else candidate


class IdmWebError(Exception):
    """Base exception for IDM local web interface errors."""


class IdmWebDependencyError(IdmWebError):
    """Raised when optional web client dependencies are missing."""


class IdmWebConnectionError(IdmWebError):
    """Raised when the local web interface cannot be reached."""


class IdmWebTimeoutError(IdmWebConnectionError):
    """Raised when a local web interface operation times out."""


class IdmWebAuthenticationError(IdmWebError):
    """Raised when the local web interface rejects authentication."""


class IdmWebPinRejectedError(IdmWebAuthenticationError):
    """Raised when the local web interface explicitly rejects the configured PIN."""


class IdmWebCsrfError(IdmWebAuthenticationError):
    """Raised when a local web interface rejects or requires a CSRF token."""


class IdmWebProtocolError(IdmWebError):
    """Raised when the local web interface violates the expected protocol."""


class IdmWebWebSocketError(IdmWebProtocolError):
    """Raised for Navigator 10 websocket protocol failures."""


class IdmWebResponseError(IdmWebProtocolError):
    """Raised when the local web interface returns an unexpected response."""


# Short aliases requested by downstream integrations. They intentionally point
# to the IDM-prefixed classes to preserve the existing public exception tree.
AuthenticationError = IdmWebAuthenticationError
PinRejectedError = IdmWebPinRejectedError
CsrfError = IdmWebCsrfError
ConnectionError = IdmWebConnectionError
TimeoutError = IdmWebTimeoutError
WebSocketError = IdmWebWebSocketError
ProtocolError = IdmWebProtocolError

_NAV2_REQUEST_ERRORS: tuple[type[BaseException], ...] = (
    IdmWebError,
    OSError,
    builtins.TimeoutError,
)
if _AIOHTTP_CLIENT_ERROR_CLS is not None:
    _NAV2_REQUEST_ERRORS = (*_NAV2_REQUEST_ERRORS, _AIOHTTP_CLIENT_ERROR_CLS)

# Navigator 10 reconnect loop error categories. Built once at import time
# (analogue to _NAV2_REQUEST_ERRORS above) so request handling does not
# reallocate these tuples on every websocket request.
_NAV10_RECOVERABLE_ERRORS: tuple[type[BaseException], ...] = (
    IdmWebProtocolError,
    OSError,
    builtins.TimeoutError,
)
_NAV10_RECONNECT_ERRORS: tuple[type[BaseException], ...] = (
    IdmWebProtocolError,
    IdmWebConnectionError,
    IdmWebTimeoutError,
    OSError,
    builtins.TimeoutError,
)
if _AIOHTTP_CLIENT_ERROR_CLS is not None:
    _NAV10_RECOVERABLE_ERRORS = (*_NAV10_RECOVERABLE_ERRORS, _AIOHTTP_CLIENT_ERROR_CLS)
    _NAV10_RECONNECT_ERRORS = (*_NAV10_RECONNECT_ERRORS, _AIOHTTP_CLIENT_ERROR_CLS)


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


class _CsrfTokenParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.token:
            return
        attr_map = {name.lower(): value for name, value in attrs if value is not None}
        if tag == "input" and attr_map.get("name") == "csrf_token":
            self.token = attr_map.get("value")
        elif tag == "meta" and attr_map.get("name") == "csrf-token":
            self.token = attr_map.get("content")


_CSRF_TOKEN_PATTERNS = (
    r'csrf_token="([^"]+)"',
    r"csrf_token='([^']+)'",
    r'name="csrf_token"\s+value="([^"]+)"',
    r"name='csrf_token'\s+value='([^']+)'",
    r'content="([^"]+)"\s+name="csrf-token"',
    r'name="csrf-token"\s+content="([^"]+)"',
    r'csrfToken\s*=\s*"([^"]+)"',
    r"csrfToken\s*=\s*'([^']+)'",
    r'csrf_token\s*=\s*"([^"]+)"',
    r"csrf_token\s*=\s*'([^']+)'",
)


def _extract_csrf_token(html: str) -> str | None:
    """Extract a NAV2 CSRF token from common HTML, meta, and script variants."""
    parser = _CsrfTokenParser()
    parser.feed(html)
    if parser.token:
        return unescape(parser.token)
    for pattern in _CSRF_TOKEN_PATTERNS:
        match = re.search(pattern, html, flags=re.IGNORECASE)
        if match and match.group(1):
            return unescape(match.group(1))
    return None


def _looks_like_login_page(text: str) -> bool:
    """Return True if the response looks like an HTML login page."""
    lowered = text.lower()
    if "<html" not in lowered:
        return False
    # Precise signal: an HTML form with a password/PIN input field.
    if _LOGIN_FORM_RE.search(text) and _PASSWORD_INPUT_RE.search(text):
        return True
    # Fallback heuristic for non-standard or JS-generated login pages.
    return any(marker in lowered for marker in ("login", "pin", "password", "passwort", "csrf"))


def _looks_like_auth_failure(text: str) -> bool:
    """Return whether a JSON or text response explicitly rejects authentication."""
    stripped = text.strip()
    lowered = stripped.casefold()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        if payload.get("authorized") is False or payload.get("authenticated") is False:
            return True
        status = str(payload.get("status", "")).casefold()
        if status in {"unauthorized", "forbidden", "authentication_failed"}:
            return True

    return any(
        marker in lowered
        for marker in (
            "authorization required",
            "authentication failed",
            "invalid pin",
            "pin rejected",
            "unauthorized",
            "forbidden",
        )
    )


def _looks_like_data_response(text: str) -> bool:
    stripped = text.strip()
    if not stripped or _looks_like_login_page(stripped) or _looks_like_auth_failure(stripped):
        return False
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict) and any(
        key.casefold() in {"error", "errors", "exception"} for key in payload
    ):
        return False
    return any(marker in stripped.lower() for marker in ("<table", "setting", "heatpump", "value"))


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
        # raw_key and raw_description are already normalized above; ``or`` only
        # selects one of them (no concatenation), so no second normalization is
        # needed for the lookup key.
        lookup_key = raw_key or raw_description
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


@dataclass(frozen=True)
class IdmWebDiagnostics:
    """Diagnostic snapshot for optional local web clients."""

    navigator_type: str
    websocket_connected: bool = False
    web_data_enabled: bool = False
    firmware: str | None = None
    api_version: str | None = None
    model: str | None = None
    serial_number: str | None = None
    last_success_monotonic: float | None = None
    last_error: str | None = None
    last_reconnect_monotonic: float | None = None
    reconnect_attempts: int = 0
    used_endpoints: tuple[str, ...] = ()
    cached: bool = False


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
        reconnect_base_delay: float = 0.25,
        reconnect_max_delay: float = 5.0,
        max_reconnect_attempts: int = 3,
        session: Any | None = None,
    ) -> None:
        if not host:
            raise ValueError("Host must not be empty")
        if not pin:
            raise ValueError("PIN must not be empty")
        if not (1 <= port <= 65535):
            raise ValueError(f"Port must be between 1 and 65535, got {port}")
        self._host = host
        self._url_host = _format_url_host(host)
        self._pin = pin
        self._port = int(port)
        self._timeout = float(timeout)
        self._request_delay = max(0.0, float(request_delay))
        self._reconnect_base_delay = max(0.0, float(reconnect_base_delay))
        self._reconnect_max_delay = max(self._reconnect_base_delay, float(reconnect_max_delay))
        self._max_reconnect_attempts = max(1, int(max_reconnect_attempts))
        self._session = session
        self._own_session = False
        self._ws: Any | None = None
        self._last_success_monotonic: float | None = None
        self._last_error: str | None = None
        self._last_reconnect_monotonic: float | None = None
        self._reconnect_attempts = 0
        self._cached_data: IdmWebData | None = None
        self._lock = asyncio.Lock()

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
        try:
            await self.close()
        except Exception:  # noqa: BLE001
            if exc_type is None:
                raise

    async def connect(self) -> None:
        async with self._lock:
            await self._connect_unlocked()

    async def _connect_unlocked(self) -> None:
        if self._ws is not None:
            if not self._websocket_closed(self._ws):
                return
            self._ws = None
        if self._session is None:
            aiohttp = _require_aiohttp()
            self._session = aiohttp.ClientSession()
            self._own_session = True

        encoded_pin = quote(self._pin, safe="")
        url = f"ws://{self._url_host}:{self._port}/?auth_code={encoded_pin}"
        try:
            self._ws = await self._session.ws_connect(url, timeout=self._timeout)
            auth = await self._receive_text()
        except builtins.TimeoutError as exc:
            self._last_error = "Navigator 10 websocket connection timed out"
            await self.close()
            raise IdmWebTimeoutError(self._last_error) from exc
        except OSError as exc:
            self._last_error = f"Navigator 10 websocket connection failed: {type(exc).__name__}"
            await self.close()
            raise IdmWebConnectionError(self._last_error) from exc
        except Exception:
            self._last_error = "Navigator 10 websocket connection failed"
            await self.close()
            raise
        has_key, authorized = _parse_auth_response(auth)
        if not (has_key and authorized is True):
            await self.close()
            if has_key and authorized is False:
                self._last_error = "Navigator 10 rejected the PIN"
                raise IdmWebPinRejectedError(self._last_error)
            self._last_error = "Navigator 10 authorization response was not recognized"
            raise IdmWebProtocolError(self._last_error)
        self._last_success_monotonic = time.monotonic()
        self._last_error = None

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Ignoring exception while closing Navigator 10 websocket")
            finally:
                self._ws = None
        if self._own_session and self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Ignoring exception while closing Navigator 10 session")
            finally:
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

        for i, setting_id in enumerate(setting_ids):
            request = dict(_NAVIGATOR10_SETTING_REQUEST)
            request["data"] = {"settingId": setting_id}
            raw = await self._send_json_and_receive_text(request)
            if include_raw:
                raw_responses[f"setting:{setting_id}"] = raw
            values.update(parse_navigator_setting_response(raw))
            if self._request_delay and i < len(setting_ids) - 1:
                await asyncio.sleep(self._request_delay)

        data = IdmWebData(model="Navigator 10 Web", values=values, raw_responses=raw_responses)
        self._cached_data = data
        self._last_success_monotonic = time.monotonic()
        return data

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
        data = IdmWebData(
            model="Navigator 10 Web",
            values=parse_navigator_statistic_response(raw, prefix),
            raw_responses={f"statistic:{statistic_type}:{period_type}": raw} if include_raw else {},
        )
        self._last_success_monotonic = time.monotonic()
        return data

    async def read_notifications(self, *, include_raw: bool = False) -> IdmWebNotifications:
        await self.connect()
        raw = await self._send_json_and_receive_text(_NAVIGATOR10_NOTIFICATION_REQUEST)
        notifications = parse_navigator_notifications_response(raw, include_raw=include_raw)
        self._last_success_monotonic = time.monotonic()
        return notifications

    def get_cached_data(self) -> IdmWebData | None:
        """Return the last valid Navigator 10 data snapshot, if one exists."""
        return self._cached_data

    def diagnostics(self) -> IdmWebDiagnostics:
        """Return a sanitized Navigator 10 diagnostic snapshot."""
        return IdmWebDiagnostics(
            navigator_type="nav10",
            websocket_connected=self._ws is not None and not self._websocket_closed(self._ws),
            web_data_enabled=True,
            last_success_monotonic=self._last_success_monotonic,
            last_error=self._last_error,
            last_reconnect_monotonic=self._last_reconnect_monotonic,
            reconnect_attempts=self._reconnect_attempts,
            cached=self._cached_data is not None,
        )

    async def _send_json_and_receive_text(self, payload: dict[str, Any]) -> str:
        async with self._lock:
            try:
                return await self._send_json_and_receive_text_once(payload)
            except IdmWebAuthenticationError:
                raise
            except _NAV10_RECOVERABLE_ERRORS as exc:
                self._last_error = f"Navigator 10 websocket request failed: {type(exc).__name__}"
            delay = self._reconnect_base_delay
            last_exc: BaseException | None = None
            for attempt in range(1, self._max_reconnect_attempts + 1):
                self._reconnect_attempts = attempt
                self._last_reconnect_monotonic = time.monotonic()
                try:
                    await self.close()
                    if delay:
                        await asyncio.sleep(min(delay, self._reconnect_max_delay))
                        delay = min(delay * 2, self._reconnect_max_delay)
                    await self._connect_unlocked()
                    result = await self._send_json_and_receive_text_once(payload)
                    self._reconnect_attempts = 0
                    return result
                except IdmWebAuthenticationError:
                    await self.close()
                    raise
                except _NAV10_RECONNECT_ERRORS as exc:
                    last_exc = exc
                    self._last_error = (
                        f"Navigator 10 websocket reconnect attempt {attempt} failed: "
                        f"{type(exc).__name__}"
                    )
            if last_exc is not None:
                raise IdmWebWebSocketError(
                    self._last_error or "Navigator 10 websocket reconnect failed"
                ) from last_exc
            raise IdmWebWebSocketError("Navigator 10 websocket reconnect failed")

    async def _send_json_and_receive_text_once(self, payload: dict[str, Any]) -> str:
        if self._ws is None:
            raise IdmWebWebSocketError("Navigator 10 websocket is not connected")
        if self._websocket_closed(self._ws):
            raise IdmWebWebSocketError("Navigator 10 websocket is closed")
        await self._ws.send_json(payload)
        return await self._receive_text()

    async def _receive_text(self) -> str:
        if self._ws is None:
            raise IdmWebWebSocketError("Navigator 10 websocket is not connected")
        message = await self._ws.receive(timeout=self._timeout)
        message_type = getattr(message, "type", None)
        if self._is_ws_text_message(message_type):
            return str(message.data)
        if self._is_ws_closed_message(message_type):
            raise IdmWebWebSocketError("Navigator 10 websocket was closed by the device")
        if self._is_ws_error_message(message_type):
            raise IdmWebWebSocketError(f"Navigator 10 websocket error: {self._ws.exception()}")
        raise IdmWebProtocolError(
            f"Navigator 10 websocket returned unexpected frame: {message_type}"
        )

    @staticmethod
    def _websocket_closed(ws: Any) -> bool:
        return bool(getattr(ws, "closed", False))

    @staticmethod
    def _is_ws_text_message(message_type: Any) -> bool:
        if str(message_type) in {"1", "TEXT", "WSMsgType.TEXT"}:
            return True
        return _AIOHTTP_WS_TEXT is not None and bool(message_type == _AIOHTTP_WS_TEXT)

    @staticmethod
    def _is_ws_closed_message(message_type: Any) -> bool:
        if str(message_type) in {"257", "CLOSED", "WSMsgType.CLOSED"}:
            return True
        return _AIOHTTP_WS_CLOSED is not None and bool(message_type == _AIOHTTP_WS_CLOSED)

    @staticmethod
    def _is_ws_error_message(message_type: Any) -> bool:
        if str(message_type) in {"258", "ERROR", "WSMsgType.ERROR"}:
            return True
        return _AIOHTTP_WS_ERROR is not None and bool(message_type == _AIOHTTP_WS_ERROR)


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
        self._url_host = _format_url_host(host)
        self._pin = pin
        self._timeout = float(timeout)
        self._session = session
        self._own_session = False
        self._csrf_token: str | None = None
        self._data_paths: tuple[str, ...] = ()
        self._probe_responses: dict[str, str] = {}
        self._login_form_returned = False
        self._last_success_monotonic: float | None = None
        self._last_error: str | None = None
        self._cached_data: IdmWebData | None = None
        self._lock = asyncio.Lock()

    @property
    def model_name(self) -> str:
        return MODEL_NAVIGATOR_20

    async def __aenter__(self) -> IdmNavigator20WebClient:
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            await self.close()
        except Exception:  # noqa: BLE001
            if exc_type is None:
                raise

    async def connect(self) -> None:
        await self.login()

    async def detect(self) -> bool:
        try:
            await self.connect()
        except IdmWebError:
            return False
        return bool(self._data_paths)

    async def login(self) -> None:
        async with self._lock:
            if self._session is None:
                aiohttp = _require_aiohttp()
                cookie_jar = aiohttp.CookieJar(unsafe=_is_ip_literal(self._host))
                self._session = aiohttp.ClientSession(cookie_jar=cookie_jar)
                self._own_session = True
            try:
                initial = await self._initial_get()
                self._csrf_token = _extract_csrf_token(initial)
                if self._csrf_token is None:
                    _LOGGER.debug("NAV2 CSRF token not found, trying cookie-only login fallback")
                await self._try_login()
                self._probe_responses.clear()
                paths = await self._probe_data_endpoints(DEFAULT_NAVIGATOR20_PATHS)
                if not paths:
                    if self._login_form_returned:
                        raise IdmWebAuthenticationError(
                            "NAV2 web login failed: PIN rejected or login form returned again"
                        )
                    raise IdmWebResponseError(
                        "NAV2 web detection failed after trying "
                        f"{len(DEFAULT_NAVIGATOR20_PATHS)} endpoint candidates"
                    )
                self._data_paths = paths
                _LOGGER.debug("NAV2 login successful for %s, endpoints: %s", self._host, paths)
            except Exception:
                await self.close()
                raise
            self._last_success_monotonic = time.monotonic()
            self._last_error = None

    async def close(self) -> None:
        self._csrf_token = None
        self._data_paths = ()
        self._probe_responses.clear()
        self._login_form_returned = False
        if self._own_session and self._session is not None:
            try:
                await self._session.close()
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Ignoring exception while closing Navigator 2.0 session")
            finally:
                self._session = None
                self._own_session = False

    async def read_data(
        self,
        paths: tuple[str, ...] = DEFAULT_NAVIGATOR20_PATHS,
        *,
        include_raw: bool = False,
    ) -> IdmWebData:
        use_probe_responses = False
        if not self._data_paths:
            await self.login()
            use_probe_responses = True
        else:
            self._probe_responses.clear()
        if self._session is None:
            raise IdmWebResponseError("Navigator 2.0 HTTP session is not connected")

        values: dict[str, IdmWebValue] = {}
        raw_responses: dict[str, str] = {}
        csrf_retried = False
        # Caller may pass a subset of paths; intersect with the endpoints that
        # were confirmed during login. Fall back to all confirmed endpoints when
        # the caller's subset does not overlap the detected paths.
        selected_paths = tuple(p for p in paths if p in self._data_paths) or self._data_paths
        try:
            for path in selected_paths:
                try:
                    text = self._probe_responses.pop(path, None) if use_probe_responses else None
                    if text is None:
                        text = await self._request_text("GET", path)
                except IdmWebCsrfError:
                    if csrf_retried:
                        raise
                    _LOGGER.debug(
                        "NAV2 CSRF token rejected while reading %s, attempting one re-login", path
                    )
                    self._csrf_token = None
                    await self.login()
                    csrf_retried = True
                    use_probe_responses = True
                    text = self._probe_responses.pop(path, None)
                    if text is None:
                        text = await self._request_text("GET", path)
                if "invalid csrf token" in text.lower():
                    self._csrf_token = None
                    raise IdmWebCsrfError("Navigator 2.0 CSRF token was rejected")
                if _looks_like_auth_failure(text) or _looks_like_login_page(text):
                    raise IdmWebAuthenticationError(
                        f"NAV2 endpoint {path} returned an authentication response instead of data"
                    )
                if include_raw:
                    raw_responses[path] = text
                values.update(parse_idm_html_table_values(text))
        finally:
            self._probe_responses.clear()

        data = IdmWebData(model="Navigator 2.0 Web", values=values, raw_responses=raw_responses)
        self._cached_data = data
        self._last_success_monotonic = time.monotonic()
        return data

    async def read_extra_data(self) -> dict[str, Any]:
        data = await self.read_data()
        return data.simple_values

    def get_cached_data(self) -> IdmWebData | None:
        """Return the last valid Navigator 2.0 web data snapshot, if one exists."""
        return self._cached_data

    def capabilities(self) -> dict[str, bool]:
        """Return capabilities inferred from successfully probed NAV2 endpoints/data."""
        path_text = " ".join(self._data_paths).lower()
        value_names = set(self._cached_data.values) if self._cached_data is not None else set()
        return {
            "web_data": bool(self._data_paths),
            "settings": "/data/settings.php" in self._data_paths,
            "heatpump": "/data/heatpump.php" in self._data_paths,
            "rooms": "rooms" in path_text or any("room" in name for name in value_names),
            "zones": "zones" in path_text or any("zone" in name for name in value_names),
            "pv": any("pv" in name for name in value_names),
            "smart_grid": any("smart_grid" in name for name in value_names),
        }

    def diagnostics(self) -> IdmWebDiagnostics:
        """Return a sanitized Navigator 2.0 diagnostic snapshot."""
        return IdmWebDiagnostics(
            navigator_type="nav2",
            websocket_connected=False,
            web_data_enabled=bool(self._data_paths),
            last_success_monotonic=self._last_success_monotonic,
            last_error=self._last_error,
            used_endpoints=self._data_paths,
            cached=self._cached_data is not None,
        )

    async def _initial_get(self) -> str:
        errors: list[str] = []
        for path in ("/", "/index.php"):
            try:
                # Do not send a possibly stale CSRF token when fetching the
                # initial login page; the server returns the form/token fresh.
                text = await self._request_text("GET", path, include_csrf=False)
                _LOGGER.debug("NAV2 initial GET %s succeeded", path)
                return text
            except _NAV2_REQUEST_ERRORS as exc:
                errors.append(f"{path}: {type(exc).__name__}")
        self._last_error = "Navigator 2.0 HTTP interface was not reachable: " + ", ".join(errors)
        raise IdmWebConnectionError(self._last_error)

    async def _try_login(self) -> None:
        fields = ("pin", "PIN", "password", "pass")
        self._login_form_returned = False
        _LOGGER.debug(
            "NAV2 starting login handshake for %s (csrf_token present: %s)",
            self._host,
            bool(self._csrf_token),
        )
        for path in ("/", "/index.php", "/login.php"):
            for field_name in fields:
                # The CSRF token is returned by the server *after* a successful
                # login, so we must not send an (possibly stale) token in the
                # login POST itself.
                data = {field_name: self._pin}
                try:
                    text = await self._request_text(
                        "POST", path, data=data, require_ok=False, include_csrf=False
                    )
                except _NAV2_REQUEST_ERRORS as exc:
                    _LOGGER.debug(
                        "NAV2 login variant %s with field %s failed: %s",
                        path,
                        field_name,
                        type(exc).__name__,
                    )
                    continue
                if "authorization required" in text.lower():
                    _LOGGER.debug("NAV2 login variant %s requires authorization", path)
                    self._login_form_returned = True
                    continue
                token = _extract_csrf_token(text)
                if token:
                    self._csrf_token = token
                stripped = text.strip()
                if not stripped:
                    # Empty/bad response: keep trying field-name variants on this path.
                    _LOGGER.debug("NAV2 login variant %s returned empty response", path)
                    continue
                if _looks_like_login_page(text):
                    # Login form returned for this path: try the next path instead
                    # of burning through field-name variants that hit the same form.
                    _LOGGER.debug("NAV2 login variant %s returned login form", path)
                    self._login_form_returned = True
                    break
                _LOGGER.debug("NAV2 login accepted on %s with field %s", path, field_name)
                self._login_form_returned = False
                return
        _LOGGER.debug("NAV2 login handshake completed without explicit success")

    async def _probe_data_endpoints(self, paths: tuple[str, ...]) -> tuple[str, ...]:
        usable: list[str] = []
        for path in paths:
            try:
                text = await self._request_text("GET", path, require_ok=False)
            except _NAV2_REQUEST_ERRORS:
                _LOGGER.debug("NAV2 endpoint %s is not reachable", path)
                continue
            if _looks_like_data_response(text):
                _LOGGER.debug("NAV2 endpoint %s is usable", path)
                usable.append(path)
                self._probe_responses[path] = text
            elif _looks_like_auth_failure(text) or _looks_like_login_page(text):
                _LOGGER.debug("NAV2 endpoint %s returned login page instead of data", path)
                self._login_form_returned = True
            else:
                _LOGGER.debug("NAV2 endpoint %s returned unexpected response", path)
        _LOGGER.debug("NAV2 usable data endpoints: %s", usable)
        return tuple(usable)

    async def _request_text(
        self,
        method: str,
        path: str,
        *,
        data: dict[str, str] | None = None,
        require_ok: bool = True,
        include_csrf: bool = True,
    ) -> str:
        if self._session is None:
            raise IdmWebResponseError("Navigator 2.0 HTTP session is not connected")
        headers = {"X-Requested-With": "XMLHttpRequest"}
        if include_csrf and self._csrf_token:
            # Different NAV2 firmwares accept the CSRF token under different
            # header names. Send the common variants in one request.
            headers["CSRF-Token"] = self._csrf_token
            headers["X-CSRF-Token"] = self._csrf_token
            headers["X-CSRFToken"] = self._csrf_token
        url = f"http://{self._url_host}{path}"
        async with self._session.request(
            method,
            url,
            data=data,
            headers=headers,
            timeout=self._timeout,
        ) as response:
            text = str(await response.text())
            if response.status in (401, 403):
                raise IdmWebPinRejectedError("Navigator 2.0 rejected the PIN or session")
            if "invalid csrf token" in text.lower():
                raise IdmWebCsrfError("Navigator 2.0 CSRF token was rejected")
            if require_ok and response.status != 200:
                raise IdmWebResponseError(f"Navigator 2.0 {path} returned HTTP {response.status}")
            return text
