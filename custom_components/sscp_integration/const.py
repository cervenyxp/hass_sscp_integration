from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "sscp_integration"
NAME: Final = "Mervis/Domat SSCP Integration"

PLATFORMS: Final = (
    "sensor",
    "number",
    "switch",
    "binary_sensor",
    "select",
    "button",
    "light",
    "cover",
    "climate",
    "fan",
    "humidifier",
    "water_heater",
    "lock",
    "valve",
    "siren",
    "datetime",
    "vacuum",
)

DEFAULT_PROTOCOL_VERSION: Final = 7
DEFAULT_CLIENT_MAX_DATA_SIZE: Final = 10240
DEFAULT_SCAN_INTERVAL_SECONDS: Final = 5
DEFAULT_SOCKET_TIMEOUT: Final = 10.0

DEFAULT_UPDATE_INTERVAL: Final = timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS)

CONF_PANEL_TITLE: Final = "panel_title"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_COMMUNICATION_MODE: Final = "communication_mode"
CONF_WEBPANEL_CONNECTION: Final = "webpanel_connection"
CONF_WEBPANEL_SCHEME: Final = "webpanel_scheme"

COMM_MODE_SSCP: Final = "sscp"
COMM_MODE_WEBPANEL: Final = "webpanel_api"
SUPPORTED_COMMUNICATION_MODES: Final = (
    COMM_MODE_SSCP,
    COMM_MODE_WEBPANEL,
)

ATTR_UPDATED_AT: Final = "updated_at"

FRONTEND_STATIC_PATH: Final = f"/{DOMAIN}_static"
FRONTEND_STATUS_PATH: Final = f"/api/{DOMAIN}/status"
FRONTEND_ACTION_PATH: Final = f"/api/{DOMAIN}/action"

SIGNAL_RUNTIME_STATE_UPDATED: Final = f"{DOMAIN}_runtime_state_updated"
