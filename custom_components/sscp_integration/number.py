from __future__ import annotations

import logging

try:
    from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
except ImportError:  # pragma: no cover - fallback for older HA builds
    from homeassistant.components.number import NumberEntity, NumberMode

    NumberDeviceClass = None

from .const import DOMAIN
from .entity import SSCPBaseEntity
from .vlist import normalize_unit_of_measurement

_LOGGER = logging.getLogger(__name__)

NUMBER_DEVICE_CLASS_BY_VALUE = (
    {member.value: member for member in NumberDeviceClass}
    if NumberDeviceClass is not None
    else {}
)


def _coerce_number_device_class(value: str | None):
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    return NUMBER_DEVICE_CLASS_BY_VALUE.get(normalized, normalized)


async def async_setup_entry(hass, config_entry, async_add_entities):
    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    variables = config_entry.data.get("variables", [])

    numbers = [
        SSCPNumber(coordinator, client, variable, config_entry.entry_id, hass)
        for variable in variables
        if variable.get("entity_type") == "number"
    ]
    if numbers:
        async_add_entities(numbers)


class SSCPNumber(SSCPBaseEntity, NumberEntity):
    def __init__(self, coordinator, client, config, entry_id, hass):
        super().__init__(coordinator, client, config, entry_id, hass)
        suggested_display_precision = config.get("suggested_display_precision")
        self._attr_name = config["name"]
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}_number"
        self._attr_native_unit_of_measurement = normalize_unit_of_measurement(config.get("unit_of_measurement")) or None
        self._attr_device_class = _coerce_number_device_class(config.get("device_class"))
        self._attr_suggested_display_precision = (
            int(suggested_display_precision) if suggested_display_precision is not None else None
        )
        self._min_value = config.get("min_value", float("-65535"))
        self._max_value = config.get("max_value", float("65535"))
        self._step = config.get("step", 1)
        self._mode = config.get("mode", "box")

    @property
    def native_min_value(self):
        return self._min_value

    @property
    def native_max_value(self):
        return self._max_value

    @property
    def native_step(self):
        return self._step

    @property
    def native_value(self):
        return self.current_value

    @property
    def mode(self):
        return NumberMode.SLIDER if self._mode == "slider" else NumberMode.BOX

    async def async_set_native_value(self, value):
        try:
            await self.async_write_sscp_value(value)
        except Exception as err:
            _LOGGER.error("Failed to set value %s for number %s: %s", value, self.name, err)
