"""Core register definitions shared across IDM heatpump clients."""

from __future__ import annotations

from .client import DataType, RegisterDef
from .const import SYSTEM_MODE_OPTIONS

# Minimal stable core set that can be reused by external clients.
# Full Home Assistant entity mapping continues to live in idm-heatpump-hass.
CORE_REGISTERS: dict[str, RegisterDef] = {
    "outdoor_temp": RegisterDef(
        address=1000,
        datatype=DataType.FLOAT,
        name="outdoor_temp",
        unit="°C",
    ),
    "system_mode": RegisterDef(
        address=1005,
        datatype=DataType.UCHAR,
        name="system_mode",
        writable=True,
        enum_options=SYSTEM_MODE_OPTIONS,
    ),
    "storage_temp": RegisterDef(
        address=1008,
        datatype=DataType.FLOAT,
        name="storage_temp",
        unit="°C",
    ),
    "heatpump_status": RegisterDef(
        address=1090,
        datatype=DataType.BITFLAG,
        name="heatpump_status",
    ),
    "error_acknowledge": RegisterDef(
        address=1999,
        datatype=DataType.UCHAR,
        name="error_acknowledge",
        writable=True,
    ),
}


def get_register(name: str) -> RegisterDef:
    """Return a register definition by canonical name."""
    if name not in CORE_REGISTERS:
        raise ValueError(f"Register '{name}' not found in core registers.")
    return CORE_REGISTERS[name]


def get_all_registers() -> list[RegisterDef]:
    """Return all core register definitions."""
    return list(CORE_REGISTERS.values())
