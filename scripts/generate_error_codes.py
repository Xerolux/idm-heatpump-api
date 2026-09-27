"""Generate ``idm_heatpump/error_codes.json`` from a NAV10 protocol capture.

The source of truth is the decoded configuration of the Windows service tool
("IDM Smart Navigator" 2.3.118) captured during the NAV10 protocol session of
2026-09-27. The capture itself is NOT committed: besides these generic device
tables it contains plant-identifying data (PINs, serial numbers, network
addresses). Only the resolved, plant-independent error texts are packaged.

Usage::

    python scripts/generate_error_codes.py <capture-data-dir>

``<capture-data-dir>`` is the directory holding ``errors.json`` and
``translations.json``. The generator resolves every enum reference against the
German translations, normalizes line breaks and writes one entry per line so
the JSON stays reviewable in diffs.

Field order of the packed arrays:
``[is_warning, text, info, user_description, service_description]``.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

FIELDS = 5  # is_warning, text, info, user_description, service_description


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return normalized or None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    data_dir = Path(argv[1])

    with (data_dir / "translations.json").open(encoding="utf-8") as handle:
        texts: dict[str, dict[str, str]] = {}
        for row in json.load(handle):
            translation = (row.get("translation") or "").strip()
            if translation:
                texts.setdefault(row["enum"], {})[row["language"]] = translation

    def pick(enum: str | None) -> str | None:
        if not enum:
            return None
        return _clean(texts.get(enum, {}).get("de"))

    with (data_dir / "errors.json").open(encoding="utf-8") as handle:
        errors = json.load(handle)

    database: dict[int, list[object]] = {}
    extras_samples: list[tuple[int, object]] = []
    for entry in errors:
        code = int(entry["id"])
        if code in database:
            print(f"duplicate code {code}, aborting")
            return 1
        if entry.get("extras"):
            extras_samples.append((code, entry["extras"]))
        database[code] = [
            bool(entry.get("is_warning")),
            pick(entry.get("text_enum")),
            pick(entry.get("info_enum")),
            pick(entry.get("user_description_enum")),
            pick(entry.get("service_description_enum")),
        ]

    lines = [
        f'"{code}": {json.dumps(database[code], ensure_ascii=False, separators=(",", ":"))}'
        for code in sorted(database)
    ]
    payload = "{\n" + ",\n".join(lines) + "\n}\n"
    target = Path(__file__).resolve().parents[1] / "idm_heatpump" / "error_codes.json"
    target.write_text(payload, encoding="utf-8", newline="\n")

    stats: Counter[str] = Counter()
    for entry in database.values():
        if entry[1]:
            stats["text"] += 1
        if entry[2]:
            stats["info"] += 1
        if entry[3]:
            stats["user_description"] += 1
        if entry[4]:
            stats["service_description"] += 1
        if entry[0]:
            stats["is_warning"] += 1
    controller_range = sum(1 for code in database if 20 <= code <= 999)
    print(f"wrote {target} ({target.stat().st_size / 1024:.0f} KB)")
    print(f"entries: {len(database)}, controller range 20..999: {controller_range}")
    print(f"coverage: {dict(stats)}")
    if extras_samples:
        print(f"entries with non-null extras (dropped): {len(extras_samples)}")
        for code, extras in extras_samples:
            print(f"  {code}: {extras!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
