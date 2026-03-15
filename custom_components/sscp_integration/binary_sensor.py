from __future__ import annotations

from typing import Any, Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COMM_MODE_WEBPANEL, DOMAIN
from .coordinator import SSCPDataCoordinator, SSCPDiagnosticsCoordinator
from .entity import SSCPBaseEntity


def _dig(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


COMMON_DIAGNOSTIC_BINARY_SENSORS: list[dict[str, Any]] = [
    {
        "key": "connected",
        "name": "Connected",
        "extractor": lambda data: bool(data.get("connected")),
    },
]

SSCP_DIAGNOSTIC_BINARY_SENSORS: list[dict[str, Any]] = [
    {
        "key": "runtime_running",
        "name": "Runtime Running",
        "extractor": lambda data: _dig(data, "plc_statistics", "runtime", "evaluator_state_label") == "RunningNormalTasks",
    },
    {
        "key": "proxy_connected",
        "name": "Proxy Connected",
        "extractor": lambda data: _dig(data, "plc_statistics", "proxy", "proxy_status_label") == "Connected",
    },
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    client = entry_data["client"]
    coordinator: SSCPDataCoordinator | None = entry_data.get("coordinator")
    diagnostics_coordinator: SSCPDiagnosticsCoordinator | None = entry_data.get("diagnostics_coordinator")
    variables = config_entry.data.get("variables", [])

    entities: list[BinarySensorEntity] = []

    if coordinator is not None:
        entities.extend(
            SSCPBinarySensor(coordinator, client, variable, config_entry.entry_id, hass)
            for variable in variables
            if variable.get("entity_type") == "binary_sensor"
        )

    if diagnostics_coordinator is not None:
        entities.extend(
            SSCPDiagnosticBinarySensor(
                diagnostics_coordinator,
                config_entry.entry_id,
                config_entry.data.get("PLC_Name", "PLC"),
                descriptor,
            )
            for descriptor in COMMON_DIAGNOSTIC_BINARY_SENSORS
        )
        if config_entry.data.get("communication_mode") != COMM_MODE_WEBPANEL:
            entities.extend(
                SSCPDiagnosticBinarySensor(
                    diagnostics_coordinator,
                    config_entry.entry_id,
                    config_entry.data.get("PLC_Name", "PLC"),
                    descriptor,
                )
                for descriptor in SSCP_DIAGNOSTIC_BINARY_SENSORS
            )

    if entities:
        async_add_entities(entities)


class SSCPBinarySensor(SSCPBaseEntity, BinarySensorEntity):
    def __init__(self, coordinator, client, config, entry_id, hass):
        super().__init__(coordinator, client, config, entry_id, hass)
        self._attr_name = config["name"]
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}"

    @property
    def is_on(self):
        value = self.current_value
        return None if value is None else bool(value)


class SSCPDiagnosticBinarySensor(CoordinatorEntity[SSCPDiagnosticsCoordinator], BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: SSCPDiagnosticsCoordinator,
        entry_id: str,
        plc_name: str,
        descriptor: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._descriptor = descriptor
        self._entry_id = entry_id
        self._plc_name = plc_name
        self._attr_name = f"{plc_name} {descriptor['name']}"
        self._attr_unique_id = f"{entry_id}_diag_{descriptor['key']}_binary"

    @property
    def device_info(self):
        transport_name = getattr(self.coordinator.client, "transport_name", "sscp").upper()
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": self._plc_name,
            "manufacturer": "Domat/Mervis",
            "model": f"{transport_name} PLC",
        }

    @property
    def is_on(self):
        extractor: Callable[[dict[str, Any]], bool] = self._descriptor["extractor"]
        return extractor(self.coordinator.data or {})
