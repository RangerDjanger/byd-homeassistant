"""Config flow for the BYD integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pybyd import BydAuthenticationError, BydClient, BydConfig, BydError  # noqa: E402
import voluptuous as vol

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
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def _validate_login(hass, data: dict[str, Any]) -> None:
    """Validate credentials by performing a login. Raises on failure."""
    config = BydConfig(
        username=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        control_pin=data.get(CONF_CONTROL_PIN) or None,
        country_code=data.get(CONF_COUNTRY_CODE) or DEFAULT_COUNTRY_CODE,
        base_url=data.get(CONF_BASE_URL) or DEFAULT_BASE_URL,
        mqtt_enabled=False,
    )
    session = async_get_clientsession(hass)
    client = BydClient(config, session=session)
    try:
        await client.async_start()
        await client.login()
        await client.get_vehicles()
    finally:
        await client.async_close()


class BydConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for BYD."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].strip().lower())
            self._abort_if_unique_id_configured()
            try:
                await _validate_login(self.hass, user_input)
            except BydAuthenticationError:
                errors["base"] = "invalid_auth"
            except BydError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during BYD login validation")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication with new credentials."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            data = {**entry.data, **user_input}
            try:
                await _validate_login(self.hass, data)
            except BydAuthenticationError:
                errors["base"] = "invalid_auth"
            except BydError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error during BYD reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data=data)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_CONTROL_PIN): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def _user_schema(user_input: dict[str, Any] | None) -> vol.Schema:
        data = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=data.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=data.get(CONF_PASSWORD, "")): str,
                vol.Optional(CONF_CONTROL_PIN, default=data.get(CONF_CONTROL_PIN, "")): str,
                vol.Optional(
                    CONF_COUNTRY_CODE, default=data.get(CONF_COUNTRY_CODE, DEFAULT_COUNTRY_CODE)
                ): str,
                vol.Optional(CONF_BASE_URL, default=data.get(CONF_BASE_URL, DEFAULT_BASE_URL)): str,
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BydOptionsFlow:
        """Return the options flow."""
        return BydOptionsFlow()


class BydOptionsFlow(OptionsFlow):
    """Handle BYD integration options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL)),
                    vol.Optional(
                        CONF_ENABLE_MQTT,
                        default=options.get(CONF_ENABLE_MQTT, DEFAULT_ENABLE_MQTT),
                    ): bool,
                }
            ),
        )
