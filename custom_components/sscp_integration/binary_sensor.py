import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Nastavení binárních senzorů pro SSCP Integration."""
    _LOGGER.info("Setting up binary sensors for SSCP Integration")

    client = hass.data[DOMAIN][config_entry.entry_id]
    variables = config_entry.data.get("variables", [])

    binary_sensors = [
        SSCPBinarySensor(client, variable, config_entry.entry_id)
        for variable in variables
        if variable.get("entity_type") == "binary_sensor"
    ]

    if binary_sensors:
        async_add_entities(binary_sensors, update_before_add=True)

class SSCPBinarySensor(BinarySensorEntity):
    """Binární senzor pro SSCP."""

    def __init__(self, client, config, entry_id):
        """Inicializace binárního senzoru."""
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
        """Vrátí název senzoru."""
        return self._name

    @property
    def is_on(self):
        """Vrátí stav senzoru."""
        return self._state

    @property
    def unique_id(self):
        """Vrátí jedinečné ID senzoru."""
        return f"{self._entry_id}_{self._uid}_{self._offset}"

    @property
    def device_info(self):
        """Vrátí informace o zařízení."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"PLC {self._entry_id}",
            "manufacturer": "SSCP",
            "model": "PLC Binary Sensor",
        }

    async def async_update(self):
        """Aktualizuje stav senzoru."""
        try:
            value = self._client.read_variable(self._uid, self._offset, self._length, "BOOL")
            self._state = bool(value)
        except Exception as e:
            _LOGGER.error("Failed to update binary sensor %s: %s", self._name, e)
            self._state = None
