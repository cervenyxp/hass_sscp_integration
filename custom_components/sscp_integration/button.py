from __future__ import annotations

import asyncio
from functools import partial
import logging

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN
from .entity import SSCPBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    variables = config_entry.data.get("variables", [])

    buttons = [
        SSCPButton(coordinator, client, variable, config_entry.entry_id, hass)
        for variable in variables
        if variable.get("entity_type") == "button"
    ]
    if buttons:
        async_add_entities(buttons)


class SSCPButton(SSCPBaseEntity, ButtonEntity):
    def __init__(self, coordinator, client, config, entry_id, hass):
        super().__init__(coordinator, client, config, entry_id, hass)
        self._attr_name = config["name"]
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}_button"
        self._press_time = float(config.get("press_time", 0.1))

    async def async_press(self) -> None:
        try:
            await self.hass.async_add_executor_job(
                partial(
                    self._client.write_variable,
                    self._uid,
                    True,
                    offset=self._offset,
                    length=self._length,
                    type_data=self._type,
                )
            )
            await asyncio.sleep(max(0.01, self._press_time))
            await self.hass.async_add_executor_job(
                partial(
                    self._client.write_variable,
                    self._uid,
                    False,
                    offset=self._offset,
                    length=self._length,
                    type_data=self._type,
                )
            )
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to press button %s: %s", self.name, err)
