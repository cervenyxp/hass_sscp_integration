from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_STATIC_PATH


async def async_setup_frontend(hass: HomeAssistant, entry: ConfigEntry) -> None:
    if hass.data.setdefault(f"{DOMAIN}_frontend_registered", False):
        return

    static_dir = Path(__file__).parent / "static"
    panel_js_url = f"{FRONTEND_STATIC_PATH}/panel.js?v={int((static_dir / 'panel.js').stat().st_mtime)}"

    try:
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [StaticPathConfig(FRONTEND_STATIC_PATH, str(static_dir), cache_headers=False)]
        )
    except ImportError:
        hass.http.register_static_path(FRONTEND_STATIC_PATH, str(static_dir), False)

    if DOMAIN not in hass.data.get("frontend_panels", {}):
        async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="SSCP Studio",
            sidebar_icon="mdi:transmission-tower",
            frontend_url_path=DOMAIN,
            config={
                "_panel_custom": {
                    "name": "sscp-integration-panel",
                    "embed_iframe": False,
                    "trust_external": False,
                    "js_url": panel_js_url,
                }
            },
            require_admin=True,
        )

    hass.data[f"{DOMAIN}_frontend_registered"] = True
