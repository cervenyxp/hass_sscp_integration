import logging
from homeassistant.components.number import NumberEntity, NumberMode
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Nastavení číselných entit pro SSCP Integration."""
    _LOGGER.info("Setting up number entities for SSCP Integration")

    client = hass.data[DOMAIN][config_entry.entry_id]
    variables = config_entry.data.get("variables", [])

    entities = [
        SSCPNumber(client, variable, config_entry.entry_id)
        for variable in variables
        if variable.get("entity_type") == "number"
    ]

    if entities:
        async_add_entities(entities, update_before_add=True)

class SSCPNumber(NumberEntity):
    """Číselná entita pro SSCP Integration."""

    def __init__(self, client, config, entry_id):
        """Inicializace číselné entity."""
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 1)
        self._type = config["type"]
        self._name = config["name"]
        self._state = None
        self._entry_id = entry_id

        # Výchozí hodnoty
        self._min_value = config.get("min_value", float("-inf"))
        self._max_value = config.get("max_value", float("inf"))
        self._step = config.get("step", 1)
        self._mode = config.get("mode", "box")  # Nastavení výchozího režimu jako "box"

    @property
    def name(self):
        """Vrátí název entity."""
        return self._name

    @property
    def unique_id(self):
        """Vrátí jedinečné ID entity."""
        return f"{self._entry_id}_{self._uid}_{self._offset}_number"

    @property
    def device_info(self):
        """Vrátí informace o zařízení."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"PLC {self._entry_id}",
            "manufacturer": "SSCP",
            "model": "PLC Device",
        }

    @property
    def native_min_value(self):
        """Vrátí minimální hodnotu."""
        return self._min_value

    @property
    def native_max_value(self):
        """Vrátí maximální hodnotu."""
        return self._max_value

    @property
    def native_step(self):
        """Vrátí krok mezi hodnotami."""
        return self._step

    @property
    def native_value(self):
        """Vrátí aktuální hodnotu."""
        return self._state

    @property
    def mode(self):
        """Vrátí režim ovládání hodnoty."""
        return NumberMode.BOX

    async def async_update(self):
        """Aktualizuje aktuální hodnotu."""
        try:
            self._state = self._client.read_variable(
                self._uid, self._offset, self._length, self._type
            )
            _LOGGER.info("Updated number %s with value: %s", self._name, self._state)
        except Exception as e:
            _LOGGER.error("Failed to update number %s: %s", self._name, e)
            self._state = None

    async def async_set_native_value(self, value):
        """Nastaví novou hodnotu."""
        try:
            # Správná konverze hodnoty na binární reprezentaci
            self._client.write_variable(
                self._uid,
                value=value,
                offset=self._offset,
                length=self._length,
                type_data=self._type,
            )
            self._state = value
            self.async_write_ha_state()
            _LOGGER.info("Set number %s to value: %s", self._name, value)
        except Exception as e:
            _LOGGER.error("Failed to set value %s for number %s: %s", value, self._name, e)


