from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.components.fan import (
    DIRECTION_FORWARD,
    DIRECTION_REVERSE,
    FanEntity,
    FanEntityFeature,
)

from .const import DOMAIN
from .coordinator import SSCPDataCoordinator, variable_key
from .entity import async_apply_entity_area, build_plc_device_info

_LOGGER = logging.getLogger(__name__)


def _coerce_write_value(raw_value: Any, plc_type: str) -> Any:
    normalized_type = str(plc_type or "BYTE").upper()
    if normalized_type == "BOOL":
        if isinstance(raw_value, str):
            return raw_value.strip().lower() in {"1", "true", "on", "yes"}
        return bool(raw_value)
    if normalized_type in {"BYTE", "WORD", "INT", "UINT", "DINT", "UDINT", "LINT"}:
        return int(raw_value)
    if normalized_type in {"REAL", "LREAL"}:
        return float(raw_value)
    return raw_value


def _value_key(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        integer_value = int(value)
        if float(integer_value) == value:
            return str(integer_value)
    return str(value)


async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    client = entry_data["client"]
    coordinator: SSCPDataCoordinator | None = entry_data.get("coordinator")
    fans = config_entry.data.get("fan_entities", [])

    entities = [
        SSCPComposedFan(
            coordinator,
            client,
            fan_config,
            config_entry.entry_id,
            config_entry.data.get("PLC_Name", "PLC"),
            hass,
        )
        for fan_config in fans
    ]
    if entities:
        async_add_entities(entities)


class SSCPComposedFan(FanEntity):
    should_poll = False

    def __init__(
        self,
        coordinator: SSCPDataCoordinator,
        client,
        config: dict[str, Any],
        entry_id: str,
        plc_name: str,
        hass,
    ) -> None:
        self.coordinator = coordinator
        self._client = client
        self._config = config
        self._entry_id = entry_id
        self._plc_name = plc_name
        self.hass = hass
        self._refs = {
            "power_var": config.get("power_var"),
            "percentage_var": config.get("percentage_var"),
            "preset_var": config.get("preset_var"),
            "oscillate_var": config.get("oscillate_var"),
            "direction_var": config.get("direction_var"),
        }
        self._preset_map = {
            str(key): str(value).strip()
            for key, value in (config.get("preset_map") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._preset_reverse_map = {label: raw for raw, label in self._preset_map.items()}
        self._direction_map = {
            str(key): str(value).strip().lower()
            for key, value in (config.get("direction_map") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._direction_reverse_map = {label: raw for raw, label in self._direction_map.items()}
        self._percentage_step = max(1, int(config.get("percentage_step") or 1))
        self._attr_name = str(config.get("name") or "Fan")
        self._attr_unique_id = f"{entry_id}_fan_{config.get('entity_key')}"
        self._attr_has_entity_name = False

    @property
    def device_info(self):
        return build_plc_device_info(
            self._entry_id,
            self._plc_name,
            getattr(self._client, "transport_name", "sscp"),
        )

    async def async_added_to_hass(self) -> None:
        if hasattr(self.coordinator, "async_add_listener"):
            self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))
        await async_apply_entity_area(self.hass, getattr(self, "entity_id", None), self._config.get("area_id"))

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success if self.coordinator else False

    def _coordinator_value(self, ref: dict[str, Any] | None) -> Any:
        if not isinstance(ref, dict):
            return None
        return self.coordinator.data.get(variable_key(ref))

    async def _async_write_ref(self, ref: dict[str, Any] | None, raw_value: Any) -> None:
        if not isinstance(ref, dict):
            raise ValueError("Chybi datovy bod pro zapis.")
        await self.hass.async_add_executor_job(
            partial(
                self._client.write_variable,
                int(ref["uid"]),
                _coerce_write_value(raw_value, str(ref["type"])),
                offset=int(ref.get("offset", 0)),
                length=int(ref.get("length", 1)),
                type_data=str(ref["type"]),
            )
        )

    @property
    def supported_features(self) -> FanEntityFeature:
        features = FanEntityFeature(0)
        if self._refs.get("power_var"):
            features |= FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        if self._refs.get("percentage_var"):
            features |= FanEntityFeature.SET_SPEED
        if self._refs.get("preset_var") and self._preset_map:
            features |= FanEntityFeature.PRESET_MODE
        if self._refs.get("oscillate_var"):
            features |= FanEntityFeature.OSCILLATE
        if self._refs.get("direction_var") and self._direction_map:
            features |= FanEntityFeature.DIRECTION
        return features

    @property
    def is_on(self) -> bool | None:
        power_value = self._coordinator_value(self._refs.get("power_var"))
        if power_value is not None:
            return bool(power_value)
        percentage = self.percentage
        if percentage is not None:
            return percentage > 0
        return None

    @property
    def percentage(self) -> int | None:
        value = self._coordinator_value(self._refs.get("percentage_var"))
        if value is None:
            return None
        return max(0, min(100, int(round(float(value)))))

    @property
    def percentage_step(self) -> float:
        return float(self._percentage_step)

    @property
    def preset_modes(self) -> list[str] | None:
        if not self._preset_map:
            return None
        return list(dict.fromkeys(self._preset_map.values()))

    @property
    def preset_mode(self) -> str | None:
        value = self._coordinator_value(self._refs.get("preset_var"))
        if value is None:
            return None
        return self._preset_map.get(_value_key(value))

    @property
    def oscillating(self) -> bool | None:
        value = self._coordinator_value(self._refs.get("oscillate_var"))
        if value is None:
            return None
        return bool(value)

    @property
    def current_direction(self) -> str | None:
        value = self._coordinator_value(self._refs.get("direction_var"))
        if value is None:
            return None
        mapped = self._direction_map.get(_value_key(value))
        if mapped == "forward":
            return DIRECTION_FORWARD
        if mapped == "reverse":
            return DIRECTION_REVERSE
        return None

    async def async_turn_on(self, percentage: int | None = None, preset_mode: str | None = None, **kwargs) -> None:
        try:
            if self._refs.get("power_var"):
                await self._async_write_ref(self._refs.get("power_var"), True)
            elif self._refs.get("percentage_var"):
                await self._async_write_ref(self._refs.get("percentage_var"), percentage if percentage is not None else 100)
            if percentage is not None and self._refs.get("percentage_var"):
                await self._async_write_ref(self._refs.get("percentage_var"), percentage)
            if preset_mode is not None and self._refs.get("preset_var"):
                raw_value = self._preset_reverse_map.get(str(preset_mode))
                if raw_value is None:
                    raise ValueError(f"Preset mode {preset_mode} neni v mapovani definovan.")
                await self._async_write_ref(self._refs.get("preset_var"), raw_value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on fan %s: %s", self.name, err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            if self._refs.get("power_var"):
                await self._async_write_ref(self._refs.get("power_var"), False)
            elif self._refs.get("percentage_var"):
                await self._async_write_ref(self._refs.get("percentage_var"), 0)
            else:
                raise ValueError("Fan nema definovan power ani percentage point pro vypnuti.")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off fan %s: %s", self.name, err)

    async def async_set_percentage(self, percentage: int) -> None:
        try:
            await self._async_write_ref(self._refs.get("percentage_var"), max(0, min(100, int(percentage))))
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set percentage for fan %s: %s", self.name, err)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        try:
            raw_value = self._preset_reverse_map.get(str(preset_mode))
            if raw_value is None:
                raise ValueError(f"Preset mode {preset_mode} neni v mapovani definovan.")
            await self._async_write_ref(self._refs.get("preset_var"), raw_value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set preset mode for fan %s: %s", self.name, err)

    async def async_oscillate(self, oscillating: bool) -> None:
        try:
            await self._async_write_ref(self._refs.get("oscillate_var"), bool(oscillating))
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set oscillation for fan %s: %s", self.name, err)

    async def async_set_direction(self, direction: str) -> None:
        try:
            normalized = str(direction).strip().lower()
            raw_value = self._direction_reverse_map.get(normalized)
            if raw_value is None:
                raise ValueError(f"Smer ventilatoru {direction} neni v mapovani definovan.")
            await self._async_write_ref(self._refs.get("direction_var"), raw_value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set direction for fan %s: %s", self.name, err)
