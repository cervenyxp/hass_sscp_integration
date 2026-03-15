from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN
from .entity import SSCPBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    variables = config_entry.data.get("variables", [])

    switches = [
        SSCPWritableSwitch(coordinator, client, variable, config_entry.entry_id, hass)
        for variable in variables
        if variable.get("entity_type") == "switch"
    ]
    if switches:
        async_add_entities(switches)


class SSCPWritableSwitch(SSCPBaseEntity, SwitchEntity):
    def __init__(self, coordinator, client, config, entry_id, hass):
        super().__init__(coordinator, client, config, entry_id, hass)
        self._attr_name = config["name"]
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}"

    @property
    def is_on(self):
        value = self.current_value
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs):
        try:
            await self.async_write_sscp_value(True)
        except Exception as err:
            _LOGGER.error("Failed to turn on switch %s: %s", self.name, err)

    async def async_turn_off(self, **kwargs):
        try:
            await self.async_write_sscp_value(False)
        except Exception as err:
            _LOGGER.error("Failed to turn off switch %s: %s", self.name, err)
