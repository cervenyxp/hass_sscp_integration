from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.components.water_heater import WaterHeaterEntity, WaterHeaterEntityFeature
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from .const import DOMAIN
from .coordinator import SSCPDataCoordinator, variable_key
from .entity import async_apply_entity_area, build_plc_device_info
from .vlist import normalize_unit_of_measurement

_LOGGER = logging.getLogger(__name__)

_FEATURE_TURN_ON = getattr(
    WaterHeaterEntityFeature,
    "TURN_ON",
    getattr(WaterHeaterEntityFeature, "ON_OFF", WaterHeaterEntityFeature(0)),
)
_FEATURE_TURN_OFF = getattr(
    WaterHeaterEntityFeature,
    "TURN_OFF",
    getattr(WaterHeaterEntityFeature, "ON_OFF", WaterHeaterEntityFeature(0)),
)


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
    water_heaters = config_entry.data.get("water_heater_entities", [])

    entities = [
        SSCPComposedWaterHeater(
            coordinator,
            client,
            entity_config,
            config_entry.entry_id,
            config_entry.data.get("PLC_Name", "PLC"),
            hass,
        )
        for entity_config in water_heaters
    ]
    if entities:
        async_add_entities(entities)


class SSCPComposedWaterHeater(WaterHeaterEntity):
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
            "current_temperature_var": config.get("current_temperature_var"),
            "target_temperature_var": config.get("target_temperature_var"),
            "power_var": config.get("power_var"),
            "operation_mode_var": config.get("operation_mode_var"),
        }
        self._operation_mode_map = {
            str(key): str(value).strip().lower()
            for key, value in (config.get("operation_mode_map") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._operation_reverse_map = {label: raw for raw, label in self._operation_mode_map.items()}
        self._temperature_unit = normalize_unit_of_measurement(config.get("temperature_unit") or "Â°C") or "Â°C"
        self._attr_name = str(config.get("name") or "Water Heater")
        self._attr_unique_id = f"{entry_id}_water_heater_{config.get('entity_key')}"
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
    def supported_features(self) -> WaterHeaterEntityFeature:
        features = WaterHeaterEntityFeature(0)
        if self._refs.get("target_temperature_var"):
            features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
        if self._refs.get("operation_mode_var") and self._operation_mode_map:
            features |= WaterHeaterEntityFeature.OPERATION_MODE
        if self._refs.get("power_var") or self._refs.get("operation_mode_var"):
            features |= _FEATURE_TURN_ON | _FEATURE_TURN_OFF
        return features

    @property
    def temperature_unit(self) -> UnitOfTemperature:
        normalized = self._temperature_unit.strip().casefold()
        if normalized in {"Â°f", "degf", "decf"}:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def precision(self) -> float:
        digits = self._config.get("suggested_display_precision")
        if digits is None:
            return 0.1
        return {0: 1.0, 1: 0.1, 2: 0.01, 3: 0.001}.get(int(digits), 0.1)

    @property
    def current_temperature(self) -> float | None:
        value = self._coordinator_value(self._refs.get("current_temperature_var"))
        if value is None:
            return None
        return float(value)

    @property
    def target_temperature(self) -> float | None:
        value = self._coordinator_value(self._refs.get("target_temperature_var"))
        if value is None:
            return None
        return float(value)

    @property
    def min_temp(self) -> float:
        return float(self._config.get("min_temp") or 30.0)

    @property
    def max_temp(self) -> float:
        return float(self._config.get("max_temp") or 90.0)

    @property
    def target_temperature_step(self) -> float:
        return float(self._config.get("temp_step") or 0.5)

    @property
    def current_operation(self) -> str | None:
        power_value = self._coordinator_value(self._refs.get("power_var"))
        if power_value is not None and not bool(power_value):
            return "off"
        operation_value = self._coordinator_value(self._refs.get("operation_mode_var"))
        if operation_value is None:
            return "off" if power_value is False else None
        mapped = self._operation_mode_map.get(_value_key(operation_value))
        if mapped:
            return mapped
        return _value_key(operation_value)

    @property
    def operation_list(self) -> list[str]:
        values = list(dict.fromkeys(self._operation_mode_map.values()))
        if "off" not in values:
            values.insert(0, "off")
        return values

    async def async_turn_on(self, **kwargs) -> None:
        try:
            if self._refs.get("power_var"):
                await self._async_write_ref(self._refs.get("power_var"), True)
            elif self._refs.get("operation_mode_var"):
                target_mode = next((mode for mode in self.operation_list if mode != "off"), None)
                if target_mode is None:
                    raise ValueError("Water heater nema definovan zadny operation mode pro zapnuti.")
                raw_value = self._operation_reverse_map.get(target_mode)
                await self._async_write_ref(self._refs.get("operation_mode_var"), raw_value)
            else:
                raise ValueError("Water heater nema power ani operation mode point pro zapnuti.")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on water heater %s: %s", self.name, err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            if self._refs.get("power_var"):
                await self._async_write_ref(self._refs.get("power_var"), False)
            elif self._refs.get("operation_mode_var"):
                raw_value = self._operation_reverse_map.get("off")
                if raw_value is None:
                    raise ValueError("Water heater nema operation mode 'off' v mapovani.")
                await self._async_write_ref(self._refs.get("operation_mode_var"), raw_value)
            else:
                raise ValueError("Water heater nema power ani operation mode point pro vypnuti.")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off water heater %s: %s", self.name, err)

    async def async_set_temperature(self, **kwargs) -> None:
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            return
        try:
            await self._async_write_ref(self._refs.get("target_temperature_var"), float(target_temperature))
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set temperature for water heater %s: %s", self.name, err)

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        try:
            raw_value = self._operation_reverse_map.get(str(operation_mode).strip().lower())
            if raw_value is None:
                raise ValueError(f"Operation mode {operation_mode} neni v mapovani definovan.")
            await self._async_write_ref(self._refs.get("operation_mode_var"), raw_value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set operation mode for water heater %s: %s", self.name, err)
