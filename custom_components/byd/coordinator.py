"""Data update coordinator for the BYD integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import time as dt_time
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from pybyd import (
    BydAuthenticationError,
    BydCar,
    BydClient,
    BydConfig,
    BydError,
    Vehicle,
)
from pybyd._state_engine import VehicleSnapshot

from .const import (
    CONF_BASE_URL,
    CONF_CHARGING_SCAN_INTERVAL,
    CONF_CONTROL_PIN,
    CONF_COUNTRY_CODE,
    CONF_ENABLE_MQTT,
    CONF_PASSWORD,
    CONF_QUIET_END,
    CONF_QUIET_HOURS_ENABLED,
    CONF_QUIET_SCAN_INTERVAL,
    CONF_QUIET_START,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_BASE_URL,
    DEFAULT_CHARGING_SCAN_INTERVAL,
    DEFAULT_COUNTRY_CODE,
    DEFAULT_ENABLE_MQTT,
    DEFAULT_QUIET_END,
    DEFAULT_QUIET_HOURS_ENABLED,
    DEFAULT_QUIET_SCAN_INTERVAL,
    DEFAULT_QUIET_START,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
)
from .helpers import is_charging

_LOGGER = logging.getLogger(__name__)

type BydConfigEntry = ConfigEntry[BydDataUpdateCoordinator]


class BydDataUpdateCoordinator(DataUpdateCoordinator[dict[str, VehicleSnapshot]]):
    """Coordinate polling + MQTT push updates for a BYD account."""

    config_entry: BydConfigEntry

    def __init__(self, hass: HomeAssistant, entry: BydConfigEntry) -> None:
        self._scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=self._scan_interval),
        )

        self.client: BydClient | None = None
        self.cars: dict[str, BydCar] = {}
        self.vehicles: dict[str, Vehicle] = {}
        self._commands_verified: set[str] = set()
        self._has_pin = bool(entry.data.get(CONF_CONTROL_PIN))
        # While a poll is running, per-section state callbacks are suppressed;
        # the poll publishes one combined update when it finishes.
        self._polling = False

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    def _build_config(self) -> BydConfig:
        entry = self.config_entry
        return BydConfig(
            username=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            control_pin=entry.data.get(CONF_CONTROL_PIN),
            country_code=entry.data.get(CONF_COUNTRY_CODE) or DEFAULT_COUNTRY_CODE,
            base_url=entry.data.get(CONF_BASE_URL) or DEFAULT_BASE_URL,
            mqtt_enabled=bool(entry.options.get(CONF_ENABLE_MQTT, DEFAULT_ENABLE_MQTT)),
        )

    async def _async_setup(self) -> None:
        """Authenticate, discover vehicles, and build per-VIN cars.

        Runs once, inside ``async_config_entry_first_refresh``, so a transient
        failure here becomes ``ConfigEntryNotReady`` (HA retries the setup)
        rather than a permanent setup error.
        """
        client = BydClient(self._build_config(), session=async_get_clientsession(self.hass))
        try:
            await client.async_start()
            await client.login()
            vehicles = await client.get_vehicles()
            for vehicle in vehicles:
                vin = vehicle.vin
                if not vin:
                    continue
                self.vehicles[vin] = vehicle
                self.cars[vin] = await client.get_car(
                    vin,
                    vehicle=vehicle,
                    on_state_changed=self._handle_state_changed,
                )
        except BydAuthenticationError as err:
            await self._async_abort_setup(client)
            raise ConfigEntryAuthFailed(str(err)) from err
        except BydError as err:
            await self._async_abort_setup(client)
            raise UpdateFailed(f"Failed to connect to BYD: {err}") from err
        self.client = client

    async def _async_abort_setup(self, client: BydClient) -> None:
        self.cars.clear()
        self.vehicles.clear()
        await client.async_close()

    async def async_shutdown(self) -> None:
        """Close the client and release resources.

        Registered automatically on entry unload because the coordinator is
        constructed with ``config_entry``.
        """
        await super().async_shutdown()
        if self.client is not None:
            await self.client.async_close()
            self.client = None

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, VehicleSnapshot]:
        snapshots: dict[str, VehicleSnapshot] = {}
        self._polling = True
        try:
            for vin, car in self.cars.items():
                try:
                    await self._poll_car(car)
                except BydAuthenticationError as err:
                    raise ConfigEntryAuthFailed(str(err)) from err
                except BydError as err:
                    _LOGGER.debug("Polling failed for %s: %s", vin, err)
                snapshots[vin] = car.state
        finally:
            self._polling = False
        self._apply_dynamic_interval(snapshots)
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
    # Quiet hours / dynamic polling interval
    # ------------------------------------------------------------------

    def _apply_dynamic_interval(self, snapshots: dict[str, VehicleSnapshot]) -> None:
        """Re-evaluate the polling interval after each cycle.

        HA reschedules the next refresh from ``self.update_interval`` once a
        cycle completes, so mutating it here takes effect from the next poll.
        """
        interval = self._compute_update_interval(snapshots)
        if interval != self.update_interval:
            _LOGGER.debug(
                "BYD polling interval -> %ss (was %ss)",
                int(interval.total_seconds()),
                int(self.update_interval.total_seconds()) if self.update_interval else None,
            )
            self.update_interval = interval

    def _compute_update_interval(self, snapshots: dict[str, VehicleSnapshot]) -> timedelta:
        """Choose the polling interval for the upcoming cycle.

        Outside quiet hours the normal scan interval always applies. Inside the
        quiet window we slow right down, except while a vehicle is charging — then
        we use the (gentler-than-normal) charging interval so charge % and
        time-to-full stay reasonably fresh.
        """
        fast = timedelta(seconds=self._scan_interval)
        options = self.config_entry.options
        if not options.get(CONF_QUIET_HOURS_ENABLED, DEFAULT_QUIET_HOURS_ENABLED):
            return fast

        start = _parse_time(options.get(CONF_QUIET_START), DEFAULT_QUIET_START)
        end = _parse_time(options.get(CONF_QUIET_END), DEFAULT_QUIET_END)
        if start == end:
            # Degenerate window (never / always) — treat as disabled.
            return fast

        if not _in_window(dt_util.now().time(), start, end):
            return fast

        if any(is_charging(snapshot) for snapshot in snapshots.values()):
            charging = int(
                options.get(CONF_CHARGING_SCAN_INTERVAL, DEFAULT_CHARGING_SCAN_INTERVAL)
            )
            return timedelta(seconds=charging)

        quiet = int(options.get(CONF_QUIET_SCAN_INTERVAL, DEFAULT_QUIET_SCAN_INTERVAL))
        return timedelta(seconds=quiet)

    # ------------------------------------------------------------------
    # MQTT push
    # ------------------------------------------------------------------

    @callback
    def _handle_state_changed(self, vin: str, snapshot: VehicleSnapshot) -> None:
        """Handle an accepted state mutation (poll result, command or MQTT push)."""
        if self._polling:
            # The running poll reads ``car.state`` when it finishes, which
            # already includes this mutation.
            return
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

    async def async_run_command(self, vin: str, action: Callable[[], Awaitable[Any]]) -> None:
        """Verify command access, execute a pybyd action, then refresh.

        pybyd errors are re-raised as :class:`HomeAssistantError` so they
        surface cleanly in the UI.
        """
        try:
            await self.async_verify_commands(vin)
            await action()
        except BydError as err:
            raise HomeAssistantError(f"BYD command failed: {err}") from err
        await self.async_request_refresh()

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


def _parse_time(value: Any, default: str) -> dt_time:
    """Parse an ``HH:MM[:SS]`` option value, falling back to ``default``."""
    parsed = dt_util.parse_time(value) if value else None
    if parsed is None:
        parsed = dt_util.parse_time(default)
    assert parsed is not None  # defaults are always valid
    return parsed


def _in_window(now: dt_time, start: dt_time, end: dt_time) -> bool:
    """Whether ``now`` falls in the ``[start, end)`` window, handling wrap.

    A window where ``start > end`` (e.g. 22:00–07:00) crosses midnight, so a
    time is inside it when it is at/after the start *or* before the end.
    """
    if start <= end:
        return start <= now < end
    return now >= start or now < end
