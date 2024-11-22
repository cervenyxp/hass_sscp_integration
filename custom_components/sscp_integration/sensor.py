import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Mapování jednotek na device_class
UNIT_DEVICE_CLASS_MAP = {
    "°C": "temperature",
    "°F": "temperature",
    "Pa": "pressure",
    "kPa": "pressure",
    "bar": "pressure",
    "m": "distance",
    "cm": "distance",
    "mm": "distance",
    "V": "voltage",
    "mV": "voltage",
    "A": "current",
    "mA": "current",
    "Hz": "frequency",
    "W": "power",
    "kW": "power",
    "kWh": "energy",
    "%": "humidity",
}

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

class SSCPVariableSensor(CoordinatorEntity, SensorEntity):
    """Reprezentace SSCP senzoru."""

    def __init__(self, client, config, entry_id):
        """Inicializace senzoru."""
        super().__init__(client)
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 1)
        self._type = config["type"]
        self._name = config["name"]
        self._unit_of_measurement = config.get("unit_of_measurement", None)
        self._device_class = config.get("device_class", UNIT_DEVICE_CLASS_MAP.get(self._unit_of_measurement))
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
    def unit_of_measurement(self):
        """Vrátí jednotku měření."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Vrátí typ senzoru podle jednotky měření."""
        return self._device_class

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
        except Exception as e:
            _LOGGER.error("Failed to update sensor %s: %s", self._name, e)