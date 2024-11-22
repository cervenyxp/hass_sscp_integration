import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import ConfigEntryNotReady
from .sscp_client import SSCPClient
from .const import DOMAIN

DOMAIN = "sscp_integration"
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Nastavení integrace na základě konfigurace."""
    _LOGGER.info("Setting up SSCP Integration for %s", entry.data["host"])

    # Inicializace SSCP klienta
    client = SSCPClient(
        entry.data["host"],
        entry.data["port"],
        entry.data["username"],
        entry.data["password"],
        entry.data["sscp_address"],
        entry.data["PLC_Name"]
    )
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = client

    # Připojení a přihlášení k SSCP serveru
    try:
        client.connect()
        client.login()
        _LOGGER.info("Connected and logged in to SSCP server.")
    except Exception as e:
        _LOGGER.error("Failed to connect/login to SSCP server: %s", e)
        raise ConfigEntryNotReady from e

    # Předání konfigurace pro všechny entity
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "number", "switch", "binary_sensor"])

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Odpojení a vyčištění při odstraňování integrace."""
    _LOGGER.info("Unloading SSCP Integration for %s", entry.data["host"])

    client = hass.data[DOMAIN].pop(entry.entry_id, None)
    if client:
        try:
            client.disconnect()
            _LOGGER.info("Disconnected from SSCP server.")
        except Exception as e:
            _LOGGER.warning("Error during SSCP client disconnect: %s", e)

    # Vyčistěte všechny typy entit
    await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    await hass.config_entries.async_forward_entry_unload(entry, "number")
    await hass.config_entries.async_forward_entry_unload(entry, "switch")
    await hass.config_entries.async_forward_entry_unload(entry, "binary_sensor")

    return True

async def async_reload_entry(hass, config_entry):
    """Znovu načte konfiguraci PLC."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
