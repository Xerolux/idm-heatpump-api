"""Read-only IDM controller error-code database.

The data was decoded from the configuration of the Windows service tool
("IDM Smart Navigator" 2.3.118) during the NAV10 protocol session of
2026-09-27. The numbering is cross-checked against the message numbers the
Modbus ``internal_message`` register reports; provenance and privacy handling
are documented in the idm-heatpump-hass wiki page "Navigator Protocol
Analysis".

Numbering structure:

- ``0`` — "no error" placeholder with empty texts,
- ``20..999`` — controller messages and errors; this is the range the Modbus
  ``internal_message`` register reports (020-999),
- ``10000+`` — device-side error blocks (20000 display, 30000+ outdoor unit,
  inverter, fan, EVD, Carel peripherals, cascade devices).

Every entry carries the affected component (``text``, for example
"Wärmepumpenvorlauf") and, where the vendor database has one, the error kind
(``info``, for example "Maximaltemperatur"); ``"{text} {info}"`` reproduces
the controller display wording. ``user_description`` and
``service_description`` hold the vendor's remediation texts where available.
All texts are German: the vendor translation table ships German only for
these enums.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any

_DATA_FILE = "error_codes.json"


@dataclass(frozen=True, slots=True)
class ErrorCodeInfo:
    """One entry of the vendor error-code database (German texts)."""

    code: int
    is_warning: bool
    text: str | None
    info: str | None
    user_description: str | None
    service_description: str | None

    @property
    def display_text(self) -> str:
        """Component and error kind as one phrase, e.g. "Vorlauf Maximaltemperatur"."""
        return " ".join(part for part in (self.text, self.info) if part)


@lru_cache(maxsize=1)
def _load() -> dict[int, ErrorCodeInfo]:
    raw = (resources.files("idm_heatpump") / _DATA_FILE).read_text(encoding="utf-8")
    parsed: dict[str, list[Any]] = json.loads(raw)
    return {
        int(code): ErrorCodeInfo(
            code=int(code),
            is_warning=bool(fields[0]),
            text=fields[1] or None,
            info=fields[2] or None,
            user_description=fields[3] or None,
            service_description=fields[4] or None,
        )
        for code, fields in parsed.items()
    }


def get_error_code_info(code: int) -> ErrorCodeInfo | None:
    """Return the database entry for ``code``, or ``None`` when unknown."""
    return _load().get(code)
