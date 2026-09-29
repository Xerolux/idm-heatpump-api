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
from datetime import datetime
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
    # ``ws_connect(timeout=<float>)`` is the *close* timeout in every aiohttp
    # release (3.10+ spells it ``ClientWSTimeout(ws_close=...)`` and warns on
    # the float form). Neither bounds the TCP connect or the HTTP upgrade.
    _AIOHTTP_WS_TIMEOUT_CLS: Any = getattr(aiohttp, "ClientWSTimeout", None)
except ModuleNotFoundError:
    _AIOHTTP_WS_TEXT = None
    _AIOHTTP_WS_CLOSED = None
    _AIOHTTP_WS_ERROR = None
    _AIOHTTP_CLIENT_ERROR = ()
    _AIOHTTP_CLIENT_ERROR_CLS = None
    _AIOHTTP_WS_TIMEOUT_CLS = None

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

# Navigator 2.0 statistics pages: one URL per statistics type (runtime,
# generated heat, electrical energy consumption). The pages answer with JSON
# carrying a unitTotal scale and a localized category list.
NAVIGATOR20_STATISTICS_PATHS: tuple[tuple[str, str], ...] = (
    ("runtime", "/data/statistics.php?type=heatpump"),
    ("genheat", "/data/statistics.php?type=amountofheat"),
    ("elcons", "/data/statistics.php?type=baenergyhp"),
)

# Localized category names of the statistics JSON (confirmed German and
# English firmwares); mapped onto the stable English slugs.
_STATISTICS_CATEGORY_NAMES: dict[str, str] = {
    "heizen": "heating",
    "kühlen": "cooling",
    "kühlung": "cooling",
    "warmwasser": "hotwater",
    "abtauung": "defrost",
    "heating": "heating",
    "cooling": "cooling",
    "hot water": "hotwater",
    "domestic hot water": "hotwater",
    "defrost": "defrost",
}

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

_NAVIGATOR10_HOME_REQUEST = {
    "controller": "home",
    "command": "detail",
}

_NAVIGATOR10_HOME_OVERVIEW_REQUEST = {
    "controller": "home",
    "command": "overview",
}

# Operating-mode values of ``home/save`` — identical to the Modbus system_mode
# register numbering, confirmed frame by frame on a live Navigator 10
# (jsonVersion 11, September 2026). ``-1`` (unknown) appears in the device's
# option list but is never a write target.
NAVIGATOR10_SYSTEM_MODE_STANDBY = 0
NAVIGATOR10_SYSTEM_MODE_AUTOMATIC = 1
NAVIGATOR10_SYSTEM_MODE_AWAY = 2
NAVIGATOR10_SYSTEM_MODE_HOLIDAY = 3
NAVIGATOR10_SYSTEM_MODE_HOT_WATER_ONLY = 4
NAVIGATOR10_SYSTEM_MODE_HEATING_COOLING_ONLY = 5
NAVIGATOR10_WRITABLE_SYSTEM_MODES = frozenset(range(0, 6))

# Domestic-hot-water setpoint (tap temperature). The settings-tree item and
# its system.freshwater parameter alias were confirmed on a live Navigator 10
# (jsonVersion 11, September 2026); the device declares the value range
# itself (30..60 degrees Celsius in increments of 0.5 there) and the write is
# validated against exactly that declaration.
NAVIGATOR10_DHW_SETPOINT_SETTING_ID = "13256"
NAVIGATOR10_DATETIME_SETTING_ID = "4537"
NAVIGATOR10_DHW_SETPOINT_PARAM = "FW030"

_NAVIGATOR10_STATUS_REQUEST = {
    "controller": "status",
    "command": "overview",
}

_NAVIGATOR10_FRESHWATER_REQUEST = {
    "controller": "system.freshwater",
    "command": "overview",
}

# System-level read controllers the SPA uses for the performance page, the
# weather tile, the iON cloud-optimization status and the energy-flow widget
# (controller/command pairs capture-confirmed on a live Navigator 10,
# jsonVersion 11, September 2026). All four are read-only: none of them has
# a save command in the shipped frontend except ``ion``, whose write side is
# deliberately not wrapped here.
_NAVIGATOR10_PERFORMANCE_REQUEST = {
    "controller": "system.heatpump.performance",
    "command": "detail",
}

_NAVIGATOR10_WEATHER_REQUEST = {
    "controller": "weather",
    "command": "detail",
}

_NAVIGATOR10_ION_REQUEST = {
    "controller": "ion",
    "command": "overview",
}

_NAVIGATOR10_ENERGYFLOW_REQUEST = {
    "controller": "energyflow",
    "command": "overview",
}

# Navigator 10 statistic/detail selectors, verified against a live controller
# (jsonVersion 11, September 2026). ``statisticType`` selects the value block:
# 0 heat-pump runtimes (heating / DHW "priority" / defrost), 2 second-stage
# bivalence runtime, 3 energy-management heat pump, 4 energy-management
# heating element, 5 energy flow, 6 heat quantities (heating / DHW). Type 1
# was reported by the web UI analysis but the controller answers "not
# available" on this firmware. ``periodType`` selects the aggregation: 0 the
# daily history rows, 1 today plus the key dictionary, 7 lifetime totals.
NAVIGATOR10_STATISTIC_RUNTIME_HEATPUMP = 0
NAVIGATOR10_STATISTIC_RUNTIME_BIVALENCE = 2
NAVIGATOR10_STATISTIC_EMHP = 3
NAVIGATOR10_STATISTIC_EMEH = 4
NAVIGATOR10_STATISTIC_ENERGY_FLOW = 5
NAVIGATOR10_STATISTIC_HEAT_QUANTITIES = 6
NAVIGATOR10_STATISTIC_PERIOD_DAILY = 0
NAVIGATOR10_STATISTIC_PERIOD_TODAY = 1
NAVIGATOR10_STATISTIC_PERIOD_TOTAL = 7


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
    # Heating-circuit flow temperatures. Verified linear sequence B51+i for
    # circuits A-G: B51=A (and existing), B52=B, B53=C (existing), B54=D
    # (verified live on a Navigator 10 ALM with circuits A+D, 26.8 C matching
    # Modbus register 1356), B55=E, B56=F, B57=G. The device only sends codes
    # for configured circuits, so unconfigured ones are simply absent.
    "B51": "flow_temp_HK_A",
    "B52": "flow_temp_HK_B",
    "B53": "flow_temp_HK_C",
    "B54": "flow_temp_HK_D",
    "B55": "flow_temp_HK_E",
    "B56": "flow_temp_HK_F",
    "B57": "flow_temp_HK_G",
    # Heating-circuit room temperatures. Linear sequence B61+i for circuits A-G:
    # B61=A, B62=B, B63=C, B64=D (verified live on a Navigator 10 ALM with
    # circuits A+D), B65=E, B66=F, B67=G.
    "B61": "room_temperature_HK_A",
    "B62": "room_temperature_HK_B",
    "B63": "room_temperature_HK_C",
    "B64": "room_temperature_HK_D",
    "B65": "room_temperature_HK_E",
    "B66": "room_temperature_HK_F",
    "B67": "room_temperature_HK_G",
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
    # Heating-circuit pump and mixer. Verified linear sequences M31+i (pump)
    # and M41+i (mixer) for circuits A-G: M31/M41=A (existing), M34/M44=D
    # (verified live on a Nav10 ALM with circuits A+D). The device only sends
    # codes for configured circuits.
    ("4789", "M31"): "pump_heating_circuitA",
    ("4789", "M32"): "pump_heating_circuitB",
    ("4789", "M33"): "pump_heating_circuitC",
    ("4789", "M34"): "pump_heating_circuitD",
    ("4789", "M35"): "pump_heating_circuitE",
    ("4789", "M36"): "pump_heating_circuitF",
    ("4789", "M37"): "pump_heating_circuitG",
    ("4789", "M41"): "mixer_heating_circuitA",
    ("4789", "M42"): "mixer_heating_circuitB",
    ("4789", "M43"): "mixer_heating_circuitC",
    ("4789", "M44"): "mixer_heating_circuitD",
    ("4789", "M45"): "mixer_heating_circuitE",
    ("4789", "M46"): "mixer_heating_circuitF",
    ("4789", "M47"): "mixer_heating_circuitG",
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

# Raised by the HTTP stack itself (as opposed to a response the device sent);
# _request_text translates these into the IdmWebError tree.
_NAV2_TRANSPORT_ERRORS: tuple[type[BaseException], ...] = (OSError, *_AIOHTTP_CLIENT_ERROR)

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
    **{
        f"flow_temp_HK_{letter}": IdmWebValueDescription(
            f"flow_temp_HK_{letter}", "°C", device_class="temperature", state_class="measurement"
        )
        for letter in ("A", "B", "C", "D", "E", "F", "G")
    },
    **{
        f"room_temperature_HK_{letter}": IdmWebValueDescription(
            f"room_temperature_HK_{letter}",
            "°C",
            device_class="temperature",
            state_class="measurement",
        )
        for letter in ("A", "B", "C", "D", "E", "F", "G")
    },
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
    # SPA shells can mention login/PIN/CSRF without presenting a login form.
    return bool(_LOGIN_FORM_RE.search(text) and _PASSWORD_INPUT_RE.search(text))


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

    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 setting response is not a JSON object")
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

    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 statistic response is not a JSON object")
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

    today = data.get("today")
    if isinstance(today, dict):
        for key, value in today.items():
            if key in {"date", "idx", "typeDict", "groupDict"}:
                continue
            name = f"{prefix}_today_{key}"
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

    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 notification response is not a JSON object")
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
class IdmWebDemandReason:
    """One decoded demand-reason widget of the Navigator 10 home screen."""

    path: str
    operation_mode: int | None
    info: int | None
    reason: str | None


@dataclass(frozen=True)
class IdmWebHomeDetail:
    """Read-only Navigator 10 home/detail snapshot.

    Covers the widgets the controller uses to render its demand reason
    ("Anforderungsgrund") plus the live energy-flow block. The demand-reason
    widgets carry ``operationMode`` always and an ``info`` bitmask while a
    demand is active; without an active demand no ``info`` is present.
    """

    demand_reasons: tuple[IdmWebDemandReason, ...] = ()
    pv_power: IdmWebValue | None = None
    grid_power: IdmWebValue | None = None
    raw_response: str | None = None

    @property
    def pv_demand_active(self) -> bool:
        """Return whether any widget reports PV as its demand reason."""
        return any(node.reason == "pv" for node in self.demand_reasons)


# Navigator 10 demand reason tables, decoded from the web UI's JavaScript
# (firmware jsonVersion 11, verified September 2026 against live frames).
# ``operationMode`` selects the table: 1 heating, 4 domestic hot water,
# 0 "no information", 8 "off". The check order is the SPA's priority order;
# the first matching bit wins, and more than one set bit (ignoring bit 0)
# means "more demands". Bit 32 is PV in both tables.
NAVIGATOR10_HEATING_DEMAND_REASON_BITS: tuple[tuple[int, str], ...] = (
    (2, "no_info"),
    (4, "external_input"),
    (8, "external_bus"),
    (16, "isc"),
    (32, "pv"),
    (64, "frost_protection"),
    (128, "hc_a"),
    (256, "hc_b"),
    (512, "hc_c"),
    (1024, "hc_d"),
    (2048, "hc_e"),
    (4096, "hc_f"),
    (8192, "hc_g"),
    (16384, "system_off"),
    (32768, "ion"),
)
NAVIGATOR10_DHW_DEMAND_REASON_BITS: tuple[tuple[int, str], ...] = (
    (2, "single_loading"),
    (4, "single_loading_boost"),
    (8, "external_input"),
    (16, "external_bus"),
    (32, "pv"),
    (64, "isc"),
    (128, "schedule"),
    (256, "schedule_boost"),
    (512, "system_off"),
    (1024, "dhw_comfort"),
    (2048, "ion"),
    (4096, "cascade"),
    (8192, "dhw_booster"),
)


def decode_navigator10_demand_reason(operation_mode: int | None, info: int | None) -> str | None:
    """Decode one demand-reason widget exactly like the Navigator 10 web UI.

    Returns ``None`` for an undocumented ``operationMode``, a missing info
    bitmask while a demand table applies, or an info bitmask whose set bits
    are unknown to the firmware tables.
    """
    if operation_mode == 0:
        return "no_info"
    if operation_mode == 8:
        return "off"
    if operation_mode is None or info is None:
        return None
    masked = info & -2
    if masked & (masked - 1):
        return "more_demands"
    if operation_mode == 1:
        table = NAVIGATOR10_HEATING_DEMAND_REASON_BITS
    elif operation_mode == 4:
        table = NAVIGATOR10_DHW_DEMAND_REASON_BITS
    else:
        return None
    for bit, reason in table:
        if info & bit:
            return reason
    return None


def _parse_home_power(value: object, name: str) -> IdmWebValue | None:
    if not isinstance(value, dict):
        return None
    raw = value.get("value")
    if raw is None:
        return None
    try:
        numeric = float(str(raw))
    except ValueError:
        numeric = None
    return IdmWebValue(name=name, value=str(raw), raw_key=name, unit="kW", numeric_value=numeric)


def parse_navigator_home_response(
    raw_response: str,
    *,
    include_raw: bool = False,
) -> IdmWebHomeDetail:
    """Parse a Navigator 10 home/detail response.

    Walks the whole payload for widgets carrying ``operationMode``/``info``
    (the demand-reason tiles of the home screen) and reads the energy-flow
    block's ``pv``/``grid`` values where present. The response envelope is
    either ``home`` (full push) or ``homeDetail`` (detail request).
    """
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 home response is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 home response is not a JSON object")

    demand_reasons: list[IdmWebDemandReason] = []
    pv_power: IdmWebValue | None = None
    grid_power: IdmWebValue | None = None

    def walk(node: object, path: str) -> None:
        nonlocal pv_power, grid_power
        if isinstance(node, dict):
            if "operationMode" in node or "info" in node:
                mode = node.get("operationMode")
                info = node.get("info")
                mode_int = mode if isinstance(mode, int) and not isinstance(mode, bool) else None
                info_int = info if isinstance(info, int) and not isinstance(info, bool) else None
                demand_reasons.append(
                    IdmWebDemandReason(
                        path=path,
                        operation_mode=mode_int,
                        info=info_int,
                        reason=decode_navigator10_demand_reason(mode_int, info_int),
                    )
                )
            if "pv" in node and pv_power is None:
                pv_power = _parse_home_power(node.get("pv"), "home_pv_power")
            if "grid" in node and grid_power is None:
                grid_power = _parse_home_power(node.get("grid"), "home_grid_power")
            for key, value in node.items():
                walk(value, f"{path}/{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{path}[{index}]")

    walk(payload, "home")

    return IdmWebHomeDetail(
        demand_reasons=tuple(demand_reasons),
        pv_power=pv_power,
        grid_power=grid_power,
        raw_response=raw_response if include_raw else None,
    )


@dataclass(frozen=True)
class IdmWebStatus:
    """Read-only Navigator 10 status/overview snapshot.

    The frame the web UI consults for connection-level facts: the firmware's
    JSON protocol version, the active user level, the controller clock and the
    frost-protection flag. Fields the firmware does not deliver stay ``None``.
    """

    json_version: int | None = None
    userlevel: int | None = None
    language: str | None = None
    notification_count: int | None = None
    timestamp_ms: int | None = None
    frost_protection_active: bool | None = None
    network: bool | None = None
    authentication_enabled: bool | None = None
    raw_response: str | None = None


def _optional_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def _optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _optional_str(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _optional_float(value: object) -> float | None:
    """Accept the controller's mixed numeric spellings (``"0.0"``, ``5.9``, ``0``)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def parse_navigator_status_response(
    raw_response: str,
    *,
    include_raw: bool = False,
) -> IdmWebStatus:
    """Parse a Navigator 10 status/overview response.

    Every field is read defensively: firmwares differ in which keys they
    deliver, and a support-relevant fact must never turn a whole snapshot
    unusable.
    """
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 status response is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 status response is not a JSON object")
    status = payload.get("status")
    if not isinstance(status, dict):
        raise IdmWebResponseError("Navigator 10 response does not contain a status object")

    frost = status.get("frostProtectionInfo")
    frost_active = None
    if isinstance(frost, dict):
        frost_active = _optional_bool(frost.get("active"))

    return IdmWebStatus(
        json_version=_optional_int(status.get("jsonVersion")),
        userlevel=_optional_int(status.get("userlevel")),
        language=_optional_str(status.get("language")),
        notification_count=_optional_int(status.get("notificationCount")),
        timestamp_ms=_optional_int(status.get("timestamp")),
        frost_protection_active=frost_active,
        network=_optional_bool(status.get("network")),
        authentication_enabled=_optional_bool(status.get("authenticationEnabled")),
        raw_response=raw_response if include_raw else None,
    )


@dataclass(frozen=True)
class IdmWebFreshwater:
    """Read-only Navigator 10 system.freshwater/overview snapshot.

    Domestic-hot-water detail the controller renders on its freshwater page:
    the circulation-pump state, the numeric status info, the DHW system mode
    and the two tank temperatures as delivered by the web interface.
    """

    circulation_active: bool | None = None
    status: int | None = None
    system_mode: int | None = None
    temperature_top: IdmWebValue | None = None
    temperature_bottom: IdmWebValue | None = None
    raw_response: str | None = None


def _parse_freshwater_temperature(value: object, name: str) -> IdmWebValue | None:
    if value is None:
        return None
    try:
        numeric = float(str(value))
    except ValueError:
        numeric = None
    return IdmWebValue(
        name=name,
        value=str(value),
        raw_key=name,
        unit="°C",
        numeric_value=numeric,
    )


@dataclass(frozen=True)
class IdmWebSystemMode:
    """The operating-mode widget of the Navigator 10 home screen."""

    value: int | None = None
    options: tuple[int, ...] = ()
    cooling_configured: bool | None = None


@dataclass(frozen=True)
class IdmWebHomeOverview:
    """Read-only Navigator 10 home/overview snapshot.

    The frame renders the home screen tiles; the operating-mode tile carries
    the current ``systemMode`` and the controller's own list of selectable
    values. Tiles the firmware omits stay empty.
    """

    system_mode: IdmWebSystemMode | None = None
    raw_response: str | None = None


def parse_navigator_home_overview_response(
    raw_response: str,
    *,
    include_raw: bool = False,
) -> IdmWebHomeOverview:
    """Parse a Navigator 10 home/overview response.

    Walks the payload for the ``systemMode`` block; unknown tile shapes are
    ignored rather than failing the snapshot.
    """
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 home/overview response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 home/overview response is not a JSON object")

    system_mode: IdmWebSystemMode | None = None

    def walk(node: object) -> None:
        nonlocal system_mode
        if system_mode is not None:
            return
        if isinstance(node, dict):
            mode = node.get("systemMode")
            if isinstance(mode, dict) and ("value" in mode or "options" in mode):
                raw_value = mode.get("value")
                value = (
                    raw_value
                    if isinstance(raw_value, int) and not isinstance(raw_value, bool)
                    else None
                )
                raw_options = mode.get("options")
                options = (
                    tuple(
                        item
                        for item in (
                            opt.get("value") for opt in raw_options if isinstance(opt, dict)
                        )
                        if isinstance(item, int) and not isinstance(item, bool)
                    )
                    if isinstance(raw_options, list)
                    else ()
                )
                cooling = mode.get("coolingConfigured")
                system_mode = IdmWebSystemMode(
                    value=value,
                    options=options,
                    cooling_configured=cooling if isinstance(cooling, bool) else None,
                )
                return
            for child in node.values():
                walk(child)
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(payload)
    return IdmWebHomeOverview(
        system_mode=system_mode,
        raw_response=raw_response if include_raw else None,
    )


def parse_navigator_save_response(raw_response: str, response_key: str) -> str:
    """Parse a ``<controller>Save`` answer and return the success note text.

    Every write is answered with exactly one frame keyed by the controller
    name plus ``Save`` carrying a ``note`` object (capture-confirmed
    2026-09-28). The note types follow the read-side convention, so a
    rejected write raises :class:`IdmWebResponseError` and can never be
    mistaken for a confirmed one.
    """
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 save response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 save response is not a JSON object")
    block = payload.get(response_key)
    if not isinstance(block, dict):
        raise IdmWebResponseError(f"Navigator 10 response does not contain {response_key}")
    note = block.get("note")
    note_type = note.get("type") if isinstance(note, dict) else None
    note_text = note.get("text") if isinstance(note, dict) else None
    if note_type != "success":
        detail = note_text if isinstance(note_text, str) and note_text else str(note_type)
        raise IdmWebResponseError(f"Navigator 10 rejected the write: {detail}")
    return note_text if isinstance(note_text, str) and note_text else "success"


@dataclass(frozen=True)
class IdmWebHeatingCircuitRef:
    """One entry of the heating-circuit list (id, display name, mode)."""

    hc_id: str
    display_name: str | None = None
    mode: int | None = None


@dataclass(frozen=True)
class IdmWebHeatingCircuitChoice:
    """One chooselist option of a heating-circuit parameter."""

    key: int
    name: str | None = None


@dataclass(frozen=True)
class IdmWebHeatingCircuitValue:
    """One writable heating-circuit value with its device-declared range."""

    parameter_id: str
    value: float | int | None = None
    min_value: float | None = None
    max_value: float | None = None
    increment: str | None = None


@dataclass(frozen=True)
class IdmWebHeatingCircuit:
    """Read-only Navigator 10 ``system.heatingcircuit/detail`` snapshot.

    One frame carries the whole circuit state: the operating mode (with the
    device's own chooselist), the normal and eco room setpoints (with their
    device-declared ranges), the room and flow temperatures, the pump state
    and the list of every configured circuit. Parameter ids follow the
    ``HK<x>NN`` scheme (``HKD04`` is circuit D's normal room setpoint).
    """

    hc_id: str
    display_name: str | None = None
    mode_value: int | None = None
    mode_parameter_id: str | None = None
    mode_options: tuple[IdmWebHeatingCircuitChoice, ...] = ()
    setpoint_normal: IdmWebHeatingCircuitValue | None = None
    setpoint_eco: IdmWebHeatingCircuitValue | None = None
    room_temperature: float | None = None
    flow_setpoint: float | None = None
    pump_active: bool | None = None
    available_circuits: tuple[IdmWebHeatingCircuitRef, ...] = ()
    raw_response: str | None = None


def _parse_hc_value(block: object) -> IdmWebHeatingCircuitValue | None:
    if not isinstance(block, dict):
        return None
    parameter_id = block.get("id")
    if not isinstance(parameter_id, str) or not parameter_id:
        return None
    return IdmWebHeatingCircuitValue(
        parameter_id=parameter_id,
        value=_optional_number(block.get("value")),
        min_value=_optional_number(block.get("min")),
        max_value=_optional_number(block.get("max")),
        increment=_optional_str(block.get("increment")),
    )


def parse_navigator_heatingcircuit_response(
    raw_response: str,
    *,
    include_raw: bool = False,
) -> IdmWebHeatingCircuit:
    """Parse a Navigator 10 ``system.heatingcircuit/detail`` response."""
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 heatingcircuit response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 heatingcircuit response is not a JSON object")
    detail = payload.get("heatingcircuitDetail")
    if not isinstance(detail, dict):
        raise IdmWebResponseError("Navigator 10 response does not contain heatingcircuitDetail")
    hc_id = detail.get("id")
    if not isinstance(hc_id, str) or not hc_id:
        raise IdmWebResponseError("Navigator 10 heatingcircuitDetail carries no id")

    mode_block = detail.get("mode")
    mode_value: int | None = None
    mode_parameter_id: str | None = None
    mode_options: tuple[IdmWebHeatingCircuitChoice, ...] = ()
    if isinstance(mode_block, dict):
        mode_parameter_id = _optional_str(mode_block.get("id"))
        mode_value_raw = _optional_number(mode_block.get("value"))
        mode_value = int(mode_value_raw) if mode_value_raw is not None else None
        raw_types = mode_block.get("types")
        if isinstance(raw_types, list):
            options = []
            for entry in raw_types:
                if not isinstance(entry, dict):
                    continue
                key = _optional_number(entry.get("key"))
                if key is None:
                    continue
                options.append(
                    IdmWebHeatingCircuitChoice(key=int(key), name=_optional_str(entry.get("name")))
                )
            mode_options = tuple(options)

    temperatures = detail.get("temperatures")
    setpoint_normal = None
    setpoint_eco = None
    if isinstance(temperatures, dict):
        heating = temperatures.get("heating")
        if isinstance(heating, dict):
            setpoint_normal = _parse_hc_value(heating.get("normal"))
            setpoint_eco = _parse_hc_value(heating.get("eco"))

    flow_setpoint: float | None = None
    if isinstance(temperatures, dict):
        raw_set = temperatures.get("set")
        if isinstance(raw_set, (int, float)) and not isinstance(raw_set, bool):
            flow_setpoint = float(raw_set)
        elif isinstance(raw_set, str):
            try:
                flow_setpoint = float(raw_set)
            except ValueError:
                flow_setpoint = None

    room = detail.get("room")
    room_temperature: float | None = None
    if isinstance(room, dict):
        room_temperatures = room.get("temperatures")
        if isinstance(room_temperatures, dict):
            raw_actual = room_temperatures.get("actual")
            if isinstance(raw_actual, str):
                try:
                    room_temperature = float(raw_actual)
                except ValueError:
                    room_temperature = None
            else:
                room_temperature = _optional_number(raw_actual)

    available = detail.get("availableHeatingCircuits")
    available_circuits: tuple[IdmWebHeatingCircuitRef, ...] = ()
    if isinstance(available, list):
        refs = []
        for entry in available:
            if not isinstance(entry, dict):
                continue
            entry_id = entry.get("id")
            if not isinstance(entry_id, str) or not entry_id:
                continue
            refs.append(
                IdmWebHeatingCircuitRef(
                    hc_id=entry_id,
                    display_name=_optional_str(entry.get("displayName")),
                    mode=(lambda m: int(m) if m is not None else None)(
                        _optional_number(entry.get("mode"))
                    ),
                )
            )
        available_circuits = tuple(refs)

    pump = detail.get("pumpActive")
    return IdmWebHeatingCircuit(
        hc_id=hc_id,
        display_name=_optional_str(detail.get("displayName")),
        mode_value=mode_value,
        mode_parameter_id=mode_parameter_id,
        mode_options=mode_options,
        setpoint_normal=setpoint_normal,
        setpoint_eco=setpoint_eco,
        room_temperature=room_temperature,
        flow_setpoint=flow_setpoint,
        pump_active=pump if isinstance(pump, bool) else None,
        available_circuits=available_circuits,
        raw_response=raw_response if include_raw else None,
    )


@dataclass(frozen=True)
class IdmWebSettingParameter:
    """One parameter of the Navigator 10 settings tree.

    ``setting/detail`` answers with the parameter's definition: the device's
    own min/max/increment, its type and unit, the current value, and — where
    the parameter also exists as a ``system.*`` sub-controller value — the
    ``param`` alias (for example ``FW030`` for the hot-water setpoint).
    """

    setting_id: str
    name: str | None = None
    param: str | None = None
    type: str | None = None
    value: float | int | str | None = None
    min_value: float | None = None
    max_value: float | None = None
    increment: str | None = None
    unit: str | None = None
    default: float | int | str | None = None


def _optional_number(value: object) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def parse_navigator_setting_parameter(raw_response: str) -> IdmWebSettingParameter:
    """Parse a Navigator 10 ``setting/detail`` parameter answer.

    Every field is read defensively; an answer without a ``settingDetail``
    object raises, unknown fields stay ``None``.
    """
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 setting response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 setting response is not a JSON object")
    detail = payload.get("settingDetail")
    if not isinstance(detail, dict):
        raise IdmWebResponseError("Navigator 10 response does not contain settingDetail")
    setting_id = detail.get("id")
    if not isinstance(setting_id, str) or not setting_id:
        raise IdmWebResponseError("Navigator 10 settingDetail carries no id")
    raw_value = detail.get("value")
    value: float | int | str | None
    if isinstance(raw_value, bool) or raw_value is None:
        value = raw_value if isinstance(raw_value, str) else None
    elif isinstance(raw_value, (int, float)):
        value = raw_value
    else:
        value = str(raw_value)
    return IdmWebSettingParameter(
        setting_id=setting_id,
        name=_optional_str(detail.get("name")),
        param=_optional_str(detail.get("param")),
        type=_optional_str(detail.get("type")),
        value=value,
        min_value=_optional_number(detail.get("min")),
        max_value=_optional_number(detail.get("max")),
        increment=_optional_str(detail.get("increment")),
        unit=_optional_str(detail.get("unit")),
        default=detail.get("def") if isinstance(detail.get("def"), (int, float, str)) else None,
    )


def parse_navigator_freshwater_response(
    raw_response: str,
    *,
    include_raw: bool = False,
) -> IdmWebFreshwater:
    """Parse a Navigator 10 system.freshwater/overview response."""
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 freshwater response is not valid JSON") from exc

    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 freshwater response is not a JSON object")
    freshwater = payload.get("freshwater")
    if not isinstance(freshwater, dict):
        raise IdmWebResponseError("Navigator 10 response does not contain a freshwater object")

    circulation = freshwater.get("circulation")
    circulation_active = None
    if isinstance(circulation, dict):
        circulation_active = _optional_bool(circulation.get("active"))
    status_info = freshwater.get("statusInfo")
    status = None
    if isinstance(status_info, dict):
        status = _optional_int(status_info.get("status"))
    temperatures = freshwater.get("temperatures")

    return IdmWebFreshwater(
        circulation_active=circulation_active,
        status=status,
        system_mode=_optional_int(freshwater.get("systemMode")),
        temperature_top=(
            _parse_freshwater_temperature(temperatures.get("top"), "freshwater_temp_top")
            if isinstance(temperatures, dict)
            else None
        ),
        temperature_bottom=(
            _parse_freshwater_temperature(temperatures.get("bottom"), "freshwater_temp_bottom")
            if isinstance(temperatures, dict)
            else None
        ),
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


@dataclass(frozen=True)
class IdmWebPerformance:
    """Read-only Navigator 10 system.heatpump.performance/detail snapshot.

    The performance page's live power figures: electrical consumption and
    source-side (environment) power plus the flow temperature the controller
    reports for the production side. ``source`` is the controller's own
    measurement-origin code; fields the firmware omits stay ``None``.
    """

    consumption_power: float | None = None
    consumption_source: int | None = None
    consumption_battery: bool | None = None
    environment_power: float | None = None
    environment_source: int | None = None
    environment_temperature_in: float | None = None
    production_flow_temperature: float | None = None
    heating_rod: bool | None = None
    mode: int | None = None
    system_mode: int | None = None
    raw_response: str | None = None


def _nested_float(node: object, dict_key: str, value_key: str) -> float | None:
    if not isinstance(node, dict):
        return None
    inner = node.get(dict_key)
    if not isinstance(inner, dict):
        return None
    return _optional_float(inner.get(value_key))


def parse_navigator_performance_response(
    raw_response: str,
    *,
    include_raw: bool = False,
) -> IdmWebPerformance:
    """Parse a Navigator 10 system.heatpump.performance/detail response.

    Every field is optional on the wire; a frame that lacks the
    ``performanceDetail`` object entirely is a protocol error.
    """
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 performance response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 performance response is not a JSON object")
    detail = payload.get("performanceDetail")
    if not isinstance(detail, dict):
        raise IdmWebResponseError(
            "Navigator 10 response does not contain a performanceDetail object"
        )

    consumption = detail.get("consumption")
    environment = detail.get("environment")
    production = detail.get("production")

    return IdmWebPerformance(
        consumption_power=(
            _optional_float(consumption.get("power")) if isinstance(consumption, dict) else None
        ),
        consumption_source=(
            _optional_int(consumption.get("source")) if isinstance(consumption, dict) else None
        ),
        consumption_battery=(
            _optional_bool(consumption.get("battery")) if isinstance(consumption, dict) else None
        ),
        environment_power=(
            _optional_float(environment.get("power")) if isinstance(environment, dict) else None
        ),
        environment_source=(
            _optional_int(environment.get("source")) if isinstance(environment, dict) else None
        ),
        environment_temperature_in=_nested_float(environment, "temperatures", "in"),
        production_flow_temperature=_nested_float(production, "temperatures", "flow"),
        heating_rod=_optional_bool(detail.get("heatingRod")),
        mode=_optional_int(detail.get("mode")),
        system_mode=_optional_int(detail.get("systemMode")),
        raw_response=raw_response if include_raw else None,
    )


@dataclass(frozen=True)
class IdmWebWeatherDay:
    """One day of the Navigator 10 controller-side weather forecast.

    ``sun`` arrives as an integer amount that matches the day's daylight
    budget in seconds; ``symbol`` is the controller's weather symbol code
    (``sym_w50``). ``temperature_avg_label`` only exists on ``today`` and is
    kept as the controller's formatted string (``"14°C/16.0h"``).
    """

    date: str | None = None
    day_of_week: str | None = None
    cloud_cover: float | None = None
    rain_probability: float | None = None
    sun_seconds: int | None = None
    symbol: int | None = None
    temperature: float | None = None
    temperature_min: float | None = None
    temperature_max: float | None = None
    temperature_avg_label: str | None = None
    wind_speed_min: float | None = None
    wind_speed_max: float | None = None


@dataclass(frozen=True)
class IdmWebWeatherDetail:
    """Read-only Navigator 10 weather/detail snapshot.

    The controller pulls its own forecast (myiDM service) and serves it on
    the local web interface: ``today`` plus up to six forecast days. Fields
    the firmware omits stay ``None``; forecast days arrive in
    ``forecast1``…``forecast6`` order.
    """

    today: IdmWebWeatherDay | None = None
    forecasts: tuple[IdmWebWeatherDay, ...] = ()
    raw_response: str | None = None


def _parse_weather_day(node: object) -> IdmWebWeatherDay:
    if not isinstance(node, dict):
        return IdmWebWeatherDay()
    temperature = node.get("temperature")
    wind = node.get("windSpeed")
    return IdmWebWeatherDay(
        date=_optional_str(node.get("date")),
        day_of_week=_optional_str(node.get("dayofweek")),
        cloud_cover=_optional_float(node.get("cloudCover")),
        rain_probability=_optional_float(node.get("rainProbability")),
        sun_seconds=_optional_int(node.get("sun")),
        symbol=_optional_int(node.get("sym_w50")),
        temperature=_optional_float(
            temperature.get("act") if isinstance(temperature, dict) else None
        ),
        temperature_min=_optional_float(
            temperature.get("min") if isinstance(temperature, dict) else None
        ),
        temperature_max=_optional_float(
            temperature.get("max") if isinstance(temperature, dict) else None
        ),
        temperature_avg_label=_optional_str(
            temperature.get("avg") if isinstance(temperature, dict) else None
        ),
        wind_speed_min=_optional_float(wind.get("min") if isinstance(wind, dict) else None),
        wind_speed_max=_optional_float(wind.get("max") if isinstance(wind, dict) else None),
    )


def parse_navigator_weather_response(
    raw_response: str,
    *,
    include_raw: bool = False,
) -> IdmWebWeatherDetail:
    """Parse a Navigator 10 weather/detail response.

    A frame without the ``weatherDetail`` object is a protocol error; missing
    individual days are simply absent from ``forecasts``.
    """
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 weather response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 weather response is not a JSON object")
    detail = payload.get("weatherDetail")
    if not isinstance(detail, dict):
        raise IdmWebResponseError("Navigator 10 response does not contain a weatherDetail object")

    forecasts = []
    for index in range(1, 7):
        day_node = detail.get(f"forecast{index}")
        if day_node is None:
            continue
        forecasts.append(_parse_weather_day(day_node))

    today_node = detail.get("today")
    return IdmWebWeatherDetail(
        today=_parse_weather_day(today_node) if today_node is not None else None,
        forecasts=tuple(forecasts),
        raw_response=raw_response if include_raw else None,
    )


@dataclass(frozen=True)
class IdmWebIon:
    """Read-only Navigator 10 ion/overview snapshot.

    iON is IDM's cloud energy-optimization subscription. The frame reports
    whether optimization is currently steering the plant, the state of the
    enable setting (``CE001`` chooselist on the captured firmware) and the
    subscription status (``-1`` observed while not subscribed).
    """

    active: bool | None = None
    enabled_setting_id: str | None = None
    enabled_value: int | None = None
    subscription_status: int | None = None
    raw_response: str | None = None


def parse_navigator_ion_response(
    raw_response: str,
    *,
    include_raw: bool = False,
) -> IdmWebIon:
    """Parse a Navigator 10 ion/overview response."""
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 ion response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 ion response is not a JSON object")
    ion = payload.get("ion")
    if not isinstance(ion, dict):
        raise IdmWebResponseError("Navigator 10 response does not contain an ion object")

    enabled = ion.get("enabled")
    return IdmWebIon(
        active=_optional_bool(ion.get("active")),
        enabled_setting_id=_optional_str(enabled.get("id")) if isinstance(enabled, dict) else None,
        enabled_value=_optional_int(enabled.get("value")) if isinstance(enabled, dict) else None,
        subscription_status=_optional_int(ion.get("ionSubscriptionStatus")),
        raw_response=raw_response if include_raw else None,
    )


@dataclass(frozen=True)
class IdmWebEnergyflow:
    """Read-only Navigator 10 energyflow/overview snapshot.

    The energy-flow widget's instantaneous powers. Firmware
    ``T_NAV10_20.24-1580`` removed the ``house`` channel from this frame, so
    ``house_power`` stays ``None`` there and is only populated on older
    firmwares that still deliver it.
    """

    grid_power: float | None = None
    pv_power: float | None = None
    house_power: float | None = None
    signal: int | None = None
    type: int | None = None
    raw_response: str | None = None


def parse_navigator_energyflow_response(
    raw_response: str,
    *,
    include_raw: bool = False,
) -> IdmWebEnergyflow:
    """Parse a Navigator 10 energyflow/overview response."""
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 10 energyflow response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 10 energyflow response is not a JSON object")
    flow = payload.get("energyflow")
    if not isinstance(flow, dict):
        raise IdmWebResponseError("Navigator 10 response does not contain an energyflow object")

    def channel_power(name: str) -> float | None:
        node = flow.get(name)
        if not isinstance(node, dict):
            return None
        return _optional_float(node.get("value"))

    return IdmWebEnergyflow(
        grid_power=channel_power("grid"),
        pv_power=channel_power("pv"),
        house_power=channel_power("house"),
        signal=_optional_int(flow.get("signal")),
        type=_optional_int(flow.get("type")),
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
        self._closed = False
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
            # An explicit connect() re-opens a client that was closed; only
            # the reconnect loop must refuse to run after close().
            self._closed = False
            await self._connect_unlocked()

    async def _connect_unlocked(self) -> None:
        if self._closed:
            raise IdmWebConnectionError("Navigator 10 web client is closed")
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
        ws_timeout: Any = (
            _AIOHTTP_WS_TIMEOUT_CLS(ws_close=self._timeout)
            if _AIOHTTP_WS_TIMEOUT_CLS is not None
            else self._timeout
        )
        try:
            # ``asyncio.timeout`` is what actually bounds the TCP connect, the
            # HTTP upgrade and the authorization frame; the aiohttp timeout
            # only governs the close handshake.
            async with asyncio.timeout(self._timeout):
                self._ws = await self._session.ws_connect(url, timeout=ws_timeout)
                auth = await self._receive_text()
        except builtins.TimeoutError as exc:
            self._last_error = "Navigator 10 websocket connection timed out"
            await self._close_unlocked()
            raise IdmWebTimeoutError(self._last_error) from exc
        except OSError as exc:
            self._last_error = f"Navigator 10 websocket connection failed: {type(exc).__name__}"
            await self._close_unlocked()
            raise IdmWebConnectionError(self._last_error) from exc
        except _AIOHTTP_CLIENT_ERROR as exc:
            # WSServerHandshakeError (no 101: wrong port, HTTP frontend, a
            # firmware answering the auth_code with a status) and
            # ServerDisconnectedError are ClientError but not OSError.
            self._last_error = f"Navigator 10 websocket handshake failed: {type(exc).__name__}"
            await self._close_unlocked()
            raise IdmWebConnectionError(self._last_error) from exc
        except Exception:
            self._last_error = "Navigator 10 websocket connection failed"
            await self._close_unlocked()
            raise
        has_key, authorized = _parse_auth_response(auth)
        if not (has_key and authorized is True):
            await self._close_unlocked()
            if has_key and authorized is False:
                self._last_error = "Navigator 10 rejected the PIN"
                raise IdmWebPinRejectedError(self._last_error)
            self._last_error = "Navigator 10 authorization response was not recognized"
            raise IdmWebProtocolError(self._last_error)
        self._last_success_monotonic = time.monotonic()
        self._last_error = None

    async def close(self) -> None:
        # Set before touching the websocket: closing it fails the request that
        # may be in flight under the lock, and that request must not reconnect
        # (which would leave a websocket and an owned session nobody closes).
        self._closed = True
        await self._close_unlocked()

    async def _close_unlocked(self) -> None:
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

        parsed_sections = 0

        for i, setting_id in enumerate(setting_ids):
            request = dict(_NAVIGATOR10_SETTING_REQUEST)
            request["data"] = {"settingId": setting_id}
            raw = await self._send_json_and_receive_text(request)
            if include_raw:
                raw_responses[f"setting:{setting_id}"] = raw
            try:
                section_values = parse_navigator_setting_response(raw)
            except IdmWebResponseError:
                # Firmware-specific optional sections may be unavailable even
                # after successful authentication. Do not hide malformed data.
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    raise IdmWebResponseError(
                        "Navigator 10 setting response is not valid JSON"
                    ) from None
                setting = payload.get("setting") if isinstance(payload, dict) else None
                note = setting.get("note") if isinstance(setting, dict) else None
                if not (
                    isinstance(note, dict)
                    and note.get("text") == f"setting item [{setting_id}] is not accessible!"
                ):
                    raise
                _LOGGER.debug("Navigator 10 setting %s is not accessible; skipping", setting_id)
            else:
                values.update(section_values)
                parsed_sections += 1
            if self._request_delay and i < len(setting_ids) - 1:
                await asyncio.sleep(self._request_delay)

        if not parsed_sections:
            raise IdmWebResponseError("Navigator 10 returned no accessible setting sections")

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

    async def read_home_detail(self, *, include_raw: bool = False) -> IdmWebHomeDetail:
        """Read the Navigator 10 home screen detail (demand reason, energy flow).

        Navigator 10 only: the home/detail controller does not exist on the
        Navigator 2.0 PHP interface.
        """
        await self.connect()
        raw = await self._send_json_and_receive_text(_NAVIGATOR10_HOME_REQUEST)
        detail = parse_navigator_home_response(raw, include_raw=include_raw)
        self._last_success_monotonic = time.monotonic()
        return detail

    async def read_status_overview(self, *, include_raw: bool = False) -> IdmWebStatus:
        """Read the Navigator 10 status/overview frame (jsonVersion, userlevel).

        The frame is connection-level metadata rather than plant telemetry, so
        callers may read it less often than :meth:`read_data`. Strictly
        read-only like every client method.
        """
        await self.connect()
        raw = await self._send_json_and_receive_text(_NAVIGATOR10_STATUS_REQUEST)
        status = parse_navigator_status_response(raw, include_raw=include_raw)
        self._last_success_monotonic = time.monotonic()
        return status

    async def read_performance(self, *, include_raw: bool = False) -> IdmWebPerformance:
        """Read the Navigator 10 performance detail (live power figures).

        ``system.heatpump.performance/detail`` carries the electrical
        consumption power, the source-side (environment) power and the
        production flow temperature — the numbers the performance page
        renders. Read-only like every client method.
        """
        await self.connect()
        raw = await self._send_json_and_receive_text(_NAVIGATOR10_PERFORMANCE_REQUEST)
        performance = parse_navigator_performance_response(raw, include_raw=include_raw)
        self._last_success_monotonic = time.monotonic()
        return performance

    async def read_weather(self, *, include_raw: bool = False) -> IdmWebWeatherDetail:
        """Read the Navigator 10 controller-side weather forecast.

        The controller pulls its own forecast through the myiDM service and
        serves it locally: today plus up to six forecast days with
        temperature, cloud cover, rain probability, sunshine and wind.
        """
        await self.connect()
        raw = await self._send_json_and_receive_text(_NAVIGATOR10_WEATHER_REQUEST)
        weather = parse_navigator_weather_response(raw, include_raw=include_raw)
        self._last_success_monotonic = time.monotonic()
        return weather

    async def read_ion(self, *, include_raw: bool = False) -> IdmWebIon:
        """Read the Navigator 10 iON cloud-optimization status.

        Reports whether iON is currently steering the plant, the enable
        setting's state and the subscription status. Strictly read-only: the
        ``ion/save`` write side is intentionally not wrapped.
        """
        await self.connect()
        raw = await self._send_json_and_receive_text(_NAVIGATOR10_ION_REQUEST)
        ion = parse_navigator_ion_response(raw, include_raw=include_raw)
        self._last_success_monotonic = time.monotonic()
        return ion

    async def read_energyflow(self, *, include_raw: bool = False) -> IdmWebEnergyflow:
        """Read the Navigator 10 energy-flow widget state (grid/PV power).

        Firmware ``T_NAV10_20.24-1580`` removed the ``house`` channel; the
        field stays ``None`` there so older firmwares keep working unchanged.
        """
        await self.connect()
        raw = await self._send_json_and_receive_text(_NAVIGATOR10_ENERGYFLOW_REQUEST)
        energyflow = parse_navigator_energyflow_response(raw, include_raw=include_raw)
        self._last_success_monotonic = time.monotonic()
        return energyflow

    async def read_freshwater_overview(self, *, include_raw: bool = False) -> IdmWebFreshwater:
        """Read the Navigator 10 domestic-hot-water detail (system.freshwater).

        Covers the circulation state and the numeric status info that the
        Modbus map does not expose. Sub-controllers of the ``system.*`` family
        key their responses by their own name, not by ``settingId``.
        """
        await self.connect()
        raw = await self._send_json_and_receive_text(_NAVIGATOR10_FRESHWATER_REQUEST)
        freshwater = parse_navigator_freshwater_response(raw, include_raw=include_raw)
        self._last_success_monotonic = time.monotonic()
        return freshwater

    async def read_home_overview(self, *, include_raw: bool = False) -> IdmWebHomeOverview:
        """Read the Navigator 10 home screen overview (operating mode state).

        The frame carries the ``systemMode`` tile: the current operating mode
        and the controller's own selectable values — the numbering matches
        the Modbus ``system_mode`` register.
        """
        await self.connect()
        raw = await self._send_json_and_receive_text(_NAVIGATOR10_HOME_OVERVIEW_REQUEST)
        overview = parse_navigator_home_overview_response(raw, include_raw=include_raw)
        self._last_success_monotonic = time.monotonic()
        return overview

    async def set_system_mode(self, mode: int) -> None:
        """Set the operating mode through the local web interface.

        Explicitly a write, on an otherwise read-only client: nothing calls
        it unless the consumer asks for it. The values are the Modbus
        ``system_mode`` numbering (0 standby, 1 automatic, 2 away, 3 holiday,
        4 hot-water-only, 5 heating/cooling-only); ``-1`` (unknown) is not
        writable. The answer frame must confirm with a success note — a
        rejected write raises :class:`IdmWebResponseError`.
        """
        if (
            isinstance(mode, bool)
            or not isinstance(mode, int)
            or mode not in NAVIGATOR10_WRITABLE_SYSTEM_MODES
        ):
            raise ValueError(
                f"mode must be one of {sorted(NAVIGATOR10_WRITABLE_SYSTEM_MODES)}, got {mode!r}"
            )
        await self.connect()
        raw = await self._send_json_and_receive_text(
            {
                "controller": "home",
                "command": "save",
                "data": {"systemMode": {"value": mode}},
            }
        )
        parse_navigator_save_response(raw, "homeSave")

    async def acknowledge_all_notifications(self) -> None:
        """Acknowledge every active Navigator message (``quitAll``)."""
        await self.connect()
        raw = await self._send_json_and_receive_text(
            {
                "controller": "notification",
                "command": "save",
                "data": {"quitAll": True},
            }
        )
        parse_navigator_save_response(raw, "notificationSave")

    async def acknowledge_notification(self, code: str, *, remind_me_later: bool = False) -> None:
        """Acknowledge one Navigator message by its code."""
        clean_code = str(code).strip()
        if not clean_code:
            raise ValueError("code must not be empty")
        await self.connect()
        raw = await self._send_json_and_receive_text(
            {
                "controller": "notification",
                "command": "save",
                "data": {"code": clean_code, "remindMeLater": bool(remind_me_later)},
            }
        )
        parse_navigator_save_response(raw, "notificationSave")

    async def read_setting_parameter(self, setting_id: str) -> IdmWebSettingParameter:
        """Read one parameter definition from the settings tree.

        The device answers with its own min/max/increment, the type and unit
        and the current value — the validation basis for writes.
        """
        clean_id = str(setting_id).strip()
        if not clean_id:
            raise ValueError("setting_id must not be empty")
        await self.connect()
        raw = await self._send_json_and_receive_text(
            {
                "controller": "setting",
                "command": "detail",
                "data": {"settingId": clean_id},
            }
        )
        return parse_navigator_setting_parameter(raw)

    async def save_freshwater_parameter(
        self,
        parameter_id: str,
        value: float | int,
        *,
        setting_id: str | None = None,
    ) -> None:
        """Write one ``system.freshwater`` parameter, range-validated.

        When ``setting_id`` names the settings-tree item of the parameter
        (``detail.param`` links both), the device's own definition is read
        first and the value is checked against the declared min/max —
        exactly the write safety of the register path, applied to the web
        interface. The write itself goes through
        ``system.freshwater/save {parameterId, value}`` like the official UI.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"value must be a number, got {value!r}")
        clean_parameter = str(parameter_id).strip()
        if not clean_parameter:
            raise ValueError("parameter_id must not be empty")
        if setting_id is not None:
            definition = await self.read_setting_parameter(setting_id)
            if definition.param is not None and definition.param != clean_parameter:
                raise ValueError(
                    f"setting {setting_id} is parameter {definition.param}, not {clean_parameter}"
                )
            if definition.min_value is not None and value < definition.min_value:
                raise ValueError(
                    f"value {value} is below the device-declared minimum {definition.min_value}"
                )
            if definition.max_value is not None and value > definition.max_value:
                raise ValueError(
                    f"value {value} is above the device-declared maximum {definition.max_value}"
                )
        await self.connect()
        raw = await self._send_json_and_receive_text(
            {
                "controller": "system.freshwater",
                "command": "save",
                "data": {"parameterId": clean_parameter, "value": value},
            }
        )
        parse_navigator_save_response(raw, "freshwaterSave")

    async def save_dhw_setpoint(self, celsius: float) -> None:
        """Set the domestic-hot-water setpoint (tap temperature).

        Validates against the device's own declared range (setting 13256 /
        parameter FW030 on the confirmed firmware) and writes through
        ``system.freshwater/save``; a rejected write raises.
        """
        await self.save_freshwater_parameter(
            NAVIGATOR10_DHW_SETPOINT_PARAM,
            celsius,
            setting_id=NAVIGATOR10_DHW_SETPOINT_SETTING_ID,
        )

    async def set_datetime(self, value: datetime) -> None:
        """Set the controller clock through the local web interface.

        Capture-confirmed on a live Navigator 10: setting item 4537
        (``N2_SETDATETIME``, type ``setdt``) written through
        ``setting/save`` with the value in ISO-8601 form including the
        millisecond ``.000Z`` suffix the interface submits.
        """
        if not isinstance(value, datetime):
            raise ValueError("value must be a datetime")
        await self.connect()
        raw = await self._send_json_and_receive_text(
            {
                "controller": "setting",
                "command": "save",
                "data": {"settingId": NAVIGATOR10_DATETIME_SETTING_ID, "value": value.isoformat()},
            }
        )
        parse_navigator_save_response(raw, "settingSave")

    async def read_heatingcircuit(self, hc_id: str) -> IdmWebHeatingCircuit:
        """Read one heating circuit's state through ``system.heatingcircuit``.

        The frame carries the operating mode with the device's own option
        list, the normal and eco room setpoints with their declared ranges,
        the room temperature, the pump state and the list of every
        configured circuit.
        """
        clean_id = str(hc_id).strip().upper()
        if not clean_id:
            raise ValueError("hc_id must not be empty")
        await self.connect()
        raw = await self._send_json_and_receive_text(
            {
                "controller": "system.heatingcircuit",
                "command": "detail",
                "data": {"hcId": clean_id},
            }
        )
        circuit = parse_navigator_heatingcircuit_response(raw)
        self._last_success_monotonic = time.monotonic()
        return circuit

    async def save_heatingcircuit_parameter(
        self,
        parameter_id: str,
        value: float | int,
        *,
        min_value: float | None = None,
        max_value: float | None = None,
    ) -> None:
        """Write one ``system.heatingcircuit`` parameter, range-validated.

        The bounds are the device-declared range as delivered by
        :meth:`read_heatingcircuit` (``setpoint_normal.min_value`` etc.) or
        the mode chooselist keys — the register write safety applied to the
        web interface. The write goes through
        ``system.heatingcircuit/save {parameterId, value}``.
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"value must be a number, got {value!r}")
        clean_parameter = str(parameter_id).strip()
        if not clean_parameter:
            raise ValueError("parameter_id must not be empty")
        if min_value is not None and value < min_value:
            raise ValueError(f"value {value} is below the device-declared minimum {min_value}")
        if max_value is not None and value > max_value:
            raise ValueError(f"value {value} is above the device-declared maximum {max_value}")
        await self.connect()
        raw = await self._send_json_and_receive_text(
            {
                "controller": "system.heatingcircuit",
                "command": "save",
                "data": {"parameterId": clean_parameter, "value": value},
            }
        )
        parse_navigator_save_response(raw, "heatingcircuitSave")

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
                if self._closed:
                    raise IdmWebWebSocketError(
                        "Navigator 10 web client was closed during the request"
                    ) from exc
                self._last_error = f"Navigator 10 websocket request failed: {type(exc).__name__}"
            delay = self._reconnect_base_delay
            last_exc: BaseException | None = None
            for attempt in range(1, self._max_reconnect_attempts + 1):
                if self._closed:
                    raise IdmWebWebSocketError(
                        "Navigator 10 web client was closed during the request"
                    ) from last_exc
                self._reconnect_attempts = attempt
                self._last_reconnect_monotonic = time.monotonic()
                try:
                    await self._close_unlocked()
                    if delay:
                        await asyncio.sleep(min(delay, self._reconnect_max_delay))
                        delay = min(delay * 2, self._reconnect_max_delay)
                    await self._connect_unlocked()
                    result = await self._send_json_and_receive_text_once(payload)
                    self._reconnect_attempts = 0
                    return result
                except IdmWebAuthenticationError:
                    await self._close_unlocked()
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


def parse_navigator20_statistics_response(
    raw_response: str, stat_type: str
) -> dict[str, IdmWebValue]:
    """Parse one Navigator 2.0 ``statistics.php`` JSON answer.

    The page carries a ``unitTotal`` scale (Wh/kWh/MWh/GWh, or h/min for
    runtime) and a localized ``total`` list by category. Values are
    normalized to kWh (energy) or hours (runtime) and keyed
    ``stat_<type>_total_<category>``.
    """
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise IdmWebResponseError("Navigator 2.0 statistics response is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise IdmWebResponseError("Navigator 2.0 statistics response is not a JSON object")

    unit = payload.get("unitTotal")
    factor = 1.0
    if isinstance(unit, str):
        unit_clean = unit.strip().strip('",')
        factors = {
            "Wh": 0.001,
            "kWh": 1.0,
            "MWh": 1000.0,
            "GWh": 1000000.0,
            "h": 1.0,
            "min": 1.0 / 60.0,
        }
        factor = factors.get(unit_clean, 1.0)

    values: dict[str, IdmWebValue] = {}
    total = payload.get("total")
    if not isinstance(total, list):
        return values
    for entry in total:
        if not isinstance(entry, dict):
            continue
        raw_name = entry.get("name")
        raw_value = entry.get("value")
        if not isinstance(raw_name, str) or not isinstance(raw_value, (int, float)):
            continue
        category = _STATISTICS_CATEGORY_NAMES.get(raw_name.strip().casefold())
        if category is None:
            continue
        value = float(raw_value) * factor
        name = f"stat_{stat_type}_total_{category}"
        values[name] = IdmWebValue(
            name=name,
            value=f"{value:g}",
            raw_key=raw_name,
            unit="h" if stat_type == "runtime" else "kWh",
            numeric_value=value,
        )
    return values


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
        self._auth_error: IdmWebAuthenticationError | None = None
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
                    if self._auth_error is not None:
                        # A firmware that answers with HTTP 401/403 already
                        # named the cause; do not downgrade it to "detection
                        # failed" or to the generic login-form message.
                        self._last_error = str(self._auth_error)
                        raise self._auth_error
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
        self._auth_error = None
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
        auth_retried = False
        # Caller may pass a subset of paths; intersect with the endpoints that
        # were confirmed during login. Fall back to all confirmed endpoints when
        # the caller's subset does not overlap the detected paths.
        selected_paths = tuple(p for p in paths if p in self._data_paths) or self._data_paths
        try:
            for path in selected_paths:
                while True:
                    try:
                        text = (
                            self._probe_responses.pop(path, None) if use_probe_responses else None
                        )
                        if text is None:
                            text = await self._request_text("GET", path)
                    except IdmWebCsrfError:
                        if csrf_retried:
                            raise
                        _LOGGER.debug(
                            "NAV2 CSRF token rejected while reading %s, attempting one re-login",
                            path,
                        )
                        self._csrf_token = None
                        await self.login()
                        csrf_retried = True
                        use_probe_responses = True
                        continue
                    if "invalid csrf token" in text.lower():
                        self._csrf_token = None
                        raise IdmWebCsrfError("Navigator 2.0 CSRF token was rejected")
                    if _looks_like_auth_failure(text) or _looks_like_login_page(text):
                        if auth_retried:
                            raise IdmWebAuthenticationError(
                                f"NAV2 endpoint {path} returned an authentication response "
                                "instead of data"
                            )
                        # The session cookie expired or the controller rebooted:
                        # the endpoint serves its login page again. Log in once
                        # more instead of reporting a rejected PIN on every poll
                        # until the consumer restarts.
                        _LOGGER.debug(
                            "NAV2 endpoint %s returned the login page, attempting one re-login",
                            path,
                        )
                        self._data_paths = ()
                        self._csrf_token = None
                        await self.login()
                        auth_retried = True
                        use_probe_responses = True
                        continue
                    break
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

    async def read_statistics(self, *, include_raw: bool = False) -> IdmWebData:
        """Read the Navigator 2.0 statistics pages (runtime, heat, energy).

        Fetches ``/data/statistics.php`` for the runtime, generated-heat and
        electrical-energy types and normalizes the totals to hours/kWh. Pages
        a firmware does not answer are skipped; an empty result raises only
        when no page answered at all.
        """
        await self.login()
        values: dict[str, IdmWebValue] = {}
        answered = 0
        for stat_type, path in NAVIGATOR20_STATISTICS_PATHS:
            try:
                raw = await self._request_text("GET", path)
            except IdmWebError:
                _LOGGER.debug("Navigator 2.0 statistics page %s unavailable", path)
                continue
            answered += 1
            try:
                values.update(parse_navigator20_statistics_response(raw, stat_type))
            except IdmWebResponseError:
                _LOGGER.debug("Navigator 2.0 statistics page %s unparseable", path, exc_info=True)
        if not answered:
            raise IdmWebResponseError("Navigator 2.0 answered none of the statistics pages")
        data = IdmWebData(model="Navigator 2.0 Web", values=values)
        self._last_success_monotonic = time.monotonic()
        return data

    async def set_datetime(self, value: datetime) -> None:
        """Set the controller clock through the local settings page.

        The interface expects the ``SSETDATETIME`` settings item as the PUT
        body, with the value in ISO-8601 form — the same shape the settings
        page submits for its date/time editor.
        """
        if not isinstance(value, datetime):
            raise ValueError("value must be a datetime")
        await self.login()
        if self._session is None:  # pragma: no cover - login() guarantees a session
            raise IdmWebResponseError("Navigator 2.0 HTTP session is not connected")
        payload = (
            '{"edesc":"_SETDATETIME","id":"SSETDATETIME","index":3,'
            '"name":"Date/time","type":"setdt","value":"' + value.isoformat() + '"}'
        )
        headers = {"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"}
        if self._csrf_token:
            headers["CSRF-Token"] = self._csrf_token
            headers["X-CSRF-Token"] = self._csrf_token
        url = f"http://{self._url_host}/index.php"
        try:
            async with self._session.put(
                url, data=payload.encode("utf-8"), headers=headers, timeout=self._timeout
            ) as response:
                text = str(await response.text())
                if response.status in (401, 403):
                    raise IdmWebPinRejectedError("Navigator 2.0 rejected the PIN or session")
                if "invalid csrf token" in text.lower():
                    raise IdmWebCsrfError("Navigator 2.0 CSRF token was rejected")
                if response.status != 200:
                    raise IdmWebResponseError(
                        f"Navigator 2.0 clock setting returned HTTP {response.status}"
                    )
        except builtins.TimeoutError as exc:
            raise IdmWebTimeoutError("Navigator 2.0 clock setting timed out") from exc
        except _NAV2_TRANSPORT_ERRORS as exc:
            raise IdmWebConnectionError(
                f"Navigator 2.0 clock setting failed: {type(exc).__name__}"
            ) from exc
        self._last_success_monotonic = time.monotonic()

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
        self._auth_error = None
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
                except IdmWebAuthenticationError as exc:
                    # HTTP 401/403: the device named the cause. Remember it so
                    # login() can raise it instead of a generic detection error.
                    _LOGGER.debug(
                        "NAV2 login variant %s with field %s was rejected: %s",
                        path,
                        field_name,
                        type(exc).__name__,
                    )
                    self._login_form_returned = True
                    self._auth_error = exc
                    continue
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
            except IdmWebAuthenticationError as exc:
                _LOGGER.debug("NAV2 endpoint %s rejected the session: %s", path, type(exc).__name__)
                self._login_form_returned = True
                self._auth_error = exc
                continue
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
        try:
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
                    raise IdmWebResponseError(
                        f"Navigator 2.0 {path} returned HTTP {response.status}"
                    )
                return text
        except builtins.TimeoutError as exc:
            # Only login() wrapped these before; a poll after login let the raw
            # aiohttp / OS error through although the docs promise IdmWebError.
            self._last_error = f"Navigator 2.0 request {path} timed out"
            raise IdmWebTimeoutError(self._last_error) from exc
        except _NAV2_TRANSPORT_ERRORS as exc:
            self._last_error = f"Navigator 2.0 request {path} failed: {type(exc).__name__}"
            raise IdmWebConnectionError(self._last_error) from exc
