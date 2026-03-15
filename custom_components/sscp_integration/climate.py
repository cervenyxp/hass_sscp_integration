from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
try:
    from homeassistant.components.climate.const import PRESET_NONE
except ImportError:  # pragma: no cover - fallback for older HA builds
    PRESET_NONE = "none"
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SSCPDataCoordinator, variable_key
from .entity import async_apply_entity_area, build_plc_device_info

_LOGGER = logging.getLogger(__name__)

_HVAC_MODE_BY_VALUE = {mode.value: mode for mode in HVACMode}
_DEFAULT_HVAC_MODE = HVACMode.HEAT
_FEATURE_TURN_ON = getattr(ClimateEntityFeature, "TURN_ON", ClimateEntityFeature(0))
_FEATURE_TURN_OFF = getattr(ClimateEntityFeature, "TURN_OFF", ClimateEntityFeature(0))
_PRECISION_BY_DIGITS = {
    0: 1.0,
    1: 0.1,
    2: 0.01,
    3: 0.001,
}


def _normalize_map(raw_map: dict[str, str] | None) -> dict[str, str]:
    return {
        str(key): str(value).strip().lower()
        for key, value in (raw_map or {}).items()
        if str(key).strip() and str(value).strip()
    }


def _normalize_ref_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        integer_value = int(value)
        if float(integer_value) == value:
            return str(integer_value)
    return str(value)


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
    coordinator = entry_data["coordinator"]
    climates = config_entry.data.get("climate_entities", [])

    entities = [
        SSCPComposedClimate(coordinator, client, climate_config, config_entry.entry_id, config_entry.data.get("PLC_Name", "PLC"), hass)
        for climate_config in climates
    ]
    if entities:
        async_add_entities(entities)


class SSCPComposedClimate(CoordinatorEntity[SSCPDataCoordinator], ClimateEntity):
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
        super().__init__(coordinator)
        self._client = client
        self._config = config
        self._entry_id = entry_id
        self._plc_name = plc_name
        self.hass = hass

        self._attr_name = str(config.get("name") or "Climate")
        self._attr_unique_id = f"{entry_id}_climate_{config.get('entity_key')}"
        self._attr_has_entity_name = False

        self._hvac_mode_map = _normalize_map(config.get("hvac_mode_map"))
        self._hvac_mode_reverse_map = {mapped: raw for raw, mapped in self._hvac_mode_map.items()}
        self._preset_map = {
            str(key): str(value).strip()
            for key, value in (config.get("preset_map") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._preset_reverse_map = {label: raw for raw, label in self._preset_map.items()}
        self._refs = {
            "current_temperature_var": config.get("current_temperature_var"),
            "target_temperature_var": config.get("target_temperature_var"),
            "current_humidity_var": config.get("current_humidity_var"),
            "power_var": config.get("power_var"),
            "hvac_mode_var": config.get("hvac_mode_var"),
            "preset_var": config.get("preset_var"),
        }
        self._temperature_unit = str(config.get("temperature_unit") or "°C")
        self._precision_digits = config.get("suggested_display_precision")
        self._default_power_hvac_mode = self._resolve_default_power_hvac_mode()

    @property
    def device_info(self):
        return build_plc_device_info(
            self._entry_id,
            self._plc_name,
            getattr(self._client, "transport_name", "sscp"),
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await async_apply_entity_area(self.hass, getattr(self, "entity_id", None), self._config.get("area_id"))

    def _resolve_default_power_hvac_mode(self) -> HVACMode:
        if self._hvac_mode_reverse_map:
            for candidate in (HVACMode.HEAT.value, HVACMode.AUTO.value, HVACMode.COOL.value):
                if candidate in self._hvac_mode_reverse_map:
                    return _HVAC_MODE_BY_VALUE.get(candidate, _DEFAULT_HVAC_MODE)
        return _DEFAULT_HVAC_MODE

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
    def supported_features(self) -> ClimateEntityFeature:
        features = ClimateEntityFeature(0)
        if self._refs.get("target_temperature_var"):
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if self._refs.get("power_var") or self._refs.get("hvac_mode_var"):
            features |= _FEATURE_TURN_ON | _FEATURE_TURN_OFF
        if self._refs.get("preset_var") and self._preset_map:
            features |= ClimateEntityFeature.PRESET_MODE
        return features

    @property
    def temperature_unit(self) -> UnitOfTemperature:
        normalized = self._temperature_unit.strip().casefold()
        if normalized in {"°f", "degf", "decf"}:
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def precision(self) -> float:
        if self._precision_digits is None:
            return 0.1
        return _PRECISION_BY_DIGITS.get(int(self._precision_digits), 0.1)

    @property
    def target_temperature_step(self) -> float:
        return float(self._config.get("temp_step") or 0.5)

    @property
    def min_temp(self) -> float:
        return float(self._config.get("min_temp") or 7.0)

    @property
    def max_temp(self) -> float:
        return float(self._config.get("max_temp") or 35.0)

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
    def current_humidity(self) -> float | None:
        value = self._coordinator_value(self._refs.get("current_humidity_var"))
        if value is None:
            return None
        return float(value)

    @property
    def hvac_modes(self) -> list[HVACMode]:
        modes: list[HVACMode] = []
        for mapped_value in self._hvac_mode_map.values():
            mode = _HVAC_MODE_BY_VALUE.get(mapped_value)
            if mode and mode not in modes:
                modes.append(mode)
        if self._refs.get("power_var") and HVACMode.OFF not in modes:
            modes.insert(0, HVACMode.OFF)
        if self._refs.get("power_var") and self._default_power_hvac_mode not in modes:
            modes.append(self._default_power_hvac_mode)
        if not modes:
            return [HVACMode.OFF, self._default_power_hvac_mode]
        if HVACMode.OFF not in modes:
            modes.insert(0, HVACMode.OFF)
        return modes

    @property
    def hvac_mode(self) -> HVACMode:
        power_ref = self._refs.get("power_var")
        power_value = self._coordinator_value(power_ref)
        if power_ref and power_value is not None and not bool(power_value):
            return HVACMode.OFF

        hvac_ref = self._refs.get("hvac_mode_var")
        if hvac_ref:
            mapped = self._hvac_mode_map.get(_normalize_ref_value(self._coordinator_value(hvac_ref)))
            if mapped in _HVAC_MODE_BY_VALUE:
                return _HVAC_MODE_BY_VALUE[mapped]

        if power_ref and power_value is not None:
            return self._default_power_hvac_mode if bool(power_value) else HVACMode.OFF
        return self.hvac_modes[0] if self.hvac_modes else HVACMode.OFF

    @property
    def preset_modes(self) -> list[str] | None:
        if not self._preset_map:
            return None
        return list(dict.fromkeys(self._preset_map.values()))

    @property
    def preset_mode(self) -> str | None:
        preset_ref = self._refs.get("preset_var")
        if not preset_ref or not self._preset_map:
            return None
        raw_value = self._coordinator_value(preset_ref)
        if raw_value is None:
            return None
        mapped = self._preset_map.get(_normalize_ref_value(raw_value))
        return mapped or PRESET_NONE

    async def async_set_temperature(self, **kwargs: Any) -> None:
        target = kwargs.get(ATTR_TEMPERATURE, kwargs.get("temperature"))
        if target is None:
            return
        try:
            await self._async_write_ref(self._refs.get("target_temperature_var"), target)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set target temperature for %s: %s", self.name, err)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        try:
            if hvac_mode == HVACMode.OFF:
                if self._refs.get("power_var"):
                    await self._async_write_ref(self._refs.get("power_var"), False)
                if self._refs.get("hvac_mode_var") and HVACMode.OFF.value in self._hvac_mode_reverse_map:
                    await self._async_write_ref(
                        self._refs.get("hvac_mode_var"),
                        self._hvac_mode_reverse_map[HVACMode.OFF.value],
                    )
                elif not self._refs.get("power_var"):
                    raise ValueError("Climate nema definovany zpusob vypnuti.")
            else:
                if self._refs.get("power_var"):
                    await self._async_write_ref(self._refs.get("power_var"), True)
                if self._refs.get("hvac_mode_var"):
                    raw_value = self._hvac_mode_reverse_map.get(hvac_mode.value)
                    if raw_value is None:
                        raise ValueError(f"HVAC mode {hvac_mode.value} neni v mapovani definovan.")
                    await self._async_write_ref(self._refs.get("hvac_mode_var"), raw_value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set hvac mode %s for %s: %s", hvac_mode, self.name, err)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(self._default_power_hvac_mode)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        try:
            raw_value = self._preset_reverse_map.get(preset_mode)
            if raw_value is None:
                raise ValueError(f"Preset {preset_mode} neni v mapovani definovan.")
            await self._async_write_ref(self._refs.get("preset_var"), raw_value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set preset %s for %s: %s", preset_mode, self.name, err)
