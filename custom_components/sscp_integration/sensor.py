from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COMM_MODE_WEBPANEL, DOMAIN
from .coordinator import SSCPDataCoordinator, SSCPDiagnosticsCoordinator
from .coordinator import variable_key
from .entity import SSCPBaseEntity, async_apply_entity_area, build_plc_device_info
from .vlist import normalize_unit_of_measurement

_LOGGER = logging.getLogger(__name__)

UNIT_DEVICE_CLASS_MAP = {
    "Â°C": SensorDeviceClass.TEMPERATURE,
    "Â°F": SensorDeviceClass.TEMPERATURE,
    "Pa": SensorDeviceClass.PRESSURE,
    "kPa": SensorDeviceClass.PRESSURE,
    "bar": SensorDeviceClass.PRESSURE,
    "m": SensorDeviceClass.DISTANCE,
    "cm": SensorDeviceClass.DISTANCE,
    "mm": SensorDeviceClass.DISTANCE,
    "V": SensorDeviceClass.VOLTAGE,
    "mV": SensorDeviceClass.VOLTAGE,
    "A": SensorDeviceClass.CURRENT,
    "mA": SensorDeviceClass.CURRENT,
    "Hz": SensorDeviceClass.FREQUENCY,
    "W": SensorDeviceClass.POWER,
    "kW": SensorDeviceClass.POWER,
    "kWh": SensorDeviceClass.ENERGY,
    "%": SensorDeviceClass.HUMIDITY,
    "degC": SensorDeviceClass.TEMPERATURE,
    "degF": SensorDeviceClass.TEMPERATURE,
    "°C": SensorDeviceClass.TEMPERATURE,
    "°F": SensorDeviceClass.TEMPERATURE,
    "C": SensorDeviceClass.TEMPERATURE,
    "F": SensorDeviceClass.TEMPERATURE,
}

SENSOR_DEVICE_CLASS_BY_VALUE = {member.value: member for member in SensorDeviceClass}
SENSOR_STATE_CLASS_BY_VALUE = {member.value: member for member in SensorStateClass}


def _coerce_sensor_device_class(value: str | None) -> SensorDeviceClass | str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    return SENSOR_DEVICE_CLASS_BY_VALUE.get(normalized, normalized)


def _coerce_sensor_state_class(value: str | None) -> SensorStateClass | str | None:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    return SENSOR_STATE_CLASS_BY_VALUE.get(normalized, normalized)


def _dig(data: dict[str, Any], *path: str) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


def _runtime_running(data: dict[str, Any]) -> bool | None:
    value = _dig(data, "plc_statistics", "runtime", "evaluator_state_label")
    if value is None:
        return None
    return str(value) == "RunningNormalTasks"


def _coordinator_metrics_attributes(data: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(_dig(data, "metrics") or {})
    metrics.pop("last_refresh_started_at", None)
    metrics.pop("last_refresh_completed_at", None)
    return metrics


COMMON_DIAGNOSTIC_SENSORS: list[dict[str, Any]] = [
    {
        "key": "transport",
        "name": "Communication Backend",
        "path": ("transport",),
    },
    {
        "key": "protocol",
        "name": "Protocol Version",
        "path": ("capabilities", "protocol_version"),
    },
    {
        "key": "rights_group",
        "name": "Rights Group",
        "path": ("capabilities", "right_group_label"),
    },
    {
        "key": "configured_entities",
        "name": "Configured Entities",
        "path": ("metrics", "configured_variable_count"),
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "readable_points",
        "name": "Readable Points",
        "path": ("metrics", "readable_variable_count"),
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "last_read_duration",
        "name": "Last Read Duration",
        "path": ("metrics", "last_refresh_duration_ms"),
        "unit": "ms",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "successful_polls",
        "name": "Successful Polls",
        "path": ("metrics", "successful_refresh_count"),
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "failed_polls",
        "name": "Failed Polls",
        "path": ("metrics", "failed_refresh_count"),
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "last_value_refresh",
        "name": "Last Value Refresh",
        "path": ("metrics", "last_refresh_completed_at"),
        "device_class": SensorDeviceClass.TIMESTAMP,
    },
    {
        "key": "last_diag_refresh",
        "name": "Last Diagnostics Refresh",
        "path": ("updated_at",),
        "device_class": SensorDeviceClass.TIMESTAMP,
        "extra_attributes": _coordinator_metrics_attributes,
    },
]

SSCP_DIAGNOSTIC_SENSORS: list[dict[str, Any]] = [
    {
        "key": "runtime_state",
        "name": "Runtime State",
        "path": ("plc_statistics", "runtime", "evaluator_state_label"),
        "extra_attributes": lambda data: dict(_dig(data, "plc_statistics", "runtime") or {}),
    },
    {
        "key": "run_mode",
        "name": "Run Mode",
        "path": ("plc_statistics", "runtime", "run_mode_label"),
    },
    {
        "key": "uptime",
        "name": "PLC Uptime",
        "path": ("plc_statistics", "runtime", "uptime"),
    },
    {
        "key": "free_heap",
        "name": "Free Heap",
        "path": ("plc_statistics", "memory", "free_heap_kb"),
        "unit": "kB",
        "state_class": SensorStateClass.MEASUREMENT,
        "extra_attributes": lambda data: dict(_dig(data, "plc_statistics", "memory") or {}),
    },
    {
        "key": "free_code_space",
        "name": "Free Code Space",
        "path": ("plc_statistics", "memory", "free_code_space_kb"),
        "unit": "kB",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "allocator_free",
        "name": "Allocator Free Space",
        "path": ("plc_statistics", "memory", "allocator_free_space_kb"),
        "unit": "kB",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    {
        "key": "platform_id",
        "name": "Platform ID",
        "path": ("basic_info", "platform_id"),
        "extra_attributes": lambda data: dict(_dig(data, "basic_info") or {}),
    },
    {
        "key": "proxy_status",
        "name": "Proxy Status",
        "path": ("plc_statistics", "proxy", "proxy_status_label"),
        "extra_attributes": lambda data: dict(_dig(data, "plc_statistics", "proxy") or {}),
    },
]


async def async_setup_entry(hass, config_entry, async_add_entities):
    entry_data = hass.data[DOMAIN][config_entry.entry_id]
    client = entry_data["client"]
    coordinator: SSCPDataCoordinator | None = entry_data.get("coordinator")
    diagnostics_coordinator: SSCPDiagnosticsCoordinator | None = entry_data.get("diagnostics_coordinator")
    variables = config_entry.data.get("variables", [])
    scheduler_entities = config_entry.data.get("scheduler_entities", [])

    entities: list[SensorEntity] = []

    if coordinator is not None:
        entities.extend(
            SSCPVariableSensor(coordinator, client, variable, config_entry.entry_id, hass)
            for variable in variables
            if variable.get("entity_type") == "sensor"
        )
        entities.extend(
            SSCPSchedulerSensor(
                coordinator,
                client,
                scheduler_config,
                config_entry.entry_id,
                config_entry.data.get("PLC_Name", "PLC"),
                hass,
            )
            for scheduler_config in scheduler_entities
        )

    if diagnostics_coordinator is not None:
        entities.extend(
            SSCPDiagnosticSensor(diagnostics_coordinator, config_entry.entry_id, config_entry.data.get("PLC_Name", "PLC"), descriptor)
            for descriptor in COMMON_DIAGNOSTIC_SENSORS
        )
        if config_entry.data.get("communication_mode") != COMM_MODE_WEBPANEL:
            entities.extend(
                SSCPDiagnosticSensor(
                    diagnostics_coordinator,
                    config_entry.entry_id,
                    config_entry.data.get("PLC_Name", "PLC"),
                    descriptor,
                )
                for descriptor in SSCP_DIAGNOSTIC_SENSORS
            )

    if entities:
        async_add_entities(entities)


class SSCPVariableSensor(SSCPBaseEntity, SensorEntity):
    def __init__(self, coordinator, client, config, entry_id, hass):
        super().__init__(coordinator, client, config, entry_id, hass)
        unit = normalize_unit_of_measurement(config.get("unit_of_measurement"))
        configured_device_class = _coerce_sensor_device_class(config.get("device_class"))
        configured_state_class = _coerce_sensor_state_class(config.get("state_class"))
        suggested_display_precision = config.get("suggested_display_precision")
        self._attr_name = config["name"]
        self._attr_native_unit_of_measurement = unit or None
        self._attr_device_class = configured_device_class or UNIT_DEVICE_CLASS_MAP.get(unit)
        self._attr_state_class = configured_state_class or (None if config.get("type") == "DT" else SensorStateClass.MEASUREMENT)
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}"
        self._attr_suggested_display_precision = (
            int(suggested_display_precision) if suggested_display_precision is not None else None
        )

        if config.get("type") == "DT":
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._attr_state_class = None

    @property
    def native_value(self):
        value = self.current_value
        if isinstance(value, datetime):
            return value
        return value


class SSCPSchedulerSensor(CoordinatorEntity[SSCPDataCoordinator], SensorEntity):
    def __init__(self, coordinator, client, config, entry_id, plc_name, hass):
        super().__init__(coordinator)
        self._client = client
        self._config = config
        self._entry_id = entry_id
        self._plc_name = plc_name
        self.hass = hass
        suggested_display_precision = config.get("suggested_display_precision")
        self._attr_name = str(config.get("name") or "Scheduler")
        self._attr_unique_id = f"{entry_id}_scheduler_{config.get('entity_key')}"
        self._attr_suggested_display_precision = (
            int(suggested_display_precision) if suggested_display_precision is not None else None
        )

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

    def _coordinator_value(self, ref: dict[str, Any] | None) -> Any:
        if not isinstance(ref, dict):
            return None
        return self.coordinator.data.get(variable_key(ref))

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

    @property
    def native_value(self):
        output = self._coordinator_value(self._config.get("out_var"))
        if output is None:
            output = self._coordinator_value(self._config.get("default_value_var"))
        if self._config.get("kind") == "bool":
            if output is None:
                return None
            return "on" if bool(output) else "off"
        return output

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        attributes = {
            "root_name": self._config.get("root_name"),
            "kind": self._config.get("kind"),
            "supports_exceptions": bool(self._config.get("supports_exceptions")),
            "point_capacity": self._config.get("point_capacity"),
            "exception_capacity": self._config.get("exception_capacity"),
            "default_value": self._coordinator_value(self._config.get("default_value_var")),
            "output_value": self._coordinator_value(self._config.get("out_var")),
            "editor_hint": "Pouzij SSCP Studio nebo budouci dashboard kartu pro upravu tydenniho programu.",
        }
        return attributes


class SSCPDiagnosticSensor(CoordinatorEntity[SSCPDiagnosticsCoordinator], SensorEntity):
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
        self._attr_unique_id = f"{entry_id}_diag_{descriptor['key']}"
        self._attr_native_unit_of_measurement = descriptor.get("unit")
        self._attr_device_class = descriptor.get("device_class")
        self._attr_state_class = descriptor.get("state_class")

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
    def available(self) -> bool:
        return super().available and self.coordinator.data is not None

    @property
    def native_value(self):
        value = _dig(self.coordinator.data or {}, *self._descriptor["path"])
        if isinstance(value, datetime):
            return value
        return value

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        extractor: Callable[[dict[str, Any]], dict[str, Any]] | None = self._descriptor.get("extra_attributes")
        if extractor is None:
            return None
        try:
            attributes = extractor(self.coordinator.data or {})
        except Exception as err:
            _LOGGER.debug("Diagnostic attributes build failed for %s: %s", self.entity_id, err)
            return None
        return attributes or None
