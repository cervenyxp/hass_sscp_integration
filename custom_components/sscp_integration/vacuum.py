from __future__ import annotations

from functools import partial
import logging
from typing import Any

try:
    from homeassistant.components.vacuum import StateVacuumEntity, VacuumEntityFeature
except ImportError:  # pragma: no cover
    from homeassistant.components.vacuum import StateVacuumEntity
    from homeassistant.components.vacuum.const import VacuumEntityFeature

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


async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    client = entry_data["client"]
    coordinator: SSCPDataCoordinator | None = entry_data.get("coordinator")
    vacuums = config_entry.data.get("vacuum_entities", [])

    entities = [
        SSCPComposedVacuum(
            coordinator,
            client,
            vacuum_config,
            config_entry.entry_id,
            config_entry.data.get("PLC_Name", "PLC"),
            hass,
        )
        for vacuum_config in vacuums
    ]
    if entities:
        async_add_entities(entities)


class SSCPComposedVacuum(StateVacuumEntity):
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
        self._status_map = {
            str(key): str(value).strip().lower()
            for key, value in (config.get("status_map") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._fan_speed_map = {
            str(key): str(value).strip()
            for key, value in (config.get("fan_speed_map") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._fan_speed_reverse_map = {label: raw for raw, label in self._fan_speed_map.items()}
        self._refs = {
            "status_var": config.get("status_var"),
            "battery_level_var": config.get("battery_level_var"),
            "battery_charging_var": config.get("battery_charging_var"),
            "fan_speed_var": config.get("fan_speed_var"),
            "start_var": config.get("start_var"),
            "pause_var": config.get("pause_var"),
            "stop_var": config.get("stop_var"),
            "return_to_base_var": config.get("return_to_base_var"),
            "locate_var": config.get("locate_var"),
        }
        self._attr_name = str(config.get("name") or "Vacuum")
        self._attr_unique_id = f"{entry_id}_vacuum_{config.get('entity_key')}"
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

    async def _async_trigger(self, ref_key: str) -> None:
        await self._async_write_ref(self._refs.get(ref_key), True)
        await self.coordinator.async_request_refresh()

    @property
    def supported_features(self) -> VacuumEntityFeature:
        features = VacuumEntityFeature(0)
        if self._refs.get("start_var"):
            features |= VacuumEntityFeature.START
        if self._refs.get("pause_var"):
            features |= VacuumEntityFeature.PAUSE
        if self._refs.get("stop_var"):
            features |= VacuumEntityFeature.STOP
        if self._refs.get("return_to_base_var"):
            features |= VacuumEntityFeature.RETURN_HOME
        if self._refs.get("locate_var"):
            features |= VacuumEntityFeature.LOCATE
        if self._refs.get("fan_speed_var") and self._fan_speed_map:
            features |= VacuumEntityFeature.FAN_SPEED
        return features

    @property
    def state(self) -> str | None:
        raw_value = self._coordinator_value(self._refs.get("status_var"))
        if raw_value is None:
            return None
        if isinstance(raw_value, bool):
            key = "1" if raw_value else "0"
        elif isinstance(raw_value, int):
            key = str(raw_value)
        elif isinstance(raw_value, float):
            integer_value = int(raw_value)
            key = str(integer_value) if float(integer_value) == raw_value else str(raw_value)
        else:
            key = str(raw_value)
        return self._status_map.get(key, key)

    @property
    def battery_level(self) -> int | None:
        value = self._coordinator_value(self._refs.get("battery_level_var"))
        if value is None:
            return None
        return max(0, min(100, int(round(float(value)))))

    @property
    def battery_icon(self):  # pragma: no cover - HA resolves icon from level
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attributes: dict[str, Any] = {}
        charging = self._coordinator_value(self._refs.get("battery_charging_var"))
        if charging is not None:
            attributes["battery_charging"] = bool(charging)
        return attributes or None

    @property
    def fan_speed(self) -> str | None:
        value = self._coordinator_value(self._refs.get("fan_speed_var"))
        if value is None or not self._fan_speed_map:
            return None
        if isinstance(value, bool):
            key = "1" if value else "0"
        elif isinstance(value, int):
            key = str(value)
        elif isinstance(value, float):
            integer_value = int(value)
            key = str(integer_value) if float(integer_value) == value else str(value)
        else:
            key = str(value)
        return self._fan_speed_map.get(key)

    @property
    def fan_speed_list(self) -> list[str]:
        return list(dict.fromkeys(self._fan_speed_map.values()))

    async def async_start(self) -> None:
        try:
            await self._async_trigger("start_var")
        except Exception as err:
            _LOGGER.error("Failed to start vacuum %s: %s", self.name, err)

    async def async_pause(self) -> None:
        try:
            await self._async_trigger("pause_var")
        except Exception as err:
            _LOGGER.error("Failed to pause vacuum %s: %s", self.name, err)

    async def async_stop(self, **kwargs) -> None:
        try:
            await self._async_trigger("stop_var")
        except Exception as err:
            _LOGGER.error("Failed to stop vacuum %s: %s", self.name, err)

    async def async_return_to_base(self, **kwargs) -> None:
        try:
            await self._async_trigger("return_to_base_var")
        except Exception as err:
            _LOGGER.error("Failed to return vacuum %s to base: %s", self.name, err)

    async def async_locate(self, **kwargs) -> None:
        try:
            await self._async_trigger("locate_var")
        except Exception as err:
            _LOGGER.error("Failed to locate vacuum %s: %s", self.name, err)

    async def async_set_fan_speed(self, fan_speed, **kwargs) -> None:
        try:
            raw_value = self._fan_speed_reverse_map.get(str(fan_speed))
            if raw_value is None:
                raise ValueError(f"Fan speed {fan_speed} neni v mapovani definovana.")
            await self._async_write_ref(self._refs.get("fan_speed_var"), raw_value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set fan speed for vacuum %s: %s", self.name, err)
