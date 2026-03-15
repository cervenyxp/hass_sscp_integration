from __future__ import annotations

from pathlib import Path
import random
from typing import Any

import voluptuous as vol

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

UNIT_ALIASES = {
    "degc": "°C",
    "decc": "°C",
    "°c": "°C",
    "degf": "°F",
    "decf": "°F",
    "°f": "°F",
}


def normalize_unit_of_measurement(value: str | None) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return ""
    return UNIT_ALIASES.get(normalized.casefold(), normalized)


def candidate_vlist_dirs() -> list[Path]:
    here = Path(__file__).resolve().parent
    return [
        Path("/config/custom_components/sscp_integration/vlist_files"),
        here / "vlist_files",
    ]


def get_vlist_dir() -> Path:
    for candidate in candidate_vlist_dirs():
        if candidate.exists():
            return candidate
    return candidate_vlist_dirs()[0]


def list_vlist_files() -> list[str]:
    vlist_dir = get_vlist_dir()
    if not vlist_dir.exists():
        return []
    return sorted(
        file_path.name
        for file_path in vlist_dir.iterdir()
        if file_path.suffix.lower() in {".vlist", ".txt"}
    )


def resolve_vlist_file(file_name: str) -> Path:
    return get_vlist_dir() / file_name


def sanitize_vlist_file_name(file_name: str) -> str:
    candidate = Path(file_name.strip()).name
    if not candidate or candidate in {".", ".."}:
        raise ValueError("Nazev VList souboru je povinny.")

    suffix = Path(candidate).suffix.lower()
    if not suffix:
        candidate = f"{candidate}.vlist"
        suffix = ".vlist"

    if suffix not in {".vlist", ".txt"}:
        raise ValueError("Podporovane jsou jen soubory .vlist nebo .txt.")

    return candidate


def write_vlist_bytes(file_name: str, content: bytes, *, overwrite: bool = False) -> Path:
    safe_name = sanitize_vlist_file_name(file_name)
    vlist_dir = get_vlist_dir()
    vlist_dir.mkdir(parents=True, exist_ok=True)

    target = vlist_dir / safe_name
    if target.exists() and not overwrite:
        raise FileExistsError(f"Soubor {safe_name} uz existuje.")

    target.write_bytes(content)
    return target


def generate_code(length: int = 5) -> str:
    return "".join(random.choices("0123456789", k=length))


def normalize_plc_type(value: str | None) -> str:
    raw = (value or "").strip().strip("$").upper()
    aliases = {
        "DT": "DT",
        "DATETIME": "DT",
        "DATE_TIME": "DT",
        "BOOL": "BOOL",
        "BOOLEAN": "BOOL",
    }
    return aliases.get(raw, raw)


def clean_vlist_name(raw_name: str) -> str:
    return raw_name.replace("$", "").strip()


def read_vlist_file(vlist_file: str | Path) -> list[str]:
    path = Path(vlist_file)
    with path.open("r", encoding="utf-8", errors="ignore") as file_handle:
        return file_handle.readlines()


def load_vlist_map(vlist_file: str | Path) -> dict[str, dict[str, Any]]:
    lines = read_vlist_file(vlist_file)
    result: dict[str, dict[str, Any]] = {}

    for line in lines[2:]:
        parts = line.strip().split(";")
        if len(parts) < 6:
            continue

        name = clean_vlist_name(parts[1])
        raw_type = normalize_plc_type(parts[2])
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


def split_name_to_parts(name: str) -> list[str]:
    return [part for part in name.split(".") if part]


def build_tree_node(names: list[str], path: list[str]) -> tuple[list[str], list[str]]:
    folders: set[str] = set()
    leaves: list[str] = []
    path_len = len(path)

    for name in names:
        parts = split_name_to_parts(name)
        if len(parts) < path_len:
            continue
        if path and parts[:path_len] != path:
            continue

        if len(parts) == path_len + 1:
            leaves.append(name)
        elif len(parts) > path_len + 1:
            folders.add(parts[path_len])

    return sorted(folders), sorted(leaves)


def guess_default_entity_type(plc_type: str, variable_name: str) -> str:
    options = PLC_TYPE_TO_ENTITIES.get(plc_type, ["sensor"])
    name = variable_name.lower()

    if plc_type == "DT":
        return "datetime" if "datetime" in options else options[0]

    if plc_type == "BOOL":
        writable_hint_tokens = [
            "cmd",
            "set",
            "write",
            "wr",
            "on",
            "off",
            "enable",
            "start",
            "stop",
        ]
        if any(token in name for token in writable_hint_tokens) and "switch" in options:
            return "switch"
        if "binary_sensor" in options:
            return "binary_sensor"

    return options[0]


def build_entity_detail_schema(entity_type: str, default_name: str) -> vol.Schema:
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
        fields[vol.Optional("device_class", default="")] = str
        fields[vol.Optional("suggested_display_precision", default=0)] = vol.Coerce(int)
        fields[vol.Optional("area_id", default="")] = str

    if entity_type == "select":
        for index in range(8):
            fields[vol.Optional(f"select_key_{index}", default="")] = str
            fields[vol.Optional(f"select_label_{index}", default="")] = str

    if entity_type == "button":
        fields[vol.Optional("press_time", default=0.1)] = vol.Coerce(float)

    if entity_type in ("sensor", "datetime"):
        fields[vol.Optional("unit_of_measurement", default="")] = str
        fields[vol.Optional("device_class", default="")] = str
        fields[vol.Optional("state_class", default="")] = str
        fields[vol.Optional("suggested_display_precision", default=0)] = vol.Coerce(int)
        fields[vol.Optional("area_id", default="")] = str

    return vol.Schema(fields)


def build_entity_entry(
    variable: dict[str, Any],
    entity_type: str,
    *,
    name: str | None = None,
    random_code: str | None = None,
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
    entity: dict[str, Any] = {
        "uid": int(variable["uid"]),
        "offset": int(variable.get("offset", 0)),
        "length": int(variable.get("length", 1)),
        "type": normalize_plc_type(variable["type"]),
        "entity_type": entity_type,
        "name": name or variable["name"],
        "name_vlist": variable["name"],
        "random_code": random_code or generate_code(),
    }

    if entity_type == "number":
        entity["min_value"] = 0.0 if min_value is None else min_value
        entity["max_value"] = 100.0 if max_value is None else max_value
        entity["step"] = 1.0 if step is None else step
        entity["mode"] = mode
        entity["unit_of_measurement"] = normalize_unit_of_measurement(unit_of_measurement)
        if device_class:
            entity["device_class"] = device_class
        if suggested_display_precision is not None:
            entity["suggested_display_precision"] = int(suggested_display_precision)

    if entity_type == "select":
        entity["select_options"] = dict(select_options or {})

    if entity_type == "button":
        entity["press_time"] = 0.1 if press_time is None else press_time

    if entity_type in ("sensor", "datetime"):
        entity["unit_of_measurement"] = normalize_unit_of_measurement(unit_of_measurement)
        if device_class:
            entity["device_class"] = device_class
        if state_class:
            entity["state_class"] = state_class
        if suggested_display_precision is not None:
            entity["suggested_display_precision"] = int(suggested_display_precision)

    if area_id:
        entity["area_id"] = area_id

    return entity


def is_duplicate_variable(
    current_variables: list[dict[str, Any]],
    selected_variable: dict[str, Any],
) -> bool:
    existing = {
        (str(item.get("name_vlist") or item.get("name")), int(item.get("uid", -1)))
        for item in current_variables
    }
    candidate = (selected_variable["name"], int(selected_variable["uid"]))
    return candidate in existing
