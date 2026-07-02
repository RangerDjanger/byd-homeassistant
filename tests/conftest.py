"""Pytest fixtures for the BYD integration tests."""

from __future__ import annotations

import os
import sys
from collections.abc import Generator

import pytest

# The integration vendors ``pybyd`` under ``custom_components/byd/_vendor`` and
# adds that directory to ``sys.path`` at runtime (see ``byd/_vendored.py``). The
# tests import ``pybyd`` directly at collection time, so replicate that here to
# exercise the vendored copy rather than any dev-installed ``pybyd``.
_VENDOR_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "custom_components",
    "byd",
    "_vendor",
)
if _VENDOR_DIR not in sys.path:
    sys.path.insert(0, _VENDOR_DIR)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
    socket_enabled: None,
) -> Generator[None, None, None]:
    """Enable custom integration loading and sockets for all tests."""
    yield
