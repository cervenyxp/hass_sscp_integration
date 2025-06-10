import logging
from datetime import datetime
from homeassistant.components.datetime import DateTimeEntity
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Nastavení datetime entit pro SSCP Integration."""
    _LOGGER.info("Setting up datetime entities for SSCP Integration")

    client = hass.data[DOMAIN][config_entry.entry_id]
    variables = config_entry.data.get("variables", [])

    datetime_entities = [
        SSCPDateTimeEntity(client, variable, config_entry.entry_id)
        for variable in variables
        if variable.get("entity_type") == "datetime"
    ]

    if datetime_entities:
        async_add_entities(datetime_entities, update_before_add=True)

class SSCPDateTimeEntity(DateTimeEntity):
    """Datetime entita pro SSCP Integration."""

    def __init__(self, client, config, entry_id):
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 6)  # očekáváme DATETIME jako 6 bytů (např. UNIX timestamp nebo struktura)
        self._type = config.get("type", "UDINT")
        self._name = config["name"]
        self._entry_id = entry_id

        self._attr_name = self._name
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}_datetime"
        self._state = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"PLC {self._entry_id}",
            "manufacturer": "SSCP",
            "model": "PLC DateTime",
        }

    @property
    def native_value(self):
        return self._state

    async def async_update(self):
        try:
            raw = self._client.read_variable(self._uid, self._offset, self._length, self._type)
            if isinstance(raw, int):
                self._state = datetime.fromtimestamp(raw)
            elif isinstance(raw, float):
                self._state = datetime.fromtimestamp(int(raw))
            else:
                self._state = None
        except Exception as e:
            _LOGGER.error("Failed to update datetime entity %s: %s", self._name, e)
            self._state = None

    async def async_set_value(self, value: datetime) -> None:
        try:
            ts = int(value.timestamp())
            self._client.write_variable(self._uid, ts, offset=self._offset, length=self._length, type_data=self._type)
            self._state = value
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error("Failed to set datetime for %s: %s", self._name, e)
