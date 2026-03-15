from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.components.siren import SirenEntity, SirenEntityFeature

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
    sirens = config_entry.data.get("siren_entities", [])

    entities = [
        SSCPComposedSiren(
            coordinator,
            client,
            siren_config,
            config_entry.entry_id,
            config_entry.data.get("PLC_Name", "PLC"),
            hass,
        )
        for siren_config in sirens
    ]
    if entities:
        async_add_entities(entities)


class SSCPComposedSiren(SirenEntity):
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
            "state_var": config.get("state_var"),
            "turn_on_var": config.get("turn_on_var"),
            "turn_off_var": config.get("turn_off_var"),
            "tone_var": config.get("tone_var"),
            "duration_var": config.get("duration_var"),
            "volume_var": config.get("volume_var"),
        }
        self._tone_map = {
            str(key): str(value).strip()
            for key, value in (config.get("tone_map") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._tone_reverse_map = {label: raw for raw, label in self._tone_map.items()}
        self._volume_scale = float(config.get("volume_scale") or 100.0)
        self._attr_name = str(config.get("name") or "Siren")
        self._attr_unique_id = f"{entry_id}_siren_{config.get('entity_key')}"
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
    def supported_features(self) -> SirenEntityFeature:
        features = SirenEntityFeature(0)
        if self._refs.get("tone_var") and self._tone_map:
            features |= getattr(SirenEntityFeature, "TONES", SirenEntityFeature(0))
        if self._refs.get("duration_var"):
            features |= getattr(SirenEntityFeature, "DURATION", SirenEntityFeature(0))
        if self._refs.get("volume_var"):
            features |= getattr(SirenEntityFeature, "VOLUME_SET", SirenEntityFeature(0))
        return features

    @property
    def is_on(self) -> bool | None:
        value = self._coordinator_value(self._refs.get("state_var"))
        if value is None:
            return None
        return bool(value)

    @property
    def available_tones(self):
        if not self._tone_map:
            return None
        return list(dict.fromkeys(self._tone_map.values()))

    async def async_turn_on(self, **kwargs) -> None:
        try:
            tone = kwargs.get("tone")
            duration = kwargs.get("duration")
            volume_level = kwargs.get("volume_level")
            if tone is not None and self._refs.get("tone_var"):
                raw_value = self._tone_reverse_map.get(str(tone))
                if raw_value is None:
                    raise ValueError(f"Tone {tone} neni v mapovani definovan.")
                await self._async_write_ref(self._refs.get("tone_var"), raw_value)
            if duration is not None and self._refs.get("duration_var"):
                await self._async_write_ref(self._refs.get("duration_var"), int(duration))
            if volume_level is not None and self._refs.get("volume_var"):
                scaled = max(0.0, min(1.0, float(volume_level))) * max(1.0, self._volume_scale)
                await self._async_write_ref(self._refs.get("volume_var"), scaled)

            if self._refs.get("turn_on_var"):
                await self._async_write_ref(self._refs.get("turn_on_var"), True)
            elif self._refs.get("state_var"):
                await self._async_write_ref(self._refs.get("state_var"), True)
            else:
                raise ValueError("Siren nema definovan turn on ani state point.")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn on siren %s: %s", self.name, err)

    async def async_turn_off(self, **kwargs) -> None:
        try:
            if self._refs.get("turn_off_var"):
                await self._async_write_ref(self._refs.get("turn_off_var"), True)
            elif self._refs.get("state_var"):
                await self._async_write_ref(self._refs.get("state_var"), False)
            else:
                raise ValueError("Siren nema definovan turn off ani state point.")
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to turn off siren %s: %s", self.name, err)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attributes: dict[str, Any] = {}
        tone_value = self._coordinator_value(self._refs.get("tone_var"))
        if tone_value is not None:
            attributes["tone"] = self._tone_map.get(_value_key(tone_value), _value_key(tone_value))
        duration_value = self._coordinator_value(self._refs.get("duration_var"))
        if duration_value is not None:
            attributes["duration"] = int(duration_value)
        volume_value = self._coordinator_value(self._refs.get("volume_var"))
        if volume_value is not None:
            attributes["volume_level"] = max(0.0, min(1.0, float(volume_value) / max(1.0, self._volume_scale)))
        return attributes or None
