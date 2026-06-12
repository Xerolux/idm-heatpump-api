"""Shared constants for IDM Heatpump API consumers."""

from __future__ import annotations

import enum

DEFAULT_PORT: int = 502
DEFAULT_SLAVE_ID: int = 1
UNUSED_VALUE: float = -1.0
DEFAULT_TIMEOUT: float = 10.0
MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 0.5

HEATING_CIRCUIT_LETTERS: list[str] = list("ABCDEFG")
MAX_HEATING_CIRCUITS: int = 7
MAX_ZONE_MODULES: int = 10
MAX_ROOMS_PER_ZONE: int = 6  # Navigator 10 / current iDM zone modules support 6 rooms each (some older configs may use 8)

MODEL_NAVIGATOR_20: str = "Navigator 2.0"
MODEL_NAVIGATOR_PRO: str = "Navigator Pro"
MODEL_NAVIGATOR_10: str = "Navigator 10"
MODEL_UNKNOWN: str = "Unknown"

FEATURE_SOLAR: str = "solar"
FEATURE_ISC: str = "isc"
FEATURE_PV: str = "pv"
FEATURE_CASCADE: str = "cascade"
FEATURE_ZONE_MODULES: str = "zone_modules"
FEATURE_HEATING_CIRCUITS: str = "heating_circuits"


class SystemMode(enum.IntEnum):
    STANDBY = 0
    AUTOMATIC = 1
    AWAY = 2
    HOT_WATER_ONLY = 4
    HEATING_COOLING_ONLY = 5


SYSTEM_MODE_OPTIONS: dict[int, str] = {
    0: "Standby",
    1: "Automatic",
    2: "Absent",
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
    1: "Time Program",
    2: "Normal",
    3: "Eco",
    4: "Manual Heat",
    5: "Manual Cool",
    255: "Not configured / Unavailable",
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


HP_OPERATING_MODE_OPTIONS: dict[int, str] = {
    0: "Standby",
    1: "Heating",
    2: "Cooling",
    4: "DHW",
    8: "Defrost",
}


# Address 90 (Navigator 10): Smart Grid status
SMART_GRID_OPTIONS: dict[int, str] = {
    0: "Red",
    1: "Yellow",
    2: "Green",
    4: "Supergreen",
}


# Address 1006 (Navigator 10): variable input ("Variabler Eingang")
VARIABLE_INPUT_OPTIONS: dict[int, str] = {
    0: "Not configured",
    1: "External DHW Charging",
    2: "PV / Digital Input",
    3: "External Heat/Cool Switch",
}


# Address 1098: EVU lock contact (0 = locked / "gesperrt")
EVU_LOCK_OPTIONS: dict[int, str] = {
    0: "Locked",
    1: "Not Locked",
}


BIVALENCE_STATE_OPTIONS: dict[int, str] = {
    0: "Off",
    1: "Bivalence 1 Active",
    2: "Bivalence 2 Active",
    3: "Bivalence 1+2 Active",
}


SOLAR_MODE_OPTIONS: dict[int, str] = {
    0: "Automatic",
    1: "DHW",
    2: "Heating",
    3: "DHW + Heating",
    4: "Heat Source / Pool",
}


ISC_MODE_OPTIONS: dict[int, str] = {
    0: "No Waste Heat",
    1: "Heating",
    4: "DHW",
    8: "Heat Source",
    255: "Not configured / Unavailable",
}


ACTIVE_HC_MODE_OPTIONS: dict[int, str] = {
    0: "Off",
    1: "Heating",
    2: "Cooling",
    255: "Not configured / Unavailable",
}


ZONE_MODULE_MODE_OPTIONS: dict[int, str] = {
    0: "Cooling",
    1: "Heating",
}


BOOSTER_FAULT_OPTIONS: dict[int, str] = {
    0: "No fault",
    1: "Booster A fault",
    2: "Booster B fault",
    3: "Booster A + B fault",
}


EEPROM_SENSITIVE_ADDRESSES: set[int] = {
    1005, 1032, 1033, 1034,
    1120, 1121, 1122, 1123,
    1393, 1394, 1395, 1396, 1397, 1398, 1399,
    1401, 1403, 1405, 1407, 1409, 1411, 1413,
    1415, 1417, 1419, 1421, 1423, 1425, 1427,
    1429, 1431, 1433, 1435, 1437, 1439, 1441,
    1442, 1443, 1444, 1445, 1446, 1447, 1448,
    1449, 1450, 1451, 1452, 1453, 1454, 1455,
    1457, 1459, 1461, 1463, 1465, 1467, 1469,
    1471, 1473, 1475, 1477, 1479, 1481, 1483,
    1484, 1485, 1486, 1487, 1488, 1489, 1490,
    1491, 1492, 1493, 1494, 1495, 1496, 1497,
    1505, 1506, 1507, 1508, 1509, 1510, 1511,
    1694, 1695,
    1856,
}


CYCLIC_REGISTERS: set[int] = {1696, 1698}
