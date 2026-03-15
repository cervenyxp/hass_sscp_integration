from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS, DOMAIN
from .studio_models import (
    iter_climate_variable_refs,
    iter_cover_variable_refs,
    iter_fan_variable_refs,
    iter_humidifier_variable_refs,
    iter_light_variable_refs,
    iter_lock_variable_refs,
    iter_scheduler_entity_refs,
    iter_siren_variable_refs,
    iter_valve_variable_refs,
    iter_vacuum_variable_refs,
    iter_water_heater_variable_refs,
)
from .transport import PLCClientProtocol


def variable_key(variable: dict[str, Any]) -> str:
    return (
        f"{variable.get('uid')}:{variable.get('offset', 0)}:{variable.get('length', 1)}:"
        f"{variable.get('name_vlist') or variable.get('name')}"
    )


def is_readable_variable(variable: dict[str, Any]) -> bool:
    return variable.get("entity_type") != "button"


class SSCPDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Batch refresh configured variables through one coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: PLCClientProtocol) -> None:
        scan_interval = int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
            )
        )
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=max(1, scan_interval)),
        )
        self.entry = entry
        self.client = client
        self.last_refresh_started_at: datetime | None = None
        self.last_refresh_completed_at: datetime | None = None
        self.last_refresh_duration_ms: float | None = None
        self.successful_refresh_count = 0
        self.failed_refresh_count = 0

    @property
    def configured_variables(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("variables", []))

    @property
    def configured_climates(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("climate_entities", []))

    @property
    def configured_lights(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("light_entities", []))

    @property
    def configured_covers(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("cover_entities", []))

    @property
    def configured_vacuums(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("vacuum_entities", []))

    @property
    def configured_fans(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("fan_entities", []))

    @property
    def configured_humidifiers(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("humidifier_entities", []))

    @property
    def configured_water_heaters(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("water_heater_entities", []))

    @property
    def configured_locks(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("lock_entities", []))

    @property
    def configured_valves(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("valve_entities", []))

    @property
    def configured_sirens(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("siren_entities", []))

    @property
    def configured_scheduler_entities(self) -> list[dict[str, Any]]:
        return list(self.entry.data.get("scheduler_entities", []))

    def metrics_payload(self) -> dict[str, Any]:
        requests = self._build_requests()
        return {
            "configured_variable_count": (
                len(self.configured_variables)
                + len(self.configured_climates)
                + len(self.configured_lights)
                + len(self.configured_covers)
                + len(self.configured_vacuums)
                + len(self.configured_fans)
                + len(self.configured_humidifiers)
                + len(self.configured_water_heaters)
                + len(self.configured_locks)
                + len(self.configured_valves)
                + len(self.configured_sirens)
                + len(self.configured_scheduler_entities)
            ),
            "readable_variable_count": len(requests),
            "last_refresh_started_at": self.last_refresh_started_at,
            "last_refresh_completed_at": self.last_refresh_completed_at,
            "last_refresh_duration_ms": self.last_refresh_duration_ms,
            "successful_refresh_count": self.successful_refresh_count,
            "failed_refresh_count": self.failed_refresh_count,
        }

    def _build_requests(self) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for variable in self.configured_variables:
            if not is_readable_variable(variable):
                continue
            request_key = variable_key(variable)
            if request_key in seen_keys:
                continue
            seen_keys.add(request_key)
            requests.append({**variable, "key": request_key})

        for climate in self.configured_climates:
            for variable in iter_climate_variable_refs(climate):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})

        for light in self.configured_lights:
            for variable in iter_light_variable_refs(light):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})

        for cover in self.configured_covers:
            for variable in iter_cover_variable_refs(cover):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})

        for vacuum in self.configured_vacuums:
            for variable in iter_vacuum_variable_refs(vacuum):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})

        for fan in self.configured_fans:
            for variable in iter_fan_variable_refs(fan):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})

        for humidifier in self.configured_humidifiers:
            for variable in iter_humidifier_variable_refs(humidifier):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})

        for water_heater in self.configured_water_heaters:
            for variable in iter_water_heater_variable_refs(water_heater):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})

        for lock in self.configured_locks:
            for variable in iter_lock_variable_refs(lock):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})

        for valve in self.configured_valves:
            for variable in iter_valve_variable_refs(valve):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})

        for siren in self.configured_sirens:
            for variable in iter_siren_variable_refs(siren):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})

        for scheduler_entity in self.configured_scheduler_entities:
            for variable in iter_scheduler_entity_refs(scheduler_entity):
                request_key = variable_key(variable)
                if request_key in seen_keys:
                    continue
                seen_keys.add(request_key)
                requests.append({**variable, "key": request_key})
        return requests

    def _sync_read(self, requests: list[dict[str, Any]]) -> dict[str, Any]:
        return self.client.read_variables(requests)

    async def _async_update_data(self) -> dict[str, Any]:
        requests = self._build_requests()
        if not requests:
            return {}
        started = datetime.now(UTC)
        started_perf = perf_counter()
        self.last_refresh_started_at = started
        try:
            result = await self.hass.async_add_executor_job(self._sync_read, requests)
            self.last_refresh_completed_at = datetime.now(UTC)
            self.last_refresh_duration_ms = (perf_counter() - started_perf) * 1000.0
            self.successful_refresh_count += 1
            return result
        except Exception as err:
            self.last_refresh_completed_at = datetime.now(UTC)
            self.last_refresh_duration_ms = (perf_counter() - started_perf) * 1000.0
            self.failed_refresh_count += 1
            raise UpdateFailed(str(err)) from err


class SSCPDiagnosticsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Periodic PLC diagnostics refresh for system entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: PLCClientProtocol,
        data_coordinator: SSCPDataCoordinator | None,
    ) -> None:
        scan_interval = int(
            entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
            )
        )
        super().__init__(
            hass,
            logger=logging.getLogger(__name__),
            name=f"{DOMAIN}_{entry.entry_id}_diagnostics",
            update_interval=timedelta(seconds=max(15, scan_interval * 3)),
        )
        self.entry = entry
        self.client = client
        self.data_coordinator = data_coordinator

    def _collect_sync(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "connected": bool(getattr(self.client, "connected", False) and getattr(self.client, "loggedin", False)),
            "transport": getattr(self.client, "transport_name", "sscp"),
            "capabilities": {},
            "basic_info": {},
            "plc_statistics": {},
            "time": {},
            "errors": {},
        }

        try:
            payload["capabilities"] = self.client.capabilities()
        except Exception as err:
            payload["errors"]["capabilities"] = str(err)

        try:
            payload["basic_info"] = self.client.get_basic_info(requested_size=0)
        except Exception as err:
            payload["errors"]["basic_info"] = str(err)

        try:
            payload["plc_statistics"] = self.client.get_plc_statistics()
        except Exception as err:
            payload["errors"]["plc_statistics"] = str(err)

        for key, mode in (
            ("utc", "utc"),
            ("local", "local"),
            ("timezone_offset", "timezone"),
            ("daylight_offset", "daylight"),
        ):
            try:
                getter = self.client.get_time if key in {"utc", "local"} else self.client.get_time_offset
                payload["time"][key] = getter(mode)
            except Exception as err:
                payload["errors"][key] = str(err)

        if self.data_coordinator is not None:
            payload["metrics"] = self.data_coordinator.metrics_payload()
        else:
            payload["metrics"] = {}

        payload["updated_at"] = datetime.now(UTC)
        return payload

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.hass.async_add_executor_job(self._collect_sync)
        except Exception as err:
            raise UpdateFailed(str(err)) from err
