"""Tests for the uninitialized-temperature band (idm-heatpump-hass #504, #668)."""

from __future__ import annotations

import math

import pytest

from idm_heatpump import UNINITIALIZED_TEMPERATURE_C, is_uninitialized_temperature


@pytest.mark.parametrize(
    "value",
    [-327.33, -327.22, -327.68, -327.0, UNINITIALIZED_TEMPERATURE_C, -1000],
)
def test_band_covers_observed_and_deeper_values(value: float) -> None:
    # -327.33 and -327.22 are field observations on Navigator 2.0 register
    # 1364 without a wired room sensor; -327.68 is the scaled INT16 minimum.
    assert is_uninitialized_temperature(value) is True


@pytest.mark.parametrize("value", [-25.0, -1.0, 0.0, 21.4, 90.0, 130.0])
def test_realistic_temperatures_are_measurements(value: float) -> None:
    assert is_uninitialized_temperature(value) is False


@pytest.mark.parametrize("value", [-60.0, 327.0, 6553.5, 65535.0])
def test_out_of_band_but_observable_values_stay_measurements(value: float) -> None:
    # Impossible temperatures that are not the documented memory band stay
    # visible so consumer plausibility checks can still observe them.
    assert is_uninitialized_temperature(value) is False


@pytest.mark.parametrize("value", [None, "cold", "", True, False, object()])
def test_non_numeric_inputs_are_not_memory(value: object) -> None:
    assert is_uninitialized_temperature(value) is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_inputs_are_not_memory(value: float) -> None:
    assert is_uninitialized_temperature(value) is False


def test_band_constant_is_sane() -> None:
    assert math.isfinite(UNINITIALIZED_TEMPERATURE_C)
    assert UNINITIALIZED_TEMPERATURE_C == -300.0
