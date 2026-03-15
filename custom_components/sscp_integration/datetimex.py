from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.datetime import DateTimeEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COMM_MODE_WEBPANEL, DOMAIN
from .coordinator import SSCPDiagnosticsCoordinator
from .entity import SSCPBaseEntity, async_apply_entity_area, build_plc_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    client = entry_data["client"]
    coordinator = entry_data["coordinator"]
    diagnostics_coordinator: SSCPDiagnosticsCoordinator | None = entry_data.get("diagnostics_coordinator")
    variables = config_entry.data.get("variables", [])

    datetime_entities: list[DateTimeEntity] = [
        SSCPDateTimeEntity(coordinator, client, variable, config_entry.entry_id, hass)
        for variable in variables
        if variable.get("entity_type") == "datetime"
    ]
    if diagnostics_coordinator is not None and config_entry.data.get("communication_mode") != COMM_MODE_WEBPANEL:
        datetime_entities.extend(
            [
                SSCPSystemDateTimeEntity(
                    diagnostics_coordinator,
                    client,
                    config_entry.entry_id,
                    config_entry.data.get("PLC_Name", "PLC"),
                    "utc",
                ),
                SSCPSystemDateTimeEntity(
                    diagnostics_coordinator,
                    client,
                    config_entry.entry_id,
                    config_entry.data.get("PLC_Name", "PLC"),
                    "local",
                ),
            ]
        )
    if datetime_entities:
        async_add_entities(datetime_entities)


class SSCPDateTimeEntity(SSCPBaseEntity, DateTimeEntity):
    def __init__(self, coordinator, client, config, entry_id, hass):
        super().__init__(coordinator, client, config, entry_id, hass)
        self._attr_name = config["name"]
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}_datetime"

    @property
    def native_value(self) -> datetime | None:
        value = self.current_value
        return value if isinstance(value, datetime) else None

    async def async_set_value(self, value: datetime) -> None:
        try:
            await self.async_write_sscp_value(value)
        except Exception as err:
            _LOGGER.error("Failed to set datetime for %s: %s", self.name, err)


class SSCPSystemDateTimeEntity(CoordinatorEntity[SSCPDiagnosticsCoordinator], DateTimeEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, client, entry_id: str, plc_name: str, mode: str) -> None:
        super().__init__(coordinator)
        self._client = client
        self._entry_id = entry_id
        self._plc_name = plc_name
        self._mode = "local" if mode == "local" else "utc"
        label = "PLC Local Time" if self._mode == "local" else "PLC UTC Time"
        self._attr_name = f"{plc_name} {label}"
        self._attr_unique_id = f"{entry_id}_system_datetime_{self._mode}"

    @property
    def device_info(self):
        return build_plc_device_info(
            self._entry_id,
            self._plc_name,
            getattr(self._client, "transport_name", "sscp"),
        )

    @property
    def native_value(self) -> datetime | None:
        value = (self.coordinator.data or {}).get("time", {}).get(self._mode)
        return value if isinstance(value, datetime) else None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await async_apply_entity_area(self.hass, getattr(self, "entity_id", None), None)

    async def async_set_value(self, value: datetime) -> None:
        try:
            await self.hass.async_add_executor_job(self._client.set_time, value, self._mode)
            await self.coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Failed to set %s time for %s: %s", self._mode, self.name, err)
