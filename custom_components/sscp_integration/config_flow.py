import os
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from .sscp_client import SSCPClient
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

def read_vlist_file(vlist_file):
    _LOGGER.debug("Reading vlist file: %s", vlist_file)
    with open(vlist_file, "r") as f:
        return f.readlines()
    
import random

def generate_code(length=5):
    return ''.join(random.choices('0123456789', k=length))
    

class SSCPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    def __init__(self):
        self.vlist_data = {}        

    async def async_step_user(self, user_input=None):
        errors = {}
        vlist_files = []
        try:
            vlist_dir = "/config/custom_components/sscp_integration/vlist_files"
            vlist_files = await self.hass.async_add_executor_job(os.listdir, vlist_dir)
        except Exception as e:
            _LOGGER.error("Error listing vlist files: %s", e)
            errors["base"] = "file_listing_failed"

        if user_input is not None:
            if "sscp_address" not in user_input:
                user_input["sscp_address"] = "1"

            _LOGGER.debug("User input received: %s", user_input)

            try:
                client = SSCPClient(
                    str(user_input["host"]),
                    str(user_input["port"]),
                    str(user_input["username"]),
                    str(user_input["password"]),
                    str(user_input["sscp_address"]),
                    str(user_input["PLC_Name"])
                )
                client.connect()
                client.login()
                self.client = client
                self.config = user_input
                if user_input["configuration_mode"] == "vlist":
                    if user_input["vlist_file"] == "No files found":
                        errors["vlist_file"] = "no_files"
                    else:
                        self.config["vlist_file"] = os.path.join(vlist_dir, user_input["vlist_file"])
                        return await self.async_step_vlist_select()
                else:
                    return await self.async_step_manual_input()
            except Exception as e:
                _LOGGER.error("Failed to connect/login to SSCP server: %s", e)
                errors["base"] = "connection_failed"

        data_schema = vol.Schema({
            vol.Required("PLC_Name", default="PLC"): str,
            vol.Required("host", default="172.19.0.31"): str,
            vol.Required("port", default="12346"): str,
            vol.Required("username", default="admin"): str,
            vol.Required("password", default="rw"): str,
            vol.Required("sscp_address", default="0x01"): str,
            vol.Required("configuration_mode", default="vlist"): vol.In(["vlist", "manual"]),
            vol.Optional("vlist_file", default=vlist_files[0] if vlist_files else "No files found"): vol.In(vlist_files),
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_vlist_select(self, user_input=None):
        errors = {}

        if user_input is not None:
            selected_var = user_input["variable"]
            var_data = self.vlist_data[selected_var]
            self.config.update(var_data)
            self.config["name"] = selected_var
            return await self.async_step_hass_config()

        if not self.vlist_data:
            try:
                lines = await self.hass.async_add_executor_job(read_vlist_file, self.config["vlist_file"])
                for idx, line in enumerate(lines[2:], start=3):
                    parts = line.strip().split(";")
                    if len(parts) >= 6:
                        name = parts[1].replace("$", "")
                        self.vlist_data[name] = {
                            "project": parts[0],
                            "uid": int(parts[3]),
                            "type": parts[2].strip('$'),
                            "offset": int(parts[4]) if parts[4] else 0,
                            "length": int(parts[5]) if parts[5] else 1,
                            "parent_type_family": parts[6] if len(parts) > 6 else "none",
                            "history_id": parts[7] if len(parts) > 7 else None,
                        }
            except Exception as e:
                _LOGGER.error("Failed to load vlist file: %s", e)
                errors["base"] = "vlist_load_failed"

        variable_options = list(self.vlist_data.keys())
        if not variable_options:
            errors["base"] = "no_variables"

        data_schema = vol.Schema({
            vol.Required("variable"): vol.In(variable_options),
        })

        return self.async_show_form(step_id="vlist_select", data_schema=data_schema, errors=errors)

    async def async_step_manual_input(self, user_input=None):
        errors = {}

        if user_input is not None:
            self.config.update(user_input)
            self.config["name"] = user_input["name"]
            return await self.async_step_hass_config()

        data_schema = vol.Schema({
            vol.Required("comm_uid"): int,
            vol.Required("offset", default=0): int,
            vol.Required("length", default=1): int,
            vol.Optional("name", default="Manual Entity"): str,
        })

        return self.async_show_form(step_id="manual_input", data_schema=data_schema, errors=errors)

    async def async_step_hass_config(self, user_input=None):
        errors = {}
        known_units = ["°C", "°F", "K", "Pa", "kPa", "hPa", "bar", "psi", "m/s", "km/h", "mph", "W", "kW", "MW", "V", "mV", "A", "mA", "Hz", "kHz", "%", "g", "kg", "t", "m", "cm", "mm", "km", "l", "ml", "m³"]

        if user_input is not None:
            self.config.update(user_input)
            try:
                value = self.client.read_variable(
                    self.config["uid"],
                    self.config["offset"],
                    self.config["length"],
                    self.config["type"]
                )
                _LOGGER.info("Variable value read successfully: %s", value)

                if "variables" not in self.config:
                    self.config["variables"] = []

                variable = {
                    "uid": self.config["uid"],
                    "offset": self.config["offset"],
                    "length": self.config["length"],
                    "type": self.config["type"],
                    "name": self.config["name"],
                    "entity_type": user_input["entity_type"],
                }

                if user_input["entity_type"] not in ["switch", "binary_sensor", "button", "light"]:
                    variable["unit_of_measurement"] = user_input.get("unit_of_measurement")

                if user_input["entity_type"] == "select":
                    options_map = {}
                    for i in range(5):
                        key = user_input.get(f"select_key_{i}")
                        label = user_input.get(f"select_label_{i}")
                        if key and label:
                            options_map[key.strip()] = label.strip()
                    variable["select_options"] = options_map

                self.config["variables"].append(variable)

                if user_input.get("finish", False):
                    return self.async_create_entry(title=self.config["PLC_Name"], data=self.config)
                else:
                    if self.config.get("configuration_mode") == "vlist":
                        return await self.async_step_vlist_select()
                    else:
                        return await self.async_step_manual_input()
            except Exception as e:
                _LOGGER.error("Failed to read variable: %s", e)
                errors["base"] = "read_failed"

        data_dict = {
            vol.Required("entity_type", default="sensor"): vol.In(["sensor", "binary_sensor", "switch", "number", "select", "button", "light"]),
            vol.Required("domain", default="generic"): str,
        }

        if user_input is None or user_input.get("entity_type", "sensor") not in ["switch", "binary_sensor", "button", "light"]:
            data_dict[vol.Optional("unit_of_measurement", default="°C")] = vol.In(known_units)

        if user_input is None or user_input.get("entity_type", "sensor") == "select":
            for i in range(5):
                data_dict[vol.Optional(f"select_key_{i}", default="")] = str
                data_dict[vol.Optional(f"select_label_{i}", default="")] = str

        data_dict[vol.Optional("finish", default=False)] = bool

        data_schema = vol.Schema(data_dict)

        return self.async_show_form(step_id="hass_config", data_schema=data_schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        from .config_flow import SSCPOptionsFlow
        return SSCPOptionsFlow(config_entry)

class SSCPOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        super().__init__()
        self.config_entry = config_entry
        self.selected_entity = None
        self.vlist_data = {}
        self.original_config = dict(config_entry.data)
        self.current_variables = list(config_entry.data.get("variables", []))

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            if user_input["action"] == "edit_entities":
                return await self.async_step_manage_entities()
            elif user_input["action"] == "reload_from_vlist":
                await self.reload_from_vlist()
                return self.async_create_entry(title="", data={})
            elif user_input["action"] == "add_entity_from_vlist":
                return await self.async_step_add_entity_from_vlist()

        data_schema = vol.Schema({
            vol.Optional("host", default=self.config_entry.data.get("host", "")): str,
            vol.Optional("port", default=self.config_entry.data.get("port", "")): str,
            vol.Optional("username", default=self.config_entry.data.get("username", "")): str,
            vol.Optional("password", default=self.config_entry.data.get("password", "")): str,
            vol.Optional("sscp_address", default=self.config_entry.data.get("sscp_address", "")): str,
            vol.Required("action", default="edit_entities"): vol.In({
                "edit_entities": "Editovat entity",
                "reload_from_vlist": "Načíst znovu z .vlist",
                "add_entity_from_vlist": "Přidat entitu z .vlist",
            })
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)

    async def async_step_manage_entities(self, user_input=None):
        if user_input is not None:
            # najdeme tuple (index, entity) podle vybrané položky
            selected_name = user_input.get("entity")
            try:
                idx, ent = next(
                    (i, var)
                    for i, var in enumerate(self.current_variables)
                    if f"{var['name']} (UID: {var['uid']})" == selected_name
                )
            except StopIteration:
                return self.async_abort(reason="entity_not_found")
            self.selected_entity = (idx, ent)

            if user_input["action"] == "edit_entity":
                return await self.async_step_edit_entity()
            if user_input["action"] == "delete_entity":
                return await self.async_step_confirm_delete_entity()
            if user_input["action"] == "save_and_reload":
                await self._update_config_entry(self.current_variables)
                return self.async_create_entry(title="Uloženo", data={})
        entities = [
            f"{entity['name']} (UID: {entity['uid']})"
            for entity in self.config_entry.data.get("variables", [])
        ]
        if not entities:
            return self.async_abort(reason="no_entities")

        data_schema = vol.Schema({
            vol.Required("entity"): vol.In(entities),
            vol.Required("action", default="edit_entity"): vol.In({
                "edit_entity": "Editovat entitu",
                "delete_entity": "Smazat entitu",
                "save_and_reload": "Uložit změny a reload"
            })
        })

        return self.async_show_form(step_id="manage_entities", data_schema=data_schema)


    async def async_step_hass_config(self, user_input=None):
        errors = {}
        known_units = ["°C", "°F", "K", "Pa", "kPa", "hPa", "bar", "psi", "m/s", "km/h", "mph", "W", "kW", "MW", "V", "mV", "A", "mA", "Hz", "kHz", "%", "g", "kg", "t", "m", "cm", "mm", "km", "l", "ml", "m³"]

        if user_input is not None:
            self.config.update(user_input)
            try:
                value = self.client.read_variable(
                    self.config["uid"],
                    self.config["offset"],
                    self.config["length"],
                    self.config["type"]
                )
                _LOGGER.info("Variable value read successfully: %s", value)

                if "variables" not in self.config:
                    self.config["variables"] = []

                variable = {
                    "uid": self.config["uid"],
                    "offset": self.config["offset"],
                    "length": self.config["length"],
                    "type": self.config["type"],
                    "name": self.config["name"],
                    "entity_type": user_input["entity_type"],
                }

                if user_input["entity_type"] not in ["switch", "binary_sensor", "button", "light"]:
                    variable["unit_of_measurement"] = user_input.get("unit_of_measurement")

                if user_input["entity_type"] == "select":
                    options_map = {}
                    for i in range(5):
                        key = user_input.get(f"select_key_{i}")
                        label = user_input.get(f"select_label_{i}")
                        if key and label:
                            options_map[key.strip()] = label.strip()
                    variable["select_options"] = options_map

                self.config["variables"].append(variable)

                if user_input.get("finish", False):
                    return self.async_create_entry(title=self.config["PLC_Name"], data=self.config)
                else:
                    if self.config.get("configuration_mode") == "vlist":
                        return await self.async_step_vlist_select()
                    else:
                        return await self.async_step_manual_input()
            except Exception as e:
                _LOGGER.error("Failed to read variable: %s", e)
                errors["base"] = "read_failed"

        data_dict = {
            vol.Required("entity_type", default="sensor"): vol.In(["sensor", "binary_sensor", "switch", "number", "select", "button", "light"]),
            vol.Required("domain", default="generic"): str,
        }

        if user_input is None or user_input.get("entity_type", "sensor") not in ["switch", "binary_sensor", "button", "light"]:
            data_dict[vol.Optional("unit_of_measurement", default="°C")] = vol.In(known_units)

        if user_input is None or user_input.get("entity_type", "sensor") == "select":
            for i in range(5):
                data_dict[vol.Optional(f"select_key_{i}", default="")] = str
                data_dict[vol.Optional(f"select_label_{i}", default="")] = str

        data_dict[vol.Optional("finish", default=False)] = bool

        data_schema = vol.Schema(data_dict)

        return self.async_show_form(step_id="hass_config", data_schema=data_schema, errors=errors)

    async def async_step_edit_entity(self, user_input=None):
        idx, entity = self.selected_entity
        variables = self.current_variables

        # Předvyplníme formulář
        data_schema = vol.Schema({
            vol.Required("name", default=entity["name"]): str,
            vol.Required("uid", default=entity["uid"]): int,
            vol.Required("offset", default=entity["offset"]): int,
            vol.Required("length", default=entity["length"]): int,
            vol.Required("type", default=entity["type"]): str,
            vol.Required("entity_type", default=entity["entity_type"]): vol.In(["sensor", "binary_sensor", "switch", "number", "select", "button", "light"]),
            vol.Optional("unit_of_measurement", default=entity.get("unit_of_measurement", "")): str,
            vol.Required("action", default="save_and_exit"): vol.In({
                "save": "Uložit a zpět",
                "save_and_exit": "Uložit a ukončit",
                "cancel": "Zrušit"
            }),
        })

        if entity.get("entity_type") == "select":
            existing = entity.get("select_options", {})
            for i, (key, val) in enumerate(list(existing.items())[:5]):
                data_schema = data_schema.extend({
                    vol.Optional(f"select_key_{i}", default=key): str,
                    vol.Optional(f"select_label_{i}", default=val): str
                })
            for i in range(len(existing), 5):
                data_schema = data_schema.extend({
                    vol.Optional(f"select_key_{i}"): str,
                    vol.Optional(f"select_label_{i}"): str
                })

        if user_input is not None:
            if user_input.get("action") == "cancel":
                return await self.async_step_manage_entities()

            # 1) Smazat původní entitu
            old_variable = variables.pop(idx)

            # 2) Vytvořit novou entitu s novými hodnotami (pokud měníš UID, vždy nový kód!)
            new_variable = {
                "name": user_input["name"],
                "uid": user_input["uid"],
                "offset": user_input["offset"],
                "length": user_input["length"],
                "type": user_input["type"],
                "entity_type": user_input["entity_type"],
                "unit_of_measurement": user_input.get("unit_of_measurement", ""),
            }

            # zachovej původní random_code pokud UID nezměnil, jinak vygeneruj nový
            if user_input["uid"] == old_variable["uid"] and "random_code" in old_variable:
                new_variable["random_code"] = old_variable["random_code"]
            else:
                new_variable["random_code"] = generate_code()

            # Pokud je typ select, přidej volby
            if user_input["entity_type"] == "select":
                select_options = {}
                for i in range(0, 5):
                    key = user_input.get(f"select_key_{i}")
                    label = user_input.get(f"select_label_{i}")
                    if key and label:
                        select_options[str(key).strip()] = label.strip()
                new_variable["select_options"] = select_options

            # 3) Přidat novou entitu
            variables.append(new_variable)

            # 4) Uložit a reloadnout
            await self._update_config_entry(variables)
            if user_input["action"] == "save_and_exit":
                return self.async_create_entry(title="", data={})
            else:
                return await self.async_step_manage_entities()

        return self.async_show_form(step_id="edit_entity", data_schema=data_schema)

    async def async_step_confirm_delete_entity(self, user_input=None):
        """Potvrdit smazání entity – jen aktualizujeme entry.data a ukončíme Flow."""
        if user_input is None:
            # zobrazíme potvrzovací formulář
            index, entity = self.selected_entity
            return self.async_show_form(
                step_id="confirm_delete_entity",
                data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
                description_placeholders={"name": entity["name"]},
            )

        if user_input.get("confirm"):
            index, _ = self.selected_entity
            self.current_variables.pop(index)
            new_data = {**self.config_entry.data, "variables": self.current_variables}
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
        return self.async_create_entry(title="", data={})


    async def reload_from_vlist(self):
        vlist_file = self.config_entry.data.get("vlist_file")
        if not vlist_file:
            _LOGGER.error("No .vlist file specified.")
            return

        try:
            with open(vlist_file, "r") as f:
                lines = f.readlines()[2:]
                new_data = {}
                for line in lines:
                    parts = line.strip().split(";")
                    if len(parts) >= 6:
                        name = parts[1].replace("$", "")
                        new_data[name] = {
                            "uid": int(parts[3]),
                            "offset": int(parts[4]) if parts[4] else 0,
                            "length": int(parts[5]) if parts[5] else 1,
                            "type": parts[2].strip('$'),
                        }
                variables = self.config_entry.data.get("variables", [])
                for entity in variables:
                    if entity["name"] in new_data:
                        entity.update(new_data[entity["name"]])
                await self._update_config_entry(variables)
        except Exception as e:
            _LOGGER.error("Failed to reload from .vlist: %s", e)

    async def async_step_add_entity_from_vlist(self, user_input=None):
        if not self.vlist_data:
            try:
                vlist_file = self.config_entry.data.get("vlist_file")
                if not vlist_file:
                    return self.async_abort(reason="no_vlist_file")
                lines = await self.hass.async_add_executor_job(read_vlist_file, vlist_file)
                for line in lines[2:]:
                    parts = line.strip().split(";")
                    if len(parts) >= 6:
                        name = parts[1].replace("$", "")
                        self.vlist_data[name] = {
                            "project": parts[0],
                            "uid": int(parts[3]),
                            "type": parts[2].strip('$'),
                            "offset": int(parts[4]) if parts[4] else 0,
                            "length": int(parts[5]) if parts[5] else 1,
                        }
            except Exception as e:
                _LOGGER.error("Failed to load vlist file: %s", e)
                return self.async_abort(reason="vlist_load_failed")

        if user_input is not None:
            selected_var = user_input["variable"]
            var_data = self.vlist_data[selected_var]
            var_data["name"] = selected_var
            var_data["entity_type"] = user_input["entity_type"]
            var_data["unit_of_measurement"] = user_input.get("unit_of_measurement", "")

            if user_input["entity_type"] == "select":
                select_options = {}
                for i in range(0, 5):
                    key = user_input.get(f"select_key_{i}")
                    label = user_input.get(f"select_label_{i}")
                    if key and label:
                        select_options[str(key).strip()] = label.strip()
                var_data["select_options"] = select_options

            variables = self.config_entry.data.get("variables", []) + [var_data]
            await self._update_config_entry(variables)
            return self.async_create_entry(title="", data={})

        variable_options = list(self.vlist_data.keys())
        if not variable_options:
            return self.async_abort(reason="no_variables")

        # Základní pole
        base_schema = {
            vol.Required("variable"): vol.In(variable_options),
            vol.Required("entity_type", default="sensor"):  vol.In(["sensor", "binary_sensor", "switch", "number", "select", "button", "light"]),
            vol.Optional("unit_of_measurement", default=""): str,
        }

        # Přidáme pole pro select možnosti
        for i in range(0, 5):
            base_schema[vol.Optional(f"select_key_{i}")] = str
            base_schema[vol.Optional(f"select_label_{i}")] = str

        return self.async_show_form(step_id="add_entity_from_vlist", data_schema=vol.Schema(base_schema))


    async def _update_config_entry(self, variables):
        """Update config_entry data and remove deleted entities from registry."""
        # Determine removed UIDs
        old_uids = {v["uid"] for v in self.original_config.get("variables", [])}
        new_uids = {v["uid"] for v in variables}
        removed_uids = old_uids - new_uids
        _LOGGER.debug("SSCPintegration – old_uids: %s, new_uids: %s, removed_uids: %s",
              old_uids, new_uids, removed_uids)

        # Remove stale entities from registry
        registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(registry, self.config_entry.entry_id)
        for entry in entries:
            try:
                uid = int(entry.unique_id.rsplit("-", 1)[-1])
            except (ValueError, IndexError):
                continue
            if uid in removed_uids:
                _LOGGER.debug("SSCPintegration – mažu entity %s (uid %s)", entry.entity_id, uid)
                registry.async_remove(entry.entity_id)

        # Update entry data and reload integration
        new_data = {**self.original_config, "variables": variables}
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=new_data
        )
        # Store new config for future operations
        self.original_config = new_data
        # Reload to apply changes immediately
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )
    
    async def _finalize_update(self):
        """Uloží novou konfiguraci, smaže staré registry a reloadne entry."""
        # 1) Vypočítáme removed_uids
        old_uids = {v["uid"] for v in self.original_config.get("variables", [])}
        new_uids = {v["uid"] for v in self.current_variables}
        removed_uids = old_uids - new_uids

        # 2) Odstraníme stale entity
        registry = er.async_get(self.hass)
        entries = er.async_entries_for_config_entry(registry, self.config_entry.entry_id)
        for entry in entries:
            try:
                uid = int(entry.unique_id.rsplit("-", 1)[-1])
            except (ValueError, IndexError):
                continue
            if uid in removed_uids:
                _LOGGER.debug("SSCPintegration – Removing registry entry %s", entry.entity_id)
                registry.async_remove(entry.entity_id)

        # 3) Update config entry
        new_data = {**self.original_config, "variables": list(self.current_variables)}
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
        # Uložení pro další operace
        self.original_config = new_data

        # 4) Reload entry, pak ukončíme Flow
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )
        return self.async_create_entry(title="", data={})


    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SSCPOptionsFlow(config_entry)
