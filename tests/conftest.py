"""Pytest fixtures for the BYD integration tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
    socket_enabled: None,
) -> Generator[None, None, None]:
    """Enable custom integration loading and sockets for all tests."""
    yield
