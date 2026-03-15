from __future__ import annotations

from functools import partial
import logging
from typing import Any

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SSCPDataCoordinator, variable_key
from .transport import PLCClientProtocol

_LOGGER = logging.getLogger(__name__)


def build_plc_device_info(entry_id: str, plc_name: str, transport_name: str):
    return {
        "identifiers": {(DOMAIN, entry_id)},
        "name": plc_name,
        "manufacturer": "Domat/Mervis",
        "model": f"{transport_name.upper()} PLC",
    }


async def async_apply_entity_area(hass, entity_id: str | None, area_id: str | None) -> None:
    normalized_area_id = str(area_id or "").strip()
    if not normalized_area_id or not entity_id:
        return

    registry = er.async_get(hass)
    entry = registry.async_get(entity_id)
    if entry is None or entry.area_id == normalized_area_id:
        return

    try:
        registry.async_update_entity(entity_id, area_id=normalized_area_id)
    except Exception as err:
        _LOGGER.warning("Failed to apply area %s to %s: %s", normalized_area_id, entity_id, err)


class SSCPBaseEntity(CoordinatorEntity[SSCPDataCoordinator]):
    """Shared helper for all SSCP entities backed by the coordinator."""

    should_poll = False

    def __init__(
        self,
        coordinator: SSCPDataCoordinator,
        client: PLCClientProtocol,
        config: dict[str, Any],
        entry_id: str,
        hass,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._config = config
        self._uid = int(config["uid"])
        self._offset = int(config.get("offset", 0))
        self._length = int(config.get("length", 1))
        self._type = str(config["type"])
        self._entry_id = entry_id
        self.hass = hass
        self._coordinator_key = variable_key(config)

    @property
    def plc_name(self) -> str:
        return self.coordinator.entry.data.get("PLC_Name", f"PLC {self._entry_id}")

    @property
    def device_info(self):
        return build_plc_device_info(
            self._entry_id,
            self.plc_name,
            getattr(self._client, "transport_name", "sscp"),
        )

    @property
    def current_value(self) -> Any:
        return self.coordinator.data.get(self._coordinator_key)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_apply_area_id()

    async def _async_apply_area_id(self) -> None:
        await async_apply_entity_area(self.hass, getattr(self, "entity_id", None), self._config.get("area_id"))

    async def async_write_value(self, value: Any) -> None:
        await self.hass.async_add_executor_job(
            partial(
                self._client.write_variable,
                self._uid,
                value,
                offset=self._offset,
                length=self._length,
                type_data=self._type,
            )
        )
        await self.coordinator.async_request_refresh()

    async def async_write_sscp_value(self, value: Any) -> None:
        await self.async_write_value(value)
