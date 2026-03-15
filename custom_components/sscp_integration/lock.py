from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.components.lock import LockEntity, LockEntityFeature

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
    locks = config_entry.data.get("lock_entities", [])

    entities = [
        SSCPComposedLock(
            coordinator,
            client,
            lock_config,
            config_entry.entry_id,
            config_entry.data.get("PLC_Name", "PLC"),
            hass,
        )
        for lock_config in locks
    ]
    if entities:
        async_add_entities(entities)


class SSCPComposedLock(LockEntity):
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
            "lock_var": config.get("lock_var"),
            "unlock_var": config.get("unlock_var"),
            "open_var": config.get("open_var"),
        }
        self._state_map = {
            str(key): str(value).strip().lower()
            for key, value in (config.get("state_map") or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self._attr_name = str(config.get("name") or "Lock")
        self._attr_unique_id = f"{entry_id}_lock_{config.get('entity_key')}"
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

    def _state_label(self) -> str | None:
        value = self._coordinator_value(self._refs.get("state_var"))
        if value is None:
            return None
        if isinstance(value, bool) and not self._state_map:
            return "locked" if value else "unlocked"
        return self._state_map.get(_value_key(value))

    @property
    def supported_features(self) -> LockEntityFeature:
        features = LockEntityFeature(0)
        if self._refs.get("open_var"):
            features |= LockEntityFeature.OPEN
        return features

    @property
    def is_locked(self) -> bool | None:
        state = self._state_label()
        if state is None:
            return None
        if state in {"locked", "locking"}:
            return True
        if state in {"unlocked", "unlocking", "open", "opening"}:
            return False
        return None

    @property
    def is_locking(self) -> bool | None:
        return self._state_label() == "locking"

    @property
    def is_unlocking(self) -> bool | None:
        return self._state_label() == "unlocking"

    @property
    def is_jammed(self) -> bool | None:
        return self._state_label() == "jammed"

    @property
    def is_open(self) -> bool | None:
        state = self._state_label()
        if state is None:
            return None
        return state in {"open", "opening"}

    async def async_lock(self, **kwargs) -> None:
        try:
            await self._async_write_ref(self._refs.get("lock_var"), True)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to lock %s: %s", self.name, err)

    async def async_unlock(self, **kwargs) -> None:
        try:
            await self._async_write_ref(self._refs.get("unlock_var"), True)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to unlock %s: %s", self.name, err)

    async def async_open(self, **kwargs) -> None:
        try:
            await self._async_write_ref(self._refs.get("open_var"), True)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to open lock %s: %s", self.name, err)
