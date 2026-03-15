from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.components.humidifier import HumidifierEntity, HumidifierEntityFeature
try:
    from homeassistant.components.humidifier import HumidifierAction, HumidifierDeviceClass
except ImportError:  # pragma: no cover
    HumidifierAction = None
    HumidifierDeviceClass = None

from .const import DOMAIN
from .coordinator import SSCPDataCoordinator, variable_key
from .entity import async_apply_entity_area, build_plc_device_info

_LOGGER = logging.getLogger(__name__)

_HUMIDIFIER_DEVICE_CLASS_BY_VALUE = (
    {member.value: member for member in HumidifierDeviceClass}
    if HumidifierDeviceClass is not None
    else {}
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


def _coerce_device_class(value: str | None):
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    return _HUMIDIFIER_DEVICE_CLASS_BY_VALUE.get(normalized, normalized)


async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    client = entry_data["client"]
    coordinator: SSCPDataCoordinator | None = entry_data.get("coordinator")
    humidifiers = config_entry.data.get("humidifier_entities", [])

    entities = [
        SSCPComposedHumidifier(
            coordinator,
            client,
            humidifier_config,
            config_entry.entry_id,
            config_entry.data.get("PLC_Name", "PLC"),
            hass,
        )
        for humidifier_config in humidifiers
    ]
    if entities:
        async_add_entities(entities)


class SSCPComposedHumidifier(HumidifierEntity):
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
            "current_humidity_var": config.get("current_humidity_var"),
            "target_humidity_var": config.get("target_humidity_var"),
            "power_var": config.get("power_var"),
            "mode_var": config.get("mode_var"),
        }
        self._mode_map = {
            str(key): str(value).strip()
            for key, value in (config.get("mode_map") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._mode_reverse_map = {label: raw for raw, label in self._mode_map.items()}
        self._attr_name = str(config.get("name") or "Humidifier")
        self._attr_unique_id = f"{entry_id}_humidifier_{config.get('entity_key')}"
        self._attr_has_entity_name = False
        self._attr_device_class = _coerce_device_class(config.get("device_class"))

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
    def supported_features(self) -> HumidifierEntityFeature:
        features = HumidifierEntityFeature(0)
        if self._refs.get("mode_var") and self._mode_map:
            features |= HumidifierEntityFeature.MODES
        return features

    @property
    def is_on(self) -> bool | None:
        value = self._coordinator_value(self._refs.get("power_var"))
        if value is None:
            return None
        return bool(value)

    @property
    def current_humidity(self) -> int | None:
        value = self._coordinator_value(self._refs.get("current_humidity_var"))
        if value is None:
            return None
        return int(round(float(value)))

    @property
    def target_humidity(self) -> int | None:
        value = self._coordinator_value(self._refs.get("target_humidity_var"))
        if value is None:
            return None
        return int(round(float(value)))

    @property
    def min_humidity(self) -> int:
        return int(round(float(self._config.get("min_humidity") or 0)))

    @property
    def max_humidity(self) -> int:
        return int(round(float(self._config.get("max_humidity") or 100)))

    @property
    def target_humidity_step(self) -> int:
        return max(1, int(round(float(self._config.get("target_humidity_step") or 1))))

    @property
    def mode(self) -> str | None:
        value = self._coordinator_value(self._refs.get("mode_var"))
        if value is None:
            return None
        return self._mode_map.get(_value_key(value))

    @property
    def available_modes(self) -> list[str] | None:
        if not self._mode_map:
            return None
        return list(dict.fromkeys(self._mode_map.values()))

    @property
    def action(self):
        if HumidifierAction is None:
            return None
        is_on = self.is_on
        if not is_on:
            return HumidifierAction.OFF
        device_class = str(self._config.get("device_class") or "").strip().lower()
        if device_class == "dehumidifier":
            return getattr(HumidifierAction, "DRYING", None)
        return getattr(HumidifierAction, "HUMIDIFYING", None)

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self._async_write_ref(self._refs.get("power_var"), True)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on humidifier %s: %s", self.name, err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self._async_write_ref(self._refs.get("power_var"), False)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off humidifier %s: %s", self.name, err)

    async def async_set_humidity(self, humidity: int) -> None:
        try:
            bounded = max(self.min_humidity, min(self.max_humidity, int(humidity)))
            await self._async_write_ref(self._refs.get("target_humidity_var"), bounded)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set humidity for %s: %s", self.name, err)

    async def async_set_mode(self, mode: str) -> None:
        try:
            raw_value = self._mode_reverse_map.get(str(mode))
            if raw_value is None:
                raise ValueError(f"Humidifier mode {mode} neni v mapovani definovan.")
            await self._async_write_ref(self._refs.get("mode_var"), raw_value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set mode for %s: %s", self.name, err)
