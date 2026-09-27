"""Tests for the packaged error-code database."""

from __future__ import annotations

import json
from pathlib import Path

import idm_heatpump
from idm_heatpump.error_codes import ErrorCodeInfo, _load, get_error_code_info

_DATA_FILE = Path(idm_heatpump.__file__).parent / "error_codes.json"


def test_database_file_is_shipped_and_parseable() -> None:
    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    assert len(raw) >= 2000
    for fields in raw.values():
        assert isinstance(fields, list)
        assert len(fields) == 5
        assert isinstance(fields[0], bool)


def test_controller_range_is_covered() -> None:
    database = _load()
    controller_codes = [code for code in database if 20 <= code <= 999]
    assert len(controller_codes) >= 360
    with_text = [code for code in controller_codes if database[code].text]
    assert len(with_text) >= 330


def test_known_controller_codes_match_vendor_texts() -> None:
    # The hand-collected Modbus internal_message texts (idm-heatpump-hass
    # internal_messages.py) decode code 20 as "Wärmepumpenvorlauf
    # Maximaltemperatur" and code 100 as an outdoor-sensor fault.
    code_20 = get_error_code_info(20)
    assert code_20 == ErrorCodeInfo(
        code=20,
        is_warning=True,
        text="Wärmepumpenvorlauf",
        info="Maximaltemperatur",
        user_description=code_20.user_description if code_20 else None,
        service_description=code_20.service_description if code_20 else None,
    )
    assert code_20 is not None
    assert code_20.user_description is not None
    assert "Quittierung" in code_20.user_description
    assert code_20.service_description is not None
    assert "Durchflussmenge" in code_20.service_description

    code_100 = get_error_code_info(100)
    assert code_100 is not None
    assert code_100.is_warning is False
    assert code_100.text == "Außentemperatur"
    assert code_100.info == "Kurzschluss"
    assert code_100.user_description == "Fühlerüberprüfung durch Service erforderlich."

    code_516 = get_error_code_info(516)
    assert code_516 is not None
    assert code_516.display_text == "Modbus Kommunikationsfehler"


def test_display_text_joins_and_falls_back() -> None:
    code_20000 = get_error_code_info(20000)
    assert code_20000 is not None
    assert code_20000.text == "Display Neustart"
    assert code_20000.info is None
    assert code_20000.display_text == "Display Neustart"


def test_zero_is_the_empty_placeholder() -> None:
    code_0 = get_error_code_info(0)
    assert code_0 is not None
    assert code_0.text is None
    assert code_0.info is None
    assert code_0.display_text == ""


def test_unknown_and_gap_codes_return_none() -> None:
    assert get_error_code_info(999999) is None
    # gaps inside the vendor numbering, verified absent from the source data
    assert get_error_code_info(1) is None
    assert get_error_code_info(15) is None


def test_no_carriage_returns_in_texts() -> None:
    for info in _load().values():
        for field in (
            info.text,
            info.info,
            info.user_description,
            info.service_description,
        ):
            assert field is None or "\r" not in field


def test_exported_from_package_root() -> None:
    assert idm_heatpump.ErrorCodeInfo is ErrorCodeInfo
    assert idm_heatpump.get_error_code_info is get_error_code_info
