"""Shared constants for IDM Heatpump API consumers."""

from __future__ import annotations

import enum

DEFAULT_PORT: int = 502
DEFAULT_SLAVE_ID: int = 1
UNUSED_VALUE: float = -1.0


class SystemMode(enum.IntEnum):
    STANDBY = 0
    AUTOMATIC = 1
    AWAY = 2
    HOLIDAY = 3
    HOT_WATER_ONLY = 4
    HEATING_COOLING_ONLY = 5


SYSTEM_MODE_OPTIONS: dict[int, str] = {
    0: "Standby",
    1: "Automatik",
    2: "Abwesend",
    3: "Urlaub",
    4: "Nur Warmwasser",
    5: "Nur Heizung/Kuehlung",
}


class CircuitMode(enum.IntEnum):
    OFF = 0
    TIMED = 1
    NORMAL = 2
    ECO = 3
    MANUAL_HEAT = 4
    MANUAL_COOL = 5


CIRCUIT_MODE_OPTIONS: dict[int, str] = {
    0: "Aus",
    1: "Zeitprogramm",
    2: "Normal",
    3: "Eco",
    4: "Manuell Heizen",
    5: "Manuell Kuehlen",
}


class RoomMode(enum.IntEnum):
    OFF = 0
    AUTOMATIC = 1
    ECO = 2
    NORMAL = 3
    COMFORT = 4


ROOM_MODE_OPTIONS: dict[int, str] = {
    0: "Aus",
    1: "Automatik",
    2: "Eco",
    3: "Normal",
    4: "Komfort",
}
