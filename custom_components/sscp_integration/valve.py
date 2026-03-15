from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.components.valve import ValveEntity, ValveEntityFeature
try:
    from homeassistant.components.valve import ValveDeviceClass
except ImportError:  # pragma: no cover
    ValveDeviceClass = None

from .const import DOMAIN
from .coordinator import SSCPDataCoordinator, variable_key
from .entity import async_apply_entity_area, build_plc_device_info

_LOGGER = logging.getLogger(__name__)

_VALVE_DEVICE_CLASS_BY_VALUE = (
    {member.value: member for member in ValveDeviceClass}
    if ValveDeviceClass is not None
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


def _normalize_position(value: Any, invert: bool = False) -> int | None:
    if value is None:
        return None
    position = max(0, min(100, int(round(float(value)))))
    return 100 - position if invert else position


def _coerce_device_class(value: str | None):
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    return _VALVE_DEVICE_CLASS_BY_VALUE.get(normalized, normalized)


async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    client = entry_data["client"]
    coordinator: SSCPDataCoordinator | None = entry_data.get("coordinator")
    valves = config_entry.data.get("valve_entities", [])

    entities = [
        SSCPComposedValve(
            coordinator,
            client,
            valve_config,
            config_entry.entry_id,
            config_entry.data.get("PLC_Name", "PLC"),
            hass,
        )
        for valve_config in valves
    ]
    if entities:
        async_add_entities(entities)


class SSCPComposedValve(ValveEntity):
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
        self._invert = bool(config.get("invert_position"))
        self._refs = {
            "current_position_var": config.get("current_position_var"),
            "target_position_var": config.get("target_position_var"),
            "open_var": config.get("open_var"),
            "close_var": config.get("close_var"),
            "stop_var": config.get("stop_var"),
        }
        self._attr_name = str(config.get("name") or "Valve")
        self._attr_unique_id = f"{entry_id}_valve_{config.get('entity_key')}"
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
    def supported_features(self) -> ValveEntityFeature:
        features = ValveEntityFeature(0)
        if self._refs.get("open_var"):
            features |= getattr(ValveEntityFeature, "OPEN", ValveEntityFeature(0))
        if self._refs.get("close_var"):
            features |= getattr(ValveEntityFeature, "CLOSE", ValveEntityFeature(0))
        if self._refs.get("stop_var"):
            features |= getattr(ValveEntityFeature, "STOP", ValveEntityFeature(0))
        if self._refs.get("target_position_var"):
            features |= getattr(ValveEntityFeature, "SET_POSITION", ValveEntityFeature(0))
        return features

    @property
    def current_valve_position(self) -> int | None:
        value = self._coordinator_value(self._refs.get("current_position_var"))
        if value is None:
            value = self._coordinator_value(self._refs.get("target_position_var"))
        return _normalize_position(value, self._invert)

    @property
    def is_closed(self) -> bool | None:
        position = self.current_valve_position
        if position is None:
            return None
        return position <= 0

    async def async_open_valve(self, **kwargs) -> None:
        try:
            if self._refs.get("open_var"):
                await self._async_write_ref(self._refs.get("open_var"), True)
            elif self._refs.get("target_position_var"):
                await self._async_write_ref(self._refs.get("target_position_var"), 0 if self._invert else 100)
            else:
                raise ValueError("Valve nema definovan open point.")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to open valve %s: %s", self.name, err)

    async def async_close_valve(self, **kwargs) -> None:
        try:
            if self._refs.get("close_var"):
                await self._async_write_ref(self._refs.get("close_var"), True)
            elif self._refs.get("target_position_var"):
                await self._async_write_ref(self._refs.get("target_position_var"), 100 if self._invert else 0)
            else:
                raise ValueError("Valve nema definovan close point.")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to close valve %s: %s", self.name, err)

    async def async_stop_valve(self, **kwargs) -> None:
        try:
            await self._async_write_ref(self._refs.get("stop_var"), True)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to stop valve %s: %s", self.name, err)

    async def async_set_valve_position(self, position: int, **kwargs) -> None:
        try:
            normalized = max(0, min(100, int(position)))
            raw_value = 100 - normalized if self._invert else normalized
            await self._async_write_ref(self._refs.get("target_position_var"), raw_value)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set valve position for %s: %s", self.name, err)
