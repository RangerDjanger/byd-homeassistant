"""The BYD Integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import _vendored  # noqa: F401  # must precede any pybyd import
from .const import DOMAIN, PLATFORMS
from .coordinator import BydConfigEntry, BydDataUpdateCoordinator
from .services import async_register_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the integration's actions once, independent of config entries."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: BydConfigEntry) -> bool:
    """Set up BYD Integration from a config entry."""
    coordinator = BydDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BydConfigEntry) -> bool:
    """Unload a config entry (the coordinator shuts itself down on unload)."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
