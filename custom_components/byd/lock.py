"""Lock platform for the BYD integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pybyd.models.realtime import LockState  # noqa: E402

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator
from .entity import BydBaseEntity

_LOCK_ATTRS = (
    "left_front_door_lock",
    "right_front_door_lock",
    "left_rear_door_lock",
    "right_rear_door_lock",
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BYD lock entities."""
    coordinator: BydDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BydLock] = []
    for vin, car in coordinator.cars.items():
        if car.capabilities.lock or car.capabilities.unlock:
            entities.append(BydLock(coordinator, vin))
    async_add_entities(entities)


class BydLock(BydBaseEntity, LockEntity):
    """Aggregate door lock for a BYD vehicle."""

    _attr_translation_key = "doors"

    def __init__(self, coordinator: BydDataUpdateCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "lock")

    @property
    def is_locked(self) -> bool | None:
        snapshot = self.snapshot
        if snapshot is None or snapshot.realtime is None:
            return None
        states = [getattr(snapshot.realtime, attr, None) for attr in _LOCK_ATTRS]
        known = [s for s in states if s not in (None, LockState.UNKNOWN, LockState.UNAVAILABLE)]
        if not known:
            return None
        if any(s == LockState.UNLOCKED for s in known):
            return False
        return all(s == LockState.LOCKED for s in known)

    async def async_lock(self, **kwargs: Any) -> None:
        await self.async_run_command(self.car.lock.lock)

    async def async_unlock(self, **kwargs: Any) -> None:
        await self.async_run_command(self.car.lock.unlock)
