"""Data update coordinator for the BYD integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pybyd import (  # noqa: E402  # import after vendored path setup
    BydAuthenticationError,
    BydCar,
    BydClient,
    BydConfig,
    BydError,
    Vehicle,
)
from pybyd._state_engine import VehicleSnapshot  # noqa: E402

from .const import (
    CONF_BASE_URL,
    CONF_CONTROL_PIN,
    CONF_COUNTRY_CODE,
    CONF_ENABLE_MQTT,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_BASE_URL,
    DEFAULT_COUNTRY_CODE,
    DEFAULT_ENABLE_MQTT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)


class BydDataUpdateCoordinator(DataUpdateCoordinator[dict[str, VehicleSnapshot]]):
    """Coordinate polling + MQTT push updates for a BYD account."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.config_entry = entry

        scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )

        self.client: BydClient | None = None
        self.cars: dict[str, BydCar] = {}
        self.vehicles: dict[str, Vehicle] = {}
        self._commands_verified: set[str] = set()
        self._has_pin = bool(entry.data.get(CONF_CONTROL_PIN))

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    def _build_config(self) -> BydConfig:
        entry = self.config_entry
        enable_mqtt = bool(entry.options.get(CONF_ENABLE_MQTT, DEFAULT_ENABLE_MQTT))
        return BydConfig(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            control_pin=entry.data.get(CONF_CONTROL_PIN),
            country_code=entry.data.get(CONF_COUNTRY_CODE) or DEFAULT_COUNTRY_CODE,
            base_url=entry.data.get(CONF_BASE_URL) or DEFAULT_BASE_URL,
            mqtt_enabled=enable_mqtt,
        )

    async def async_setup(self) -> None:
        """Authenticate, discover vehicles, and build per-VIN cars."""
        session = async_get_clientsession(self.hass)
        client = BydClient(self._build_config(), session=session)
        try:
            await client.async_start()
            await client.login()
            vehicles = await client.get_vehicles()
        except BydAuthenticationError as err:
            await client.async_close()
            raise ConfigEntryAuthFailed(str(err)) from err
        except BydError as err:
            await client.async_close()
            raise UpdateFailed(f"Failed to connect to BYD: {err}") from err

        self.client = client
        for vehicle in vehicles:
            vin = vehicle.vin
            if not vin:
                continue
            self.vehicles[vin] = vehicle
            car = await client.get_car(
                vin,
                vehicle=vehicle,
                on_state_changed=self._handle_state_changed,
            )
            self.cars[vin] = car

    async def async_shutdown(self) -> None:
        """Close the client and release resources."""
        await super().async_shutdown()
        if self.client is not None:
            await self.client.async_close()
            self.client = None

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, VehicleSnapshot]:
        if self.client is None:
            await self.async_setup()

        snapshots: dict[str, VehicleSnapshot] = {}
        for vin, car in self.cars.items():
            try:
                await self._poll_car(car)
            except BydAuthenticationError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except BydError as err:
                _LOGGER.debug("Polling failed for %s: %s", vin, err)
            snapshots[vin] = car.state
        return snapshots

    async def _poll_car(self, car: BydCar) -> None:
        """Refresh all data sections for one vehicle, tolerating per-section gaps."""
        await car.update_realtime()
        for fetch in (car.update_hvac, car.update_gps, car.update_charging, car.update_energy):
            try:
                await fetch()
            except BydError as err:  # pragma: no cover - section may be unsupported
                _LOGGER.debug("Section refresh failed for %s: %s", car.vin, err)

    # ------------------------------------------------------------------
    # MQTT push
    # ------------------------------------------------------------------

    @callback
    def _handle_state_changed(self, vin: str, snapshot: VehicleSnapshot) -> None:
        """Handle an accepted state mutation (poll result or MQTT push)."""
        data = dict(self.data or {})
        data[vin] = snapshot
        self.async_set_updated_data(data)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    async def async_verify_commands(self, vin: str) -> None:
        """Ensure remote command access is verified once per session for a VIN."""
        if not self._has_pin:
            raise BydError("A control PIN is required for remote commands.")
        if vin in self._commands_verified or self.client is None:
            return
        await self.client.verify_command_access(vin)
        self._commands_verified.add(vin)

    def get_snapshot(self, vin: str) -> VehicleSnapshot | None:
        """Return the latest snapshot for a VIN."""
        if self.data is None:
            return None
        return self.data.get(vin)

    @property
    def has_pin(self) -> bool:
        """Whether a control PIN was configured."""
        return self._has_pin

    def device_meta(self, vin: str) -> dict[str, Any]:
        """Return device metadata fields for a VIN."""
        vehicle = self.vehicles.get(vin)
        if vehicle is None:
            return {"name": vin, "model": None, "manufacturer": MANUFACTURER, "sw_version": None}
        return {
            "name": vehicle.auto_alias or vehicle.model_name or vin,
            "model": vehicle.model_name or None,
            "manufacturer": vehicle.brand_name or MANUFACTURER,
            "sw_version": vehicle.tbox_version or None,
        }
