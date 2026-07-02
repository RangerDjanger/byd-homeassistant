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
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pybyd import BydAuthenticationError, BydClient, BydConfig, BydError  # noqa: E402
import voluptuous as vol

from .const import (
    CONF_BASE_URL,
    CONF_CONTROL_PIN,
    CONF_COUNTRY_CODE,
    CONF_ENABLE_MQTT,
    CONF_PASSWORD,
    CONF_PRESSURE_UNIT,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    COUNTRIES,
    DEFAULT_BASE_URL,
    DEFAULT_COUNTRY_CODE,
    DEFAULT_ENABLE_MQTT,
    DEFAULT_PRESSURE_UNIT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    base_url_for_country,
)

_LOGGER = logging.getLogger(__name__)

# Fixed polling-interval choices offered in the options flow. Values are
# seconds (stored as strings by the select selector); the coordinator coerces
# them back to int.
SCAN_INTERVAL_OPTIONS = [
    selector.SelectOptionDict(value="30", label="30 seconds"),
    selector.SelectOptionDict(value="60", label="1 minute"),
    selector.SelectOptionDict(value="120", label="2 minutes"),
    selector.SelectOptionDict(value="180", label="3 minutes"),
    selector.SelectOptionDict(value="240", label="4 minutes"),
]

# Country dropdown offered at setup. Value is the ISO code stored as
# CONF_COUNTRY_CODE; the API base URL is derived from it. Labelled by country
# name so the user never has to know the endpoint.
COUNTRY_OPTIONS = [
    selector.SelectOptionDict(value=code, label=name) for code, name, _node in COUNTRIES
]

# Tyre-pressure display unit choices for the options flow. "default" keeps the
# unit the vehicle reports.
PRESSURE_UNIT_OPTIONS = [
    selector.SelectOptionDict(value="default", label="Vehicle default"),
    selector.SelectOptionDict(value="kPa", label="kPa"),
    selector.SelectOptionDict(value="psi", label="psi"),
    selector.SelectOptionDict(value="bar", label="bar"),
]


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
            user_input = self._normalize_endpoint(user_input)
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
    def _normalize_endpoint(user_input: dict[str, Any]) -> dict[str, Any]:
        """Derive the API base URL from the chosen country.

        A non-empty manual ``base_url`` (advanced field, for grey imports)
        always wins; otherwise the endpoint is looked up from the country.
        """
        data = dict(user_input)
        country = (data.get(CONF_COUNTRY_CODE) or DEFAULT_COUNTRY_CODE).upper()
        data[CONF_COUNTRY_CODE] = country
        override = (data.get(CONF_BASE_URL) or "").strip()
        data[CONF_BASE_URL] = override or base_url_for_country(country)
        return data

    @staticmethod
    def _user_schema(user_input: dict[str, Any] | None) -> vol.Schema:
        data = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=data.get(CONF_USERNAME, "")): str,
                vol.Required(CONF_PASSWORD, default=data.get(CONF_PASSWORD, "")): str,
                vol.Optional(CONF_CONTROL_PIN, default=data.get(CONF_CONTROL_PIN, "")): str,
                vol.Required(
                    CONF_COUNTRY_CODE,
                    default=data.get(CONF_COUNTRY_CODE, DEFAULT_COUNTRY_CODE),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=COUNTRY_OPTIONS,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                        custom_value=True,
                    )
                ),
                vol.Optional(CONF_BASE_URL, default=data.get(CONF_BASE_URL, "")): str,
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
                        default=str(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=SCAN_INTERVAL_OPTIONS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_PRESSURE_UNIT,
                        default=options.get(CONF_PRESSURE_UNIT, DEFAULT_PRESSURE_UNIT),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=PRESSURE_UNIT_OPTIONS,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        CONF_ENABLE_MQTT,
                        default=options.get(CONF_ENABLE_MQTT, DEFAULT_ENABLE_MQTT),
                    ): bool,
                }
            ),
        )
