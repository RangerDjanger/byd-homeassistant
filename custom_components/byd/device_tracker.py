"""Device tracker platform for the BYD integration."""

from __future__ import annotations

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import BydConfigEntry, BydDataUpdateCoordinator
from .entity import BydBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BydConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BYD device trackers."""
    coordinator = entry.runtime_data
    async_add_entities(BydDeviceTracker(coordinator, vin) for vin in coordinator.cars)


class BydDeviceTracker(BydBaseEntity, TrackerEntity):
    """GPS location tracker for a BYD vehicle."""

    _attr_translation_key = "location"

    def __init__(self, coordinator: BydDataUpdateCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "location")

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def latitude(self) -> float | None:
        snapshot = self.snapshot
        return getattr(snapshot.gps, "latitude", None) if snapshot and snapshot.gps else None

    @property
    def longitude(self) -> float | None:
        snapshot = self.snapshot
        return getattr(snapshot.gps, "longitude", None) if snapshot and snapshot.gps else None
