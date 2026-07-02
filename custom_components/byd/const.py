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
CONF_PRESSURE_UNIT = "pressure_unit"

# Defaults
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
DEFAULT_ENABLE_MQTT = True
# "default" keeps the unit the vehicle reports; otherwise "kPa" / "psi" / "bar".
DEFAULT_PRESSURE_UNIT = "default"
DEFAULT_COUNTRY_CODE = "AU"
DEFAULT_BASE_URL = "https://dilinkappoversea-au.byd.auto"

MANUFACTURER = "BYD"

# ---------------------------------------------------------------------------
# BYD overseas regional endpoints
#
# BYD routes each account to one of 16 regional "oversea" nodes, selected by
# the account's country. The node map mirrors the upstream
# jkaberg/hass-byd-vehicle integration.
# ---------------------------------------------------------------------------

# Node key -> API base URL. NOTE: the "no" node is BYD's Middle East/Africa
# node, NOT Norway — Norway (NO) is served by the "eu" node.
NODE_BASE_URLS: dict[str, str] = {
    "eu": "https://dilinkappoversea-eu.byd.auto",
    "sg": "https://dilinkappoversea-sg.byd.auto",
    "au": "https://dilinkappoversea-au.byd.auto",
    "br": "https://dilinkappoversea-br.byd.auto",
    "jp": "https://dilinkappoversea-jp.byd.auto",
    "uz": "https://dilinkappoversea-uz.byd.auto",
    "no": "https://dilinkappoversea-no.byd.auto",
    "mx": "https://dilinkappoversea-mx.byd.auto",
    "id": "https://dilinkappoversea-id.byd.auto",
    "tr": "https://dilinkappoversea-tr.byd.auto",
    "kr": "https://dilinkappoversea-kr.byd.auto",
    "in": "https://dilinkappoversea-in.byd.auto",
    "vn": "https://dilinkappoversea-vn.byd.auto",
    "sa": "https://dilinkappoversea-sa.byd.auto",
    "om": "https://dilinkappoversea-om.byd.auto",
    "kz": "https://dilinkappoversea-kz.byd.auto",
}

# (ISO country code, display name, node key), ordered by display name.
COUNTRIES: tuple[tuple[str, str, str], ...] = (
    ("AL", "Albania", "eu"),
    ("AR", "Argentina", "mx"),
    ("AU", "Australia", "au"),
    ("AT", "Austria", "eu"),
    ("BH", "Bahrain", "no"),
    ("BD", "Bangladesh", "sg"),
    ("BE", "Belgium", "eu"),
    ("BT", "Bhutan", "sg"),
    ("BO", "Bolivia", "mx"),
    ("BA", "Bosnia and Herzegovina", "eu"),
    ("BR", "Brazil", "br"),
    ("BN", "Brunei", "sg"),
    ("BG", "Bulgaria", "eu"),
    ("KH", "Cambodia", "sg"),
    ("CL", "Chile", "mx"),
    ("CO", "Colombia", "mx"),
    ("CR", "Costa Rica", "mx"),
    ("HR", "Croatia", "eu"),
    ("CY", "Cyprus", "eu"),
    ("CZ", "Czech Republic", "eu"),
    ("DK", "Denmark", "eu"),
    ("DO", "Dominican Republic", "mx"),
    ("EC", "Ecuador", "mx"),
    ("EG", "Egypt", "no"),
    ("SV", "El Salvador", "mx"),
    ("EE", "Estonia", "eu"),
    ("FI", "Finland", "eu"),
    ("FR", "France", "eu"),
    ("PF", "French Polynesia", "sg"),
    ("DE", "Germany", "eu"),
    ("GR", "Greece", "eu"),
    ("GT", "Guatemala", "mx"),
    ("HN", "Honduras", "mx"),
    ("HK", "Hong Kong", "sg"),
    ("HU", "Hungary", "eu"),
    ("IS", "Iceland", "eu"),
    ("IN", "India", "in"),
    ("ID", "Indonesia", "id"),
    ("IE", "Ireland", "eu"),
    ("IL", "Israel", "eu"),
    ("IT", "Italy", "eu"),
    ("JP", "Japan", "jp"),
    ("JO", "Jordan", "no"),
    ("KZ", "Kazakhstan", "kz"),
    ("XK", "Kosovo", "eu"),
    ("KW", "Kuwait", "no"),
    ("LA", "Laos", "sg"),
    ("LV", "Latvia", "eu"),
    ("LI", "Liechtenstein", "eu"),
    ("LT", "Lithuania", "eu"),
    ("LU", "Luxembourg", "eu"),
    ("MO", "Macao", "sg"),
    ("MY", "Malaysia", "sg"),
    ("MV", "Maldives", "sg"),
    ("MT", "Malta", "eu"),
    ("MU", "Mauritius", "no"),
    ("MX", "Mexico", "mx"),
    ("MD", "Moldova", "eu"),
    ("MC", "Monaco", "eu"),
    ("MN", "Mongolia", "sg"),
    ("ME", "Montenegro", "eu"),
    ("MA", "Morocco", "no"),
    ("MM", "Myanmar", "sg"),
    ("NP", "Nepal", "sg"),
    ("NL", "Netherlands", "eu"),
    ("NC", "New Caledonia", "sg"),
    ("NZ", "New Zealand", "au"),
    ("NI", "Nicaragua", "mx"),
    ("MK", "North Macedonia", "eu"),
    ("NO", "Norway", "eu"),
    ("OM", "Oman", "om"),
    ("PK", "Pakistan", "sg"),
    ("PA", "Panama", "mx"),
    ("PY", "Paraguay", "mx"),
    ("PE", "Peru", "mx"),
    ("PH", "Philippines", "sg"),
    ("PL", "Poland", "eu"),
    ("PT", "Portugal", "eu"),
    ("QA", "Qatar", "no"),
    ("RE", "Reunion Island", "no"),
    ("RO", "Romania", "eu"),
    ("SA", "Saudi Arabia", "sa"),
    ("RS", "Serbia", "eu"),
    ("SG", "Singapore", "sg"),
    ("SK", "Slovakia", "eu"),
    ("SI", "Slovenia", "eu"),
    ("ZA", "South Africa", "no"),
    ("KR", "South Korea", "kr"),
    ("ES", "Spain", "eu"),
    ("LK", "Sri Lanka", "sg"),
    ("SE", "Sweden", "eu"),
    ("CH", "Switzerland", "eu"),
    ("TH", "Thailand", "sg"),
    ("TR", "Turkey", "tr"),
    ("UA", "Ukraine", "eu"),
    ("AE", "United Arab Emirates", "no"),
    ("GB", "United Kingdom", "eu"),
    ("UY", "Uruguay", "mx"),
    ("UZ", "Uzbekistan", "uz"),
    ("VA", "Vatican City", "eu"),
    ("VN", "Vietnam", "vn"),
)

# Derived lookups.
COUNTRY_TO_BASE_URL: dict[str, str] = {
    code: NODE_BASE_URLS[node] for code, _name, node in COUNTRIES
}
COUNTRY_NAMES: dict[str, str] = {code: name for code, name, _node in COUNTRIES}


def base_url_for_country(country_code: str | None) -> str:
    """Return the BYD API base URL for an ISO country code.

    Falls back to :data:`DEFAULT_BASE_URL` for an unknown/empty code.
    """
    if country_code:
        url = COUNTRY_TO_BASE_URL.get(country_code.upper())
        if url:
            return url
    return DEFAULT_BASE_URL

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
