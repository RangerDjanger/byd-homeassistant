"""Diagnostics support for the BYD integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pybyd._redact import redact_for_log  # noqa: E402

from .const import (
    CONF_BASE_URL,
    CONF_CONTROL_PIN,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
)
from .coordinator import BydDataUpdateCoordinator

TO_REDACT_ENTRY = {CONF_USERNAME, CONF_PASSWORD, CONF_CONTROL_PIN, CONF_BASE_URL}
TO_REDACT_SNAPSHOT = {"latitude", "longitude", "lat", "lon", "lng", "vin"}

_SECTIONS = ("realtime", "hvac", "gps", "charging", "energy", "charging_schedule")


def _dump_snapshot(snapshot: Any) -> dict[str, Any]:
    """Serialise a VehicleSnapshot to redacted plain dicts."""
    data: dict[str, Any] = {}
    for section in _SECTIONS:
        model = getattr(snapshot, section, None)
        if model is None:
            data[section] = None
            continue
        try:
            raw = model.model_dump(mode="json", by_alias=False)
        except Exception:  # noqa: BLE001 - diagnostics must never raise
            raw = {"_error": "failed to serialise section"}
        data[section] = async_redact_data(redact_for_log(raw), TO_REDACT_SNAPSHOT)
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: BydDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    vehicles: dict[str, Any] = {}
    for index, (vin, car) in enumerate(coordinator.cars.items()):
        snapshot = coordinator.get_snapshot(vin)
        vehicles[f"vehicle_{index}"] = {
            "capabilities": {
                name: getattr(car.capabilities, name, None)
                for name in dir(car.capabilities)
                if not name.startswith("_")
                and not callable(getattr(car.capabilities, name, None))
            },
            "snapshot": _dump_snapshot(snapshot) if snapshot is not None else None,
        }

    return {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT_ENTRY),
            "options": dict(entry.options),
        },
        "vehicle_count": len(coordinator.cars),
        "vehicles": vehicles,
    }
