from __future__ import annotations

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN
from .runtime import resolve_runtime

SERVICE_REFRESH_RUNTIME = "refresh_runtime"
SERVICE_SYNC_TIME = "sync_time"
SERVICE_SET_PLC_TIME = "set_plc_time"
SERVICE_RELOAD_FROM_VLIST = "reload_from_vlist"


async def async_register_services(hass: HomeAssistant) -> None:
    if hass.data.setdefault(f"{DOMAIN}_services_registered", False):
        return

    async def _refresh_runtime(call: ServiceCall) -> None:
        runtime = resolve_runtime(hass, call.data.get("entry_id"))
        if runtime is not None:
            await runtime.async_refresh_protocol_state()
            entry_state = hass.data.get(DOMAIN, {}).get(runtime.entry.entry_id, {})
            coordinator = entry_state.get("coordinator")
            diagnostics_coordinator = entry_state.get("diagnostics_coordinator")
            if coordinator is not None:
                await coordinator.async_request_refresh()
            if diagnostics_coordinator is not None:
                await diagnostics_coordinator.async_request_refresh()

    async def _sync_time(call: ServiceCall) -> None:
        runtime = resolve_runtime(hass, call.data.get("entry_id"))
        if runtime is not None:
            await runtime.async_sync_time(mode=call.data.get("mode", "utc"))
            entry_state = hass.data.get(DOMAIN, {}).get(runtime.entry.entry_id, {})
            diagnostics_coordinator = entry_state.get("diagnostics_coordinator")
            if diagnostics_coordinator is not None:
                await diagnostics_coordinator.async_request_refresh()

    async def _set_plc_time(call: ServiceCall) -> None:
        runtime = resolve_runtime(hass, call.data.get("entry_id"))
        if runtime is not None:
            await runtime.async_set_plc_time(
                value=call.data.get("value", ""),
                mode=call.data.get("mode", "local"),
            )

    async def _reload_from_vlist(call: ServiceCall) -> None:
        runtime = resolve_runtime(hass, call.data.get("entry_id"))
        if runtime is not None:
            await runtime.async_reload_from_vlist()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_RUNTIME,
        _refresh_runtime,
        schema=vol.Schema({vol.Optional("entry_id"): str}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SYNC_TIME,
        _sync_time,
        schema=vol.Schema(
            {
                vol.Optional("entry_id"): str,
                vol.Optional("mode", default="utc"): vol.In(["utc", "local"]),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_PLC_TIME,
        _set_plc_time,
        schema=vol.Schema(
            {
                vol.Optional("entry_id"): str,
                vol.Required("value"): str,
                vol.Optional("mode", default="local"): vol.In(["utc", "local"]),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RELOAD_FROM_VLIST,
        _reload_from_vlist,
        schema=vol.Schema({vol.Optional("entry_id"): str}),
    )

    hass.data[f"{DOMAIN}_services_registered"] = True
