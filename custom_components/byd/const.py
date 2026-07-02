"""Constants for the BYD integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "byd"

# Config entry data keys
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_CONTROL_PIN = "control_pin"
CONF_COUNTRY_CODE = "country_code"
CONF_BASE_URL = "base_url"

# Options keys
CONF_SCAN_INTERVAL = "scan_interval"
CONF_ENABLE_MQTT = "enable_mqtt"

# Defaults
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
DEFAULT_ENABLE_MQTT = True
DEFAULT_COUNTRY_CODE = "NL"
DEFAULT_BASE_URL = "https://dilinkappoversea-eu.byd.auto"

MANUFACTURER = "BYD"

SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.LOCK,
    Platform.CLIMATE,
    Platform.SWITCH,
    Platform.BUTTON,
]
