import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, UnitOfPressure, UnitOfLength, UnitOfVoltage, UnitOfEnergy, UnitOfPower
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Mapování jednotek na device_class a state_class
UNIT_DEVICE_CLASS_MAP = {
    "°C": SensorDeviceClass.TEMPERATURE,
    "°F": SensorDeviceClass.TEMPERATURE,
    "Pa": SensorDeviceClass.PRESSURE,
    "kPa": SensorDeviceClass.PRESSURE,
    "bar": SensorDeviceClass.PRESSURE,
    "m": SensorDeviceClass.DISTANCE,
    "cm": SensorDeviceClass.DISTANCE,
    "mm": SensorDeviceClass.DISTANCE,
    "V": SensorDeviceClass.VOLTAGE,
    "mV": SensorDeviceClass.VOLTAGE,
    "A": SensorDeviceClass.CURRENT,
    "mA": SensorDeviceClass.CURRENT,
    "Hz": SensorDeviceClass.FREQUENCY,
    "W": SensorDeviceClass.POWER,
    "kW": SensorDeviceClass.POWER,
    "kWh": SensorDeviceClass.ENERGY,
    "%": SensorDeviceClass.HUMIDITY,
}

UNIT_STATE_CLASS_MAP = {
    "°C": SensorStateClass.MEASUREMENT,
    "°F": SensorStateClass.MEASUREMENT,
    "Pa": SensorStateClass.MEASUREMENT,
    "kPa": SensorStateClass.MEASUREMENT,
    "bar": SensorStateClass.MEASUREMENT,
    "m": SensorStateClass.MEASUREMENT,
    "cm": SensorStateClass.MEASUREMENT,
    "mm": SensorStateClass.MEASUREMENT,
    "V": SensorStateClass.MEASUREMENT,
    "mV": SensorStateClass.MEASUREMENT,
    "A": SensorStateClass.MEASUREMENT,
    "mA": SensorStateClass.MEASUREMENT,
    "Hz": SensorStateClass.MEASUREMENT,
    "W": SensorStateClass.MEASUREMENT,
    "kW": SensorStateClass.MEASUREMENT,
    "kWh": SensorStateClass.MEASUREMENT,
    "%": SensorStateClass.MEASUREMENT,
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

class SSCPVariableSensor(SensorEntity):
    """Reprezentace SSCP senzoru."""

    def __init__(self, client, config, entry_id):
        """Inicializace senzoru."""
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 1)
        self._type = config["type"]
        self._entry_id = entry_id

        # Atributy nastavené dynamicky podle konfigurace
        self._attr_name = config["name"]
        self._attr_native_unit_of_measurement = config.get("unit_of_measurement")
        self._attr_device_class = UNIT_DEVICE_CLASS_MAP.get(self._attr_native_unit_of_measurement)
        self._attr_state_class = UNIT_STATE_CLASS_MAP.get(self._attr_native_unit_of_measurement, SensorStateClass.MEASUREMENT)
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}"
        self._state = None

    @property
    def native_value(self):
        """Vrátí aktuální hodnotu senzoru."""
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
        _LOGGER.debug("Updating sensor %s (UID: %s, Offset: %d, Length: %d)", self._attr_name, self._uid, self._offset, self._length)
        try:
            value = self._client.read_variable(self._uid, self._offset, self._length, self._type)
            self._state = value
            _LOGGER.info("Updated sensor %s with value: %s", self._attr_name, value)
        except Exception as e:
            _LOGGER.error("Failed to update sensor %s: %s", self._attr_name, e)
            self._state = None
