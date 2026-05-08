"""Shared constants for IDM Heatpump API consumers."""

from __future__ import annotations

import enum

DEFAULT_PORT: int = 502
DEFAULT_SLAVE_ID: int = 1
UNUSED_VALUE: float = -1.0
DEFAULT_TIMEOUT: float = 10.0
MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 0.5


class SystemMode(enum.IntEnum):
    STANDBY = 0
    AUTOMATIC = 1
    AWAY = 2
    HOLIDAY = 3
    HOT_WATER_ONLY = 4
    HEATING_COOLING_ONLY = 5


SYSTEM_MODE_OPTIONS: dict[int, str] = {
    0: "Standby",
    1: "Automatic",
    2: "Away",
    3: "Holiday",
    4: "Hot Water Only",
    5: "Heating/Cooling Only",
}


class CircuitMode(enum.IntEnum):
    OFF = 0
    TIMED = 1
    NORMAL = 2
    ECO = 3
    MANUAL_HEAT = 4
    MANUAL_COOL = 5


CIRCUIT_MODE_OPTIONS: dict[int, str] = {
    0: "Off",
    1: "Timed Schedule",
    2: "Normal",
    3: "Eco",
    4: "Manual Heat",
    5: "Manual Cool",
}


class RoomMode(enum.IntEnum):
    OFF = 0
    AUTOMATIC = 1
    ECO = 2
    NORMAL = 3
    COMFORT = 4


ROOM_MODE_OPTIONS: dict[int, str] = {
    0: "Off",
    1: "Automatic",
    2: "Eco",
    3: "Normal",
    4: "Comfort",
}
