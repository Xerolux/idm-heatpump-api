"""Tests for neutral binary register semantics metadata."""

from __future__ import annotations

import pytest

from idm_heatpump import (
    BINARY_REGISTER_METADATA,
    BinaryRegisterMetadata,
    get_all_registers,
    get_binary_register_metadata,
)


def test_core_binary_metadata_is_available() -> None:
    assert get_binary_register_metadata("heating_demand").device_class == "heat"
    assert get_binary_register_metadata("cooling_demand").device_class == "cold"
    assert get_binary_register_metadata("dhw_demand").device_class == "heat"
    assert get_binary_register_metadata("hp_sum_alarm").device_class == "problem"
    assert get_binary_register_metadata("compressor_status_1").device_class == "running"


def test_zone_room_relays_use_pattern_metadata() -> None:
    metadata = get_binary_register_metadata("zm3_room6_relay")

    assert metadata is not None
    assert metadata.on_values == (1,)
    assert metadata.off_values == (0,)
    assert metadata.device_class == "running"


def test_unknown_register_has_no_invented_semantics() -> None:
    assert get_binary_register_metadata("unknown_binary") is None


def test_explicit_metadata_points_to_existing_binary_registers() -> None:
    registers = get_all_registers()

    for name in BINARY_REGISTER_METADATA:
        assert name in registers
        assert registers[name].binary is True


def test_on_and_off_values_must_not_overlap() -> None:
    with pytest.raises(ValueError, match="must not overlap"):
        BinaryRegisterMetadata(on_values=(1,), off_values=(0, 1))


def test_bitmask_must_be_positive() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        BinaryRegisterMetadata(bitmask=0)


def test_custom_active_low_and_bitmask_metadata() -> None:
    metadata = BinaryRegisterMetadata(
        on_values=(),
        off_values=(),
        bitmask=4,
        inverted=True,
        device_class="lock",
    )

    assert metadata.bitmask == 4
    assert metadata.inverted is True
    assert metadata.device_class == "lock"
