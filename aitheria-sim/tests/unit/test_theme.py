"""Tests for aitheria.theme."""

import pytest

from aitheria.theme import NAVY_GOLD, luminance_ramp


def test_palette_values_known():
    assert NAVY_GOLD.primary == "#0A1628"
    assert NAVY_GOLD.accent == "#D4A843"


def test_palette_is_immutable():
    with pytest.raises((AttributeError, Exception)):
        NAVY_GOLD.primary = "#FFFFFF"  # type: ignore


def test_luminance_ramp_length():
    ramp = luminance_ramp("#0A1628", n=9)
    assert len(ramp) == 9
    assert ramp[0] == "#0A1628"
    assert ramp[-1] == "#FFFFFF"


def test_luminance_ramp_bad_input():
    with pytest.raises(ValueError):
        luminance_ramp("not-a-hex")
