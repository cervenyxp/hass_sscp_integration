from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import SSCPDataCoordinator, SSCPDiagnosticsCoordinator
from .migration import ENTRY_MINOR_VERSION, ENTRY_VERSION, async_migrate_entry_data
from .transport import build_client_from_entry_data, has_connection_settings

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    current_minor = getattr(entry, "minor_version", 0)
    if entry.version > ENTRY_VERSION:
        _LOGGER.error(
            "Cannot migrate SSCP entry %s from newer version %s.%s",
            entry.entry_id,
            entry.version,
            current_minor,
        )
        return False

    if entry.version == ENTRY_VERSION and current_minor >= ENTRY_MINOR_VERSION:
        return True

    _LOGGER.info(
        "Migrating SSCP entry %s from version %s.%s to %s.%s",
        entry.entry_id,
        entry.version,
        current_minor,
        ENTRY_VERSION,
        ENTRY_MINOR_VERSION,
    )

    try:
        migrated_data = await async_migrate_entry_data(hass, dict(entry.data))
    except Exception:
        _LOGGER.exception("SSCP entry migration failed for %s", entry.entry_id)
        return False

    hass.config_entries.async_update_entry(
        entry,
        title=entry.title or migrated_data.get("PLC_Name", "PLC"),
        data=migrated_data,
        version=ENTRY_VERSION,
        minor_version=ENTRY_MINOR_VERSION,
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    from .frontend import async_setup_frontend
    from .http import async_register_http_views
    from .runtime import SSCPRuntime
    from .services import async_register_services

    client = None
    coordinator: SSCPDataCoordinator | None = None
    diagnostics_coordinator: SSCPDiagnosticsCoordinator | None = None
    startup_error: str | None = None

    if has_connection_settings(entry.data):
        client = build_client_from_entry_data(entry.data)
        try:
            await hass.async_add_executor_job(client.connect)
            await hass.async_add_executor_job(client.login)
            coordinator = SSCPDataCoordinator(hass, entry, client)
            await coordinator.async_config_entry_first_refresh()
            diagnostics_coordinator = SSCPDiagnosticsCoordinator(hass, entry, client, coordinator)
            await diagnostics_coordinator.async_config_entry_first_refresh()
        except Exception as exc:
            _LOGGER.error("PLC entry %s is loaded in offline mode: %s", entry.title or entry.entry_id, exc)
            if client is not None:
                await hass.async_add_executor_job(client.disconnect)
            startup_error = str(exc)
            client = None
            coordinator = None
            diagnostics_coordinator = None

    runtime = SSCPRuntime(hass, entry, client)
    await runtime.async_initialize()
    if startup_error:
        runtime.last_error = startup_error

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "runtime": runtime,
        "coordinator": coordinator,
        "diagnostics_coordinator": diagnostics_coordinator,
        "entry": entry,
    }

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await async_register_http_views(hass)
    await async_register_services(hass)
    await async_setup_frontend(hass, entry)
    if client is not None:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    client = entry_data.get("client") if entry_data else None
    if client is not None:
        await hass.async_add_executor_job(client.disconnect)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
