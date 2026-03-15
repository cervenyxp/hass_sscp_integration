from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity

from .const import DOMAIN
from .entity import SSCPBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    variables = config_entry.data.get("variables", [])

    selects = [
        SSCPSelectEntity(coordinator, client, variable, config_entry.entry_id, hass)
        for variable in variables
        if variable.get("entity_type") == "select"
    ]
    if selects:
        async_add_entities(selects)


class SSCPSelectEntity(SSCPBaseEntity, SelectEntity):
    def __init__(self, coordinator, client, config, entry_id, hass):
        super().__init__(coordinator, client, config, entry_id, hass)
        self._attr_name = config["name"]
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}_select"
        self._value_map = config.get("select_options", {})
        self._reverse_map = {label: key for key, label in self._value_map.items()}
        self._attr_options = list(self._value_map.values())

    @property
    def current_option(self):
        value = self.current_value
        if value is None:
            return None
        key = str(int(value)) if isinstance(value, (bool, int)) else str(value)
        return self._value_map.get(key)

    async def async_select_option(self, option):
        raw_value = self._reverse_map.get(option)
        if raw_value is None:
            _LOGGER.error("Option '%s' not valid for select %s", option, self.name)
            return

        try:
            if self._type.upper() == "BOOL":
                converted_value = bool(int(raw_value))
            elif self._type.upper() in {"BYTE", "WORD", "UINT", "DINT", "UDINT", "LINT", "INT"}:
                converted_value = int(raw_value)
            elif self._type.upper() in {"REAL", "LREAL"}:
                converted_value = float(raw_value)
            else:
                converted_value = raw_value

            await self.async_write_sscp_value(converted_value)
        except Exception as err:
            _LOGGER.error("Failed to set option %s for select %s: %s", option, self.name, err)
