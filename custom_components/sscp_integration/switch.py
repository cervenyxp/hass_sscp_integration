import logging
from homeassistant.components.switch import SwitchEntity
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Nastavení přepínačů pro SSCP Integration."""
    _LOGGER.info("Setting up switches for SSCP Integration")

    client = hass.data[DOMAIN][config_entry.entry_id]
    variables = config_entry.data.get("variables", [])

    switches = [
        SSCPWritableSwitch(client, variable, config_entry.entry_id)
        for variable in variables
        if variable.get("entity_type") == "switch"
    ]

    if switches:
        async_add_entities(switches, update_before_add=True)

class SSCPWritableSwitch(SwitchEntity):
    """Zapisovatelný přepínač pro SSCP."""

    def __init__(self, client, config, entry_id):
        """Inicializace přepínače."""
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 1)
        self._type = config["type"]
        self._name = config["name"]
        self._state = None
        self._entry_id = entry_id

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
        except Exception as e:
            _LOGGER.error("Failed to turn on switch %s: %s", self._name, e)

    async def async_turn_off(self, **kwargs):
        """Vypne přepínač."""
        try:
            self._client.write_variable(self._uid, 0, offset=self._offset, length=self._length, type_data="BOOL")
            self._state = False
            self.async_write_ha_state()
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
