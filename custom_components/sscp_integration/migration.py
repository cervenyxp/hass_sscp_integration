from __future__ import annotations

from collections import defaultdict
import logging
from pathlib import Path
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant

from .const import (
    COMM_MODE_SSCP,
    COMM_MODE_WEBPANEL,
    CONF_COMMUNICATION_MODE,
    CONF_SCAN_INTERVAL,
    CONF_WEBPANEL_CONNECTION,
    CONF_WEBPANEL_SCHEME,
    DEFAULT_SCAN_INTERVAL_SECONDS,
)
from .studio_models import build_variable_ref, detect_scheduler_blocks
from .transport import communication_mode_from_data
from .vlist import (
    ALL_ENTITY_TYPES,
    PLC_TYPE_TO_ENTITIES,
    SUPPORTED_PLC_TYPES,
    generate_code,
    guess_default_entity_type,
    load_vlist_map,
    normalize_plc_type,
    normalize_unit_of_measurement,
    resolve_vlist_file,
)

_LOGGER = logging.getLogger(__name__)

ENTRY_VERSION = 2
ENTRY_MINOR_VERSION = 2


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_scan_interval(value: Any) -> int:
    parsed = _optional_int(value)
    if parsed is None:
        return DEFAULT_SCAN_INTERVAL_SECONDS
    return max(1, parsed)


def _normalize_vlist_path(raw_value: Any) -> str:
    normalized = str(raw_value or "").strip()
    if not normalized:
        return ""

    path = Path(normalized)
    if path.exists():
        return str(path)

    fallback_name = path.name
    if not fallback_name:
        return normalized

    fallback_path = resolve_vlist_file(fallback_name)
    if fallback_path.exists():
        return str(fallback_path)
    return normalized


def _normalize_select_options(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        items = value.items()
    elif isinstance(value, list):
        items = []
        for item in value:
            if isinstance(item, dict):
                key = item.get("key")
                label = item.get("label")
                if key not in (None, "") and label not in (None, ""):
                    items.append((key, label))
    else:
        return {}

    normalized: dict[str, str] = {}
    for raw_key, raw_label in items:
        key = str(raw_key).strip()
        label = str(raw_label).strip()
        if key and label:
            normalized[key] = label
    return normalized


def _normalize_label_map(value: Any, *, lowercase_values: bool = False) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}

    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        mapped = str(raw_value).strip()
        if lowercase_values:
            mapped = mapped.lower()
        if key and mapped:
            normalized[key] = mapped
    return normalized


def _normalize_supported_entity_type(plc_type: str, entity_type: Any, variable_name: str) -> str:
    allowed = PLC_TYPE_TO_ENTITIES.get(plc_type, ["sensor"])
    normalized = str(entity_type or "").strip().lower()
    if normalized in allowed and normalized in ALL_ENTITY_TYPES:
        return normalized
    return guess_default_entity_type(plc_type, variable_name)


def _build_vlist_signature_index(vlist_map: dict[str, dict[str, Any]]) -> dict[tuple[int, int, int, str], list[str]]:
    index: dict[tuple[int, int, int, str], list[str]] = defaultdict(list)
    for name, item in vlist_map.items():
        try:
            signature = (
                int(item["uid"]),
                int(item.get("offset", 0)),
                int(item.get("length", 1)),
                normalize_plc_type(item.get("type")),
            )
        except (KeyError, TypeError, ValueError):
            continue
        index[signature].append(name)
    return index


def _infer_name_vlist(
    variable: dict[str, Any],
    *,
    display_name: str,
    plc_type: str,
    uid: int,
    offset: int,
    length: int,
    vlist_map: dict[str, dict[str, Any]],
    signature_index: dict[tuple[int, int, int, str], list[str]],
) -> str:
    configured = str(variable.get("name_vlist") or "").strip()
    if configured:
        return configured

    if display_name in vlist_map:
        return display_name

    matches = signature_index.get((uid, offset, length, plc_type), [])
    if len(matches) == 1:
        return matches[0]

    uid_matches = [
        name
        for name, item in vlist_map.items()
        if int(item.get("uid", -1)) == uid and normalize_plc_type(item.get("type")) == plc_type
    ]
    if len(uid_matches) == 1:
        return uid_matches[0]

    return display_name


def _normalize_variable_ref(value: Any, vlist_map: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    if not value:
        return None
    if isinstance(value, str):
        candidate = vlist_map.get(value.strip())
        return build_variable_ref(candidate) if candidate else None
    if not isinstance(value, dict):
        return None

    try:
        uid = int(value["uid"])
        offset = int(value.get("offset", 0))
        length = int(value.get("length", 1))
    except (KeyError, TypeError, ValueError):
        name_hint = str(value.get("name_vlist") or value.get("name") or "").strip()
        candidate = vlist_map.get(name_hint)
        return build_variable_ref(candidate) if candidate else None

    plc_type = normalize_plc_type(value.get("type"))
    name = str(value.get("name") or value.get("name_vlist") or "").strip()
    name_vlist = str(value.get("name_vlist") or value.get("name") or "").strip()

    if name_vlist in vlist_map:
        return build_variable_ref(vlist_map[name_vlist])

    return {
        "uid": uid,
        "offset": offset,
        "length": length,
        "type": plc_type,
        "name": name or name_vlist,
        "name_vlist": name_vlist or name,
    }


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value or "").strip().lower()
    if normalized in {"1", "true", "on", "yes"}:
        return True
    if normalized in {"0", "false", "off", "no", ""}:
        return False
    return bool(normalized)


def _build_reference_catalog(
    vlist_map: dict[str, dict[str, Any]],
    variables: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = dict(vlist_map)
    for variable in variables:
        for key in (
            str(variable.get("name_vlist") or "").strip(),
            str(variable.get("name") or "").strip(),
        ):
            if key:
                catalog[key] = variable
    return catalog


def _resolve_entity_variable_ref(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
    *keys: str,
) -> dict[str, Any] | None:
    for key in keys:
        if key not in entity:
            continue
        ref = _normalize_variable_ref(entity.get(key), reference_catalog)
        if ref is not None:
            return ref
    return None


def _normalize_variable(
    variable: dict[str, Any],
    *,
    vlist_map: dict[str, dict[str, Any]],
    signature_index: dict[tuple[int, int, int, str], list[str]],
) -> dict[str, Any] | None:
    if not isinstance(variable, dict):
        return None

    try:
        uid = int(variable["uid"])
    except (KeyError, TypeError, ValueError):
        _LOGGER.warning("Skipping legacy SSCP variable without valid uid: %s", variable)
        return None

    offset = _optional_int(variable.get("offset"))
    length = _optional_int(variable.get("length"))
    plc_type = normalize_plc_type(variable.get("type"))

    if offset is None:
        offset = 0
    if length is None or length < 1:
        length = 1
    if plc_type not in SUPPORTED_PLC_TYPES:
        plc_type = str(variable.get("type") or "").strip().upper() or "BYTE"

    display_name = str(variable.get("name") or variable.get("name_vlist") or f"Variable {uid}").strip()
    name_vlist = _infer_name_vlist(
        variable,
        display_name=display_name,
        plc_type=plc_type,
        uid=uid,
        offset=offset,
        length=length,
        vlist_map=vlist_map,
        signature_index=signature_index,
    )
    entity_type = _normalize_supported_entity_type(plc_type, variable.get("entity_type"), name_vlist or display_name)

    normalized = dict(variable)
    normalized["uid"] = uid
    normalized["offset"] = offset
    normalized["length"] = length
    normalized["type"] = plc_type
    normalized["entity_type"] = entity_type
    normalized["name"] = display_name or name_vlist or f"Variable {uid}"
    normalized["name_vlist"] = name_vlist or display_name or f"Variable {uid}"
    normalized["random_code"] = str(variable.get("random_code") or "").strip() or generate_code()

    unit = normalize_unit_of_measurement(variable.get("unit_of_measurement"))
    if entity_type in {"sensor", "datetime", "number"}:
        normalized["unit_of_measurement"] = unit
    elif "unit_of_measurement" in normalized and unit:
        normalized["unit_of_measurement"] = unit

    if entity_type == "number":
        normalized["min_value"] = 0.0 if _optional_float(variable.get("min_value")) is None else float(variable["min_value"])
        normalized["max_value"] = 100.0 if _optional_float(variable.get("max_value")) is None else float(variable["max_value"])
        normalized["step"] = 1.0 if _optional_float(variable.get("step")) is None else float(variable["step"])
        mode = str(variable.get("mode") or "box").strip().lower()
        normalized["mode"] = mode if mode in {"box", "slider"} else "box"
        device_class = str(variable.get("device_class") or "").strip()
        if device_class:
            normalized["device_class"] = device_class
        else:
            normalized.pop("device_class", None)
    elif entity_type in {"sensor", "datetime"}:
        device_class = str(variable.get("device_class") or "").strip()
        state_class = str(variable.get("state_class") or "").strip()
        if device_class:
            normalized["device_class"] = device_class
        else:
            normalized.pop("device_class", None)
        if state_class and entity_type == "sensor":
            normalized["state_class"] = state_class
        else:
            normalized.pop("state_class", None)
    else:
        normalized.pop("state_class", None)

    precision = _optional_int(variable.get("suggested_display_precision"))
    if precision is not None and precision >= 0:
        normalized["suggested_display_precision"] = precision
    else:
        normalized.pop("suggested_display_precision", None)

    area_id = str(variable.get("area_id") or "").strip()
    if area_id:
        normalized["area_id"] = area_id
    else:
        normalized.pop("area_id", None)

    if entity_type == "select":
        normalized["select_options"] = _normalize_select_options(variable.get("select_options"))

    if entity_type == "button":
        normalized["press_time"] = 0.1 if _optional_float(variable.get("press_time")) is None else float(variable["press_time"])

    return normalized


def _reference_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name_vlist") or value.get("name") or "").strip()
    return str(value or "").strip()


def _normalize_entity_key(entity: dict[str, Any]) -> str:
    return str(entity.get("entity_key") or uuid4().hex[:10]).strip() or uuid4().hex[:10]


def _normalize_precision(value: Any) -> int | None:
    precision = _optional_int(value)
    if precision is None or precision >= 0:
        return precision
    return None


def _normalized_range(min_value: Any, max_value: Any, *, default_min: float, default_max: float) -> tuple[float, float]:
    normalized_min = default_min if _optional_float(min_value) is None else float(min_value)
    normalized_max = default_max if _optional_float(max_value) is None else float(max_value)
    if normalized_min > normalized_max:
        normalized_min, normalized_max = normalized_max, normalized_min
    return normalized_min, normalized_max


def _normalized_positive_float(value: Any, *, default: float) -> float:
    normalized = _optional_float(value)
    if normalized is None or normalized <= 0:
        return default
    return float(normalized)


def _normalized_positive_int(value: Any, *, default: int) -> int:
    normalized = _optional_int(value)
    if normalized is None or normalized <= 0:
        return default
    return int(normalized)


def _normalize_optional_ordered_int_pair(min_value: Any, max_value: Any) -> tuple[int | None, int | None]:
    normalized_min = _optional_int(min_value)
    normalized_max = _optional_int(max_value)
    if normalized_min is not None and normalized_max is not None and normalized_min > normalized_max:
        normalized_min, normalized_max = normalized_max, normalized_min
    return normalized_min, normalized_max


def _normalize_composed_entity(
    entity: dict[str, Any],
    *,
    default_name: str,
    name_fallback_keys: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    if not isinstance(entity, dict):
        return None

    normalized = {
        "entity_key": _normalize_entity_key(entity),
        "area_id": str(entity.get("area_id") or "").strip(),
    }

    entity_name = str(entity.get("name") or "").strip()
    if not entity_name:
        for key in name_fallback_keys:
            candidate = _reference_name(entity.get(key))
            if candidate:
                entity_name = candidate.split(".")[-1]
                break
    normalized["name"] = entity_name or default_name

    return normalized


def _normalize_composed_entity_list(
    value: Any,
    *,
    normalizer,
) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    normalized_items: list[dict[str, Any]] = []
    for entity in value:
        normalized = normalizer(entity)
        if normalized is not None:
            normalized_items.append(normalized)
    return normalized_items


def _normalize_climate_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Climate",
        name_fallback_keys=(
            "target_temperature_var",
            "target_temperature_name",
            "current_temperature_var",
            "current_temperature_name",
            "power_var",
            "power_name",
        ),
    )
    if normalized is None:
        return None

    min_temp, max_temp = _normalized_range(
        entity.get("min_temp"),
        entity.get("max_temp"),
        default_min=7.0,
        default_max=35.0,
    )
    normalized.update(
        {
            "temperature_unit": normalize_unit_of_measurement(entity.get("temperature_unit") or "degC") or "degC",
            "suggested_display_precision": _normalize_precision(entity.get("suggested_display_precision")),
            "min_temp": min_temp,
            "max_temp": max_temp,
            "temp_step": _normalized_positive_float(entity.get("temp_step"), default=0.5),
            "current_temperature_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "current_temperature_var",
                "current_temperature_name",
            ),
            "target_temperature_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "target_temperature_var",
                "target_temperature_name",
            ),
            "current_humidity_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "current_humidity_var",
                "current_humidity_name",
            ),
            "power_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "power_var",
                "power_name",
            ),
            "hvac_mode_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "hvac_mode_var",
                "hvac_mode_name",
            ),
            "preset_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "preset_var",
                "preset_name",
            ),
            "hvac_mode_map": _normalize_label_map(entity.get("hvac_mode_map"), lowercase_values=True),
            "preset_map": _normalize_label_map(entity.get("preset_map")),
        }
    )
    return normalized


def _normalize_light_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Light",
        name_fallback_keys=(
            "power_var",
            "power_name",
            "brightness_var",
            "brightness_name",
            "color_temp_var",
            "color_temp_name",
            "white_var",
            "white_name",
        ),
    )
    if normalized is None:
        return None

    min_mireds, max_mireds = _normalize_optional_ordered_int_pair(
        entity.get("min_mireds"),
        entity.get("max_mireds"),
    )
    normalized.update(
        {
            "suggested_display_precision": _normalize_precision(entity.get("suggested_display_precision")),
            "brightness_scale": _normalized_positive_float(entity.get("brightness_scale"), default=100.0),
            "min_mireds": min_mireds,
            "max_mireds": max_mireds,
            "power_var": _resolve_entity_variable_ref(entity, reference_catalog, "power_var", "power_name"),
            "brightness_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "brightness_var",
                "brightness_name",
            ),
            "color_temp_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "color_temp_var",
                "color_temp_name",
            ),
            "hs_hue_var": _resolve_entity_variable_ref(entity, reference_catalog, "hs_hue_var", "hs_hue_name"),
            "hs_saturation_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "hs_saturation_var",
                "hs_saturation_name",
            ),
            "rgb_red_var": _resolve_entity_variable_ref(entity, reference_catalog, "rgb_red_var", "rgb_red_name"),
            "rgb_green_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "rgb_green_var",
                "rgb_green_name",
            ),
            "rgb_blue_var": _resolve_entity_variable_ref(entity, reference_catalog, "rgb_blue_var", "rgb_blue_name"),
            "white_var": _resolve_entity_variable_ref(entity, reference_catalog, "white_var", "white_name"),
            "effect_var": _resolve_entity_variable_ref(entity, reference_catalog, "effect_var", "effect_name"),
            "effect_map": _normalize_label_map(entity.get("effect_map")),
        }
    )
    return normalized


def _normalize_cover_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Cover",
        name_fallback_keys=(
            "target_position_var",
            "target_position_name",
            "open_var",
            "open_name",
            "close_var",
            "close_name",
        ),
    )
    if normalized is None:
        return None

    normalized.update(
        {
            "device_class": str(entity.get("device_class") or "").strip().lower(),
            "invert_position": _as_bool(entity.get("invert_position")),
            "current_position_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "current_position_var",
                "current_position_name",
            ),
            "target_position_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "target_position_var",
                "target_position_name",
            ),
            "open_var": _resolve_entity_variable_ref(entity, reference_catalog, "open_var", "open_name"),
            "close_var": _resolve_entity_variable_ref(entity, reference_catalog, "close_var", "close_name"),
            "stop_var": _resolve_entity_variable_ref(entity, reference_catalog, "stop_var", "stop_name"),
            "current_tilt_position_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "current_tilt_position_var",
                "current_tilt_name",
                "current_tilt_position_name",
            ),
            "target_tilt_position_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "target_tilt_position_var",
                "target_tilt_name",
                "target_tilt_position_name",
            ),
            "tilt_open_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "tilt_open_var",
                "tilt_open_name",
            ),
            "tilt_close_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "tilt_close_var",
                "tilt_close_name",
            ),
            "tilt_stop_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "tilt_stop_var",
                "tilt_stop_name",
            ),
        }
    )
    return normalized


def _normalize_vacuum_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Vacuum",
        name_fallback_keys=(
            "status_var",
            "status_name",
            "start_var",
            "start_name",
            "return_to_base_var",
            "return_to_base_name",
        ),
    )
    if normalized is None:
        return None

    normalized.update(
        {
            "status_var": _resolve_entity_variable_ref(entity, reference_catalog, "status_var", "status_name"),
            "battery_level_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "battery_level_var",
                "battery_level_name",
            ),
            "battery_charging_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "battery_charging_var",
                "battery_charging_name",
            ),
            "fan_speed_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "fan_speed_var",
                "fan_speed_name",
            ),
            "start_var": _resolve_entity_variable_ref(entity, reference_catalog, "start_var", "start_name"),
            "pause_var": _resolve_entity_variable_ref(entity, reference_catalog, "pause_var", "pause_name"),
            "stop_var": _resolve_entity_variable_ref(entity, reference_catalog, "stop_var", "stop_name"),
            "return_to_base_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "return_to_base_var",
                "return_to_base_name",
            ),
            "locate_var": _resolve_entity_variable_ref(entity, reference_catalog, "locate_var", "locate_name"),
            "status_map": _normalize_label_map(entity.get("status_map"), lowercase_values=True),
            "fan_speed_map": _normalize_label_map(entity.get("fan_speed_map")),
        }
    )
    return normalized


def _normalize_fan_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Fan",
        name_fallback_keys=(
            "power_var",
            "power_name",
            "percentage_var",
            "percentage_name",
            "preset_var",
            "preset_name",
        ),
    )
    if normalized is None:
        return None

    normalized.update(
        {
            "percentage_step": _normalized_positive_int(entity.get("percentage_step"), default=1),
            "power_var": _resolve_entity_variable_ref(entity, reference_catalog, "power_var", "power_name"),
            "percentage_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "percentage_var",
                "percentage_name",
            ),
            "preset_var": _resolve_entity_variable_ref(entity, reference_catalog, "preset_var", "preset_name"),
            "oscillate_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "oscillate_var",
                "oscillate_name",
            ),
            "direction_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "direction_var",
                "direction_name",
            ),
            "preset_map": _normalize_label_map(entity.get("preset_map")),
            "direction_map": _normalize_label_map(entity.get("direction_map"), lowercase_values=True),
        }
    )
    return normalized


def _normalize_humidifier_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Humidifier",
        name_fallback_keys=(
            "target_humidity_var",
            "target_humidity_name",
            "power_var",
            "power_name",
            "mode_var",
            "mode_name",
        ),
    )
    if normalized is None:
        return None

    min_humidity, max_humidity = _normalized_range(
        entity.get("min_humidity"),
        entity.get("max_humidity"),
        default_min=0.0,
        default_max=100.0,
    )
    normalized.update(
        {
            "device_class": str(entity.get("device_class") or "").strip().lower(),
            "min_humidity": min_humidity,
            "max_humidity": max_humidity,
            "target_humidity_step": _normalized_positive_float(entity.get("target_humidity_step"), default=1.0),
            "current_humidity_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "current_humidity_var",
                "current_humidity_name",
            ),
            "target_humidity_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "target_humidity_var",
                "target_humidity_name",
            ),
            "power_var": _resolve_entity_variable_ref(entity, reference_catalog, "power_var", "power_name"),
            "mode_var": _resolve_entity_variable_ref(entity, reference_catalog, "mode_var", "mode_name"),
            "mode_map": _normalize_label_map(entity.get("mode_map")),
        }
    )
    return normalized


def _normalize_water_heater_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Water Heater",
        name_fallback_keys=(
            "target_temperature_var",
            "target_temperature_name",
            "power_var",
            "power_name",
            "operation_mode_var",
            "operation_mode_name",
        ),
    )
    if normalized is None:
        return None

    min_temp, max_temp = _normalized_range(
        entity.get("min_temp"),
        entity.get("max_temp"),
        default_min=30.0,
        default_max=90.0,
    )
    normalized.update(
        {
            "temperature_unit": normalize_unit_of_measurement(entity.get("temperature_unit") or "degC") or "degC",
            "suggested_display_precision": _normalize_precision(entity.get("suggested_display_precision")),
            "min_temp": min_temp,
            "max_temp": max_temp,
            "temp_step": _normalized_positive_float(entity.get("temp_step"), default=0.5),
            "current_temperature_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "current_temperature_var",
                "current_temperature_name",
            ),
            "target_temperature_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "target_temperature_var",
                "target_temperature_name",
            ),
            "power_var": _resolve_entity_variable_ref(entity, reference_catalog, "power_var", "power_name"),
            "operation_mode_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "operation_mode_var",
                "operation_mode_name",
            ),
            "operation_mode_map": _normalize_label_map(
                entity.get("operation_mode_map"),
                lowercase_values=True,
            ),
        }
    )
    return normalized


def _normalize_lock_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Lock",
        name_fallback_keys=(
            "state_var",
            "state_name",
            "lock_var",
            "lock_name",
            "unlock_var",
            "unlock_name",
        ),
    )
    if normalized is None:
        return None

    normalized.update(
        {
            "state_var": _resolve_entity_variable_ref(entity, reference_catalog, "state_var", "state_name"),
            "lock_var": _resolve_entity_variable_ref(entity, reference_catalog, "lock_var", "lock_name"),
            "unlock_var": _resolve_entity_variable_ref(entity, reference_catalog, "unlock_var", "unlock_name"),
            "open_var": _resolve_entity_variable_ref(entity, reference_catalog, "open_var", "open_name"),
            "state_map": _normalize_label_map(entity.get("state_map"), lowercase_values=True),
        }
    )
    return normalized


def _normalize_valve_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Valve",
        name_fallback_keys=(
            "target_position_var",
            "target_position_name",
            "open_var",
            "open_name",
            "close_var",
            "close_name",
        ),
    )
    if normalized is None:
        return None

    normalized.update(
        {
            "device_class": str(entity.get("device_class") or "").strip().lower(),
            "invert_position": _as_bool(entity.get("invert_position")),
            "current_position_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "current_position_var",
                "current_position_name",
            ),
            "target_position_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "target_position_var",
                "target_position_name",
            ),
            "open_var": _resolve_entity_variable_ref(entity, reference_catalog, "open_var", "open_name"),
            "close_var": _resolve_entity_variable_ref(entity, reference_catalog, "close_var", "close_name"),
            "stop_var": _resolve_entity_variable_ref(entity, reference_catalog, "stop_var", "stop_name"),
        }
    )
    return normalized


def _normalize_siren_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Siren",
        name_fallback_keys=(
            "state_var",
            "state_name",
            "turn_on_var",
            "turn_on_name",
            "turn_off_var",
            "turn_off_name",
        ),
    )
    if normalized is None:
        return None

    normalized.update(
        {
            "state_var": _resolve_entity_variable_ref(entity, reference_catalog, "state_var", "state_name"),
            "turn_on_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "turn_on_var",
                "turn_on_name",
            ),
            "turn_off_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "turn_off_var",
                "turn_off_name",
            ),
            "tone_var": _resolve_entity_variable_ref(entity, reference_catalog, "tone_var", "tone_name"),
            "duration_var": _resolve_entity_variable_ref(
                entity,
                reference_catalog,
                "duration_var",
                "duration_name",
            ),
            "volume_var": _resolve_entity_variable_ref(entity, reference_catalog, "volume_var", "volume_name"),
            "volume_scale": _normalized_positive_float(entity.get("volume_scale"), default=100.0),
            "tone_map": _normalize_label_map(entity.get("tone_map")),
        }
    )
    return normalized


def _resolve_scheduler_root_name(
    entity: dict[str, Any],
    scheduler_blocks: dict[str, dict[str, Any]],
) -> str:
    explicit_root = str(entity.get("root_name") or "").strip()
    if explicit_root:
        return explicit_root

    output_name = _reference_name(entity.get("out_var")) or _reference_name(entity.get("output_name"))
    default_value_name = _reference_name(entity.get("default_value_var")) or _reference_name(entity.get("default_value_name"))
    for root_name, block in scheduler_blocks.items():
        if output_name and output_name == _reference_name(block.get("out")):
            return root_name
        if default_value_name and default_value_name == _reference_name(block.get("defaultvalue")):
            return root_name
    return ""


def _infer_scheduler_kind(
    raw_kind: Any,
    out_var: dict[str, Any] | None,
    default_value_var: dict[str, Any] | None,
) -> str:
    normalized_kind = str(raw_kind or "").strip().lower()
    aliases = {
        "boolean": "bool",
        "integer": "int",
        "float": "real",
    }
    normalized_kind = aliases.get(normalized_kind, normalized_kind)
    if normalized_kind in {"bool", "int", "real"}:
        return normalized_kind

    for ref in (out_var, default_value_var):
        if not isinstance(ref, dict):
            continue
        plc_type = normalize_plc_type(ref.get("type"))
        if plc_type == "BOOL":
            return "bool"
        if plc_type in {"BYTE", "WORD", "INT", "UINT", "DINT", "UDINT", "LINT"}:
            return "int"
        if plc_type in {"REAL", "LREAL"}:
            return "real"
    return "real"


def _normalize_scheduler_entity(
    entity: dict[str, Any],
    reference_catalog: dict[str, dict[str, Any]],
    scheduler_blocks: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    normalized = _normalize_composed_entity(
        entity,
        default_name="Scheduler",
        name_fallback_keys=("root_name", "output_name", "default_value_name"),
    )
    if normalized is None:
        return None

    root_name = _resolve_scheduler_root_name(entity, scheduler_blocks)
    out_var = _resolve_entity_variable_ref(entity, reference_catalog, "out_var", "output_name")
    default_value_var = _resolve_entity_variable_ref(
        entity,
        reference_catalog,
        "default_value_var",
        "default_value_name",
    )
    block = scheduler_blocks.get(root_name)
    if block is not None:
        if block.get("out") is not None:
            out_var = block.get("out")
        if block.get("defaultvalue") is not None:
            default_value_var = block.get("defaultvalue")

    normalized.update(
        {
            "root_name": root_name,
            "kind": str(block.get("kind")) if block is not None else _infer_scheduler_kind(entity.get("kind"), out_var, default_value_var),
            "supports_exceptions": bool(block.get("supports_exceptions")) if block is not None else _as_bool(entity.get("supports_exceptions")),
            "point_capacity": len(block.get("points", {})) if block is not None else max(0, _optional_int(entity.get("point_capacity")) or 0),
            "exception_capacity": len(block.get("exceptions", {})) if block is not None else max(0, _optional_int(entity.get("exception_capacity")) or 0),
            "suggested_display_precision": _normalize_precision(entity.get("suggested_display_precision")),
            "out_var": out_var,
            "default_value_var": default_value_var,
        }
    )
    return normalized


async def async_migrate_entry_data(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    normalized_data = dict(data)
    vlist_path = await hass.async_add_executor_job(_normalize_vlist_path, data.get("vlist_file"))
    vlist_map: dict[str, dict[str, Any]] = {}
    if vlist_path and await hass.async_add_executor_job(Path(vlist_path).exists):
        try:
            vlist_map = await hass.async_add_executor_job(load_vlist_map, vlist_path)
        except Exception as err:
            _LOGGER.warning("Unable to load legacy VList during migration (%s): %s", vlist_path, err)
    signature_index = _build_vlist_signature_index(vlist_map)

    normalized_variables = []
    raw_variables = data.get("variables")
    if not isinstance(raw_variables, list):
        raw_variables = []
    for variable in raw_variables:
        normalized_variable = _normalize_variable(
            variable,
            vlist_map=vlist_map,
            signature_index=signature_index,
        )
        if normalized_variable is not None:
            normalized_variables.append(normalized_variable)

    reference_catalog = _build_reference_catalog(vlist_map, normalized_variables)
    scheduler_blocks = detect_scheduler_blocks(vlist_map) if vlist_map else {}

    normalized_climates = _normalize_composed_entity_list(
        data.get("climate_entities"),
        normalizer=lambda entity: _normalize_climate_entity(entity, reference_catalog),
    )
    normalized_lights = _normalize_composed_entity_list(
        data.get("light_entities"),
        normalizer=lambda entity: _normalize_light_entity(entity, reference_catalog),
    )
    normalized_covers = _normalize_composed_entity_list(
        data.get("cover_entities"),
        normalizer=lambda entity: _normalize_cover_entity(entity, reference_catalog),
    )
    normalized_vacuums = _normalize_composed_entity_list(
        data.get("vacuum_entities"),
        normalizer=lambda entity: _normalize_vacuum_entity(entity, reference_catalog),
    )
    normalized_fans = _normalize_composed_entity_list(
        data.get("fan_entities"),
        normalizer=lambda entity: _normalize_fan_entity(entity, reference_catalog),
    )
    normalized_humidifiers = _normalize_composed_entity_list(
        data.get("humidifier_entities"),
        normalizer=lambda entity: _normalize_humidifier_entity(entity, reference_catalog),
    )
    normalized_water_heaters = _normalize_composed_entity_list(
        data.get("water_heater_entities"),
        normalizer=lambda entity: _normalize_water_heater_entity(entity, reference_catalog),
    )
    normalized_locks = _normalize_composed_entity_list(
        data.get("lock_entities"),
        normalizer=lambda entity: _normalize_lock_entity(entity, reference_catalog),
    )
    normalized_valves = _normalize_composed_entity_list(
        data.get("valve_entities"),
        normalizer=lambda entity: _normalize_valve_entity(entity, reference_catalog),
    )
    normalized_sirens = _normalize_composed_entity_list(
        data.get("siren_entities"),
        normalizer=lambda entity: _normalize_siren_entity(entity, reference_catalog),
    )
    normalized_schedulers = _normalize_composed_entity_list(
        data.get("scheduler_entities"),
        normalizer=lambda entity: _normalize_scheduler_entity(entity, reference_catalog, scheduler_blocks),
    )

    webpanel_scheme = str(data.get(CONF_WEBPANEL_SCHEME, "http") or "http").strip().lower()
    if webpanel_scheme not in {"http", "https"}:
        webpanel_scheme = "http"

    configuration_mode = str(data.get("configuration_mode") or "vlist").strip().lower() or "vlist"
    if configuration_mode not in {"vlist", "manual"}:
        configuration_mode = "vlist"

    normalized_data.update(
        {
            "PLC_Name": str(data.get("PLC_Name") or data.get("plc_name") or "PLC").strip() or "PLC",
            "host": str(data.get("host") or "").strip(),
            "port": str(data.get("port") or "").strip(),
            "username": str(data.get("username") or "").strip(),
            "password": str(data.get("password") or ""),
            "sscp_address": str(data.get("sscp_address") or "0x01").strip() or "0x01",
            "configuration_mode": configuration_mode,
            "vlist_file": vlist_path,
            "variables": normalized_variables,
            "climate_entities": normalized_climates,
            "light_entities": normalized_lights,
            "cover_entities": normalized_covers,
            "vacuum_entities": normalized_vacuums,
            "fan_entities": normalized_fans,
            "humidifier_entities": normalized_humidifiers,
            "water_heater_entities": normalized_water_heaters,
            "lock_entities": normalized_locks,
            "valve_entities": normalized_valves,
            "siren_entities": normalized_sirens,
            "scheduler_entities": normalized_schedulers,
            CONF_COMMUNICATION_MODE: communication_mode_from_data(data),
            CONF_WEBPANEL_CONNECTION: str(data.get(CONF_WEBPANEL_CONNECTION) or "defaultConnection").strip()
            or "defaultConnection",
            CONF_WEBPANEL_SCHEME: webpanel_scheme,
            CONF_SCAN_INTERVAL: _normalize_scan_interval(data.get(CONF_SCAN_INTERVAL)),
        }
    )

    if normalized_data[CONF_COMMUNICATION_MODE] not in {COMM_MODE_SSCP, COMM_MODE_WEBPANEL}:
        normalized_data[CONF_COMMUNICATION_MODE] = COMM_MODE_SSCP

    return normalized_data
