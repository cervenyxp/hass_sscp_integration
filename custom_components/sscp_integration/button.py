import logging
from homeassistant.components.button import ButtonEntity
from . import DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from datetime import timedelta

SCAN_INTERVAL = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Nastavení tlačítek pro SSCP Integration."""
    _LOGGER.info("Setting up button entities for SSCP Integration")

    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    # Ujisti se, že seznam entit existuje
    if "entities" not in hass.data[DOMAIN][config_entry.entry_id]:
        hass.data[DOMAIN][config_entry.entry_id]["entities"] = []
    variables = config_entry.data.get("variables", [])

    buttons = [
        SSCPButton(client, variable, config_entry.entry_id, hass)
        for variable in variables
        if variable.get("entity_type") == "button"
    ]
    for ent in buttons:
        hass.data[DOMAIN][config_entry.entry_id]["entities"].append(ent)

    if buttons:
        async_add_entities(buttons, update_before_add=True)


async def async_unload_entry(hass, entry):
    registry = er.async_get(hass)
    er.async_clear_config_entry(registry, entry.entry_id)
    # await async_unload_platforms(...)
    return True

class SSCPButton(ButtonEntity):
    """Tlačítková entita pro SSCP Integration."""
    should_poll = True

    def __init__(self, client, config, entry_id,hass):
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 1)
        self._type = config.get("type", "BOOL")
        self._name = config["name"]
        self._entry_id = entry_id
        self.hass = hass

        self._attr_name = self._name
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}_button"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"PLC {self._entry_id}",
            "manufacturer": "SSCP",
            "model": "PLC Button",
        }

    async def async_press(self) -> None:
        """Obsluha stisknutí tlačítka - zapíše 1 do BOOL proměnné a následně 0."""
        try:
            _LOGGER.debug("Button %s pressed, writing TRUE then FALSE", self._name)
            self._client.write_variable(
                self._uid, 1, offset=self._offset, length=self._length, type_data=self._type
            )
            self._client.write_variable(
                self._uid, 0, offset=self._offset, length=self._length, type_data=self._type
            )
            # Refresh všech ostatních entit této integrace
            for ent in self.hass.data[DOMAIN][self._entry_id]["entities"]:
               if ent is not self:
                   ent.async_schedule_update_ha_state(force_refresh=True)
        except Exception as e:
            _LOGGER.error("Failed to press button %s: %s", self._name, e)
