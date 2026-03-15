from __future__ import annotations

from collections.abc import Iterable, Iterator
import re
from typing import Any


def make_variable_key(variable: dict[str, Any]) -> str:
    return (
        f"{variable.get('uid')}:{variable.get('offset', 0)}:{variable.get('length', 1)}:"
        f"{variable.get('name_vlist') or variable.get('name')}"
    )


def build_variable_ref(variable: dict[str, Any] | None) -> dict[str, Any] | None:
    if not variable:
        return None
    return {
        "uid": int(variable["uid"]),
        "offset": int(variable.get("offset", 0)),
        "length": int(variable.get("length", 1)),
        "type": str(variable["type"]),
        "name": str(variable.get("name") or variable.get("name_vlist") or ""),
        "name_vlist": str(variable.get("name_vlist") or variable.get("name") or ""),
    }


def variable_ref_name(variable: dict[str, Any] | None) -> str:
    if not variable:
        return ""
    return str(variable.get("name_vlist") or variable.get("name") or "")


def climate_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "temperature_unit": entity.get("temperature_unit"),
        "suggested_display_precision": entity.get("suggested_display_precision"),
        "min_temp": entity.get("min_temp"),
        "max_temp": entity.get("max_temp"),
        "temp_step": entity.get("temp_step"),
        "current_temperature_name": variable_ref_name(entity.get("current_temperature_var")),
        "target_temperature_name": variable_ref_name(entity.get("target_temperature_var")),
        "current_humidity_name": variable_ref_name(entity.get("current_humidity_var")),
        "power_name": variable_ref_name(entity.get("power_var")),
        "hvac_mode_name": variable_ref_name(entity.get("hvac_mode_var")),
        "preset_name": variable_ref_name(entity.get("preset_var")),
        "hvac_mode_map": dict(entity.get("hvac_mode_map") or {}),
        "preset_map": dict(entity.get("preset_map") or {}),
    }


def light_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "suggested_display_precision": entity.get("suggested_display_precision"),
        "brightness_scale": entity.get("brightness_scale"),
        "min_mireds": entity.get("min_mireds"),
        "max_mireds": entity.get("max_mireds"),
        "power_name": variable_ref_name(entity.get("power_var")),
        "brightness_name": variable_ref_name(entity.get("brightness_var")),
        "color_temp_name": variable_ref_name(entity.get("color_temp_var")),
        "hs_hue_name": variable_ref_name(entity.get("hs_hue_var")),
        "hs_saturation_name": variable_ref_name(entity.get("hs_saturation_var")),
        "rgb_red_name": variable_ref_name(entity.get("rgb_red_var")),
        "rgb_green_name": variable_ref_name(entity.get("rgb_green_var")),
        "rgb_blue_name": variable_ref_name(entity.get("rgb_blue_var")),
        "white_name": variable_ref_name(entity.get("white_var")),
        "effect_name": variable_ref_name(entity.get("effect_var")),
        "effect_map": dict(entity.get("effect_map") or {}),
    }


def cover_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "device_class": entity.get("device_class"),
        "invert_position": bool(entity.get("invert_position")),
        "current_position_name": variable_ref_name(entity.get("current_position_var")),
        "target_position_name": variable_ref_name(entity.get("target_position_var")),
        "open_name": variable_ref_name(entity.get("open_var")),
        "close_name": variable_ref_name(entity.get("close_var")),
        "stop_name": variable_ref_name(entity.get("stop_var")),
        "current_tilt_name": variable_ref_name(entity.get("current_tilt_position_var")),
        "target_tilt_name": variable_ref_name(entity.get("target_tilt_position_var")),
        "tilt_open_name": variable_ref_name(entity.get("tilt_open_var")),
        "tilt_close_name": variable_ref_name(entity.get("tilt_close_var")),
        "tilt_stop_name": variable_ref_name(entity.get("tilt_stop_var")),
    }


def vacuum_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "status_name": variable_ref_name(entity.get("status_var")),
        "battery_level_name": variable_ref_name(entity.get("battery_level_var")),
        "battery_charging_name": variable_ref_name(entity.get("battery_charging_var")),
        "fan_speed_name": variable_ref_name(entity.get("fan_speed_var")),
        "start_name": variable_ref_name(entity.get("start_var")),
        "pause_name": variable_ref_name(entity.get("pause_var")),
        "stop_name": variable_ref_name(entity.get("stop_var")),
        "return_to_base_name": variable_ref_name(entity.get("return_to_base_var")),
        "locate_name": variable_ref_name(entity.get("locate_var")),
        "status_map": dict(entity.get("status_map") or {}),
        "fan_speed_map": dict(entity.get("fan_speed_map") or {}),
    }


def fan_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "percentage_step": entity.get("percentage_step"),
        "power_name": variable_ref_name(entity.get("power_var")),
        "percentage_name": variable_ref_name(entity.get("percentage_var")),
        "preset_name": variable_ref_name(entity.get("preset_var")),
        "oscillate_name": variable_ref_name(entity.get("oscillate_var")),
        "direction_name": variable_ref_name(entity.get("direction_var")),
        "preset_map": dict(entity.get("preset_map") or {}),
        "direction_map": dict(entity.get("direction_map") or {}),
    }


def humidifier_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "device_class": entity.get("device_class"),
        "min_humidity": entity.get("min_humidity"),
        "max_humidity": entity.get("max_humidity"),
        "target_humidity_step": entity.get("target_humidity_step"),
        "current_humidity_name": variable_ref_name(entity.get("current_humidity_var")),
        "target_humidity_name": variable_ref_name(entity.get("target_humidity_var")),
        "power_name": variable_ref_name(entity.get("power_var")),
        "mode_name": variable_ref_name(entity.get("mode_var")),
        "mode_map": dict(entity.get("mode_map") or {}),
    }
 

def water_heater_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "temperature_unit": entity.get("temperature_unit"),
        "suggested_display_precision": entity.get("suggested_display_precision"),
        "min_temp": entity.get("min_temp"),
        "max_temp": entity.get("max_temp"),
        "temp_step": entity.get("temp_step"),
        "current_temperature_name": variable_ref_name(entity.get("current_temperature_var")),
        "target_temperature_name": variable_ref_name(entity.get("target_temperature_var")),
        "power_name": variable_ref_name(entity.get("power_var")),
        "operation_mode_name": variable_ref_name(entity.get("operation_mode_var")),
        "operation_mode_map": dict(entity.get("operation_mode_map") or {}),
    }
 

def lock_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "state_name": variable_ref_name(entity.get("state_var")),
        "lock_name": variable_ref_name(entity.get("lock_var")),
        "unlock_name": variable_ref_name(entity.get("unlock_var")),
        "open_name": variable_ref_name(entity.get("open_var")),
        "state_map": dict(entity.get("state_map") or {}),
    }


def valve_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "device_class": entity.get("device_class"),
        "invert_position": bool(entity.get("invert_position")),
        "current_position_name": variable_ref_name(entity.get("current_position_var")),
        "target_position_name": variable_ref_name(entity.get("target_position_var")),
        "open_name": variable_ref_name(entity.get("open_var")),
        "close_name": variable_ref_name(entity.get("close_var")),
        "stop_name": variable_ref_name(entity.get("stop_var")),
    }


def siren_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "state_name": variable_ref_name(entity.get("state_var")),
        "turn_on_name": variable_ref_name(entity.get("turn_on_var")),
        "turn_off_name": variable_ref_name(entity.get("turn_off_var")),
        "tone_name": variable_ref_name(entity.get("tone_var")),
        "duration_name": variable_ref_name(entity.get("duration_var")),
        "volume_name": variable_ref_name(entity.get("volume_var")),
        "volume_scale": entity.get("volume_scale"),
        "tone_map": dict(entity.get("tone_map") or {}),
    }


def scheduler_entity_payload(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        "entity_key": entity.get("entity_key"),
        "name": entity.get("name"),
        "area_id": entity.get("area_id"),
        "root_name": entity.get("root_name"),
        "kind": entity.get("kind"),
        "supports_exceptions": bool(entity.get("supports_exceptions")),
        "point_capacity": entity.get("point_capacity"),
        "exception_capacity": entity.get("exception_capacity"),
        "suggested_display_precision": entity.get("suggested_display_precision"),
        "output_name": variable_ref_name(entity.get("out_var")),
        "default_value_name": variable_ref_name(entity.get("default_value_var")),
    }


def iter_climate_variable_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in (
        "current_temperature_var",
        "target_temperature_var",
        "current_humidity_var",
        "power_var",
        "hvac_mode_var",
        "preset_var",
    ):
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


def iter_light_variable_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in (
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
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


def iter_cover_variable_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in (
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
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


def iter_vacuum_variable_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in (
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
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


def iter_fan_variable_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in ("power_var", "percentage_var", "preset_var", "oscillate_var", "direction_var"):
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


def iter_humidifier_variable_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in ("current_humidity_var", "target_humidity_var", "power_var", "mode_var"):
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


def iter_water_heater_variable_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in ("current_temperature_var", "target_temperature_var", "power_var", "operation_mode_var"):
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


def iter_lock_variable_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in ("state_var", "lock_var", "unlock_var", "open_var"):
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


def iter_valve_variable_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in ("current_position_var", "target_position_var", "open_var", "close_var", "stop_var"):
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


def iter_siren_variable_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in ("state_var", "turn_on_var", "turn_off_var", "tone_var", "duration_var", "volume_var"):
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


def iter_scheduler_entity_refs(entity: dict[str, Any]) -> Iterator[dict[str, Any]]:
    for key in ("out_var", "default_value_var"):
        ref = entity.get(key)
        if isinstance(ref, dict) and ref.get("uid") is not None:
            yield ref


SCHEDULER_TOKENS = {
    "t17_boolean_scheduler": {"kind": "bool", "supports_exceptions": True},
    "t18_real_scheduler": {"kind": "real", "supports_exceptions": True},
    "t19_int_scheduler": {"kind": "int", "supports_exceptions": True},
    "t19_integer_scheduler": {"kind": "int", "supports_exceptions": True},
    "t17_boolean_scheduler_base": {"kind": "bool", "supports_exceptions": False},
    "t18_real_scheduler_base": {"kind": "real", "supports_exceptions": False},
    "t19_int_scheduler_base": {"kind": "int", "supports_exceptions": False},
    "t19_integer_scheduler_base": {"kind": "int", "supports_exceptions": False},
}

NONBASE_EVENT_RE = re.compile(
    r"^(?P<root>.+\.(?P<token>t17_boolean_scheduler|t18_real_scheduler|t19_int_scheduler|t19_integer_scheduler))"
    r"\.base\.tpgvalue\.\[(?P<index>\d+)\]\.(?P<field>starttime|state)$",
    re.IGNORECASE,
)
NONBASE_EXCEPTION_RE = re.compile(
    r"^(?P<root>.+\.(?P<token>t17_boolean_scheduler|t18_real_scheduler|t19_int_scheduler|t19_integer_scheduler))"
    r"\.exceptions\.\[(?P<index>\d+)\]\.(?P<field>starttime|endtime|state)$",
    re.IGNORECASE,
)
NONBASE_AUX_RE = re.compile(
    r"^(?P<root>.+\.(?P<token>t17_boolean_scheduler|t18_real_scheduler|t19_int_scheduler|t19_integer_scheduler))"
    r"\.base\.(?P<field>defaultvalue|out)$",
    re.IGNORECASE,
)
BASE_EVENT_RE = re.compile(
    r"^(?P<root>.+\.(?P<token>t17_boolean_scheduler_base|t18_real_scheduler_base|t19_int_scheduler_base|t19_integer_scheduler_base))"
    r"\.tpgvalue\.\[(?P<index>\d+)\]\.(?P<field>starttime|state)$",
    re.IGNORECASE,
)
BASE_AUX_RE = re.compile(
    r"^(?P<root>.+\.(?P<token>t17_boolean_scheduler_base|t18_real_scheduler_base|t19_int_scheduler_base|t19_integer_scheduler_base))"
    r"\.(?P<field>defaultvalue|out)$",
    re.IGNORECASE,
)


def _ensure_scheduler_block(
    catalog: dict[str, dict[str, Any]],
    root_name: str,
    token: str,
) -> dict[str, Any]:
    block = catalog.get(root_name)
    if block is not None:
        return block

    metadata = SCHEDULER_TOKENS[token.casefold()]
    block = {
        "root_name": root_name,
        "kind": metadata["kind"],
        "supports_exceptions": metadata["supports_exceptions"],
        "points": {},
        "exceptions": {},
        "defaultvalue": None,
        "out": None,
    }
    catalog[root_name] = block
    return block


def detect_scheduler_blocks(vlist_data: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}

    for name, variable in vlist_data.items():
        matched = False
        for regex in (NONBASE_EVENT_RE, NONBASE_EXCEPTION_RE, NONBASE_AUX_RE, BASE_EVENT_RE, BASE_AUX_RE):
            result = regex.match(name)
            if not result:
                continue
            token = str(result.group("token")).casefold()
            root_name = result.group("root")
            block = _ensure_scheduler_block(catalog, root_name, token)
            field = result.group("field")

            if "index" in result.groupdict() and result.group("index") is not None:
                index = int(result.group("index"))
                if regex in (NONBASE_EVENT_RE, BASE_EVENT_RE):
                    item = block["points"].setdefault(index, {})
                else:
                    item = block["exceptions"].setdefault(index, {})
                item[field] = build_variable_ref(variable)
            else:
                block[field] = build_variable_ref(variable)

            matched = True
            break

        if not matched:
            continue

    return {
        root_name: block
        for root_name, block in catalog.items()
        if block["points"] and block.get("defaultvalue") is not None
    }


def scheduler_catalog_payload(blocks: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for block in blocks:
        payload.append(
            {
                "root_name": block["root_name"],
                "name": block["root_name"].split(".")[-1],
                "kind": block["kind"],
                "supports_exceptions": block["supports_exceptions"],
                "point_capacity": len(block["points"]),
                "exception_capacity": len(block["exceptions"]),
                "output_name": variable_ref_name(block.get("out")),
                "default_value_name": variable_ref_name(block.get("defaultvalue")),
            }
        )
    return sorted(payload, key=lambda item: item["root_name"])


def group_weekly_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = [{"day": day, "points": []} for day in range(7)]
    for item in sorted(points, key=lambda point: (point["day"], point["minute_of_day"], point["index"])):
        grouped[item["day"]]["points"].append(item)
    return grouped


def minutes_to_day_time(total_minutes: int) -> tuple[int, int]:
    if total_minutes < 0:
        total_minutes = 0
    day = min(6, total_minutes // 1440)
    minute_of_day = total_minutes % 1440
    return day, minute_of_day


def schedule_value_from_ui(value: Any, kind: str) -> Any:
    if kind == "bool":
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "on", "yes"}:
                return True
            if normalized in {"0", "false", "off", "no", ""}:
                return False
        return bool(value)
    if kind == "int":
        return int(value)
    return float(value)


def compact_weekly_items(items: Iterable[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in items:
        if raw.get("starttime") in (None, ""):
            continue
        starttime = int(raw["starttime"])
        if starttime < 0 or starttime >= 65535:
            continue
        value = schedule_value_from_ui(raw.get("value"), kind)
        normalized.append({"starttime": starttime, "value": value})

    normalized.sort(key=lambda item: item["starttime"])

    compacted: list[dict[str, Any]] = []
    for item in normalized:
        if compacted and compacted[-1]["starttime"] == item["starttime"]:
            compacted[-1] = item
            continue
        if compacted and compacted[-1]["value"] == item["value"]:
            continue
        compacted.append(item)
    return compacted
