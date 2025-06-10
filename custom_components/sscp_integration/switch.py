import logging
from homeassistant.components.switch import SwitchEntity
from . import DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from datetime import timedelta

SCAN_INTERVAL = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Nastavení switch entities pro SSCP Integration."""
    _LOGGER.info("Setting up switch entities for SSCP Integration")

    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    # Zajisti seznam entit
    if "entities" not in hass.data[DOMAIN][config_entry.entry_id]:
        hass.data[DOMAIN][config_entry.entry_id]["entities"] = []
    variables = config_entry.data.get("variables", [])

    switches = [
        SSCPWritableSwitch(client, variable, config_entry.entry_id, hass)
        for variable in variables
        if variable.get("entity_type") == "switch"
    ]
    for ent in switches:
        hass.data[DOMAIN][config_entry.entry_id]["entities"].append(ent)

    if switches:
        async_add_entities(switches, update_before_add=True)

async def async_unload_entry(hass, entry):
    registry = er.async_get(hass)
    er.async_clear_config_entry(registry, entry.entry_id)
    # await async_unload_platforms(...)
    return True


class SSCPWritableSwitch(SwitchEntity):
    """Zapisovatelný přepínač pro SSCP."""
    should_poll = True

    def __init__(self, client, config, entry_id,hass):
        """Inicializace přepínače."""
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 1)
        self._type = config["type"]
        self._name = config["name"]
        self._state = None
        self._entry_id = entry_id
        self.hass = hass

    @property
    def name(self):
        """Vrátí název přepínače."""
        return self._name

    @property
    def is_on(self):
        """Vrátí stav přepínače."""
        return self._state

    @property
    def unique_id(self):
        """Vrátí jedinečné ID přepínače."""
        return f"{self._entry_id}_{self._uid}_{self._offset}"

    @property
    def device_info(self):
        """Vrátí informace o zařízení."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"PLC {self._entry_id}",
            "manufacturer": "SSCP",
            "model": "PLC Switch",
        }

    async def async_turn_on(self, **kwargs):
        """Zapne přepínač."""
        try:
            self._client.write_variable(self._uid, 1, offset=self._offset, length=self._length, type_data="BOOL")
            self._state = True
            self.async_write_ha_state()
            for ent in self.hass.data[DOMAIN][self._entry_id]["entities"]:
                if ent is not self:
                    ent.async_schedule_update_ha_state(force_refresh=True)
        except Exception as e:
            _LOGGER.error("Failed to turn on switch %s: %s", self._name, e)

    async def async_turn_off(self, **kwargs):
        """Vypne přepínač."""
        try:
            self._client.write_variable(self._uid, 0, offset=self._offset, length=self._length, type_data="BOOL")
            self._state = False
            self.async_write_ha_state()
            for ent in self.hass.data[DOMAIN][self._entry_id]["entities"]:
                if ent is not self:
                    ent.async_schedule_update_ha_state(force_refresh=True)
        except Exception as e:
            _LOGGER.error("Failed to turn off switch %s: %s", self._name, e)

    async def async_update(self):
        """Aktualizuje stav přepínače."""
        try:
            value = self._client.read_variable(self._uid, self._offset, self._length, "BOOL")
            self._state = bool(value)
        except Exception as e:
            _LOGGER.error("Failed to update switch %s: %s", self._name, e)
            self._state = None
