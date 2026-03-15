from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from functools import partial
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    COMM_MODE_WEBPANEL,
    CONF_COMMUNICATION_MODE,
    CONF_WEBPANEL_CONNECTION,
    CONF_WEBPANEL_SCHEME,
    DOMAIN,
    SIGNAL_RUNTIME_STATE_UPDATED,
    SUPPORTED_COMMUNICATION_MODES,
)
from .coordinator import variable_key
from .studio_models import (
    build_variable_ref,
    climate_entity_payload,
    compact_weekly_items,
    cover_entity_payload,
    detect_scheduler_blocks,
    fan_entity_payload,
    group_weekly_points,
    humidifier_entity_payload,
    light_entity_payload,
    lock_entity_payload,
    minutes_to_day_time,
    scheduler_entity_payload,
    scheduler_catalog_payload,
    schedule_value_from_ui,
    siren_entity_payload,
    valve_entity_payload,
    vacuum_entity_payload,
    water_heater_entity_payload,
)
from .transport import PLCClientProtocol, communication_mode_from_data, has_connection_settings
from .vlist import (
    ALL_ENTITY_TYPES,
    PLC_TYPE_TO_ENTITIES,
    SUPPORTED_PLC_TYPES,
    build_entity_entry,
    build_tree_node,
    guess_default_entity_type,
    is_duplicate_variable,
    list_vlist_files,
    load_vlist_map,
    normalize_unit_of_measurement,
    resolve_vlist_file,
    sanitize_vlist_file_name,
    write_vlist_bytes,
)

_LOGGER = logging.getLogger(__name__)


_ENTRY_STATE_LABELS = {
    "loaded": "Nacteno",
    "not_loaded": "Nenacteno",
    "setup_error": "Chyba pri nacitani",
    "setup_retry": "Opakovani nacitani",
    "setup_in_progress": "Nacitam",
    "migration_error": "Chyba migrace",
    "failed_unload": "Chyba pri uvolneni",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _entry_state_key(entry: ConfigEntry) -> str:
    state = getattr(entry, "state", None)
    return str(getattr(state, "value", state or "unknown")).strip().lower() or "unknown"


def _entry_state_label(entry: ConfigEntry) -> str:
    state_key = _entry_state_key(entry)
    return _ENTRY_STATE_LABELS.get(state_key, state_key.replace("_", " ").title())


def _entry_state_error(entry: ConfigEntry) -> str | None:
    state_key = _entry_state_key(entry)
    if state_key == "loaded":
        return None
    if state_key == "setup_in_progress":
        return "PLC entry se zrovna nacita nebo reloaduje. Zkus obnovit panel za okamzik."
    if state_key == "setup_retry":
        return "Home Assistant se pokousi PLC entry znovu nacist po chybe spojeni nebo konfigurace."
    if state_key == "setup_error":
        return "PLC entry se nepodarilo korektne nacist. Zkontroluj spojeni a uloz konfiguraci znovu."
    if state_key == "not_loaded":
        return "PLC entry neni aktivne nactena. Muze jit o probihajici reload nebo chybu konfigurace."
    if state_key == "migration_error":
        return "PLC entry ma problem s migraci konfigurace."
    if state_key == "failed_unload":
        return "Predchozi unload PLC entry skoncil chybou."
    return f"PLC entry je docasne mimo runtime ({_entry_state_label(entry)})."


def _normalize_climate_mode_map(mode_map: dict[str, str] | None) -> dict[str, str]:
    allowed = {"off", "heat", "cool", "heat_cool", "auto", "dry", "fan_only"}
    normalized: dict[str, str] = {}
    for raw_key, raw_value in (mode_map or {}).items():
        key = str(raw_key).strip()
        value = str(raw_value).strip().lower()
        if not key or not value:
            continue
        if value not in allowed:
            raise ValueError(f"Nepodporovany HVAC mode {raw_value}.")
        normalized[key] = value
    return normalized


def _normalize_label_map(label_map: dict[str, str] | None) -> dict[str, str]:
    return {
        str(raw_key).strip(): str(raw_value).strip()
        for raw_key, raw_value in (label_map or {}).items()
        if str(raw_key).strip() and str(raw_value).strip()
    }


def _normalize_vacuum_status_map(status_map: dict[str, str] | None) -> dict[str, str]:
    allowed = {"cleaning", "docked", "returning", "idle", "paused", "error"}
    normalized: dict[str, str] = {}
    for raw_key, raw_value in (status_map or {}).items():
        key = str(raw_key).strip()
        value = str(raw_value).strip().lower()
        if not key or not value:
            continue
        if value not in allowed:
            raise ValueError(f"Nepodporovany vacuum stav {raw_value}.")
        normalized[key] = value
    return normalized


def _normalize_fan_direction_map(direction_map: dict[str, str] | None) -> dict[str, str]:
    allowed = {"forward", "reverse"}
    normalized: dict[str, str] = {}
    for raw_key, raw_value in (direction_map or {}).items():
        key = str(raw_key).strip()
        value = str(raw_value).strip().lower()
        if not key or not value:
            continue
        if value not in allowed:
            raise ValueError(f"Nepodporovany smer ventilatoru {raw_value}.")
        normalized[key] = value
    return normalized


def _normalize_lock_state_map(state_map: dict[str, str] | None) -> dict[str, str]:
    allowed = {"locked", "unlocked", "locking", "unlocking", "jammed", "open", "opening"}
    normalized: dict[str, str] = {}
    for raw_key, raw_value in (state_map or {}).items():
        key = str(raw_key).strip()
        value = str(raw_value).strip().lower()
        if not key or not value:
            continue
        if value not in allowed:
            raise ValueError(f"Nepodporovany lock stav {raw_value}.")
        normalized[key] = value
    return normalized


def _parse_ui_datetime(raw_value: str, mode: str) -> datetime:
    normalized = str(raw_value or "").strip()
    if not normalized:
        raise ValueError("Cas PLC nesmi byt prazdny.")
    value = datetime.fromisoformat(normalized)
    if value.tzinfo is not None:
        return value
    if mode == "local":
        return value.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return value.replace(tzinfo=UTC)


def _coerce_plc_write_value(raw_value: Any, plc_type: str) -> Any:
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


class SSCPRuntime:
    """Entry-scoped runtime state for diagnostics and panel operations."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: PLCClientProtocol | None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.client = client
        self.vlist_data: dict[str, dict[str, Any]] = {}
        self.protocol_state: dict[str, Any] = {}
        self.last_error: str | None = None
        self.last_updated: datetime | None = None

    @property
    def plc_name(self) -> str:
        return self.entry.data.get("PLC_Name", self.entry.title or "PLC")

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

    @property
    def has_connection_settings(self) -> bool:
        return has_connection_settings(dict(self.entry.data))

    @property
    def communication_mode(self) -> str:
        return communication_mode_from_data(dict(self.entry.data))

    @property
    def is_connected(self) -> bool:
        return bool(
            self.client
            and getattr(self.client, "connected", False)
            and getattr(self.client, "loggedin", False)
        )

    async def async_initialize(self) -> None:
        await self.async_ensure_vlist_data()
        if self.client is None:
            self.last_error = "Připojení ještě není nakonfigurované."
            self.last_updated = datetime.now(UTC)
            return
        await self.async_refresh_protocol_state()

    async def async_ensure_vlist_data(self) -> None:
        if self.vlist_data:
            return
        vlist_file = self.entry.data.get("vlist_file")
        if not vlist_file:
            return
        path = Path(vlist_file)
        if not await self.hass.async_add_executor_job(path.exists):
            return
        self.vlist_data = await self.hass.async_add_executor_job(load_vlist_map, path)

    def _refresh_sync(self) -> dict[str, Any]:
        if self.client is None:
            raise ValueError("SSCP client is not configured.")
        state: dict[str, Any] = {
            "capabilities": self.client.capabilities(),
            "basic_info": None,
            "plc_statistics": None,
            "time": {},
        }

        try:
            state["basic_info"] = self.client.get_basic_info(requested_size=0)
        except Exception as err:
            state["basic_info_error"] = str(err)

        try:
            state["plc_statistics"] = self.client.get_plc_statistics()
        except Exception as err:
            state["plc_statistics_error"] = str(err)

        try:
            state["time"]["utc"] = self.client.get_time("utc")
        except Exception as err:
            state["time"]["utc_error"] = str(err)

        try:
            state["time"]["local"] = self.client.get_time("local")
        except Exception as err:
            state["time"]["local_error"] = str(err)

        try:
            state["time"]["timezone_offset"] = self.client.get_time_offset("timezone")
        except Exception as err:
            state["time"]["timezone_offset_error"] = str(err)

        try:
            state["time"]["daylight_offset"] = self.client.get_time_offset("daylight")
        except Exception as err:
            state["time"]["daylight_offset_error"] = str(err)

        return state

    async def async_refresh_protocol_state(self) -> dict[str, Any]:
        if self.client is None:
            self.last_error = "Připojení ještě není nakonfigurované."
            self.last_updated = datetime.now(UTC)
            payload = await self.async_state_payload()
            async_dispatcher_send(self.hass, SIGNAL_RUNTIME_STATE_UPDATED, payload)
            return payload
        try:
            self.protocol_state = await self.hass.async_add_executor_job(self._refresh_sync)
            self.last_error = None
        except Exception as err:
            self.last_error = str(err)
            _LOGGER.error("Failed to refresh protocol state for %s: %s", self.plc_name, err)
        self.last_updated = datetime.now(UTC)
        payload = await self.async_state_payload()
        async_dispatcher_send(self.hass, SIGNAL_RUNTIME_STATE_UPDATED, payload)
        return payload

    def _variable_payload(self, variable: dict[str, Any]) -> dict[str, Any]:
        allowed = PLC_TYPE_TO_ENTITIES.get(variable.get("type", ""), ["sensor"])
        return {
            "key": variable_key(variable),
            "name": variable.get("name"),
            "name_vlist": variable.get("name_vlist") or variable.get("name"),
            "uid": variable.get("uid"),
            "offset": variable.get("offset", 0),
            "length": variable.get("length", 1),
            "type": variable.get("type"),
            "entity_type": variable.get("entity_type"),
            "unit_of_measurement": normalize_unit_of_measurement(variable.get("unit_of_measurement")),
            "device_class": variable.get("device_class"),
            "state_class": variable.get("state_class"),
            "suggested_display_precision": variable.get("suggested_display_precision"),
            "area_id": variable.get("area_id"),
            "select_options": dict(variable.get("select_options") or {}),
            "min_value": variable.get("min_value"),
            "max_value": variable.get("max_value"),
            "step": variable.get("step"),
            "mode": variable.get("mode"),
            "press_time": variable.get("press_time"),
            "allowed_entity_types": allowed,
            "quick_entity_types": allowed,
            "default_entity_type": guess_default_entity_type(
                str(variable.get("type", "")),
                str(variable.get("name_vlist") or variable.get("name") or ""),
            ),
        }

    def _protocol_features(self) -> list[dict[str, Any]]:
        if self.communication_mode == COMM_MODE_WEBPANEL:
            return [
                {
                    "label": "WebPanel values.cgi",
                    "status": "ok",
                    "detail": "HTTP polling datovych bodu pres WebPanel API",
                },
                {
                    "label": "WebPanel command.cgi",
                    "status": "warning",
                    "detail": "HTTP zapis pres command.cgi, doporucena validace na cilovem panelu",
                },
                {
                    "label": "PLC Statistics",
                    "status": "warning",
                    "detail": "WebPanel API neposkytuje stejna runtime data jako SSCP",
                },
                {
                    "label": "Time Setup Extended",
                    "status": "warning",
                    "detail": "Synchronizace a detailni casove funkce jsou jen v SSCP rezimu",
                },
                {
                    "label": "System DateTime Setter",
                    "status": "warning",
                    "detail": "Nastaveni PLC casu neni ve WebPanel API rezimu v teto integraci k dispozici",
                },
            ]

        right_group = self.client.right_group if self.client else 0
        right_group = right_group or 0
        return [
            {
                "label": "Get Basic Info",
                "status": "ok" if self.protocol_state.get("basic_info") else "warning",
                "detail": "Autodetekce a identifikace PLC",
            },
            {
                "label": "File Transfer",
                "status": "ok" if right_group >= 0x80 else "warning",
                "detail": "/var/direct, /sys/caps, /log, /d/*",
            },
            {
                "label": "PLC Statistics",
                "status": "ok",
                "detail": "Runtime, memory, sections, proxy",
            },
            {
                "label": "Batch Read / Write",
                "status": "ok",
                "detail": "Dávkové čtení a zápis až 64 proměnných",
            },
            {
                "label": "Time Setup Extended",
                "status": "ok",
                "detail": "UTC, local time, timezone and DST offsets",
            },
            {
                "label": "System DateTime Setter",
                "status": "ok",
                "detail": "Priame nastaveni PLC UTC nebo local time z UI a systemovych datetime entit",
            },
        ]

    def _scheduler_blocks(self) -> dict[str, dict[str, Any]]:
        if not self.vlist_data:
            return {}
        return detect_scheduler_blocks(self.vlist_data)

    def state_payload(self, *, available_vlists: list[str] | None = None) -> dict[str, Any]:
        entity_counts = Counter(variable.get("entity_type", "sensor") for variable in self.configured_variables)
        if self.configured_climates:
            entity_counts["climate"] += len(self.configured_climates)
        if self.configured_lights:
            entity_counts["light_composer"] += len(self.configured_lights)
        if self.configured_covers:
            entity_counts["cover"] += len(self.configured_covers)
        if self.configured_vacuums:
            entity_counts["vacuum"] += len(self.configured_vacuums)
        if self.configured_fans:
            entity_counts["fan"] += len(self.configured_fans)
        if self.configured_humidifiers:
            entity_counts["humidifier"] += len(self.configured_humidifiers)
        if self.configured_water_heaters:
            entity_counts["water_heater"] += len(self.configured_water_heaters)
        if self.configured_locks:
            entity_counts["lock"] += len(self.configured_locks)
        if self.configured_valves:
            entity_counts["valve"] += len(self.configured_valves)
        if self.configured_sirens:
            entity_counts["siren"] += len(self.configured_sirens)
        if self.configured_scheduler_entities:
            entity_counts["scheduler"] += len(self.configured_scheduler_entities)
        selected_vlist_path = self.entry.data.get("vlist_file") or ""
        selected_vlist_name = Path(selected_vlist_path).name if selected_vlist_path else ""
        scheduler_blocks = self._scheduler_blocks()
        vlist_summary = {
            "file": selected_vlist_path,
            "file_name": selected_vlist_name,
            "loaded": bool(self.vlist_data),
            "total_variables": len(self.vlist_data),
            "available_files": list(available_vlists or []),
        }

        return {
            "entry_id": self.entry.entry_id,
            "plc_name": self.plc_name,
            "entry_state": _entry_state_key(self.entry),
            "entry_state_label": _entry_state_label(self.entry),
            "runtime_available": self.entry.entry_id in self.hass.data.get(DOMAIN, {}),
            "communication_mode": self.communication_mode,
            "supported_communication_modes": list(SUPPORTED_COMMUNICATION_MODES),
            "host": self.entry.data.get("host"),
            "port": self.entry.data.get("port"),
            "sscp_address": self.entry.data.get("sscp_address"),
            "webpanel_connection": self.entry.data.get(CONF_WEBPANEL_CONNECTION, "defaultConnection"),
            "webpanel_scheme": self.entry.data.get(CONF_WEBPANEL_SCHEME, "http"),
            "username": self.entry.data.get("username"),
            "password": self.entry.data.get("password"),
            "scan_interval": self.entry.data.get("scan_interval", 5),
            "configuration_mode": self.entry.data.get("configuration_mode", "vlist"),
            "connection_ready": self.has_connection_settings,
            "connected": self.is_connected,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "last_error": self.last_error,
            "capabilities": _json_safe(
                self.protocol_state.get("capabilities", self.client.capabilities() if self.client else {})
            ),
            "basic_info": _json_safe(self.protocol_state.get("basic_info")),
            "plc_statistics": _json_safe(self.protocol_state.get("plc_statistics")),
            "time": _json_safe(self.protocol_state.get("time", {})),
            "variables": [self._variable_payload(variable) for variable in self.configured_variables],
            "climate_entities": [climate_entity_payload(entity) for entity in self.configured_climates],
            "light_entities": [light_entity_payload(entity) for entity in self.configured_lights],
            "cover_entities": [cover_entity_payload(entity) for entity in self.configured_covers],
            "vacuum_entities": [vacuum_entity_payload(entity) for entity in self.configured_vacuums],
            "fan_entities": [fan_entity_payload(entity) for entity in self.configured_fans],
            "humidifier_entities": [humidifier_entity_payload(entity) for entity in self.configured_humidifiers],
            "water_heater_entities": [water_heater_entity_payload(entity) for entity in self.configured_water_heaters],
            "lock_entities": [lock_entity_payload(entity) for entity in self.configured_locks],
            "valve_entities": [valve_entity_payload(entity) for entity in self.configured_valves],
            "siren_entities": [siren_entity_payload(entity) for entity in self.configured_sirens],
            "scheduler_entities": [scheduler_entity_payload(entity) for entity in self.configured_scheduler_entities],
            "entity_counts": dict(entity_counts),
            "scheduler_blocks": scheduler_catalog_payload(scheduler_blocks.values()),
            "supports_plc_time_control": bool(self.client and self.communication_mode != COMM_MODE_WEBPANEL),
            "vlist_summary": vlist_summary,
            "supported_plc_types": SUPPORTED_PLC_TYPES,
            "supported_entity_types": ALL_ENTITY_TYPES,
            "entity_type_catalog": PLC_TYPE_TO_ENTITIES,
            "protocol_features": self._protocol_features(),
        }

    async def async_state_payload(self) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        available_vlists = await self.hass.async_add_executor_job(list_vlist_files)
        return self.state_payload(available_vlists=available_vlists)

    async def async_browse_vlist(
        self,
        *,
        path: list[str] | None = None,
        filter_text: str = "",
        limit: int = 200,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        path = path or []
        if not self.vlist_data:
            return {"path": path, "folders": [], "variables": [], "total_matches": 0}

        names = sorted(
            name
            for name in self.vlist_data
            if not filter_text or filter_text.casefold() in name.casefold()
        )
        folders, leaves = build_tree_node(names, path)
        visible_leaves = leaves[: max(1, limit)]

        return {
            "path": path,
            "filter_text": filter_text,
            "folders": [{"name": folder, "path": [*path, folder]} for folder in folders],
            "variables": [
                self._variable_payload(self.vlist_data[name])
                for name in visible_leaves
            ],
            "total_matches": len(names),
            "truncated": len(leaves) > len(visible_leaves),
        }

    async def async_list_vlist_variables(
        self,
        *,
        filter_text: str = "",
        limit: int = 5000,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        if not self.vlist_data:
            return {"variables": [], "total_matches": 0}

        names = sorted(
            name
            for name in self.vlist_data
            if not filter_text or filter_text.casefold() in name.casefold()
        )
        visible_names = names[: max(1, limit)]
        return {
            "variables": [self._variable_payload(self.vlist_data[name]) for name in visible_names],
            "total_matches": len(names),
            "truncated": len(names) > len(visible_names),
        }

    async def async_add_variable(
        self,
        *,
        variable_name: str,
        entity_type: str | None = None,
        display_name: str | None = None,
        select_options: dict[str, str] | None = None,
        unit_of_measurement: str = "",
        device_class: str = "",
        state_class: str = "",
        suggested_display_precision: int | None = None,
        area_id: str = "",
        min_value: float | None = None,
        max_value: float | None = None,
        step: float | None = None,
        mode: str = "box",
        press_time: float | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        if variable_name not in self.vlist_data:
            raise ValueError(f"Variable {variable_name} was not found in vlist.")

        selected = self.vlist_data[variable_name]
        current_variables = self.configured_variables
        if is_duplicate_variable(current_variables, selected):
            raise ValueError("Variable is already configured.")

        chosen_entity_type = entity_type or guess_default_entity_type(selected["type"], selected["name"])
        normalized_select_options = {
            str(key): str(value)
            for key, value in (select_options or {}).items()
            if str(key).strip() and str(value).strip()
        }
        if chosen_entity_type == "select" and not normalized_select_options:
            raise ValueError("Select entita potrebuje alespon jednu volbu.")
        if chosen_entity_type == "number" and min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError("Minimalni hodnota nesmi byt vetsi nez maximalni.")
        normalized_mode = str(mode or "box").strip().lower() or "box"
        if normalized_mode not in {"box", "slider"}:
            raise ValueError("Number mode musi byt box nebo slider.")
        if chosen_entity_type == "number" and step is not None and step <= 0:
            raise ValueError("Krok number entity musi byt vetsi nez 0.")
        if chosen_entity_type == "button" and press_time is not None and press_time <= 0:
            raise ValueError("Button press time musi byt vetsi nez 0.")
        if suggested_display_precision is not None and suggested_display_precision < 0:
            raise ValueError("Presnost zobrazeni musi byt 0 nebo vetsi.")
        new_variable = build_entity_entry(
            selected,
            chosen_entity_type,
            name=display_name or selected["name"],
            unit_of_measurement=unit_of_measurement,
            device_class=str(device_class or "").strip(),
            state_class=str(state_class or "").strip(),
            suggested_display_precision=suggested_display_precision,
            area_id=str(area_id or "").strip(),
            min_value=min_value,
            max_value=max_value,
            step=step,
            mode=normalized_mode,
            press_time=press_time,
            select_options=normalized_select_options,
        )
        await self._update_variables([*current_variables, new_variable])
        return {"status": "reload_requested"}

    async def async_update_variable(
        self,
        *,
        variable_entry_key: str,
        display_name: str | None = None,
        select_options: dict[str, str] | None = None,
        unit_of_measurement: str = "",
        device_class: str = "",
        state_class: str = "",
        suggested_display_precision: int | None = None,
        area_id: str = "",
        min_value: float | None = None,
        max_value: float | None = None,
        step: float | None = None,
        mode: str = "box",
        press_time: float | None = None,
    ) -> dict[str, Any]:
        updated_variables = list(self.configured_variables)
        target = next((item for item in updated_variables if variable_key(item) == variable_entry_key), None)
        if target is None:
            raise ValueError("Entita pro upravu nebyla nalezena.")

        entity_type = str(target.get("entity_type") or "").strip()
        normalized_mode = str(mode or "box").strip().lower() or "box"
        if entity_type == "number" and min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError("Minimalni hodnota nesmi byt vetsi nez maximalni.")
        if entity_type == "number" and normalized_mode not in {"box", "slider"}:
            raise ValueError("Number mode musi byt box nebo slider.")
        if entity_type == "number" and step is not None and step <= 0:
            raise ValueError("Krok number entity musi byt vetsi nez 0.")
        if entity_type == "button" and press_time is not None and press_time <= 0:
            raise ValueError("Button press time musi byt vetsi nez 0.")
        if suggested_display_precision is not None and suggested_display_precision < 0:
            raise ValueError("Presnost zobrazeni musi byt 0 nebo vetsi.")

        normalized_select_options = {
            str(key): str(value)
            for key, value in (select_options or {}).items()
            if str(key).strip() and str(value).strip()
        }
        if entity_type == "select" and not normalized_select_options:
            raise ValueError("Select entita potrebuje alespon jednu volbu.")

        if display_name is not None:
            stripped_name = display_name.strip()
            if stripped_name:
                target["name"] = stripped_name
        if entity_type in {"sensor", "datetime", "number"}:
            target["unit_of_measurement"] = normalize_unit_of_measurement(unit_of_measurement)
        if entity_type in {"sensor", "number"}:
            target["device_class"] = str(device_class or "").strip()
        if entity_type == "sensor":
            target["state_class"] = str(state_class or "").strip()
        elif "state_class" in target:
            target.pop("state_class", None)
        if entity_type in {"sensor", "number"}:
            if suggested_display_precision is None:
                target.pop("suggested_display_precision", None)
            else:
                target["suggested_display_precision"] = int(suggested_display_precision)
        if area_id:
            target["area_id"] = str(area_id).strip()
        else:
            target.pop("area_id", None)
        if entity_type == "number":
            target["min_value"] = 0.0 if min_value is None else min_value
            target["max_value"] = 100.0 if max_value is None else max_value
            target["step"] = 1.0 if step is None else step
            target["mode"] = normalized_mode
        if entity_type == "button":
            target["press_time"] = 0.1 if press_time is None else float(press_time)
        if entity_type == "select":
            target["select_options"] = normalized_select_options

        await self._update_variables(updated_variables)
        return {"status": "reload_requested"}

    def _resolve_vlist_variable_ref(self, variable_name: str | None) -> dict[str, Any] | None:
        normalized = str(variable_name or "").strip()
        if not normalized:
            return None
        selected = self.vlist_data.get(normalized)
        if selected is None:
            raise ValueError(f"Datovy bod {normalized} nebyl ve vlistu nalezen.")
        return build_variable_ref(selected)

    def _resolve_required_vlist_variable_ref(self, variable_name: str | None, label: str) -> dict[str, Any]:
        ref = self._resolve_vlist_variable_ref(variable_name)
        if ref is None:
            raise ValueError(f"{label} je povinny.")
        return ref

    def _upsert_entity(self, items: list[dict[str, Any]], entity: dict[str, Any]) -> list[dict[str, Any]]:
        entity_key = str(entity.get("entity_key") or "").strip()
        if not entity_key:
            raise ValueError("Composer entita nema entity_key.")
        existing_index = next(
            (index for index, item in enumerate(items) if str(item.get("entity_key")) == entity_key),
            None,
        )
        updated = list(items)
        if existing_index is None:
            updated.append(entity)
        else:
            updated[existing_index] = entity
        return updated

    async def _update_entry_section(self, data_key: str, value: list[dict[str, Any]]) -> None:
        new_data = {**self.entry.data, data_key: value}
        self.hass.config_entries.async_update_entry(
            self.entry,
            title=new_data.get("PLC_Name", self.plc_name),
            data=new_data,
        )
        await self.hass.config_entries.async_reload(self.entry.entry_id)

    async def async_save_climate_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        area_id: str = "",
        temperature_unit: str = "°C",
        suggested_display_precision: int | None = None,
        min_temp: float | None = None,
        max_temp: float | None = None,
        temp_step: float | None = None,
        current_temperature_name: str = "",
        target_temperature_name: str = "",
        current_humidity_name: str = "",
        power_name: str = "",
        hvac_mode_name: str = "",
        preset_name: str = "",
        hvac_mode_map: dict[str, str] | None = None,
        preset_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        climate_name = str(name or "").strip()
        if not climate_name:
            raise ValueError("Nazev climate entity nesmi byt prazdny.")

        if suggested_display_precision is not None and suggested_display_precision < 0:
            raise ValueError("Presnost zobrazeni musi byt 0 nebo vetsi.")

        normalized_min_temp = 7.0 if min_temp is None else float(min_temp)
        normalized_max_temp = 35.0 if max_temp is None else float(max_temp)
        normalized_step = 0.5 if temp_step is None else float(temp_step)
        if normalized_min_temp > normalized_max_temp:
            raise ValueError("Minimalni teplota nesmi byt vetsi nez maximalni.")
        if normalized_step <= 0:
            raise ValueError("Krok teploty musi byt vetsi nez 0.")

        target_temperature_var = self._resolve_vlist_variable_ref(target_temperature_name)
        if target_temperature_var is None:
            raise ValueError("Climate composer potrebuje aspon cilovou teplotu pro zapis.")

        climate_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": climate_name,
            "area_id": str(area_id or "").strip(),
            "temperature_unit": normalize_unit_of_measurement(temperature_unit) or "°C",
            "suggested_display_precision": suggested_display_precision,
            "min_temp": normalized_min_temp,
            "max_temp": normalized_max_temp,
            "temp_step": normalized_step,
            "current_temperature_var": self._resolve_vlist_variable_ref(current_temperature_name),
            "target_temperature_var": target_temperature_var,
            "current_humidity_var": self._resolve_vlist_variable_ref(current_humidity_name),
            "power_var": self._resolve_vlist_variable_ref(power_name),
            "hvac_mode_var": self._resolve_vlist_variable_ref(hvac_mode_name),
            "preset_var": self._resolve_vlist_variable_ref(preset_name),
            "hvac_mode_map": _normalize_climate_mode_map(hvac_mode_map),
            "preset_map": _normalize_label_map(preset_map),
        }

        if climate_entry["hvac_mode_var"] and not climate_entry["hvac_mode_map"]:
            raise ValueError("Kdyz vyplnis HVAC mode point, musis doplnit i mapovani hodnot.")
        if climate_entry["preset_var"] and not climate_entry["preset_map"]:
            raise ValueError("Kdyz vyplnis preset point, musis doplnit i mapovani hodnot.")

        climates = list(self.configured_climates)
        existing_index = next(
            (index for index, item in enumerate(climates) if item.get("entity_key") == climate_entry["entity_key"]),
            None,
        )
        if existing_index is None:
            climates.append(climate_entry)
        else:
            climates[existing_index] = climate_entry

        await self._update_climates(climates)
        return {"status": "reload_requested", "entity_key": climate_entry["entity_key"]}

    async def async_delete_climate_entity(self, *, entity_key: str) -> dict[str, Any]:
        climates = list(self.configured_climates)
        updated = [item for item in climates if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(climates):
            raise ValueError("Climate entity pro smazani nebyla nalezena.")
        await self._update_climates(updated)
        return {"status": "reload_requested"}

    async def async_save_light_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        area_id: str = "",
        suggested_display_precision: int | None = None,
        brightness_scale: float | None = None,
        min_mireds: int | None = None,
        max_mireds: int | None = None,
        power_name: str = "",
        brightness_name: str = "",
        color_temp_name: str = "",
        hs_hue_name: str = "",
        hs_saturation_name: str = "",
        rgb_red_name: str = "",
        rgb_green_name: str = "",
        rgb_blue_name: str = "",
        white_name: str = "",
        effect_name: str = "",
        effect_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        entity_name = str(name or "").strip()
        if not entity_name:
            raise ValueError("Nazev light entity nesmi byt prazdny.")
        if suggested_display_precision is not None and suggested_display_precision < 0:
            raise ValueError("Presnost zobrazeni musi byt 0 nebo vetsi.")

        normalized_brightness_scale = 100.0 if brightness_scale is None else float(brightness_scale)
        if normalized_brightness_scale <= 0:
            raise ValueError("Brightness scale musi byt vetsi nez 0.")

        normalized_min_mireds = None if min_mireds in (None, "") else int(min_mireds)
        normalized_max_mireds = None if max_mireds in (None, "") else int(max_mireds)
        if (
            normalized_min_mireds is not None
            and normalized_max_mireds is not None
            and normalized_min_mireds > normalized_max_mireds
        ):
            raise ValueError("Min Mireds nesmi byt vetsi nez Max Mireds.")

        hue_var = self._resolve_vlist_variable_ref(hs_hue_name)
        saturation_var = self._resolve_vlist_variable_ref(hs_saturation_name)
        if bool(hue_var) != bool(saturation_var):
            raise ValueError("Pro HS barvu je potreba vyplnit jak Hue, tak Saturation point.")

        rgb_refs = [
            self._resolve_vlist_variable_ref(rgb_red_name),
            self._resolve_vlist_variable_ref(rgb_green_name),
            self._resolve_vlist_variable_ref(rgb_blue_name),
        ]
        if any(rgb_refs) and not all(rgb_refs):
            raise ValueError("Pro RGB svetlo je potreba vyplnit Red, Green i Blue point.")

        normalized_effect_map = _normalize_label_map(effect_map)
        effect_var = self._resolve_vlist_variable_ref(effect_name)
        if effect_var and not normalized_effect_map:
            raise ValueError("Kdyz vyplnis Effect point, musis doplnit i mapovani efektu.")

        light_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": entity_name,
            "area_id": str(area_id or "").strip(),
            "suggested_display_precision": suggested_display_precision,
            "brightness_scale": normalized_brightness_scale,
            "min_mireds": normalized_min_mireds,
            "max_mireds": normalized_max_mireds,
            "power_var": self._resolve_vlist_variable_ref(power_name),
            "brightness_var": self._resolve_vlist_variable_ref(brightness_name),
            "color_temp_var": self._resolve_vlist_variable_ref(color_temp_name),
            "hs_hue_var": hue_var,
            "hs_saturation_var": saturation_var,
            "rgb_red_var": rgb_refs[0],
            "rgb_green_var": rgb_refs[1],
            "rgb_blue_var": rgb_refs[2],
            "white_var": self._resolve_vlist_variable_ref(white_name),
            "effect_var": effect_var,
            "effect_map": normalized_effect_map,
        }
        if not any(
            light_entry.get(key)
            for key in (
                "power_var",
                "brightness_var",
                "color_temp_var",
                "hs_hue_var",
                "rgb_red_var",
                "white_var",
            )
        ):
            raise ValueError("Light composer potrebuje aspon power, brightness, color temperature, HS, RGB nebo white point.")

        updated = self._upsert_entity(list(self.configured_lights), light_entry)
        await self._update_entry_section("light_entities", updated)
        return {"status": "reload_requested", "entity_key": light_entry["entity_key"]}

    async def async_delete_light_entity(self, *, entity_key: str) -> dict[str, Any]:
        entities = list(self.configured_lights)
        updated = [item for item in entities if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(entities):
            raise ValueError("Light entity pro smazani nebyla nalezena.")
        await self._update_entry_section("light_entities", updated)
        return {"status": "reload_requested"}

    async def async_save_cover_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        area_id: str = "",
        device_class: str = "",
        invert_position: bool = False,
        current_position_name: str = "",
        target_position_name: str = "",
        open_name: str = "",
        close_name: str = "",
        stop_name: str = "",
        current_tilt_name: str = "",
        target_tilt_name: str = "",
        tilt_open_name: str = "",
        tilt_close_name: str = "",
        tilt_stop_name: str = "",
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        entity_name = str(name or "").strip()
        if not entity_name:
            raise ValueError("Nazev cover entity nesmi byt prazdny.")

        cover_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": entity_name,
            "area_id": str(area_id or "").strip(),
            "device_class": str(device_class or "").strip(),
            "invert_position": bool(invert_position),
            "current_position_var": self._resolve_vlist_variable_ref(current_position_name),
            "target_position_var": self._resolve_vlist_variable_ref(target_position_name),
            "open_var": self._resolve_vlist_variable_ref(open_name),
            "close_var": self._resolve_vlist_variable_ref(close_name),
            "stop_var": self._resolve_vlist_variable_ref(stop_name),
            "current_tilt_position_var": self._resolve_vlist_variable_ref(current_tilt_name),
            "target_tilt_position_var": self._resolve_vlist_variable_ref(target_tilt_name),
            "tilt_open_var": self._resolve_vlist_variable_ref(tilt_open_name),
            "tilt_close_var": self._resolve_vlist_variable_ref(tilt_close_name),
            "tilt_stop_var": self._resolve_vlist_variable_ref(tilt_stop_name),
        }
        if not any(
            cover_entry.get(key)
            for key in ("target_position_var", "open_var", "close_var", "tilt_open_var", "tilt_close_var")
        ):
            raise ValueError("Cover composer potrebuje aspon open/close nebo target position point.")

        updated = self._upsert_entity(list(self.configured_covers), cover_entry)
        await self._update_entry_section("cover_entities", updated)
        return {"status": "reload_requested", "entity_key": cover_entry["entity_key"]}

    async def async_delete_cover_entity(self, *, entity_key: str) -> dict[str, Any]:
        entities = list(self.configured_covers)
        updated = [item for item in entities if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(entities):
            raise ValueError("Cover entity pro smazani nebyla nalezena.")
        await self._update_entry_section("cover_entities", updated)
        return {"status": "reload_requested"}

    async def async_save_vacuum_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        area_id: str = "",
        status_name: str = "",
        battery_level_name: str = "",
        battery_charging_name: str = "",
        fan_speed_name: str = "",
        start_name: str = "",
        pause_name: str = "",
        stop_name: str = "",
        return_to_base_name: str = "",
        locate_name: str = "",
        status_map: dict[str, str] | None = None,
        fan_speed_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        entity_name = str(name or "").strip()
        if not entity_name:
            raise ValueError("Nazev vacuum entity nesmi byt prazdny.")

        normalized_status_map = _normalize_vacuum_status_map(status_map)
        normalized_fan_speed_map = _normalize_label_map(fan_speed_map)
        status_var = self._resolve_vlist_variable_ref(status_name)
        fan_speed_var = self._resolve_vlist_variable_ref(fan_speed_name)
        if status_var and not normalized_status_map:
            raise ValueError("Kdyz vyplnis status point, musis doplnit i mapovani vacuum stavu.")
        if fan_speed_var and not normalized_fan_speed_map:
            raise ValueError("Kdyz vyplnis fan speed point, musis doplnit i mapovani rychlosti.")

        vacuum_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": entity_name,
            "area_id": str(area_id or "").strip(),
            "status_var": status_var,
            "battery_level_var": self._resolve_vlist_variable_ref(battery_level_name),
            "battery_charging_var": self._resolve_vlist_variable_ref(battery_charging_name),
            "fan_speed_var": fan_speed_var,
            "start_var": self._resolve_vlist_variable_ref(start_name),
            "pause_var": self._resolve_vlist_variable_ref(pause_name),
            "stop_var": self._resolve_vlist_variable_ref(stop_name),
            "return_to_base_var": self._resolve_vlist_variable_ref(return_to_base_name),
            "locate_var": self._resolve_vlist_variable_ref(locate_name),
            "status_map": normalized_status_map,
            "fan_speed_map": normalized_fan_speed_map,
        }
        if not any(
            vacuum_entry.get(key)
            for key in ("status_var", "start_var", "pause_var", "stop_var", "return_to_base_var", "locate_var")
        ):
            raise ValueError("Vacuum composer potrebuje aspon status nebo nejaky prikazovy point.")

        updated = self._upsert_entity(list(self.configured_vacuums), vacuum_entry)
        await self._update_entry_section("vacuum_entities", updated)
        return {"status": "reload_requested", "entity_key": vacuum_entry["entity_key"]}

    async def async_delete_vacuum_entity(self, *, entity_key: str) -> dict[str, Any]:
        entities = list(self.configured_vacuums)
        updated = [item for item in entities if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(entities):
            raise ValueError("Vacuum entity pro smazani nebyla nalezena.")
        await self._update_entry_section("vacuum_entities", updated)
        return {"status": "reload_requested"}

    async def async_save_fan_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        area_id: str = "",
        percentage_step: int | None = None,
        power_name: str = "",
        percentage_name: str = "",
        preset_name: str = "",
        preset_map: dict[str, str] | None = None,
        oscillate_name: str = "",
        direction_name: str = "",
        direction_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        entity_name = str(name or "").strip()
        if not entity_name:
            raise ValueError("Nazev fan entity nesmi byt prazdny.")
        normalized_percentage_step = 1 if percentage_step in (None, "") else int(percentage_step)
        if normalized_percentage_step <= 0:
            raise ValueError("Percentage step musi byt vetsi nez 0.")

        normalized_preset_map = _normalize_label_map(preset_map)
        normalized_direction_map = _normalize_fan_direction_map(direction_map)
        if preset_name and not normalized_preset_map:
            raise ValueError("Kdyz vyplnis preset point, musis doplnit i preset map.")
        if direction_name and not normalized_direction_map:
            raise ValueError("Kdyz vyplnis direction point, musis doplnit i direction map.")

        fan_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": entity_name,
            "area_id": str(area_id or "").strip(),
            "percentage_step": normalized_percentage_step,
            "power_var": self._resolve_vlist_variable_ref(power_name),
            "percentage_var": self._resolve_vlist_variable_ref(percentage_name),
            "preset_var": self._resolve_vlist_variable_ref(preset_name),
            "oscillate_var": self._resolve_vlist_variable_ref(oscillate_name),
            "direction_var": self._resolve_vlist_variable_ref(direction_name),
            "preset_map": normalized_preset_map,
            "direction_map": normalized_direction_map,
        }
        if not any(fan_entry.get(key) for key in ("power_var", "percentage_var", "preset_var", "oscillate_var", "direction_var")):
            raise ValueError("Fan composer potrebuje aspon power, percentage, preset, oscillate nebo direction point.")

        updated = self._upsert_entity(list(self.configured_fans), fan_entry)
        await self._update_entry_section("fan_entities", updated)
        return {"status": "reload_requested", "entity_key": fan_entry["entity_key"]}

    async def async_delete_fan_entity(self, *, entity_key: str) -> dict[str, Any]:
        entities = list(self.configured_fans)
        updated = [item for item in entities if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(entities):
            raise ValueError("Fan entity pro smazani nebyla nalezena.")
        await self._update_entry_section("fan_entities", updated)
        return {"status": "reload_requested"}

    async def async_save_humidifier_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        area_id: str = "",
        device_class: str = "",
        min_humidity: float | None = None,
        max_humidity: float | None = None,
        target_humidity_step: float | None = None,
        current_humidity_name: str = "",
        target_humidity_name: str = "",
        power_name: str = "",
        mode_name: str = "",
        mode_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        entity_name = str(name or "").strip()
        if not entity_name:
            raise ValueError("Nazev humidifier entity nesmi byt prazdny.")
        normalized_min = 0.0 if min_humidity is None else float(min_humidity)
        normalized_max = 100.0 if max_humidity is None else float(max_humidity)
        normalized_step = 1.0 if target_humidity_step is None else float(target_humidity_step)
        if normalized_min > normalized_max:
            raise ValueError("Minimalni vlhkost nesmi byt vetsi nez maximalni.")
        if normalized_step <= 0:
            raise ValueError("Krok cilove vlhkosti musi byt vetsi nez 0.")

        normalized_mode_map = _normalize_label_map(mode_map)
        if mode_name and not normalized_mode_map:
            raise ValueError("Kdyz vyplnis mode point, musis doplnit i mode map.")

        humidifier_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": entity_name,
            "area_id": str(area_id or "").strip(),
            "device_class": str(device_class or "").strip().lower(),
            "min_humidity": normalized_min,
            "max_humidity": normalized_max,
            "target_humidity_step": normalized_step,
            "current_humidity_var": self._resolve_vlist_variable_ref(current_humidity_name),
            "target_humidity_var": self._resolve_vlist_variable_ref(target_humidity_name),
            "power_var": self._resolve_vlist_variable_ref(power_name),
            "mode_var": self._resolve_vlist_variable_ref(mode_name),
            "mode_map": normalized_mode_map,
        }
        if not any(humidifier_entry.get(key) for key in ("target_humidity_var", "power_var", "mode_var")):
            raise ValueError("Humidifier composer potrebuje aspon power, target humidity nebo mode point.")

        updated = self._upsert_entity(list(self.configured_humidifiers), humidifier_entry)
        await self._update_entry_section("humidifier_entities", updated)
        return {"status": "reload_requested", "entity_key": humidifier_entry["entity_key"]}

    async def async_delete_humidifier_entity(self, *, entity_key: str) -> dict[str, Any]:
        entities = list(self.configured_humidifiers)
        updated = [item for item in entities if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(entities):
            raise ValueError("Humidifier entity pro smazani nebyla nalezena.")
        await self._update_entry_section("humidifier_entities", updated)
        return {"status": "reload_requested"}

    async def async_save_water_heater_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        area_id: str = "",
        temperature_unit: str = "Â°C",
        suggested_display_precision: int | None = None,
        min_temp: float | None = None,
        max_temp: float | None = None,
        temp_step: float | None = None,
        current_temperature_name: str = "",
        target_temperature_name: str = "",
        power_name: str = "",
        operation_mode_name: str = "",
        operation_mode_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        entity_name = str(name or "").strip()
        if not entity_name:
            raise ValueError("Nazev water heater entity nesmi byt prazdny.")
        if suggested_display_precision is not None and suggested_display_precision < 0:
            raise ValueError("Presnost zobrazeni musi byt 0 nebo vetsi.")

        normalized_min_temp = 30.0 if min_temp is None else float(min_temp)
        normalized_max_temp = 90.0 if max_temp is None else float(max_temp)
        normalized_step = 0.5 if temp_step is None else float(temp_step)
        if normalized_min_temp > normalized_max_temp:
            raise ValueError("Minimalni teplota nesmi byt vetsi nez maximalni.")
        if normalized_step <= 0:
            raise ValueError("Krok teploty musi byt vetsi nez 0.")

        normalized_operation_map = _normalize_label_map(operation_mode_map)
        if operation_mode_name and not normalized_operation_map:
            raise ValueError("Kdyz vyplnis operation mode point, musis doplnit i operation map.")

        water_heater_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": entity_name,
            "area_id": str(area_id or "").strip(),
            "temperature_unit": normalize_unit_of_measurement(temperature_unit) or "Â°C",
            "suggested_display_precision": suggested_display_precision,
            "min_temp": normalized_min_temp,
            "max_temp": normalized_max_temp,
            "temp_step": normalized_step,
            "current_temperature_var": self._resolve_vlist_variable_ref(current_temperature_name),
            "target_temperature_var": self._resolve_vlist_variable_ref(target_temperature_name),
            "power_var": self._resolve_vlist_variable_ref(power_name),
            "operation_mode_var": self._resolve_vlist_variable_ref(operation_mode_name),
            "operation_mode_map": normalized_operation_map,
        }
        if not any(
            water_heater_entry.get(key)
            for key in ("target_temperature_var", "power_var", "operation_mode_var")
        ):
            raise ValueError("Water heater composer potrebuje aspon target temperature, power nebo operation mode point.")

        updated = self._upsert_entity(list(self.configured_water_heaters), water_heater_entry)
        await self._update_entry_section("water_heater_entities", updated)
        return {"status": "reload_requested", "entity_key": water_heater_entry["entity_key"]}

    async def async_delete_water_heater_entity(self, *, entity_key: str) -> dict[str, Any]:
        entities = list(self.configured_water_heaters)
        updated = [item for item in entities if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(entities):
            raise ValueError("Water heater entity pro smazani nebyla nalezena.")
        await self._update_entry_section("water_heater_entities", updated)
        return {"status": "reload_requested"}

    async def async_save_lock_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        area_id: str = "",
        state_name: str = "",
        lock_name: str = "",
        unlock_name: str = "",
        open_name: str = "",
        state_map: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        entity_name = str(name or "").strip()
        if not entity_name:
            raise ValueError("Nazev lock entity nesmi byt prazdny.")

        normalized_state_map = _normalize_lock_state_map(state_map)
        lock_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": entity_name,
            "area_id": str(area_id or "").strip(),
            "state_var": self._resolve_vlist_variable_ref(state_name),
            "lock_var": self._resolve_vlist_variable_ref(lock_name),
            "unlock_var": self._resolve_vlist_variable_ref(unlock_name),
            "open_var": self._resolve_vlist_variable_ref(open_name),
            "state_map": normalized_state_map,
        }
        if not any(lock_entry.get(key) for key in ("state_var", "lock_var", "unlock_var", "open_var")):
            raise ValueError("Lock composer potrebuje aspon state, lock, unlock nebo open point.")

        updated = self._upsert_entity(list(self.configured_locks), lock_entry)
        await self._update_entry_section("lock_entities", updated)
        return {"status": "reload_requested", "entity_key": lock_entry["entity_key"]}

    async def async_delete_lock_entity(self, *, entity_key: str) -> dict[str, Any]:
        entities = list(self.configured_locks)
        updated = [item for item in entities if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(entities):
            raise ValueError("Lock entity pro smazani nebyla nalezena.")
        await self._update_entry_section("lock_entities", updated)
        return {"status": "reload_requested"}

    async def async_save_valve_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        area_id: str = "",
        device_class: str = "",
        invert_position: bool = False,
        current_position_name: str = "",
        target_position_name: str = "",
        open_name: str = "",
        close_name: str = "",
        stop_name: str = "",
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        entity_name = str(name or "").strip()
        if not entity_name:
            raise ValueError("Nazev valve entity nesmi byt prazdny.")

        valve_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": entity_name,
            "area_id": str(area_id or "").strip(),
            "device_class": str(device_class or "").strip(),
            "invert_position": bool(invert_position),
            "current_position_var": self._resolve_vlist_variable_ref(current_position_name),
            "target_position_var": self._resolve_vlist_variable_ref(target_position_name),
            "open_var": self._resolve_vlist_variable_ref(open_name),
            "close_var": self._resolve_vlist_variable_ref(close_name),
            "stop_var": self._resolve_vlist_variable_ref(stop_name),
        }
        if not any(valve_entry.get(key) for key in ("target_position_var", "open_var", "close_var")):
            raise ValueError("Valve composer potrebuje aspon open/close nebo target position point.")

        updated = self._upsert_entity(list(self.configured_valves), valve_entry)
        await self._update_entry_section("valve_entities", updated)
        return {"status": "reload_requested", "entity_key": valve_entry["entity_key"]}

    async def async_delete_valve_entity(self, *, entity_key: str) -> dict[str, Any]:
        entities = list(self.configured_valves)
        updated = [item for item in entities if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(entities):
            raise ValueError("Valve entity pro smazani nebyla nalezena.")
        await self._update_entry_section("valve_entities", updated)
        return {"status": "reload_requested"}

    async def async_save_siren_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        area_id: str = "",
        state_name: str = "",
        turn_on_name: str = "",
        turn_off_name: str = "",
        tone_name: str = "",
        tone_map: dict[str, str] | None = None,
        duration_name: str = "",
        volume_name: str = "",
        volume_scale: float | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        entity_name = str(name or "").strip()
        if not entity_name:
            raise ValueError("Nazev siren entity nesmi byt prazdny.")
        normalized_volume_scale = 100.0 if volume_scale is None else float(volume_scale)
        if normalized_volume_scale <= 0:
            raise ValueError("Volume scale musi byt vetsi nez 0.")

        normalized_tone_map = _normalize_label_map(tone_map)
        if tone_name and not normalized_tone_map:
            raise ValueError("Kdyz vyplnis tone point, musis doplnit i tone map.")

        siren_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": entity_name,
            "area_id": str(area_id or "").strip(),
            "state_var": self._resolve_vlist_variable_ref(state_name),
            "turn_on_var": self._resolve_vlist_variable_ref(turn_on_name),
            "turn_off_var": self._resolve_vlist_variable_ref(turn_off_name),
            "tone_var": self._resolve_vlist_variable_ref(tone_name),
            "duration_var": self._resolve_vlist_variable_ref(duration_name),
            "volume_var": self._resolve_vlist_variable_ref(volume_name),
            "volume_scale": normalized_volume_scale,
            "tone_map": normalized_tone_map,
        }
        if not any(
            siren_entry.get(key)
            for key in ("state_var", "turn_on_var", "turn_off_var", "tone_var", "duration_var", "volume_var")
        ):
            raise ValueError("Siren composer potrebuje aspon state, turn on/off, tone, duration nebo volume point.")

        updated = self._upsert_entity(list(self.configured_sirens), siren_entry)
        await self._update_entry_section("siren_entities", updated)
        return {"status": "reload_requested", "entity_key": siren_entry["entity_key"]}

    async def async_delete_siren_entity(self, *, entity_key: str) -> dict[str, Any]:
        entities = list(self.configured_sirens)
        updated = [item for item in entities if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(entities):
            raise ValueError("Siren entity pro smazani nebyla nalezena.")
        await self._update_entry_section("siren_entities", updated)
        return {"status": "reload_requested"}

    async def async_save_scheduler_entity(
        self,
        *,
        entity_key: str | None,
        name: str,
        root_name: str,
        area_id: str = "",
        suggested_display_precision: int | None = None,
    ) -> dict[str, Any]:
        await self.async_ensure_vlist_data()
        entity_name = str(name or "").strip()
        if not entity_name:
            raise ValueError("Nazev scheduler entity nesmi byt prazdny.")
        if suggested_display_precision is not None and suggested_display_precision < 0:
            raise ValueError("Presnost zobrazeni musi byt 0 nebo vetsi.")

        block = self._scheduler_blocks().get(str(root_name or "").strip())
        if block is None:
            raise ValueError("Vybrany scheduler blok nebyl ve vlistu nalezen.")

        scheduler_entry = {
            "entity_key": str(entity_key or uuid4().hex[:10]),
            "name": entity_name,
            "area_id": str(area_id or "").strip(),
            "root_name": block["root_name"],
            "kind": block["kind"],
            "supports_exceptions": bool(block["supports_exceptions"]),
            "point_capacity": len(block["points"]),
            "exception_capacity": len(block["exceptions"]),
            "suggested_display_precision": suggested_display_precision,
            "out_var": build_variable_ref(block.get("out")) if block.get("out") else None,
            "default_value_var": build_variable_ref(block.get("defaultvalue")) if block.get("defaultvalue") else None,
        }

        updated = self._upsert_entity(list(self.configured_scheduler_entities), scheduler_entry)
        await self._update_entry_section("scheduler_entities", updated)
        return {"status": "reload_requested", "entity_key": scheduler_entry["entity_key"]}

    async def async_delete_scheduler_entity(self, *, entity_key: str) -> dict[str, Any]:
        entities = list(self.configured_scheduler_entities)
        updated = [item for item in entities if str(item.get("entity_key")) != str(entity_key)]
        if len(updated) == len(entities):
            raise ValueError("Scheduler entity pro smazani nebyla nalezena.")
        await self._update_entry_section("scheduler_entities", updated)
        return {"status": "reload_requested"}

    async def async_add_manual_variable(
        self,
        *,
        variable_name: str,
        uid: int,
        offset: int,
        length: int,
        plc_type: str,
        entity_type: str,
        display_name: str | None = None,
        unit_of_measurement: str = "",
        device_class: str = "",
        state_class: str = "",
        suggested_display_precision: int | None = None,
        area_id: str = "",
        min_value: float | None = None,
        max_value: float | None = None,
        step: float | None = None,
        mode: str = "box",
        press_time: float | None = None,
        select_options: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        normalized_name = variable_name.strip()
        if not normalized_name:
            raise ValueError("Nazev datoveho bodu nesmi byt prazdny.")

        normalized_type = plc_type.strip().upper()
        if normalized_type not in SUPPORTED_PLC_TYPES:
            raise ValueError(f"Nepodporovaný PLC typ {plc_type}.")

        normalized_entity_type = entity_type.strip()
        allowed_entity_types = PLC_TYPE_TO_ENTITIES.get(normalized_type, ["sensor"])
        if normalized_entity_type not in allowed_entity_types:
            raise ValueError(f"Entita {entity_type} není podporovaná pro typ {normalized_type}.")

        normalized_length = int(length)
        if normalized_length < 1:
            raise ValueError("Delka datoveho bodu musi byt alespon 1.")

        if normalized_entity_type == "number" and min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError("Minimalni hodnota nesmi byt vetsi nez maximalni.")
        normalized_mode = str(mode or "box").strip().lower() or "box"
        if normalized_entity_type == "number" and normalized_mode not in {"box", "slider"}:
            raise ValueError("Number mode musi byt box nebo slider.")
        if normalized_entity_type == "number" and step is not None and step <= 0:
            raise ValueError("Krok number entity musi byt vetsi nez 0.")
        if suggested_display_precision is not None and suggested_display_precision < 0:
            raise ValueError("Presnost zobrazeni musi byt 0 nebo vetsi.")

        normalized_select_options = {
            str(key): str(value)
            for key, value in (select_options or {}).items()
            if str(key).strip() and str(value).strip()
        }
        if normalized_entity_type == "select" and not normalized_select_options:
            raise ValueError("Select entita potrebuje alespon jednu volbu.")

        selected = {
            "name": normalized_name,
            "uid": int(uid),
            "offset": int(offset),
            "length": normalized_length,
            "type": normalized_type,
        }
        current_variables = self.configured_variables
        if is_duplicate_variable(current_variables, selected):
            raise ValueError("Datový bod je už nakonfigurovaný.")

        new_variable = build_entity_entry(
            selected,
            normalized_entity_type,
            name=(display_name or selected["name"]).strip() or selected["name"],
            unit_of_measurement=unit_of_measurement,
            device_class=str(device_class or "").strip(),
            state_class=str(state_class or "").strip(),
            suggested_display_precision=suggested_display_precision,
            area_id=str(area_id or "").strip(),
            min_value=min_value,
            max_value=max_value,
            step=step,
            mode=normalized_mode,
            press_time=press_time,
            select_options=normalized_select_options,
        )
        await self._update_variables([*current_variables, new_variable])
        return {"status": "reload_requested"}

    async def async_save_config(
        self,
        *,
        plc_name: str,
        communication_mode: str,
        host: str,
        port: str,
        username: str,
        password: str,
        sscp_address: str,
        webpanel_connection: str,
        webpanel_scheme: str,
        scan_interval: int,
        vlist_file_name: str,
        configuration_mode: str = "vlist",
    ) -> dict[str, Any]:
        vlist_path = ""
        if vlist_file_name:
            candidate = resolve_vlist_file(vlist_file_name)
            if not await self.hass.async_add_executor_job(candidate.exists):
                raise ValueError(f"VList soubor {vlist_file_name} neexistuje.")
            vlist_path = str(candidate)

        new_data = {
            **self.entry.data,
            "PLC_Name": plc_name.strip() or "PLC",
            CONF_COMMUNICATION_MODE: communication_mode_from_data({CONF_COMMUNICATION_MODE: communication_mode}),
            "host": host.strip(),
            "port": str(port).strip(),
            "username": username.strip(),
            "password": password,
            "sscp_address": sscp_address.strip() or "0x01",
            CONF_WEBPANEL_CONNECTION: webpanel_connection.strip() or "defaultConnection",
            CONF_WEBPANEL_SCHEME: str(webpanel_scheme or "http").strip().lower() or "http",
            "scan_interval": max(1, int(scan_interval)),
            "configuration_mode": configuration_mode or "vlist",
            "vlist_file": vlist_path,
        }
        self.hass.config_entries.async_update_entry(
            self.entry,
            title=new_data["PLC_Name"],
            data=new_data,
        )
        await self.hass.config_entries.async_reload(self.entry.entry_id)
        return {"status": "reload_requested"}

    async def async_upload_vlist(
        self,
        *,
        file_name: str,
        content: bytes,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        if not content:
            raise ValueError("VList soubor je prazdny.")

        safe_name = sanitize_vlist_file_name(file_name)
        target_path = await self.hass.async_add_executor_job(
            partial(write_vlist_bytes, safe_name, content, overwrite=overwrite)
        )

        selected_vlist_name = Path(self.entry.data.get("vlist_file", "")).name
        if selected_vlist_name == target_path.name:
            self.vlist_data = {}

        return {
            "status": "uploaded",
            "file_name": target_path.name,
            "overwritten": bool(overwrite),
        }

    async def async_delete_variable(self, *, variable_entry_key: str) -> dict[str, Any]:
        current_variables = self.configured_variables
        updated = [item for item in current_variables if variable_key(item) != variable_entry_key]
        if len(updated) == len(current_variables):
            raise ValueError("Variable was not found in configured entities.")
        await self._update_variables(updated)
        return {"status": "reload_requested"}

    async def async_reload_from_vlist(self) -> dict[str, Any]:
        # Always refresh from the currently selected file instead of reusing a stale cache.
        self.vlist_data = {}
        await self.async_ensure_vlist_data()
        if not self.vlist_data:
            raise ValueError("No vlist file is configured.")

        updated_variables = list(self.configured_variables)
        updated_climates = list(self.configured_climates)
        updated_lights = list(self.configured_lights)
        updated_covers = list(self.configured_covers)
        updated_vacuums = list(self.configured_vacuums)
        updated_fans = list(self.configured_fans)
        updated_humidifiers = list(self.configured_humidifiers)
        updated_water_heaters = list(self.configured_water_heaters)
        updated_locks = list(self.configured_locks)
        updated_valves = list(self.configured_valves)
        updated_sirens = list(self.configured_sirens)
        updated_scheduler_entities = list(self.configured_scheduler_entities)
        changed = False
        for entity in updated_variables:
            key = entity.get("name_vlist") or entity.get("name")
            if key not in self.vlist_data:
                continue
            source = self.vlist_data[key]
            for field in ("uid", "offset", "length", "type"):
                if entity.get(field) != source.get(field):
                    entity[field] = source[field]
                    changed = True

        for climate in updated_climates:
            for ref_key in (
                "current_temperature_var",
                "target_temperature_var",
                "current_humidity_var",
                "power_var",
                "hvac_mode_var",
                "preset_var",
            ):
                ref = climate.get(ref_key)
                variable_name = ref.get("name_vlist") if isinstance(ref, dict) else None
                if not variable_name or variable_name not in self.vlist_data:
                    continue
                updated_ref = build_variable_ref(self.vlist_data[variable_name])
                if updated_ref and ref != updated_ref:
                    climate[ref_key] = updated_ref
                    changed = True

        for light in updated_lights:
            for ref_key in (
                "power_var",
                "brightness_var",
                "color_temp_var",
                "hs_hue_var",
                "hs_saturation_var",
                "rgb_red_var",
                "rgb_green_var",
                "rgb_blue_var",
                "white_var",
                "effect_var",
            ):
                ref = light.get(ref_key)
                variable_name = ref.get("name_vlist") if isinstance(ref, dict) else None
                if not variable_name or variable_name not in self.vlist_data:
                    continue
                updated_ref = build_variable_ref(self.vlist_data[variable_name])
                if updated_ref and ref != updated_ref:
                    light[ref_key] = updated_ref
                    changed = True

        for cover in updated_covers:
            for ref_key in (
                "current_position_var",
                "target_position_var",
                "open_var",
                "close_var",
                "stop_var",
                "current_tilt_position_var",
                "target_tilt_position_var",
                "tilt_open_var",
                "tilt_close_var",
                "tilt_stop_var",
            ):
                ref = cover.get(ref_key)
                variable_name = ref.get("name_vlist") if isinstance(ref, dict) else None
                if not variable_name or variable_name not in self.vlist_data:
                    continue
                updated_ref = build_variable_ref(self.vlist_data[variable_name])
                if updated_ref and ref != updated_ref:
                    cover[ref_key] = updated_ref
                    changed = True

        for vacuum in updated_vacuums:
            for ref_key in (
                "status_var",
                "battery_level_var",
                "battery_charging_var",
                "fan_speed_var",
                "start_var",
                "pause_var",
                "stop_var",
                "return_to_base_var",
                "locate_var",
            ):
                ref = vacuum.get(ref_key)
                variable_name = ref.get("name_vlist") if isinstance(ref, dict) else None
                if not variable_name or variable_name not in self.vlist_data:
                    continue
                updated_ref = build_variable_ref(self.vlist_data[variable_name])
                if updated_ref and ref != updated_ref:
                    vacuum[ref_key] = updated_ref
                    changed = True

        for fan in updated_fans:
            for ref_key in ("power_var", "percentage_var", "preset_var", "oscillate_var", "direction_var"):
                ref = fan.get(ref_key)
                variable_name = ref.get("name_vlist") if isinstance(ref, dict) else None
                if not variable_name or variable_name not in self.vlist_data:
                    continue
                updated_ref = build_variable_ref(self.vlist_data[variable_name])
                if updated_ref and ref != updated_ref:
                    fan[ref_key] = updated_ref
                    changed = True

        for humidifier in updated_humidifiers:
            for ref_key in ("current_humidity_var", "target_humidity_var", "power_var", "mode_var"):
                ref = humidifier.get(ref_key)
                variable_name = ref.get("name_vlist") if isinstance(ref, dict) else None
                if not variable_name or variable_name not in self.vlist_data:
                    continue
                updated_ref = build_variable_ref(self.vlist_data[variable_name])
                if updated_ref and ref != updated_ref:
                    humidifier[ref_key] = updated_ref
                    changed = True

        for water_heater in updated_water_heaters:
            for ref_key in ("current_temperature_var", "target_temperature_var", "power_var", "operation_mode_var"):
                ref = water_heater.get(ref_key)
                variable_name = ref.get("name_vlist") if isinstance(ref, dict) else None
                if not variable_name or variable_name not in self.vlist_data:
                    continue
                updated_ref = build_variable_ref(self.vlist_data[variable_name])
                if updated_ref and ref != updated_ref:
                    water_heater[ref_key] = updated_ref
                    changed = True

        for lock in updated_locks:
            for ref_key in ("state_var", "lock_var", "unlock_var", "open_var"):
                ref = lock.get(ref_key)
                variable_name = ref.get("name_vlist") if isinstance(ref, dict) else None
                if not variable_name or variable_name not in self.vlist_data:
                    continue
                updated_ref = build_variable_ref(self.vlist_data[variable_name])
                if updated_ref and ref != updated_ref:
                    lock[ref_key] = updated_ref
                    changed = True

        for valve in updated_valves:
            for ref_key in ("current_position_var", "target_position_var", "open_var", "close_var", "stop_var"):
                ref = valve.get(ref_key)
                variable_name = ref.get("name_vlist") if isinstance(ref, dict) else None
                if not variable_name or variable_name not in self.vlist_data:
                    continue
                updated_ref = build_variable_ref(self.vlist_data[variable_name])
                if updated_ref and ref != updated_ref:
                    valve[ref_key] = updated_ref
                    changed = True

        for siren in updated_sirens:
            for ref_key in ("state_var", "turn_on_var", "turn_off_var", "tone_var", "duration_var", "volume_var"):
                ref = siren.get(ref_key)
                variable_name = ref.get("name_vlist") if isinstance(ref, dict) else None
                if not variable_name or variable_name not in self.vlist_data:
                    continue
                updated_ref = build_variable_ref(self.vlist_data[variable_name])
                if updated_ref and ref != updated_ref:
                    siren[ref_key] = updated_ref
                    changed = True

        for scheduler_entity in updated_scheduler_entities:
            root_name = str(scheduler_entity.get("root_name") or "").strip()
            block = self._scheduler_blocks().get(root_name)
            if block is not None:
                new_out_var = build_variable_ref(block.get("out")) if block.get("out") else None
                new_default_var = build_variable_ref(block.get("defaultvalue")) if block.get("defaultvalue") else None
                if scheduler_entity.get("out_var") != new_out_var:
                    scheduler_entity["out_var"] = new_out_var
                    changed = True
                if scheduler_entity.get("default_value_var") != new_default_var:
                    scheduler_entity["default_value_var"] = new_default_var
                    changed = True
                new_point_capacity = len(block["points"])
                new_exception_capacity = len(block["exceptions"])
                if scheduler_entity.get("point_capacity") != new_point_capacity:
                    scheduler_entity["point_capacity"] = new_point_capacity
                    changed = True
                if scheduler_entity.get("exception_capacity") != new_exception_capacity:
                    scheduler_entity["exception_capacity"] = new_exception_capacity
                    changed = True
                if scheduler_entity.get("kind") != block["kind"]:
                    scheduler_entity["kind"] = block["kind"]
                    changed = True
                supports_exceptions = bool(block["supports_exceptions"])
                if bool(scheduler_entity.get("supports_exceptions")) != supports_exceptions:
                    scheduler_entity["supports_exceptions"] = supports_exceptions
                    changed = True

        if changed:
            new_data = {
                **self.entry.data,
                "variables": updated_variables,
                "climate_entities": updated_climates,
                "light_entities": updated_lights,
                "cover_entities": updated_covers,
                "vacuum_entities": updated_vacuums,
                "fan_entities": updated_fans,
                "humidifier_entities": updated_humidifiers,
                "water_heater_entities": updated_water_heaters,
                "lock_entities": updated_locks,
                "valve_entities": updated_valves,
                "siren_entities": updated_sirens,
                "scheduler_entities": updated_scheduler_entities,
            }
            self.hass.config_entries.async_update_entry(
                self.entry,
                title=new_data.get("PLC_Name", self.plc_name),
                data=new_data,
            )
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return {"status": "reload_requested"}
        return {"status": "noop"}

    async def async_sync_time(self, *, mode: str = "utc") -> dict[str, Any]:
        if self.client is None:
            raise ValueError("Připojení ještě není nakonfigurované.")
        if self.communication_mode == COMM_MODE_WEBPANEL:
            raise ValueError("Synchronizace PLC času je dostupná jen v SSCP režimu.")
        await self.hass.async_add_executor_job(partial(self.client.sync_time, mode=mode))
        payload = await self.async_refresh_protocol_state()
        return {"status": "ok", "payload": payload}

    async def async_set_plc_time(self, *, value: str, mode: str = "local") -> dict[str, Any]:
        if self.client is None:
            raise ValueError("Připojení ještě není nakonfigurované.")
        if self.communication_mode == COMM_MODE_WEBPANEL:
            raise ValueError("Nastavení PLC času je dostupné jen v SSCP režimu.")
        normalized_mode = "local" if str(mode or "local").strip().lower() == "local" else "utc"
        target_value = _parse_ui_datetime(value, normalized_mode)
        if not hasattr(self.client, "set_time"):
            raise ValueError("Aktualni backend neumí nastavení PLC času.")
        await self.hass.async_add_executor_job(partial(self.client.set_time, target_value, mode=normalized_mode))
        await self._async_refresh_entry_coordinators()
        payload = await self.async_refresh_protocol_state()
        return {"status": "ok", "payload": payload}

    async def async_get_scheduler(self, *, root_name: str) -> dict[str, Any]:
        if self.client is None:
            raise ValueError("Připojení ještě není nakonfigurované.")
        await self.async_ensure_vlist_data()
        block = self._scheduler_blocks().get(root_name)
        if block is None:
            raise ValueError("Vybrany tydenni program nebyl ve vlistu nalezen.")

        requests: list[dict[str, Any]] = [{**block["defaultvalue"], "key": "defaultvalue"}]
        for index, point in sorted(block["points"].items()):
            requests.append({**point["starttime"], "key": f"point:{index}:starttime"})
            requests.append({**point["state"], "key": f"point:{index}:value"})
        for index, exception in sorted(block["exceptions"].items()):
            start_ref = exception.get("starttime")
            end_ref = exception.get("endtime")
            state_ref = exception.get("state")
            if start_ref and end_ref and state_ref:
                requests.append({**start_ref, "key": f"exception:{index}:starttime"})
                requests.append({**end_ref, "key": f"exception:{index}:endtime"})
                requests.append({**state_ref, "key": f"exception:{index}:value"})

        values = await self.hass.async_add_executor_job(self.client.read_variables, requests)

        weekly_items: list[dict[str, Any]] = []
        for index in sorted(block["points"]):
            starttime = values.get(f"point:{index}:starttime")
            if starttime in (None, 65535):
                continue
            starttime_value = int(starttime)
            day, minute_of_day = minutes_to_day_time(starttime_value)
            weekly_items.append(
                {
                    "index": index,
                    "starttime": starttime_value,
                    "day": day,
                    "minute_of_day": minute_of_day,
                    "value": values.get(f"point:{index}:value"),
                }
            )

        exceptions: list[dict[str, Any]] = []
        for index in sorted(block["exceptions"]):
            starttime = values.get(f"exception:{index}:starttime")
            endtime = values.get(f"exception:{index}:endtime")
            if starttime in (None, 65535) or endtime in (None, 65535):
                continue
            exceptions.append(
                {
                    "index": index,
                    "starttime": int(starttime),
                    "endtime": int(endtime),
                    "value": values.get(f"exception:{index}:value"),
                }
            )

        return {
            "root_name": root_name,
            "name": root_name.split(".")[-1],
            "kind": block["kind"],
            "supports_exceptions": block["supports_exceptions"],
            "point_capacity": len(block["points"]),
            "exception_capacity": len(block["exceptions"]),
            "default_value": values.get("defaultvalue"),
            "weekly_items": weekly_items,
            "grouped_weekly_items": group_weekly_points(weekly_items),
            "exceptions": exceptions,
        }

    async def async_save_scheduler(
        self,
        *,
        root_name: str,
        default_value: Any,
        weekly_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self.client is None:
            raise ValueError("Připojení ještě není nakonfigurované.")
        await self.async_ensure_vlist_data()
        block = self._scheduler_blocks().get(root_name)
        if block is None:
            raise ValueError("Vybrany tydenni program nebyl ve vlistu nalezen.")

        compacted = compact_weekly_items(weekly_items, block["kind"])
        point_capacity = len(block["points"])
        if len(compacted) > point_capacity:
            raise ValueError(f"Tydenni program podporuje maximalne {point_capacity} zlomu.")

        normalized_default = schedule_value_from_ui(default_value, block["kind"])
        ordered_points = [block["points"][index] for index in sorted(block["points"])]

        await self.hass.async_add_executor_job(
            partial(
                self.client.write_variable,
                int(block["defaultvalue"]["uid"]),
                _coerce_plc_write_value(normalized_default, str(block["defaultvalue"]["type"])),
                offset=int(block["defaultvalue"].get("offset", 0)),
                length=int(block["defaultvalue"].get("length", 1)),
                type_data=str(block["defaultvalue"]["type"]),
            )
        )

        for point, item in zip(ordered_points, compacted, strict=False):
            await self.hass.async_add_executor_job(
                partial(
                    self.client.write_variable,
                    int(point["starttime"]["uid"]),
                    int(item["starttime"]),
                    offset=int(point["starttime"].get("offset", 0)),
                    length=int(point["starttime"].get("length", 1)),
                    type_data=str(point["starttime"]["type"]),
                )
            )
            await self.hass.async_add_executor_job(
                partial(
                    self.client.write_variable,
                    int(point["state"]["uid"]),
                    _coerce_plc_write_value(item["value"], str(point["state"]["type"])),
                    offset=int(point["state"].get("offset", 0)),
                    length=int(point["state"].get("length", 1)),
                    type_data=str(point["state"]["type"]),
                )
            )

        for point in ordered_points[len(compacted) :]:
            await self.hass.async_add_executor_job(
                partial(
                    self.client.write_variable,
                    int(point["starttime"]["uid"]),
                    65535,
                    offset=int(point["starttime"].get("offset", 0)),
                    length=int(point["starttime"].get("length", 1)),
                    type_data=str(point["starttime"]["type"]),
                )
            )
            await self.hass.async_add_executor_job(
                partial(
                    self.client.write_variable,
                    int(point["state"]["uid"]),
                    _coerce_plc_write_value(normalized_default, str(point["state"]["type"])),
                    offset=int(point["state"].get("offset", 0)),
                    length=int(point["state"].get("length", 1)),
                    type_data=str(point["state"]["type"]),
                )
            )

        await self._async_refresh_entry_coordinators()
        return {
            "status": "ok",
            "root_name": root_name,
            "saved_points": len(compacted),
            "ignored_exceptions": len(block["exceptions"]),
        }

    async def _async_refresh_entry_coordinators(self) -> None:
        entry_state = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {})
        coordinator = entry_state.get("coordinator")
        diagnostics_coordinator = entry_state.get("diagnostics_coordinator")
        if coordinator is not None:
            await coordinator.async_request_refresh()
        if diagnostics_coordinator is not None:
            await diagnostics_coordinator.async_request_refresh()

    async def _update_variables(self, variables: list[dict[str, Any]]) -> None:
        new_data = {**self.entry.data, "variables": variables}
        self.hass.config_entries.async_update_entry(self.entry, title=new_data.get("PLC_Name", self.plc_name), data=new_data)
        await self.hass.config_entries.async_reload(self.entry.entry_id)

    async def _update_climates(self, climates: list[dict[str, Any]]) -> None:
        new_data = {**self.entry.data, "climate_entities": climates}
        self.hass.config_entries.async_update_entry(
            self.entry,
            title=new_data.get("PLC_Name", self.plc_name),
            data=new_data,
        )
        await self.hass.config_entries.async_reload(self.entry.entry_id)


async def async_domain_state_payload(hass: HomeAssistant) -> dict[str, Any]:
    domain_data = hass.data.get(DOMAIN, {})
    runtimes_by_entry_id = {
        entry_id: item["runtime"]
        for entry_id, item in domain_data.items()
        if item.get("runtime") is not None
    }
    entries = []
    for entry in sorted(hass.config_entries.async_entries(DOMAIN), key=lambda item: item.title or item.entry_id):
        runtime = runtimes_by_entry_id.get(entry.entry_id)
        if runtime is None:
            runtime = SSCPRuntime(hass, entry, None)
            if has_connection_settings(dict(entry.data)):
                runtime.last_error = _entry_state_error(entry)
        entries.append(await runtime.async_state_payload())
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "entries": entries,
    }


def resolve_runtime(
    hass: HomeAssistant,
    entry_id: str | None = None,
    *,
    allow_fallback: bool = False,
) -> SSCPRuntime | None:
    domain_data = hass.data.get(DOMAIN, {})
    if not domain_data:
        if not allow_fallback:
            return None
    if entry_id and entry_id in domain_data:
        return domain_data[entry_id]["runtime"]
    if not entry_id and domain_data:
        first_entry = next(iter(domain_data.values()))
        return first_entry["runtime"]

    if not allow_fallback:
        return None

    entries = hass.config_entries.async_entries(DOMAIN)
    if entry_id:
        matching_entry = next((entry for entry in entries if entry.entry_id == entry_id), None)
        if matching_entry is None:
            return None
        runtime = SSCPRuntime(hass, matching_entry, None)
        if has_connection_settings(dict(matching_entry.data)):
            runtime.last_error = _entry_state_error(matching_entry)
        return runtime
    first_entry = next(iter(entries), None)
    if first_entry is None:
        return None
    runtime = SSCPRuntime(hass, first_entry, None)
    if has_connection_settings(dict(first_entry.data)):
        runtime.last_error = _entry_state_error(first_entry)
    return runtime
