"""Plausibility helpers for decoded register values.

These helpers classify decoded values that a controller reports even though
they cannot be measurements. They never change decoding: values are handed
through faithfully, and consumers decide what to publish — exactly like the
per-register sentinel sets, which also flow through and are interpreted by
the caller (see ``RegisterDef.effective_sentinel_values``).
"""

from __future__ import annotations

import math
from typing import Any, Final

#: Temperature readings at or below this value are uninitialized controller
#: memory, not measurements. A heating-circuit room-temperature input without
#: a wired sensor answers with memory garbage instead of a documented
#: sentinel — observed as -327.33 °C and -327.22 °C on Navigator 2.0 register
#: 1364 (idm-heatpump-hass issues #504 and #668). The value is finite and
#: stable per boot, so sentinel and NaN guards pass it through. Scaled INT16
#: garbage bottoms out at -327.68 °C; no temperature anywhere in a heat pump
#: is at or below -300 °C, and the margin also covers variants that park the
#: register near its datatype minimum.
UNINITIALIZED_TEMPERATURE_C: Final = -300.0


def is_uninitialized_temperature(value: Any) -> bool:
    """Return True if ``value`` is uninitialized memory, not a measurement.

    Only the documented low band counts: it is backed by field evidence.
    High-side garbage has no field observations and stays visible to the
    plausibility checks of consumers. Non-numeric and non-finite inputs are
    never uninitialized memory; callers handle them through their own
    sentinel and NaN rules.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    numeric = float(value)
    return math.isfinite(numeric) and numeric <= UNINITIALIZED_TEMPERATURE_C
