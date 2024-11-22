import logging
from homeassistant.helpers.entity import Entity
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Nastavení senzorů pro SSCP Integration."""
    _LOGGER.info("Setting up sensors for SSCP Integration")

    client = hass.data[DOMAIN][config_entry.entry_id]
    variables = config_entry.data.get("variables", [])

    sensors = [
        SSCPVariableSensor(client, variable, config_entry.entry_id)
        for variable in variables
        if variable.get("entity_type") == "sensor"
    ]

    if sensors:
        async_add_entities(sensors, update_before_add=True)

class SSCPVariableSensor(Entity):
    """Reprezentace SSCP senzoru."""

    def __init__(self, client, config, entry_id):
        """Inicializace senzoru."""
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 1)
        self._type = config["type"]
        self._name = config["name"]
        self._unit = config.get("unit_of_measurement", None)  # Přidáno: jednotka měření
        self._state = None
        self._entry_id = entry_id

    @property
    def name(self):
        """Vrátí název senzoru."""
        return self._name

    @property
    def unique_id(self):
        """Vrátí jedinečné ID senzoru."""
        return f"{self._entry_id}_{self._uid}_{self._offset}"

    @property
    def state(self):
        """Vrátí aktuální stav senzoru."""
        return self._state

    @property
    def device_info(self):
        """Vrátí informace o zařízení."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"PLC {self._entry_id}",
            "manufacturer": "SSCP",
            "model": "PLC Sensor",
        }

    async def async_update(self):
        """Aktualizuje stav senzoru."""
        _LOGGER.debug("Updating sensor %s (UID: %s, Offset: %d, Length: %d)", self._name, self._uid, self._offset, self._length)
        try:
            value = self._client.read_variable(self._uid, self._offset, self._length, self._type)
            self._state = value
            _LOGGER.info("Updated sensor %s with value: %s", self._name, value)
        except Exception as e:
            _LOGGER.error("Failed to update sensor %s: %s", self._name, e)
            self._state = None
