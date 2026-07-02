"""Tests for BYD constants and basic module import integrity."""

from __future__ import annotations

from homeassistant.const import Platform

from custom_components.byd.const import DOMAIN, PLATFORMS


def test_domain() -> None:
    """The integration domain is stable."""
    assert DOMAIN == "byd"


def test_platforms_registered() -> None:
    """All expected platforms are declared."""
    assert Platform.SENSOR in PLATFORMS
    assert Platform.BINARY_SENSOR in PLATFORMS
    assert Platform.DEVICE_TRACKER in PLATFORMS
    assert Platform.LOCK in PLATFORMS
    assert Platform.CLIMATE in PLATFORMS
    assert Platform.SWITCH in PLATFORMS
    assert Platform.BUTTON in PLATFORMS


def test_vendored_pybyd_importable() -> None:
    """The vendored pybyd package resolves via the integration package."""
    import pybyd

    import custom_components.byd  # noqa: F401  # triggers sys.path shim

    assert pybyd.__version__
