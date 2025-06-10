
import logging
from homeassistant.components.light import LightEntity, ColorMode
from . import DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from datetime import timedelta

SCAN_INTERVAL = timedelta(seconds=5)


_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Nastavení světel pro SSCP Integration."""
    _LOGGER.info("Setting up light entities for SSCP Integration")

    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    # POKUD entities pole ještě neexistuje, založ ho!
    if "entities" not in hass.data[DOMAIN][config_entry.entry_id]:
        hass.data[DOMAIN][config_entry.entry_id]["entities"] = []
    variables = config_entry.data.get("variables", [])

    lights = [
        SSCPLight(client, variable, config_entry.entry_id, hass)
        for variable in variables
        if variable.get("entity_type") == "light"
    ]
    for ent in lights:
        hass.data[DOMAIN][config_entry.entry_id]["entities"].append(ent)

    if lights:
        async_add_entities(lights, update_before_add=True)

async def async_unload_entry(hass, entry):
    registry = er.async_get(hass)
    er.async_clear_config_entry(registry, entry.entry_id)
    # await async_unload_platforms(...)
    return True


class SSCPLight(LightEntity):
    """Světelná entita pro SSCP Integration."""
    should_poll = True
    
    def __init__(self, client, config, entry_id,hass):
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 1)
        self._type = config.get("type", "BOOL")
        self._name = config["name"]
        self._entry_id = entry_id
        self._state = False

        self._attr_name = self._name
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}_light"
        self._attr_supported_color_modes = [ColorMode.ONOFF]
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_is_on = self._state
        self.hass = hass

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"PLC {self._entry_id}",
            "manufacturer": "SSCP",
            "model": "PLC Light",
        }

    async def async_turn_on(self, **kwargs):
        try:
            self._client.write_variable(self._uid, 1, offset=self._offset, length=self._length, type_data=self._type)
            self._state = True
            self._attr_is_on = True
            self.async_write_ha_state()
            for ent in self.hass.data[DOMAIN][self._entry_id]["entities"]:
                if ent is not self:
                    ent.async_schedule_update_ha_state(force_refresh=True)
        except Exception as e:
            _LOGGER.error("Failed to turn on light %s: %s", self._name, e)

    async def async_turn_off(self, **kwargs):
        try:
            self._client.write_variable(self._uid, 0, offset=self._offset, length=self._length, type_data=self._type)
            self._state = False
            self._attr_is_on = False
            self.async_write_ha_state()
            for ent in self.hass.data[DOMAIN][self._entry_id]["entities"]:
                if ent is not self:
                    ent.async_schedule_update_ha_state(force_refresh=True)
        except Exception as e:
            _LOGGER.error("Failed to turn off light %s: %s", self._name, e)

    async def async_update(self):
        try:
            value = self._client.read_variable(self._uid, self._offset, self._length, self._type)
            self._state = bool(value)
            self._attr_is_on = self._state
        except Exception as e:
            _LOGGER.error("Failed to update light %s: %s", self._name, e)
            self._state = False
            self._attr_is_on = False