from __future__ import annotations

import logging
from pathlib import Path
import random
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    COMM_MODE_SSCP,
    COMM_MODE_WEBPANEL,
    CONF_COMMUNICATION_MODE,
    CONF_SCAN_INTERVAL,
    CONF_WEBPANEL_CONNECTION,
    CONF_WEBPANEL_SCHEME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
)
from .migration import ENTRY_MINOR_VERSION, ENTRY_VERSION
from .runtime import SSCPRuntime
from .sscp_client import SSCPClient
from .vlist import get_vlist_dir, list_vlist_files, resolve_vlist_file

_LOGGER = logging.getLogger(__name__)

VLIST_DIR = str(get_vlist_dir())

SUPPORTED_PLC_TYPES = [
    "BOOL",
    "BYTE",
    "WORD",
    "INT",
    "UINT",
    "DINT",
    "UDINT",
    "LINT",
    "REAL",
    "LREAL",
    "DT",
]

PLC_TYPE_TO_ENTITIES = {
    "BOOL": ["switch", "binary_sensor", "button", "light", "select"],
    "BYTE": ["sensor", "number", "select"],
    "WORD": ["sensor", "number", "select"],
    "INT": ["sensor", "number", "select"],
    "UINT": ["sensor", "number", "select"],
    "DINT": ["sensor", "number", "select"],
    "UDINT": ["sensor", "number", "select"],
    "LINT": ["sensor", "number", "select"],
    "REAL": ["sensor", "number", "select"],
    "LREAL": ["sensor", "number", "select"],
    "DT": ["datetime", "sensor"],
}

ALL_ENTITY_TYPES = [
    "sensor",
    "binary_sensor",
    "switch",
    "light",
    "button",
    "number",
    "select",
    "datetime",
]


def generate_code(length: int = 5) -> str:
    return "".join(random.choices("0123456789", k=length))


def _normalize_plc_type(value: str | None) -> str:
    raw = (value or "").strip().strip("$").upper()
    aliases = {
        "DT": "DT",
        "DATETIME": "DT",
        "DATE_TIME": "DT",
        "BOOL": "BOOL",
        "BOOLEAN": "BOOL",
    }
    return aliases.get(raw, raw)


def _clean_vlist_name(raw_name: str) -> str:
    return raw_name.replace("$", "").strip()


def _read_vlist_file(vlist_file: str) -> list[str]:
    with open(vlist_file, "r", encoding="utf-8", errors="ignore") as file:
        return file.readlines()


def _load_vlist_map(vlist_file: str) -> dict[str, dict[str, Any]]:
    lines = _read_vlist_file(vlist_file)
    result: dict[str, dict[str, Any]] = {}

    for line in lines[2:]:
        parts = line.strip().split(";")
        if len(parts) < 6:
            continue

        name = _clean_vlist_name(parts[1])
        raw_type = _normalize_plc_type(parts[2])
        if raw_type not in SUPPORTED_PLC_TYPES:
            continue

        try:
            uid = int(parts[3])
            offset = int(parts[4]) if parts[4] else 0
            length = int(parts[5]) if parts[5] else 1
        except ValueError:
            continue

        result[name] = {
            "name": name,
            "project": parts[0],
            "uid": uid,
            "type": raw_type,
            "offset": offset,
            "length": length,
            "parent_type_family": parts[6] if len(parts) > 6 else "none",
            "history_id": parts[7] if len(parts) > 7 else None,
        }

    return result


def _split_name_to_parts(name: str) -> list[str]:
    return [part for part in name.split(".") if part]


def _guess_default_entity_type(plc_type: str, variable_name: str) -> str:
    options = PLC_TYPE_TO_ENTITIES.get(plc_type, ["sensor"])
    name = variable_name.lower()

    if plc_type == "DT":
        return "datetime" if "datetime" in options else options[0]

    if plc_type == "BOOL":
        writable_hint_tokens = ["cmd", "set", "write", "wr", "on", "off", "enable", "start", "stop"]
        if any(token in name for token in writable_hint_tokens) and "switch" in options:
            return "switch"
        if "binary_sensor" in options:
            return "binary_sensor"

    return options[0]


def _build_entity_detail_schema(entity_type: str, default_name: str) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Required("name_ha", default=default_name): str,
        vol.Optional("random_code", default=generate_code()): str,
    }

    if entity_type == "number":
        fields[vol.Optional("min_value", default=0.0)] = vol.Coerce(float)
        fields[vol.Optional("max_value", default=100.0)] = vol.Coerce(float)
        fields[vol.Optional("step", default=1.0)] = vol.Coerce(float)
        fields[vol.Optional("mode", default="box")] = vol.In(["box", "slider"])
        fields[vol.Optional("unit_of_measurement", default="")] = str

    if entity_type == "select":
        for i in range(8):
            fields[vol.Optional(f"select_key_{i}", default="")] = str
            fields[vol.Optional(f"select_label_{i}", default="")] = str

    if entity_type == "button":
        fields[vol.Optional("press_time", default=0.1)] = vol.Coerce(float)

    if entity_type in ("sensor", "datetime"):
        fields[vol.Optional("unit_of_measurement", default="")] = str

    return vol.Schema(fields)


def _scan_interval_value(value: Any) -> int:
    try:
        return max(1, min(300, int(value)))
    except (TypeError, ValueError):
        return DEFAULT_SCAN_INTERVAL_SECONDS


def _vlist_file_name_from_data(data: dict[str, Any]) -> str:
    raw_value = str(data.get("vlist_file") or "").strip()
    if not raw_value:
        return ""
    return Path(raw_value).name


def _vlist_options(current_name: str = "") -> dict[str, str]:
    options = {"": "Bez VListu"}
    for file_name in list_vlist_files():
        options[file_name] = file_name
    if current_name and current_name not in options:
        options[current_name] = current_name
    return options


def _workspace_defaults(data: dict[str, Any] | None = None) -> dict[str, Any]:
    source = data or {}
    return {
        "plc_name": str(source.get("PLC_Name") or source.get("plc_name") or "PLC").strip() or "PLC",
        "communication_mode": str(source.get(CONF_COMMUNICATION_MODE) or COMM_MODE_SSCP).strip().lower() or COMM_MODE_SSCP,
        "host": str(source.get("host") or "").strip(),
        "port": str(source.get("port") or "12346").strip() or "12346",
        "username": str(source.get("username") or "").strip(),
        "password": str(source.get("password") or ""),
        "sscp_address": str(source.get("sscp_address") or "0x01").strip() or "0x01",
        "webpanel_connection": str(source.get(CONF_WEBPANEL_CONNECTION) or "defaultConnection").strip() or "defaultConnection",
        "webpanel_scheme": str(source.get(CONF_WEBPANEL_SCHEME) or "http").strip().lower() or "http",
        "scan_interval": _scan_interval_value(source.get(CONF_SCAN_INTERVAL)),
        "vlist_file_name": _vlist_file_name_from_data(source),
    }


def _workspace_schema(defaults: dict[str, Any], *, include_action: bool = False) -> vol.Schema:
    fields: dict[Any, Any] = {
        vol.Required("plc_name", default=defaults["plc_name"]): str,
        vol.Required("communication_mode", default=defaults["communication_mode"]): vol.In(
            {
                COMM_MODE_SSCP: "SSCP protokol",
                COMM_MODE_WEBPANEL: "WebPanel API",
            }
        ),
        vol.Optional("host", default=defaults["host"]): str,
        vol.Optional("port", default=defaults["port"]): str,
        vol.Optional("username", default=defaults["username"]): str,
        vol.Optional("password", default=defaults["password"]): str,
        vol.Optional("sscp_address", default=defaults["sscp_address"]): str,
        vol.Optional("webpanel_connection", default=defaults["webpanel_connection"]): str,
        vol.Optional("webpanel_scheme", default=defaults["webpanel_scheme"]): vol.In({"http": "http", "https": "https"}),
        vol.Optional("scan_interval", default=defaults["scan_interval"]): vol.All(vol.Coerce(int), vol.Range(min=1, max=300)),
        vol.Optional("vlist_file_name", default=defaults["vlist_file_name"]): vol.In(_vlist_options(defaults["vlist_file_name"])),
    }
    if include_action:
        fields[vol.Required("action", default="save")] = vol.In(
            {
                "save": "Ulozit nastaveni",
                "reload_from_vlist": "Ulozit a znovu nacist metadata z VListu",
                "legacy_entity_wizard": "Otevrit legacy 1:1 entity wizard",
                "legacy_add_entity_from_vlist": "Legacy pridani 1:1 entity z VListu",
            }
        )
    return vol.Schema(fields)


def _entry_data_from_workspace_input(user_input: dict[str, Any]) -> dict[str, Any]:
    communication_mode = str(user_input.get("communication_mode") or COMM_MODE_SSCP).strip().lower()
    if communication_mode not in {COMM_MODE_SSCP, COMM_MODE_WEBPANEL}:
        communication_mode = COMM_MODE_SSCP

    selected_vlist_name = str(user_input.get("vlist_file_name") or "").strip()
    vlist_path = ""
    if selected_vlist_name:
        candidate = resolve_vlist_file(selected_vlist_name)
        if not candidate.exists():
            raise ValueError(f"Vybrany VList soubor {selected_vlist_name} nebyl nalezen v {VLIST_DIR}.")
        vlist_path = str(candidate)

    return {
        "PLC_Name": str(user_input.get("plc_name") or "PLC").strip() or "PLC",
        CONF_COMMUNICATION_MODE: communication_mode,
        "host": str(user_input.get("host") or "").strip(),
        "port": str(user_input.get("port") or "12346").strip() or "12346",
        "username": str(user_input.get("username") or "").strip(),
        "password": str(user_input.get("password") or ""),
        "sscp_address": str(user_input.get("sscp_address") or "0x01").strip() or "0x01",
        CONF_WEBPANEL_CONNECTION: str(user_input.get("webpanel_connection") or "defaultConnection").strip() or "defaultConnection",
        CONF_WEBPANEL_SCHEME: str(user_input.get("webpanel_scheme") or "http").strip().lower() or "http",
        CONF_SCAN_INTERVAL: _scan_interval_value(user_input.get("scan_interval")),
        "configuration_mode": "vlist",
        "vlist_file": vlist_path,
    }


class SSCPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for SSCP integration."""

    VERSION = ENTRY_VERSION
    MINOR_VERSION = ENTRY_MINOR_VERSION

    def __init__(self):
        self.client: SSCPClient | None = None
        self.config: dict[str, Any] = {}
        self.vlist_data: dict[str, dict[str, Any]] = {}

        self.chosen_var: dict[str, Any] | None = None
        self.chosen_entity_type: str | None = None
        self.chosen_type: str | None = None
        self.temp_entity: dict[str, Any] = {}

        self.vlist_filter: str = ""
        self.vlist_limit: int = 200
        self.vlist_selection_mode: str = "tree"
        self.vlist_tree_path: list[str] = []

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                entry_data = _entry_data_from_workspace_input(user_input)
            except ValueError as error:
                _LOGGER.warning("Unable to create SSCP workspace from config flow input: %s", error)
                errors["vlist_file_name"] = "vlist_file_not_found"
            else:
                entry_data.update(
                    {
                        "variables": [],
                        "climate_entities": [],
                        "light_entities": [],
                        "cover_entities": [],
                        "vacuum_entities": [],
                        "fan_entities": [],
                        "humidifier_entities": [],
                        "water_heater_entities": [],
                        "lock_entities": [],
                        "valve_entities": [],
                        "siren_entities": [],
                        "scheduler_entities": [],
                    }
                )
                return self.async_create_entry(
                    title=entry_data["PLC_Name"],
                    data=entry_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_workspace_schema(_workspace_defaults()),
            errors=errors,
            description_placeholders={
                "info": (
                    "Systemovy config flow pouziva stejnou zakladni logiku jako SSCP Studio: "
                    "nastavis PLC, backend a volitelne vyberes VList. Entity a pokrocile skladani "
                    "se pak pohodlne spravuji v panelu SSCP Studio."
                )
            },
        )

    def _test_connection(self, host: str, port: str, username: str, password: str, sscp_address: str, plc_name: str) -> None:
        client = SSCPClient(host, port, username, password, sscp_address, plc_name)
        try:
            client.connect()
            client.login()
        finally:
            try:
                client.disconnect()
            except Exception:
                pass

    async def _ensure_vlist_data(self) -> None:
        if self.vlist_data:
            return

        vlist_file = self.config.get("vlist_file")
        if not vlist_file:
            raise ValueError("No vlist file configured")

        self.vlist_data = await self.hass.async_add_executor_job(_load_vlist_map, vlist_file)

    def _get_filtered_vlist_names(self) -> list[str]:
        all_names = sorted(self.vlist_data.keys())
        return [
            name
            for name in all_names
            if not self.vlist_filter or self.vlist_filter.casefold() in name.casefold()
        ]

    def _build_tree_node(self, names: list[str], path: list[str]) -> tuple[list[str], list[str]]:
        folders: set[str] = set()
        leaves: list[str] = []
        path_len = len(path)

        for name in names:
            parts = _split_name_to_parts(name)
            if len(parts) < path_len:
                continue
            if path and parts[:path_len] != path:
                continue

            if len(parts) == path_len + 1:
                leaves.append(name)
            elif len(parts) > path_len + 1:
                folders.add(parts[path_len])

        return sorted(folders), sorted(leaves)

    async def async_step_vlist_filter(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self.vlist_filter = (user_input.get("filter_text") or "").strip()
            self.vlist_limit = int(user_input.get("show_limit", 200))
            self.vlist_selection_mode = user_input.get("selection_mode", "tree")
            self.vlist_tree_path = []
            if self.vlist_limit < 20 or self.vlist_limit > 1000:
                errors["show_limit"] = "invalid_limit"
            else:
                if self.vlist_selection_mode == "tree":
                    return await self.async_step_vlist_tree_select()
                return await self.async_step_vlist_select()

        data_schema = vol.Schema(
            {
                vol.Optional("filter_text", default=self.vlist_filter): str,
                vol.Optional("show_limit", default=self.vlist_limit): vol.All(vol.Coerce(int), vol.Range(min=20, max=1000)),
                vol.Optional("selection_mode", default=self.vlist_selection_mode): vol.In(
                    {"tree": "Strom (doporučeno)", "list": "Klasický seznam"}
                ),
            }
        )

        return self.async_show_form(
            step_id="vlist_filter",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "info": "Filtruj proměnné z vlistu (obsah názvu), aby výběr byl rychlý a přehledný.",
            },
        )

    async def async_step_vlist_tree_select(self, user_input=None):
        errors: dict[str, str] = {}

        try:
            await self._ensure_vlist_data()
        except Exception as exc:
            _LOGGER.error("Failed to load vlist file: %s", exc)
            errors["base"] = "vlist_load_failed"
            return self.async_show_form(step_id="vlist_tree_select", data_schema=vol.Schema({}))

        filtered_names = self._get_filtered_vlist_names()
        if not filtered_names:
            errors["base"] = "no_variables"
            return await self.async_step_vlist_filter()

        # Keep path valid if filter changed.
        while self.vlist_tree_path:
            path_folders, path_leaves = self._build_tree_node(filtered_names, self.vlist_tree_path)
            if path_folders or path_leaves:
                break
            self.vlist_tree_path.pop()

        folders, leaves = self._build_tree_node(filtered_names, self.vlist_tree_path)
        leaves = leaves[: self.vlist_limit]

        options: dict[str, str] = {"__filter__": "Změnit filtr/režim"}
        if self.vlist_tree_path:
            options["__up__"] = ".. o úroveň výš"
        for folder in folders:
            options[f"D:{folder}"] = f"[DIR] {folder}"
        for leaf_name in leaves:
            leaf_label = _split_name_to_parts(leaf_name)[-1] if "." in leaf_name else leaf_name
            options[f"V:{leaf_name}"] = f"[VAR] {leaf_label}"

        if user_input is not None:
            choice = user_input["choice"]
            if choice == "__filter__":
                return await self.async_step_vlist_filter()
            if choice == "__up__":
                if self.vlist_tree_path:
                    self.vlist_tree_path.pop()
                return await self.async_step_vlist_tree_select()
            if choice.startswith("D:"):
                self.vlist_tree_path.append(choice[2:])
                return await self.async_step_vlist_tree_select()
            if choice.startswith("V:"):
                selected_name = choice[2:]
                self.chosen_var = self.vlist_data[selected_name]
                self.chosen_type = self.chosen_var["type"]
                return await self.async_step_entity_type_select()

        if len(options) == 1:
            errors["base"] = "no_variables"
            return await self.async_step_vlist_filter()

        schema = vol.Schema({vol.Required("choice"): vol.In(options)})
        current_path = ".".join(self.vlist_tree_path) if self.vlist_tree_path else "/"
        return self.async_show_form(
            step_id="vlist_tree_select",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "info": (
                    f"Cesta: {current_path} | složky: {len(folders)} | proměnné: {len(leaves)} | "
                    f"filtr: '{self.vlist_filter or '*'}'"
                )
            },
        )

    async def async_step_vlist_select(self, user_input=None):
        errors: dict[str, str] = {}

        try:
            await self._ensure_vlist_data()
        except Exception as exc:
            _LOGGER.error("Failed to load vlist file: %s", exc)
            errors["base"] = "vlist_load_failed"
            return self.async_show_form(step_id="vlist_select", data_schema=vol.Schema({}))

        filtered_names = self._get_filtered_vlist_names()

        if not filtered_names:
            errors["base"] = "no_variables"
            data_schema = vol.Schema(
                {
                    vol.Optional("filter_text", default=self.vlist_filter): str,
                    vol.Optional("show_limit", default=self.vlist_limit): vol.All(vol.Coerce(int), vol.Range(min=20, max=1000)),
                }
            )
            return self.async_show_form(step_id="vlist_filter", data_schema=data_schema, errors=errors)

        truncated = len(filtered_names) > self.vlist_limit
        visible_names = filtered_names[: self.vlist_limit]

        if user_input is not None:
            if user_input.get("refine_filter"):
                return await self.async_step_vlist_filter()

            selected_name = user_input["variable"]
            self.chosen_var = self.vlist_data[selected_name]
            self.chosen_type = self.chosen_var["type"]
            return await self.async_step_entity_type_select()

        data_schema = vol.Schema(
            {
                vol.Required("variable"): vol.In(visible_names),
                vol.Optional("refine_filter", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="vlist_select",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "info": (
                    f"Nalezeno {len(filtered_names)} proměnných. "
                    f"Zobrazuji {len(visible_names)}. "
                    f"Filtr: '{self.vlist_filter or '*'}'."
                )
                if truncated
                else f"Nalezeno {len(visible_names)} proměnných. Filtr: '{self.vlist_filter or '*'}'."
            },
        )

    async def async_step_manual_input(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized_type = _normalize_plc_type(user_input["type"])
            if normalized_type not in SUPPORTED_PLC_TYPES:
                errors["type"] = "unsupported_type"
            else:
                self.chosen_var = {
                    "name": user_input["name"],
                    "uid": int(user_input["uid"]),
                    "offset": int(user_input.get("offset", 0)),
                    "length": int(user_input.get("length", 1)),
                    "type": normalized_type,
                }
                self.chosen_type = normalized_type
                return await self.async_step_entity_type_select()

        data_schema = vol.Schema(
            {
                vol.Required("name", default="Ručně zadaná proměnná"): str,
                vol.Required("uid"): int,
                vol.Optional("offset", default=0): int,
                vol.Optional("length", default=1): int,
                vol.Required("type", default="INT"): vol.In(SUPPORTED_PLC_TYPES),
            }
        )

        return self.async_show_form(
            step_id="manual_input",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"info": "Zadej parametry proměnné a vyber vhodný typ entity."},
        )

    async def async_step_entity_type_select(self, user_input=None):
        if not self.chosen_var or not self.chosen_type:
            return self.async_abort(reason="type_not_found")

        allowed_entity_types = PLC_TYPE_TO_ENTITIES.get(self.chosen_type, ["sensor"])
        guessed_default = _guess_default_entity_type(self.chosen_type, self.chosen_var["name"])

        schema = vol.Schema(
            {
                vol.Required("entity_type", default=guessed_default): vol.In(allowed_entity_types),
            }
        )

        if user_input is not None:
            self.chosen_entity_type = user_input["entity_type"]
            return await self.async_step_entity_detail_config()

        return self.async_show_form(
            step_id="entity_type_select",
            data_schema=schema,
            description_placeholders={
                "typ": self.chosen_type,
                "name": self.chosen_var["name"],
            },
        )

    async def async_step_entity_detail_config(self, user_input=None):
        if not self.chosen_var or not self.chosen_type or not self.chosen_entity_type:
            return self.async_abort(reason="missing_entity_context")

        errors: dict[str, str] = {}
        schema = _build_entity_detail_schema(self.chosen_entity_type, self.chosen_var["name"])

        if user_input is not None:
            if self.chosen_entity_type == "number":
                min_value = user_input.get("min_value", 0.0)
                max_value = user_input.get("max_value", 100.0)
                if min_value > max_value:
                    errors["base"] = "invalid_number_range"

            select_options: dict[str, str] = {}
            if self.chosen_entity_type == "select":
                for i in range(8):
                    key = (user_input.get(f"select_key_{i}") or "").strip()
                    label = (user_input.get(f"select_label_{i}") or "").strip()
                    if key and label:
                        select_options[key] = label

                if not select_options:
                    errors["base"] = "select_options_required"

            if not errors:
                self.temp_entity = {
                    "uid": self.chosen_var["uid"],
                    "offset": self.chosen_var["offset"],
                    "length": self.chosen_var["length"],
                    "type": self.chosen_type,
                    "entity_type": self.chosen_entity_type,
                    "name": user_input["name_ha"],
                    "name_vlist": self.chosen_var["name"],
                    "random_code": user_input.get("random_code") or generate_code(),
                }

                if self.chosen_entity_type == "number":
                    self.temp_entity["min_value"] = user_input.get("min_value")
                    self.temp_entity["max_value"] = user_input.get("max_value")
                    self.temp_entity["step"] = user_input.get("step")
                    self.temp_entity["mode"] = user_input.get("mode", "box")
                    self.temp_entity["unit_of_measurement"] = user_input.get("unit_of_measurement", "")

                if self.chosen_entity_type == "select":
                    self.temp_entity["select_options"] = select_options

                if self.chosen_entity_type == "button":
                    self.temp_entity["press_time"] = user_input.get("press_time", 0.1)

                if self.chosen_entity_type in ("sensor", "datetime"):
                    self.temp_entity["unit_of_measurement"] = user_input.get("unit_of_measurement", "")

                return await self.async_step_confirm_or_next()

        return self.async_show_form(step_id="entity_detail_config", data_schema=schema, errors=errors)

    async def async_step_confirm_or_next(self, user_input=None):
        if user_input is not None:
            action = user_input.get("action", "add_next")
            self.config.setdefault("variables", []).append(self.temp_entity)

            if action == "finish":
                return self.async_create_entry(title=self.config["PLC_Name"], data=self.config)

            if self.config.get("configuration_mode") == "manual":
                return await self.async_step_manual_input()
            if self.vlist_selection_mode == "tree":
                return await self.async_step_vlist_tree_select()
            return await self.async_step_vlist_select()

        schema = vol.Schema(
            {
                vol.Required("action", default="add_next"): vol.In(
                    {
                        "add_next": "Přidat další entitu",
                        "finish": "Dokončit konfiguraci",
                    }
                )
            }
        )
        return self.async_show_form(step_id="confirm_or_next", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SSCPOptionsFlow(config_entry)


class SSCPOptionsFlow(config_entries.OptionsFlow):
    """Options flow for SSCP integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self.vlist_data: dict[str, dict[str, Any]] = {}
        self.current_variables: list[dict[str, Any]] = list(config_entry.data.get("variables", []))
        self.selected_entity_index: int | None = None
        self.add_vlist_filter: str = ""
        self.add_vlist_limit: int = 200
        self.add_vlist_selection_mode: str = "tree"
        self.add_vlist_tree_path: list[str] = []
        self.add_chosen_var: dict[str, Any] | None = None
        self.add_chosen_type: str | None = None
        self.add_chosen_entity_type: str | None = None

    @property
    def entry(self) -> config_entries.ConfigEntry:
        return self._entry

    def _current_workspace_defaults(self) -> dict[str, Any]:
        return _workspace_defaults(self.entry.data)

    def _core_settings_changed(self, updated_data: dict[str, Any]) -> bool:
        tracked_keys = (
            "PLC_Name",
            CONF_COMMUNICATION_MODE,
            "host",
            "port",
            "username",
            "password",
            "sscp_address",
            CONF_WEBPANEL_CONNECTION,
            CONF_WEBPANEL_SCHEME,
            CONF_SCAN_INTERVAL,
            "vlist_file",
        )
        return any(self.entry.data.get(key) != updated_data.get(key) for key in tracked_keys)

    def _runtime_instance(self) -> SSCPRuntime | None:
        domain_data = self.hass.data.get(DOMAIN, {}).get(self.entry.entry_id, {})
        runtime = domain_data.get("runtime")
        return runtime if isinstance(runtime, SSCPRuntime) else None

    async def _reload_from_vlist_with_runtime_fallback(self) -> None:
        runtime = self._runtime_instance()
        if runtime is not None:
            await runtime.async_reload_from_vlist()
            return
        await self.reload_from_vlist()

    async def async_step_init(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            action = user_input["action"]

            try:
                core_updates = _entry_data_from_workspace_input(user_input)
            except ValueError as error:
                _LOGGER.warning("Unable to save SSCP options flow input: %s", error)
                errors["vlist_file_name"] = "vlist_file_not_found"
            else:
                updated_data = {
                    **self.entry.data,
                    **core_updates,
                }
                settings_changed = self._core_settings_changed(updated_data)
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    title=updated_data["PLC_Name"],
                    data=updated_data,
                )

                if action == "legacy_entity_wizard":
                    self.current_variables = list(updated_data.get("variables", []))
                    return await self.async_step_manage_entities()

                if action == "legacy_add_entity_from_vlist":
                    self.current_variables = list(updated_data.get("variables", []))
                    return await self.async_step_add_entity_from_vlist_filter()

                if action == "reload_from_vlist":
                    await self._reload_from_vlist_with_runtime_fallback()
                    if settings_changed:
                        await self.hass.config_entries.async_reload(self.entry.entry_id)
                    return self.async_create_entry(title="", data={})

                if settings_changed:
                    await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_workspace_schema(self._current_workspace_defaults(), include_action=True),
            errors=errors,
            description_placeholders={
                "info": (
                    "Stejne core nastaveni jako v panelu SSCP Studio. Pro beznou spravu entit je doporuceny Studio panel; "
                    "legacy wizard nechavam jen jako kompatibilni fallback pro starsi 1:1 entity workflow."
                )
            },
        )

    async def async_step_manage_entities(self, user_input=None):
        labels = [
            f"{v.get('name', '')} (UID: {v.get('uid')}, type: {v.get('entity_type', 'sensor')})"
            for v in self.current_variables
        ]

        if not labels:
            return self.async_abort(reason="no_entities")

        if user_input is not None:
            selected = user_input["entity"]
            action = user_input["action"]
            self.selected_entity_index = labels.index(selected)

            if action == "delete_entity":
                return await self.async_step_confirm_delete_entity()
            if action == "edit_entity":
                return await self.async_step_edit_entity_type()

            await self._save_variables(self.current_variables)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required("entity"): vol.In(labels),
                vol.Required("action", default="edit_entity"): vol.In(
                    {
                        "edit_entity": "Editovat entitu",
                        "delete_entity": "Smazat entitu",
                        "save_and_reload": "Uložit a reload",
                    }
                ),
            }
        )
        return self.async_show_form(step_id="manage_entities", data_schema=schema)

    def _get_options_filtered_vlist_names(self) -> list[str]:
        all_names = sorted(self.vlist_data.keys())
        return [
            name
            for name in all_names
            if not self.add_vlist_filter or self.add_vlist_filter.casefold() in name.casefold()
        ]

    def _build_options_tree_node(self, names: list[str], path: list[str]) -> tuple[list[str], list[str]]:
        folders: set[str] = set()
        leaves: list[str] = []
        path_len = len(path)

        for name in names:
            parts = _split_name_to_parts(name)
            if len(parts) < path_len:
                continue
            if path and parts[:path_len] != path:
                continue
            if len(parts) == path_len + 1:
                leaves.append(name)
            elif len(parts) > path_len + 1:
                folders.add(parts[path_len])
        return sorted(folders), sorted(leaves)

    async def _ensure_options_vlist_data(self) -> None:
        if self.vlist_data:
            return
        vlist_file = self.entry.data.get("vlist_file")
        if not vlist_file:
            raise ValueError("No vlist file")
        self.vlist_data = await self.hass.async_add_executor_job(_load_vlist_map, vlist_file)

    async def async_step_add_entity_from_vlist_filter(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self.add_vlist_filter = (user_input.get("filter_text") or "").strip()
            self.add_vlist_limit = int(user_input.get("show_limit", 200))
            self.add_vlist_selection_mode = user_input.get("selection_mode", "tree")
            self.add_vlist_tree_path = []
            if self.add_vlist_limit < 20 or self.add_vlist_limit > 1000:
                errors["show_limit"] = "invalid_limit"
            else:
                if self.add_vlist_selection_mode == "tree":
                    return await self.async_step_add_entity_from_vlist_tree()
                return await self.async_step_add_entity_from_vlist()

        schema = vol.Schema(
            {
                vol.Optional("filter_text", default=self.add_vlist_filter): str,
                vol.Optional("show_limit", default=self.add_vlist_limit): vol.All(vol.Coerce(int), vol.Range(min=20, max=1000)),
                vol.Optional("selection_mode", default=self.add_vlist_selection_mode): vol.In(
                    {"tree": "Strom (doporučeno)", "list": "Klasický seznam"}
                ),
            }
        )
        return self.async_show_form(
            step_id="add_entity_from_vlist_filter",
            data_schema=schema,
            errors=errors,
            description_placeholders={"info": "Nastav filtr a režim výběru pro přidání entity z .vlist."},
        )

    def _is_duplicate_variable(self, selected: dict[str, Any]) -> bool:
        existing = {
            (str(v.get("name_vlist") or v.get("name")), int(v.get("uid", -1)))
            for v in self.current_variables
        }
        candidate_key = (selected["name"], int(selected["uid"]))
        return candidate_key in existing

    def _set_add_selected_variable(self, selected_name: str) -> None:
        selected = self.vlist_data[selected_name]
        self.add_chosen_var = selected
        self.add_chosen_type = selected["type"]
        self.add_chosen_entity_type = None

    async def _save_new_added_variable(self, new_variable: dict[str, Any]) -> None:
        self.current_variables = list(self.entry.data.get("variables", [])) + [new_variable]
        await self._save_variables(self.current_variables)

    async def _create_new_variable_from_add_flow(self, user_input: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
        if not self.add_chosen_var or not self.add_chosen_type or not self.add_chosen_entity_type:
            return None, "missing_entity_context"

        if self._is_duplicate_variable(self.add_chosen_var):
            return None, "already_configured"

        if self.add_chosen_entity_type == "number":
            min_value = user_input.get("min_value", 0.0)
            max_value = user_input.get("max_value", 100.0)
            if min_value > max_value:
                return None, "invalid_number_range"

        select_options: dict[str, str] = {}
        if self.add_chosen_entity_type == "select":
            for i in range(8):
                key = (user_input.get(f"select_key_{i}") or "").strip()
                label = (user_input.get(f"select_label_{i}") or "").strip()
                if key and label:
                    select_options[key] = label
            if not select_options:
                return None, "select_options_required"

        new_variable: dict[str, Any] = {
            "uid": self.add_chosen_var["uid"],
            "offset": self.add_chosen_var["offset"],
            "length": self.add_chosen_var["length"],
            "type": self.add_chosen_type,
            "entity_type": self.add_chosen_entity_type,
            "name": user_input["name_ha"],
            "name_vlist": self.add_chosen_var["name"],
            "random_code": user_input.get("random_code") or generate_code(),
        }

        if self.add_chosen_entity_type == "number":
            new_variable["min_value"] = user_input.get("min_value")
            new_variable["max_value"] = user_input.get("max_value")
            new_variable["step"] = user_input.get("step")
            new_variable["mode"] = user_input.get("mode", "box")
            new_variable["unit_of_measurement"] = user_input.get("unit_of_measurement", "")

        if self.add_chosen_entity_type == "select":
            new_variable["select_options"] = select_options

        if self.add_chosen_entity_type == "button":
            new_variable["press_time"] = user_input.get("press_time", 0.1)

        if self.add_chosen_entity_type in ("sensor", "datetime"):
            new_variable["unit_of_measurement"] = user_input.get("unit_of_measurement", "")

        return new_variable, None

    def _clear_add_flow_selection(self) -> None:
        self.add_chosen_var = None
        self.add_chosen_type = None
        self.add_chosen_entity_type = None

    async def _start_add_entity_after_variable_pick(self, selected_name: str):
        self._set_add_selected_variable(selected_name)
        return await self.async_step_add_entity_type_select()

    async def _finalize_new_variable_from_add_flow(self, user_input: dict[str, Any], errors: dict[str, str]):
        new_variable, error_key = await self._create_new_variable_from_add_flow(user_input)
        if error_key:
            errors["base"] = error_key
            return None
        await self._save_new_added_variable(new_variable)
        self._clear_add_flow_selection()
        return None

    async def async_step_add_entity_from_vlist_tree(self, user_input=None):
        errors: dict[str, str] = {}

        try:
            await self._ensure_options_vlist_data()
        except Exception:
            return self.async_abort(reason="no_vlist_file")

        filtered_names = self._get_options_filtered_vlist_names()
        if not filtered_names:
            errors["base"] = "no_variables"
            return await self.async_step_add_entity_from_vlist_filter()

        while self.add_vlist_tree_path:
            path_folders, path_leaves = self._build_options_tree_node(filtered_names, self.add_vlist_tree_path)
            if path_folders or path_leaves:
                break
            self.add_vlist_tree_path.pop()

        folders, leaves = self._build_options_tree_node(filtered_names, self.add_vlist_tree_path)
        leaves = leaves[: self.add_vlist_limit]

        options: dict[str, str] = {"__filter__": "Změnit filtr/režim"}
        if self.add_vlist_tree_path:
            options["__up__"] = ".. o úroveň výš"
        for folder in folders:
            options[f"D:{folder}"] = f"[DIR] {folder}"
        for leaf_name in leaves:
            leaf_label = _split_name_to_parts(leaf_name)[-1] if "." in leaf_name else leaf_name
            options[f"V:{leaf_name}"] = f"[VAR] {leaf_label}"

        if user_input is not None:
            choice = user_input["choice"]
            if choice == "__filter__":
                return await self.async_step_add_entity_from_vlist_filter()
            if choice == "__up__":
                if self.add_vlist_tree_path:
                    self.add_vlist_tree_path.pop()
                return await self.async_step_add_entity_from_vlist_tree()
            if choice.startswith("D:"):
                self.add_vlist_tree_path.append(choice[2:])
                return await self.async_step_add_entity_from_vlist_tree()
            if choice.startswith("V:"):
                return await self._start_add_entity_after_variable_pick(choice[2:])

        if len(options) == 1:
            errors["base"] = "no_variables"
            return await self.async_step_add_entity_from_vlist_filter()

        schema = vol.Schema({vol.Required("choice"): vol.In(options)})
        current_path = ".".join(self.add_vlist_tree_path) if self.add_vlist_tree_path else "/"
        return self.async_show_form(
            step_id="add_entity_from_vlist_tree",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "info": (
                    f"Cesta: {current_path} | složky: {len(folders)} | proměnné: {len(leaves)} | "
                    f"filtr: '{self.add_vlist_filter or '*'}'"
                )
            },
        )

    async def async_step_edit_entity_type(self, user_input=None):
        if self.selected_entity_index is None:
            return await self.async_step_manage_entities()

        entity = self.current_variables[self.selected_entity_index]
        plc_type = _normalize_plc_type(entity.get("type", ""))
        allowed = PLC_TYPE_TO_ENTITIES.get(plc_type, ALL_ENTITY_TYPES)

        if user_input is not None:
            entity["entity_type"] = user_input["entity_type"]
            return await self.async_step_edit_entity_detail()

        schema = vol.Schema(
            {
                vol.Required("entity_type", default=entity.get("entity_type", allowed[0])): vol.In(allowed),
            }
        )
        return self.async_show_form(step_id="edit_entity_type", data_schema=schema)

    async def async_step_edit_entity_detail(self, user_input=None):
        if self.selected_entity_index is None:
            return await self.async_step_manage_entities()

        entity = self.current_variables[self.selected_entity_index]
        entity_type = entity.get("entity_type", "sensor")

        schema_fields: dict[Any, Any] = {
            vol.Required("name", default=entity.get("name", "")): str,
        }

        if entity_type == "number":
            schema_fields[vol.Optional("min_value", default=entity.get("min_value", 0.0))] = vol.Coerce(float)
            schema_fields[vol.Optional("max_value", default=entity.get("max_value", 100.0))] = vol.Coerce(float)
            schema_fields[vol.Optional("step", default=entity.get("step", 1.0))] = vol.Coerce(float)
            schema_fields[vol.Optional("mode", default=entity.get("mode", "box"))] = vol.In(["box", "slider"])
            schema_fields[vol.Optional("unit_of_measurement", default=entity.get("unit_of_measurement", ""))] = str

        if entity_type in ("sensor", "datetime"):
            schema_fields[vol.Optional("unit_of_measurement", default=entity.get("unit_of_measurement", ""))] = str

        if user_input is not None:
            entity["name"] = user_input["name"]
            if entity_type == "number":
                entity["min_value"] = user_input.get("min_value")
                entity["max_value"] = user_input.get("max_value")
                entity["step"] = user_input.get("step")
                entity["mode"] = user_input.get("mode", "box")
                entity["unit_of_measurement"] = user_input.get("unit_of_measurement", "")
            if entity_type in ("sensor", "datetime"):
                entity["unit_of_measurement"] = user_input.get("unit_of_measurement", "")

            self.current_variables[self.selected_entity_index] = entity
            await self._save_variables(self.current_variables)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="edit_entity_detail", data_schema=vol.Schema(schema_fields))

    async def async_step_confirm_delete_entity(self, user_input=None):
        if self.selected_entity_index is None:
            return await self.async_step_manage_entities()

        entity = self.current_variables[self.selected_entity_index]

        if user_input is None:
            schema = vol.Schema({vol.Required("confirm", default=False): bool})
            return self.async_show_form(
                step_id="confirm_delete_entity",
                data_schema=schema,
                description_placeholders={"name": entity.get("name", "")},
            )

        if user_input.get("confirm"):
            self.current_variables.pop(self.selected_entity_index)
            await self._save_variables(self.current_variables)

        return self.async_create_entry(title="", data={})

    async def async_step_add_entity_from_vlist(self, user_input=None):
        errors: dict[str, str] = {}

        try:
            await self._ensure_options_vlist_data()
        except Exception:
            return self.async_abort(reason="no_vlist_file")

        var_names = self._get_options_filtered_vlist_names()
        if not var_names:
            errors["base"] = "no_variables"
            return await self.async_step_add_entity_from_vlist_filter()

        if user_input is not None:
            if user_input.get("change_filter"):
                return await self.async_step_add_entity_from_vlist_filter()
            return await self._start_add_entity_after_variable_pick(user_input["variable"])

        schema = vol.Schema(
            {
                vol.Required("variable"): vol.In(var_names[: min(self.add_vlist_limit, 500)]),
                vol.Optional("change_filter", default=False): bool,
            }
        )
        return self.async_show_form(step_id="add_entity_from_vlist", data_schema=schema, errors=errors)

    async def async_step_add_entity_type_select(self, user_input=None):
        if not self.add_chosen_var or not self.add_chosen_type:
            return await self.async_step_add_entity_from_vlist_filter()

        allowed_entity_types = PLC_TYPE_TO_ENTITIES.get(self.add_chosen_type, ["sensor"])
        guessed_default = _guess_default_entity_type(self.add_chosen_type, self.add_chosen_var["name"])
        schema = vol.Schema(
            {
                vol.Required("entity_type", default=guessed_default): vol.In(allowed_entity_types),
            }
        )

        if user_input is not None:
            self.add_chosen_entity_type = user_input["entity_type"]
            return await self.async_step_add_entity_detail()

        return self.async_show_form(
            step_id="add_entity_type_select",
            data_schema=schema,
            description_placeholders={
                "typ": self.add_chosen_type,
                "name": self.add_chosen_var["name"],
            },
        )

    async def async_step_add_entity_detail(self, user_input=None):
        if not self.add_chosen_var or not self.add_chosen_type or not self.add_chosen_entity_type:
            return await self.async_step_add_entity_from_vlist_filter()

        errors: dict[str, str] = {}
        schema = _build_entity_detail_schema(self.add_chosen_entity_type, self.add_chosen_var["name"])

        if user_input is not None:
            result = await self._finalize_new_variable_from_add_flow(user_input, errors)
            if result is None and not errors:
                return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="add_entity_detail", data_schema=schema, errors=errors)

    async def reload_from_vlist(self) -> None:
        vlist_file = self.entry.data.get("vlist_file")
        if not vlist_file:
            _LOGGER.error("No .vlist file specified.")
            return

        vlist_map = await self.hass.async_add_executor_job(_load_vlist_map, vlist_file)

        updated = False
        for entity in self.current_variables:
            key = entity.get("name_vlist") or entity.get("name")
            if key in vlist_map:
                source = vlist_map[key]
                for field in ("uid", "offset", "length", "type"):
                    if entity.get(field) != source.get(field):
                        entity[field] = source[field]
                        updated = True

        if updated:
            await self._save_variables(self.current_variables)

    async def _save_variables(self, variables: list[dict[str, Any]]) -> None:
        new_data = {**self.entry.data, "variables": variables}
        self.hass.config_entries.async_update_entry(self.entry, data=new_data)
        await self.hass.config_entries.async_reload(self.entry.entry_id)



