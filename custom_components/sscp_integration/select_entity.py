import logging
from homeassistant.components.select import SelectEntity
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Nastavení select entit pro SSCP Integration."""
    _LOGGER.info("Setting up select entities for SSCP Integration")

    client = hass.data[DOMAIN][config_entry.entry_id]
    variables = config_entry.data.get("variables", [])

    entities = [
        SSCPSelect(client, variable, config_entry.entry_id)
        for variable in variables
        if variable.get("entity_type") == "select"
    ]

    if entities:
        async_add_entities(entities, update_before_add=True)

class SSCPSelect(SelectEntity):
    """Select entita pro SSCP Integration."""

    def __init__(self, client, config, entry_id):
        """Inicializace select entity."""
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 1)
        self._type = config["type"]
        self._name = config["name"]
        self._options = config.get("options", {})
        self._state = None
        self._entry_id = entry_id

    @property
    def name(self):
        """Vrátí název entity."""
        return self._name

    @property
    def unique_id(self):
        """Vrátí jedinečné ID entity."""
        return f"{self._entry_id}_{self._uid}_{self._offset}_select"

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
    def options(self):
        """Vrátí seznam možných voleb."""
        return list(self._options.values())

    @property
    def current_option(self):
        """Vrátí aktuální vybranou volbu."""
        if self._state in self._options:
            return self._options[self._state]
        return None

    async def async_update(self):
        """Aktualizuje aktuální hodnotu."""
        try:
            value = self._client.read_variable(
                self._uid, self._offset, self._length, self._type
            )
            self._state = value
            _LOGGER.info("Updated select %s with value: %s", self._name, self._state)
        except Exception as e:
            _LOGGER.error("Failed to update select %s: %s", self._name, e)
            self._state = None

    async def async_select_option(self, option):
        """Nastaví vybranou volbu."""
        value = None
        for key, val in self._options.items():
            if val == option:
                value = key
                break

        if value is None:
            _LOGGER.error("Invalid option '%s' for select %s", option, self._name)
            return

        try:
            self._client.write_variable(
                self._uid,
                value=value,
                offset=self._offset,
                length=self._length,
                type_data=self._type,
            )
            self._state = value
            self.async_write_ha_state()
            _LOGGER.info("Set select %s to option: %s", self._name, option)
        except Exception as e:
            _LOGGER.error("Failed to set option %s for select %s: %s", option, self._name, e)
