# Mervis / Domat SSCP Integration

Custom Home Assistant integration for Mervis / Domat PLC projects with:

- SSCP protocol support
- WebPanel API support
- Studio UI for PLC setup, VList browsing and entity composition
- Classic variable entities and composed entities like climate, light, cover, vacuum and scheduler

## Legacy Update Compatibility

This codebase is prepared to migrate from the older on-disk version in:

`C:\projekty\hass_sscp_integration\custom_components\sscp_integration`

Checked compatibility points:

- legacy config entries using `PLC_Name`, `host`, `port`, `username`, `password`, `sscp_address`, `configuration_mode`, `vlist_file` and `variables`
- legacy variable metadata such as `uid`, `offset`, `length`, `type`, `entity_type`, `name`, `name_vlist`, `random_code`
- legacy per-entity options like `select_options`, `press_time`, `min_value`, `max_value`, `step`, `mode` and `unit_of_measurement`
- preserved classic entity `unique_id` patterns for `sensor`, `binary_sensor`, `switch`, `light`, `button`, `number`, `select` and `datetime`

Result:

- existing classic entities should stay bound after update as long as the original `config_entry` remains the same
- migration fills new defaults for communication mode, scan interval and Studio sections without dropping legacy variables
- newer composed entity sections are also normalized so partially edited config data does not easily break the UI

## GitHub Prep

This folder now includes a `.gitignore` that keeps local runtime clutter and private VList files out of git:

- Python cache folders
- local temp data in `%TEMP%`
- private `vlist_files/*.vlist`

The sample `vlist_files/example.vlist` remains trackable.

## Before Publishing

- replace the placeholder `documentation` URL in `manifest.json` with the real GitHub repository or docs URL
- review `vlist_files/` and make sure no private customer exports are committed
- initialize git in this folder or copy it into your target repository
