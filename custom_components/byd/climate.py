"""Climate platform for the BYD integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from pybyd.models.hvac import HvacOverallStatus

from .coordinator import BydConfigEntry, BydDataUpdateCoordinator
from .entity import BydBaseEntity

MIN_TEMP = 15.0
MAX_TEMP = 31.0
DEFAULT_TARGET_TEMP = 21.0
DEFAULT_DURATION = 20


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BydConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up BYD climate entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        BydClimate(coordinator, vin)
        for vin, car in coordinator.cars.items()
        if car.capabilities.climate
    )


class BydClimate(BydBaseEntity, ClimateEntity):
    """Cabin pre-conditioning climate control for a BYD vehicle."""

    _attr_translation_key = "climate"
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: BydDataUpdateCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "climate")
        # Setpoint chosen in HA while climate is off; used on the next start.
        self._pending_target: float | None = None

    @property
    def native_current_temperature(self) -> float | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        if snapshot.hvac is not None and snapshot.hvac.temp_in_car is not None:
            return snapshot.hvac.temp_in_car
        return getattr(snapshot.realtime, "temp_in_car", None) if snapshot.realtime else None

    def _vehicle_target(self) -> float | None:
        """Setpoint the vehicle reports (hvac section first, then realtime)."""
        snapshot = self.snapshot
        if snapshot is None:
            return None
        for section in (snapshot.hvac, snapshot.realtime):
            if section is not None:
                temp = section.main_setting_temp_new or section.main_setting_temp
                if temp is not None:
                    return temp
        return None

    @property
    def native_target_temperature(self) -> float | None:
        if self._pending_target is not None and self.hvac_mode == HVACMode.OFF:
            return self._pending_target
        return self._vehicle_target() or self._pending_target or DEFAULT_TARGET_TEMP

    @property
    def hvac_mode(self) -> HVACMode:
        snapshot = self.snapshot
        if (
            snapshot is not None
            and snapshot.hvac is not None
            and snapshot.hvac.status == HvacOverallStatus.ON
        ):
            return HVACMode.HEAT_COOL
        return HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        target = float(temperature)
        if self.hvac_mode == HVACMode.HEAT_COOL:
            # Climate is running: push the new setpoint to the vehicle now.
            await self._async_start(target)
        else:
            self._pending_target = target
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        await self._async_start(self.native_target_temperature or DEFAULT_TARGET_TEMP)

    async def async_turn_off(self) -> None:
        await self.async_run_command(self.car.hvac.stop)

    async def _async_start(self, temperature: float) -> None:
        await self.async_run_command(
            lambda: self.car.hvac.start(temperature=temperature, duration=DEFAULT_DURATION)
        )
        self._pending_target = None
