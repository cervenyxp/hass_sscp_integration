from __future__ import annotations

import base64
import binascii
import logging
from typing import Any

from aiohttp import web
from homeassistant.components.http import HomeAssistantView
from homeassistant.core import HomeAssistant

from .const import DOMAIN, FRONTEND_ACTION_PATH, FRONTEND_STATUS_PATH
from .runtime import async_domain_state_payload, resolve_runtime

_LOGGER = logging.getLogger(__name__)


def _ensure_admin(request) -> None:
    user = request["hass_user"] if "hass_user" in request else None
    if user is not None and not getattr(user, "is_admin", False):
        raise web.HTTPForbidden(text="Admin access required")


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


async def _async_create_plc_entry(hass: HomeAssistant) -> dict[str, Any]:
    flow_result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    if flow_result.get("type") == "form":
        flow_result = await hass.config_entries.flow.async_configure(flow_result["flow_id"], {})

    if flow_result.get("type") != "create_entry":
        raise ValueError("Nepodarilo se vytvorit novou PLC workspace entry.")

    await hass.async_block_till_done()
    entry = flow_result.get("result")
    return {
        "status": "created",
        "entry_id": getattr(entry, "entry_id", None),
    }


class SSCPStatusView(HomeAssistantView):
    url = FRONTEND_STATUS_PATH
    name = f"{DOMAIN}:status"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def get(self, request):
        _ensure_admin(request)
        return web.json_response(await async_domain_state_payload(self.hass))


class SSCPActionView(HomeAssistantView):
    url = FRONTEND_ACTION_PATH
    name = f"{DOMAIN}:action"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass

    async def post(self, request):
        _ensure_admin(request)
        payload = await request.json()
        action = payload.get("action")

        try:
            if action == "create_plc":
                result = await _async_create_plc_entry(self.hass)
                return web.json_response(result)

            runtime = resolve_runtime(self.hass, payload.get("entry_id"), allow_fallback=True)
            if runtime is None:
                return web.json_response({"error": "runtime_unavailable"}, status=503)

            if action == "refresh":
                result = await runtime.async_refresh_protocol_state()
                return web.json_response(result)

            if action == "browse_vlist":
                result = await runtime.async_browse_vlist(
                    path=payload.get("path") or [],
                    filter_text=payload.get("filter_text") or "",
                    limit=int(payload.get("limit", 200)),
                )
                return web.json_response(result)

            if action == "list_vlist_variables":
                result = await runtime.async_list_vlist_variables(
                    filter_text=payload.get("filter_text") or "",
                    limit=int(payload.get("limit", 5000)),
                )
                return web.json_response(result)

            if action == "save_config":
                result = await runtime.async_save_config(
                    plc_name=payload.get("plc_name", runtime.plc_name),
                    communication_mode=payload.get("communication_mode", runtime.communication_mode),
                    host=payload.get("host", ""),
                    port=str(payload.get("port", "")),
                    username=payload.get("username", ""),
                    password=payload.get("password", ""),
                    sscp_address=payload.get("sscp_address", "0x01"),
                    webpanel_connection=payload.get("webpanel_connection", "defaultConnection"),
                    webpanel_scheme=payload.get("webpanel_scheme", "http"),
                    scan_interval=int(payload.get("scan_interval", 5)),
                    vlist_file_name=payload.get("vlist_file_name", ""),
                    configuration_mode=payload.get("configuration_mode", "vlist"),
                )
                return web.json_response(result)

            if action == "add_variable":
                result = await runtime.async_add_variable(
                    variable_name=payload["variable_name"],
                    entity_type=payload.get("entity_type"),
                    display_name=payload.get("display_name"),
                    select_options=payload.get("select_options") or {},
                    unit_of_measurement=str(payload.get("unit_of_measurement", "")),
                    device_class=str(payload.get("device_class", "")),
                    state_class=str(payload.get("state_class", "")),
                    suggested_display_precision=_optional_int(payload.get("suggested_display_precision")),
                    area_id=str(payload.get("area_id", "")),
                    min_value=_optional_float(payload.get("min_value")),
                    max_value=_optional_float(payload.get("max_value")),
                    step=_optional_float(payload.get("step")),
                    mode=str(payload.get("mode", "box")),
                    press_time=_optional_float(payload.get("press_time")),
                )
                return web.json_response(result)

            if action == "add_manual_variable":
                result = await runtime.async_add_manual_variable(
                    variable_name=str(payload.get("variable_name", "")),
                    uid=int(payload.get("uid", 0)),
                    offset=int(payload.get("offset", 0)),
                    length=int(payload.get("length", 1)),
                    plc_type=str(payload.get("plc_type", "")),
                    entity_type=str(payload.get("entity_type", "")),
                    display_name=payload.get("display_name"),
                    unit_of_measurement=str(payload.get("unit_of_measurement", "")),
                    device_class=str(payload.get("device_class", "")),
                    state_class=str(payload.get("state_class", "")),
                    suggested_display_precision=_optional_int(payload.get("suggested_display_precision")),
                    area_id=str(payload.get("area_id", "")),
                    min_value=_optional_float(payload.get("min_value")),
                    max_value=_optional_float(payload.get("max_value")),
                    step=_optional_float(payload.get("step")),
                    mode=str(payload.get("mode", "box")),
                    press_time=_optional_float(payload.get("press_time")),
                    select_options=payload.get("select_options") or {},
                )
                return web.json_response(result)

            if action == "update_variable":
                result = await runtime.async_update_variable(
                    variable_entry_key=str(payload.get("variable_entry_key", "")),
                    display_name=payload.get("display_name"),
                    select_options=payload.get("select_options") or {},
                    unit_of_measurement=str(payload.get("unit_of_measurement", "")),
                    device_class=str(payload.get("device_class", "")),
                    state_class=str(payload.get("state_class", "")),
                    suggested_display_precision=_optional_int(payload.get("suggested_display_precision")),
                    area_id=str(payload.get("area_id", "")),
                    min_value=_optional_float(payload.get("min_value")),
                    max_value=_optional_float(payload.get("max_value")),
                    step=_optional_float(payload.get("step")),
                    mode=str(payload.get("mode", "box")),
                    press_time=_optional_float(payload.get("press_time")),
                )
                return web.json_response(result)

            if action == "save_climate_entity":
                result = await runtime.async_save_climate_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    area_id=str(payload.get("area_id", "")),
                    temperature_unit=str(payload.get("temperature_unit", "°C")),
                    suggested_display_precision=_optional_int(payload.get("suggested_display_precision")),
                    min_temp=_optional_float(payload.get("min_temp")),
                    max_temp=_optional_float(payload.get("max_temp")),
                    temp_step=_optional_float(payload.get("temp_step")),
                    current_temperature_name=str(payload.get("current_temperature_name", "")),
                    target_temperature_name=str(payload.get("target_temperature_name", "")),
                    current_humidity_name=str(payload.get("current_humidity_name", "")),
                    power_name=str(payload.get("power_name", "")),
                    hvac_mode_name=str(payload.get("hvac_mode_name", "")),
                    preset_name=str(payload.get("preset_name", "")),
                    hvac_mode_map=payload.get("hvac_mode_map") or {},
                    preset_map=payload.get("preset_map") or {},
                )
                return web.json_response(result)

            if action == "delete_climate_entity":
                result = await runtime.async_delete_climate_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "save_light_entity":
                result = await runtime.async_save_light_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    area_id=str(payload.get("area_id", "")),
                    suggested_display_precision=_optional_int(payload.get("suggested_display_precision")),
                    brightness_scale=_optional_float(payload.get("brightness_scale")),
                    min_mireds=_optional_int(payload.get("min_mireds")),
                    max_mireds=_optional_int(payload.get("max_mireds")),
                    power_name=str(payload.get("power_name", "")),
                    brightness_name=str(payload.get("brightness_name", "")),
                    color_temp_name=str(payload.get("color_temp_name", "")),
                    hs_hue_name=str(payload.get("hs_hue_name", "")),
                    hs_saturation_name=str(payload.get("hs_saturation_name", "")),
                    rgb_red_name=str(payload.get("rgb_red_name", "")),
                    rgb_green_name=str(payload.get("rgb_green_name", "")),
                    rgb_blue_name=str(payload.get("rgb_blue_name", "")),
                    white_name=str(payload.get("white_name", "")),
                    effect_name=str(payload.get("effect_name", "")),
                    effect_map=payload.get("effect_map") or {},
                )
                return web.json_response(result)

            if action == "delete_light_entity":
                result = await runtime.async_delete_light_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "save_cover_entity":
                result = await runtime.async_save_cover_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    area_id=str(payload.get("area_id", "")),
                    device_class=str(payload.get("device_class", "")),
                    invert_position=bool(payload.get("invert_position", False)),
                    current_position_name=str(payload.get("current_position_name", "")),
                    target_position_name=str(payload.get("target_position_name", "")),
                    open_name=str(payload.get("open_name", "")),
                    close_name=str(payload.get("close_name", "")),
                    stop_name=str(payload.get("stop_name", "")),
                    current_tilt_name=str(payload.get("current_tilt_name", "")),
                    target_tilt_name=str(payload.get("target_tilt_name", "")),
                    tilt_open_name=str(payload.get("tilt_open_name", "")),
                    tilt_close_name=str(payload.get("tilt_close_name", "")),
                    tilt_stop_name=str(payload.get("tilt_stop_name", "")),
                )
                return web.json_response(result)

            if action == "delete_cover_entity":
                result = await runtime.async_delete_cover_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "save_vacuum_entity":
                result = await runtime.async_save_vacuum_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    area_id=str(payload.get("area_id", "")),
                    status_name=str(payload.get("status_name", "")),
                    battery_level_name=str(payload.get("battery_level_name", "")),
                    battery_charging_name=str(payload.get("battery_charging_name", "")),
                    fan_speed_name=str(payload.get("fan_speed_name", "")),
                    start_name=str(payload.get("start_name", "")),
                    pause_name=str(payload.get("pause_name", "")),
                    stop_name=str(payload.get("stop_name", "")),
                    return_to_base_name=str(payload.get("return_to_base_name", "")),
                    locate_name=str(payload.get("locate_name", "")),
                    status_map=payload.get("status_map") or {},
                    fan_speed_map=payload.get("fan_speed_map") or {},
                )
                return web.json_response(result)

            if action == "delete_vacuum_entity":
                result = await runtime.async_delete_vacuum_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "save_fan_entity":
                result = await runtime.async_save_fan_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    area_id=str(payload.get("area_id", "")),
                    percentage_step=_optional_int(payload.get("percentage_step")),
                    power_name=str(payload.get("power_name", "")),
                    percentage_name=str(payload.get("percentage_name", "")),
                    preset_name=str(payload.get("preset_name", "")),
                    preset_map=payload.get("preset_map") or {},
                    oscillate_name=str(payload.get("oscillate_name", "")),
                    direction_name=str(payload.get("direction_name", "")),
                    direction_map=payload.get("direction_map") or {},
                )
                return web.json_response(result)

            if action == "delete_fan_entity":
                result = await runtime.async_delete_fan_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "save_humidifier_entity":
                result = await runtime.async_save_humidifier_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    area_id=str(payload.get("area_id", "")),
                    device_class=str(payload.get("device_class", "")),
                    min_humidity=_optional_float(payload.get("min_humidity")),
                    max_humidity=_optional_float(payload.get("max_humidity")),
                    target_humidity_step=_optional_float(payload.get("target_humidity_step")),
                    current_humidity_name=str(payload.get("current_humidity_name", "")),
                    target_humidity_name=str(payload.get("target_humidity_name", "")),
                    power_name=str(payload.get("power_name", "")),
                    mode_name=str(payload.get("mode_name", "")),
                    mode_map=payload.get("mode_map") or {},
                )
                return web.json_response(result)

            if action == "delete_humidifier_entity":
                result = await runtime.async_delete_humidifier_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "save_water_heater_entity":
                result = await runtime.async_save_water_heater_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    area_id=str(payload.get("area_id", "")),
                    temperature_unit=str(payload.get("temperature_unit", "Â°C")),
                    suggested_display_precision=_optional_int(payload.get("suggested_display_precision")),
                    min_temp=_optional_float(payload.get("min_temp")),
                    max_temp=_optional_float(payload.get("max_temp")),
                    temp_step=_optional_float(payload.get("temp_step")),
                    current_temperature_name=str(payload.get("current_temperature_name", "")),
                    target_temperature_name=str(payload.get("target_temperature_name", "")),
                    power_name=str(payload.get("power_name", "")),
                    operation_mode_name=str(payload.get("operation_mode_name", "")),
                    operation_mode_map=payload.get("operation_mode_map") or {},
                )
                return web.json_response(result)

            if action == "delete_water_heater_entity":
                result = await runtime.async_delete_water_heater_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "save_lock_entity":
                result = await runtime.async_save_lock_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    area_id=str(payload.get("area_id", "")),
                    state_name=str(payload.get("state_name", "")),
                    lock_name=str(payload.get("lock_name", "")),
                    unlock_name=str(payload.get("unlock_name", "")),
                    open_name=str(payload.get("open_name", "")),
                    state_map=payload.get("state_map") or {},
                )
                return web.json_response(result)

            if action == "delete_lock_entity":
                result = await runtime.async_delete_lock_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "save_valve_entity":
                result = await runtime.async_save_valve_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    area_id=str(payload.get("area_id", "")),
                    device_class=str(payload.get("device_class", "")),
                    invert_position=bool(payload.get("invert_position", False)),
                    current_position_name=str(payload.get("current_position_name", "")),
                    target_position_name=str(payload.get("target_position_name", "")),
                    open_name=str(payload.get("open_name", "")),
                    close_name=str(payload.get("close_name", "")),
                    stop_name=str(payload.get("stop_name", "")),
                )
                return web.json_response(result)

            if action == "delete_valve_entity":
                result = await runtime.async_delete_valve_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "save_siren_entity":
                result = await runtime.async_save_siren_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    area_id=str(payload.get("area_id", "")),
                    state_name=str(payload.get("state_name", "")),
                    turn_on_name=str(payload.get("turn_on_name", "")),
                    turn_off_name=str(payload.get("turn_off_name", "")),
                    tone_name=str(payload.get("tone_name", "")),
                    tone_map=payload.get("tone_map") or {},
                    duration_name=str(payload.get("duration_name", "")),
                    volume_name=str(payload.get("volume_name", "")),
                    volume_scale=_optional_float(payload.get("volume_scale")),
                )
                return web.json_response(result)

            if action == "delete_siren_entity":
                result = await runtime.async_delete_siren_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "save_scheduler_entity":
                result = await runtime.async_save_scheduler_entity(
                    entity_key=str(payload.get("entity_key", "")).strip() or None,
                    name=str(payload.get("name", "")),
                    root_name=str(payload.get("root_name", "")),
                    area_id=str(payload.get("area_id", "")),
                    suggested_display_precision=_optional_int(payload.get("suggested_display_precision")),
                )
                return web.json_response(result)

            if action == "delete_scheduler_entity":
                result = await runtime.async_delete_scheduler_entity(entity_key=str(payload.get("entity_key", "")))
                return web.json_response(result)

            if action == "upload_vlist":
                try:
                    content = base64.b64decode(str(payload.get("content_base64", "")), validate=True)
                except binascii.Error as err:
                    raise ValueError("Obsah nahravaneho VList souboru je neplatny.") from err

                result = await runtime.async_upload_vlist(
                    file_name=str(payload.get("file_name", "")),
                    content=content,
                    overwrite=bool(payload.get("overwrite", False)),
                )
                return web.json_response(result)

            if action == "delete_variable":
                result = await runtime.async_delete_variable(variable_entry_key=payload["variable_entry_key"])
                return web.json_response(result)

            if action == "reload_from_vlist":
                result = await runtime.async_reload_from_vlist()
                return web.json_response(result)

            if action == "sync_time":
                result = await runtime.async_sync_time(mode=payload.get("mode", "utc"))
                return web.json_response(result)

            if action == "set_plc_time":
                result = await runtime.async_set_plc_time(
                    value=str(payload.get("value", "")),
                    mode=str(payload.get("mode", "local")),
                )
                return web.json_response(result)

            if action == "get_scheduler":
                result = await runtime.async_get_scheduler(root_name=str(payload.get("root_name", "")))
                return web.json_response(result)

            if action == "save_scheduler":
                result = await runtime.async_save_scheduler(
                    root_name=str(payload.get("root_name", "")),
                    default_value=payload.get("default_value"),
                    weekly_items=payload.get("weekly_items") or [],
                )
                return web.json_response(result)

            return web.json_response({"error": "unknown_action"}, status=400)
        except (KeyError, TypeError, ValueError) as err:
            return web.json_response(
                {
                    "error": "validation_error",
                    "message": str(err),
                },
                status=400,
            )
        except Exception as err:
            _LOGGER.exception("Unhandled SSCP panel action error for %s", action)
            return web.json_response(
                {
                    "error": "internal_error",
                    "message": str(err),
                },
                status=500,
            )


async def async_register_http_views(hass: HomeAssistant) -> None:
    if hass.data.setdefault(f"{DOMAIN}_http_registered", False):
        return
    hass.http.register_view(SSCPStatusView(hass))
    hass.http.register_view(SSCPActionView(hass))
    hass.data[f"{DOMAIN}_http_registered"] = True
