"""Neutral semantic metadata for IDM binary registers.

This module deliberately stays independent of Home Assistant. Consumers map
``device_class`` strings to their own entity model while using the explicit
on/off values, bit masks and polarity to decode controller states safely.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, TypeAlias

BinaryValue: TypeAlias = bool | int | float | str
BinaryDeviceClass: TypeAlias = Literal[
    "problem",
    "connectivity",
    "lock",
    "cold",
    "heat",
    "running",
    "power",
]


@dataclass(frozen=True)
class BinaryRegisterMetadata:
    """Semantics required to interpret one decoded binary register value."""

    on_values: tuple[BinaryValue, ...] = (1,)
    off_values: tuple[BinaryValue, ...] = (0,)
    bitmask: int | None = None
    inverted: bool = False
    device_class: BinaryDeviceClass | None = None

    def __post_init__(self) -> None:
        if set(self.on_values) & set(self.off_values):
            raise ValueError("Binary on_values and off_values must not overlap")
        if self.bitmask is not None and self.bitmask <= 0:
            raise ValueError("Binary bitmask must be positive")


def _metadata(device_class: BinaryDeviceClass) -> BinaryRegisterMetadata:
    return BinaryRegisterMetadata(device_class=device_class)


BINARY_REGISTER_METADATA: dict[str, BinaryRegisterMetadata] = {
    "heating_demand": _metadata("heat"),
    "cooling_demand": _metadata("cold"),
    "dhw_demand": _metadata("heat"),
    "hp_sum_alarm": _metadata("problem"),
    "compressor_status_1": _metadata("running"),
    "compressor_status_2": _metadata("running"),
}

_ZONE_ROOM_RELAY = re.compile(r"^zm\d+_room\d+_relay$")
_ZONE_ROOM_RELAY_METADATA = _metadata("running")


def get_binary_register_metadata(name: str) -> BinaryRegisterMetadata | None:
    """Return explicit metadata for a known binary register name."""
    metadata = BINARY_REGISTER_METADATA.get(name)
    if metadata is not None:
        return metadata
    if _ZONE_ROOM_RELAY.fullmatch(name):
        return _ZONE_ROOM_RELAY_METADATA
    return None


__all__ = [
    "BINARY_REGISTER_METADATA",
    "BinaryDeviceClass",
    "BinaryRegisterMetadata",
    "BinaryValue",
    "get_binary_register_metadata",
]
