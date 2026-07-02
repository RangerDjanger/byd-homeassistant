"""Climate platform for the BYD integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pybyd.models.hvac import HvacOverallStatus  # noqa: E402

from .const import DOMAIN
from .coordinator import BydDataUpdateCoordinator
from .entity import BydBaseEntity

MIN_TEMP = 15.0
MAX_TEMP = 31.0
DEFAULT_TARGET_TEMP = 21.0
DEFAULT_DURATION = 20


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up BYD climate entities."""
    coordinator: BydDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[BydClimate] = []
    for vin, car in coordinator.cars.items():
        if car.capabilities.climate:
            entities.append(BydClimate(coordinator, vin))
    async_add_entities(entities)


class BydClimate(BydBaseEntity, ClimateEntity):
    """Cabin pre-conditioning climate control for a BYD vehicle."""

    _attr_translation_key = "climate"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT_COOL]
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator: BydDataUpdateCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin, "climate")
        self._target_temp: float = DEFAULT_TARGET_TEMP

    @property
    def current_temperature(self) -> float | None:
        snapshot = self.snapshot
        if snapshot is None:
            return None
        if snapshot.hvac is not None and snapshot.hvac.temp_in_car is not None:
            return snapshot.hvac.temp_in_car
        return getattr(snapshot.realtime, "temp_in_car", None) if snapshot.realtime else None

    @property
    def target_temperature(self) -> float | None:
        snapshot = self.snapshot
        if snapshot is not None:
            hvac = snapshot.hvac
            if hvac is not None:
                temp = hvac.main_setting_temp_new or hvac.main_setting_temp
                if temp is not None:
                    return temp
            rt = snapshot.realtime
            if rt is not None:
                temp = rt.main_setting_temp_new or rt.main_setting_temp
                if temp is not None:
                    return temp
        return self._target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        snapshot = self.snapshot
        if snapshot is not None and snapshot.hvac is not None:
            if snapshot.hvac.status == HvacOverallStatus.ON:
                return HVACMode.HEAT_COOL
            if snapshot.hvac.status == HvacOverallStatus.OFF:
                return HVACMode.OFF
        return HVACMode.OFF

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._target_temp = float(temperature)
        # Only push to the vehicle if climate is currently running.
        if self.hvac_mode == HVACMode.HEAT_COOL:
            await self.async_run_command(
                lambda: self.car.hvac.start(
                    temperature=self._target_temp, duration=DEFAULT_DURATION
                )
            )
        else:
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if hvac_mode == HVACMode.OFF:
            await self.async_turn_off()
        else:
            await self.async_turn_on()

    async def async_turn_on(self) -> None:
        await self.async_run_command(
            lambda: self.car.hvac.start(
                temperature=self._target_temp, duration=DEFAULT_DURATION
            )
        )

    async def async_turn_off(self) -> None:
        await self.async_run_command(self.car.hvac.stop)
