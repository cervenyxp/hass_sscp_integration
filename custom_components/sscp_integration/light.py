from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.components.light import ColorMode, LightEntity

from .const import DOMAIN
from .coordinator import SSCPDataCoordinator, variable_key
from .entity import SSCPBaseEntity, async_apply_entity_area, build_plc_device_info

_LOGGER = logging.getLogger(__name__)

_WHITE_COLOR_MODE = getattr(ColorMode, "WHITE", ColorMode.BRIGHTNESS)


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


def _to_brightness(raw_value: Any, scale: float) -> int | None:
    if raw_value is None:
        return None
    normalized_scale = max(1.0, float(scale))
    value = max(0.0, min(normalized_scale, float(raw_value)))
    return max(0, min(255, int(round((value / normalized_scale) * 255.0))))


def _from_brightness(brightness: Any, scale: float) -> float:
    normalized_scale = max(1.0, float(scale))
    return max(0.0, min(normalized_scale, (float(brightness) / 255.0) * normalized_scale))


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
    variables = config_entry.data.get("variables", [])
    composed_lights = config_entry.data.get("light_entities", [])

    entities: list[LightEntity] = []
    if coordinator is not None:
        entities.extend(
            SSCPSimpleLight(coordinator, client, variable, config_entry.entry_id, hass)
            for variable in variables
            if variable.get("entity_type") == "light"
        )
        entities.extend(
            SSCPComposedLight(
                coordinator,
                client,
                light_config,
                config_entry.entry_id,
                config_entry.data.get("PLC_Name", "PLC"),
                hass,
            )
            for light_config in composed_lights
        )

    if entities:
        async_add_entities(entities)


class SSCPSimpleLight(SSCPBaseEntity, LightEntity):
    def __init__(self, coordinator, client, config, entry_id, hass):
        super().__init__(coordinator, client, config, entry_id, hass)
        self._attr_name = config["name"]
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}_light"
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF

    @property
    def is_on(self):
        value = self.current_value
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs):
        try:
            await self.async_write_sscp_value(True)
        except Exception as err:
            _LOGGER.error("Failed to turn on light %s: %s", self.name, err)

    async def async_turn_off(self, **kwargs):
        try:
            await self.async_write_sscp_value(False)
        except Exception as err:
            _LOGGER.error("Failed to turn off light %s: %s", self.name, err)


class SSCPComposedLight(LightEntity):
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
        self._brightness_scale = float(config.get("brightness_scale") or 100.0)
        self._effect_map = {
            str(key): str(value).strip()
            for key, value in (config.get("effect_map") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._effect_reverse_map = {label: raw for raw, label in self._effect_map.items()}
        self._refs = {
            "power_var": config.get("power_var"),
            "brightness_var": config.get("brightness_var"),
            "color_temp_var": config.get("color_temp_var"),
            "hs_hue_var": config.get("hs_hue_var"),
            "hs_saturation_var": config.get("hs_saturation_var"),
            "rgb_red_var": config.get("rgb_red_var"),
            "rgb_green_var": config.get("rgb_green_var"),
            "rgb_blue_var": config.get("rgb_blue_var"),
            "white_var": config.get("white_var"),
            "effect_var": config.get("effect_var"),
        }
        self._attr_name = str(config.get("name") or "Light")
        self._attr_unique_id = f"{entry_id}_light_{config.get('entity_key')}"
        self._attr_has_entity_name = False
        self._attr_supported_color_modes = set(self._compute_supported_color_modes())

    def _compute_supported_color_modes(self) -> list[ColorMode]:
        modes: list[ColorMode] = []
        if self._refs.get("rgb_red_var") and self._refs.get("rgb_green_var") and self._refs.get("rgb_blue_var"):
            modes.append(ColorMode.RGB)
        if self._refs.get("hs_hue_var") and self._refs.get("hs_saturation_var"):
            modes.append(ColorMode.HS)
        if self._refs.get("color_temp_var"):
            modes.append(ColorMode.COLOR_TEMP)
        if self._refs.get("white_var"):
            modes.append(_WHITE_COLOR_MODE)
        if self._refs.get("brightness_var") and not modes:
            modes.append(ColorMode.BRIGHTNESS)
        if not modes:
            modes.append(ColorMode.ONOFF)
        return modes

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
    def is_on(self):
        power_value = self._coordinator_value(self._refs.get("power_var"))
        if power_value is not None:
            return bool(power_value)
        brightness = self.brightness
        if brightness is not None:
            return brightness > 0
        white_value = self._coordinator_value(self._refs.get("white_var"))
        if white_value is not None:
            return float(white_value) > 0
        return None

    @property
    def brightness(self) -> int | None:
        value = self._coordinator_value(self._refs.get("brightness_var"))
        if value is None:
            value = self._coordinator_value(self._refs.get("white_var"))
        return _to_brightness(value, self._brightness_scale) if value is not None else None

    @property
    def hs_color(self):
        hue = self._coordinator_value(self._refs.get("hs_hue_var"))
        saturation = self._coordinator_value(self._refs.get("hs_saturation_var"))
        if hue is None or saturation is None:
            return None
        return (float(hue), float(saturation))

    @property
    def rgb_color(self):
        red = self._coordinator_value(self._refs.get("rgb_red_var"))
        green = self._coordinator_value(self._refs.get("rgb_green_var"))
        blue = self._coordinator_value(self._refs.get("rgb_blue_var"))
        if red is None or green is None or blue is None:
            return None
        return (
            max(0, min(255, int(round(float(red))))),
            max(0, min(255, int(round(float(green))))),
            max(0, min(255, int(round(float(blue))))),
        )

    @property
    def color_temp_kelvin(self) -> int | None:
        value = self._coordinator_value(self._refs.get("color_temp_var"))
        if value in (None, 0):
            return None
        mireds = max(1, int(round(float(value))))
        return int(round(1000000 / mireds))

    @property
    def min_color_temp_kelvin(self) -> int:
        max_mireds = int(self._config.get("max_mireds") or 500)
        return int(round(1000000 / max_mireds))

    @property
    def max_color_temp_kelvin(self) -> int:
        min_mireds = int(self._config.get("min_mireds") or 153)
        return int(round(1000000 / min_mireds))

    @property
    def effect_list(self) -> list[str] | None:
        if not self._effect_map:
            return None
        return list(dict.fromkeys(self._effect_map.values()))

    @property
    def effect(self) -> str | None:
        effect_value = self._coordinator_value(self._refs.get("effect_var"))
        if effect_value is None or not self._effect_map:
            return None
        return self._effect_map.get(_value_key(effect_value))

    @property
    def color_mode(self):
        if ColorMode.RGB in self._attr_supported_color_modes and self.rgb_color is not None:
            return ColorMode.RGB
        if ColorMode.HS in self._attr_supported_color_modes and self.hs_color is not None:
            return ColorMode.HS
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes and self.color_temp_kelvin is not None:
            return ColorMode.COLOR_TEMP
        if _WHITE_COLOR_MODE in self._attr_supported_color_modes and self.brightness is not None:
            return _WHITE_COLOR_MODE
        if ColorMode.BRIGHTNESS in self._attr_supported_color_modes and self.brightness is not None:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    async def async_turn_on(self, **kwargs):
        try:
            if self._refs.get("power_var"):
                await self._async_write_ref(self._refs.get("power_var"), True)

            if "brightness" in kwargs and self._refs.get("brightness_var"):
                await self._async_write_ref(
                    self._refs.get("brightness_var"),
                    _from_brightness(kwargs["brightness"], self._brightness_scale),
                )

            if "white" in kwargs and self._refs.get("white_var"):
                await self._async_write_ref(
                    self._refs.get("white_var"),
                    _from_brightness(kwargs["white"], self._brightness_scale),
                )

            if "hs_color" in kwargs and self._refs.get("hs_hue_var") and self._refs.get("hs_saturation_var"):
                hue, saturation = kwargs["hs_color"]
                await self._async_write_ref(self._refs.get("hs_hue_var"), hue)
                await self._async_write_ref(self._refs.get("hs_saturation_var"), saturation)

            if "rgb_color" in kwargs and self._refs.get("rgb_red_var"):
                red, green, blue = kwargs["rgb_color"]
                await self._async_write_ref(self._refs.get("rgb_red_var"), red)
                await self._async_write_ref(self._refs.get("rgb_green_var"), green)
                await self._async_write_ref(self._refs.get("rgb_blue_var"), blue)

            color_temp_kelvin = kwargs.get("color_temp_kelvin")
            color_temp_mireds = kwargs.get("color_temp")
            if self._refs.get("color_temp_var") and (color_temp_kelvin or color_temp_mireds):
                if color_temp_mireds is None and color_temp_kelvin:
                    color_temp_mireds = int(round(1000000 / max(1, float(color_temp_kelvin))))
                await self._async_write_ref(self._refs.get("color_temp_var"), color_temp_mireds)

            if "effect" in kwargs and self._refs.get("effect_var") and self._effect_reverse_map:
                raw_value = self._effect_reverse_map.get(str(kwargs["effect"]))
                if raw_value is not None:
                    await self._async_write_ref(self._refs.get("effect_var"), raw_value)

            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on composed light %s: %s", self.name, err)

    async def async_turn_off(self, **kwargs):
        try:
            if self._refs.get("power_var"):
                await self._async_write_ref(self._refs.get("power_var"), False)
            elif self._refs.get("brightness_var"):
                await self._async_write_ref(self._refs.get("brightness_var"), 0)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off composed light %s: %s", self.name, err)
