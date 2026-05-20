"""Tests for the lazy physics-engine adapters."""

import pytest

from aitheria.adapters.genesis_bridge import (
    GenesisNotAvailableError,
    genesis_is_available,
    GenesisScene,
)
from aitheria.adapters.warp_bridge import (
    WarpNotAvailableError,
    warp_is_available,
    aitheria_kernel,
)
from aitheria.adapters.cantera_bridge import (
    CanteraNotAvailableError,
    cantera_is_available,
    load_mechanism,
)


def test_genesis_availability_check_returns_bool():
    assert isinstance(genesis_is_available(), bool)


def test_genesis_scene_raises_when_unavailable():
    if genesis_is_available():
        pytest.skip("Genesis is installed; cannot test unavailable path here")
    with pytest.raises(GenesisNotAvailableError) as exc_info:
        GenesisScene()
    assert "pip install genesis-world" in str(exc_info.value)


def test_warp_availability_check_returns_bool():
    assert isinstance(warp_is_available(), bool)


def test_warp_kernel_decorator_raises_when_unavailable():
    if warp_is_available():
        pytest.skip("Warp is installed; cannot test unavailable path here")

    @aitheria_kernel
    def fake_kernel():
        return 1

    with pytest.raises(WarpNotAvailableError):
        fake_kernel()


def test_cantera_availability_check_returns_bool():
    assert isinstance(cantera_is_available(), bool)


def test_cantera_load_mechanism_raises_when_unavailable():
    if cantera_is_available():
        pytest.skip("Cantera is installed; cannot test unavailable path here")
    with pytest.raises(CanteraNotAvailableError) as exc_info:
        load_mechanism("aitheria/cleanroom/galvanoxide/mechanisms/al_water_mno2.yaml")
    assert "pip install cantera" in str(exc_info.value)
