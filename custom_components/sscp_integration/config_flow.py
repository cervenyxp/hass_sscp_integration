import os
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .sscp_client import SSCPClient
from . import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Globální proměnná pro uložení dat ze souboru .vlist
vlist_data = {}

def read_vlist_file(vlist_file):
    """Přečte obsah souboru .vlist a vrátí seznam řádků."""
    _LOGGER.debug("Reading vlist file: %s", vlist_file)
    with open(vlist_file, "r") as f:
        return f.readlines()

class SSCPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    async def async_step_user(self, user_input=None):
        """První krok - zadání základních údajů a konfigurace."""
        errors = {}

        # Asynchronní zpracování os.listdir
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
        """Výběr proměnné ze souboru .vlist."""
        errors = {}

        if user_input is not None:
            selected_var = user_input["variable"]
            var_data = vlist_data[selected_var]
            self.config.update(var_data)
            self.config["name"] = selected_var  # Nastavíme název z `.vlist`
            return await self.async_step_hass_config()

        # Inicializace vlist_data pro každý krok
        vlist_data = {}

        if not vlist_data:
            try:
                lines = await self.hass.async_add_executor_job(read_vlist_file, self.config["vlist_file"])
                for idx, line in enumerate(lines[2:], start=3):  # Načítáme proměnné od třetího řádku
                    parts = line.strip().split(";")
                    if len(parts) >= 6:
                        name = parts[1].replace("$", "")  # Odstranění `$`
                        vlist_data[name] = {
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

        variable_options = list(vlist_data.keys())
        if not variable_options:
            errors["base"] = "no_variables"

        data_schema = vol.Schema({
            vol.Required("variable"): vol.In(variable_options),
        })

        return self.async_show_form(step_id="vlist_select", data_schema=data_schema, errors=errors)

    async def async_step_manual_input(self, user_input=None):
        """Ruční zadání parametrů proměnné."""
        errors = {}

        if user_input is not None:
            self.config.update(user_input)
            self.config["name"] = user_input["name"]  # Ručně zadaný název
            return await self.async_step_hass_config()

        data_schema = vol.Schema({
            vol.Required("comm_uid"): int,
            vol.Required("offset", default=0): int,
            vol.Required("length", default=1): int,
            vol.Optional("name", default="Manual Entity"): str,  # Ručně zadaný název
        })

        return self.async_show_form(step_id="manual_input", data_schema=data_schema, errors=errors)

    async def async_step_hass_config(self, user_input=None):
        """Konfigurace Home Assistant entit."""
        errors = {}

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

                # Inicializace seznamu proměnných, pokud neexistuje
                if "variables" not in self.config:
                    self.config["variables"] = []

                # Přidání nové proměnné včetně entity_type
                self.config["variables"].append({
                    "uid": self.config["uid"],
                    "offset": self.config["offset"],
                    "length": self.config["length"],
                    "type": self.config["type"],
                    "name": self.config["name"],
                    "entity_type": user_input["entity_type"],  # Přidání entity_type
                })

                # Kontrola, zda má být konfigurace ukončena
                if user_input.get("finish", False):
                    return self.async_create_entry(title=self.config["PLC_Name"], data=self.config)
                else:
                    # Pokračování výběrem další proměnné
                    if self.config.get("configuration_mode") == "vlist":
                        return await self.async_step_vlist_select()
                    else:
                        return await self.async_step_manual_input()
            except Exception as e:
                _LOGGER.error("Failed to read variable: %s", e)
                errors["base"] = "read_failed"

        data_schema = vol.Schema({
            vol.Required("entity_type", default="sensor"): vol.In(["sensor", "binary_sensor", "switch", "number", "select"]),
            vol.Required("domain", default="generic"): str,
            vol.Optional("finish", default=False): bool,  # Zaškrtávátko pro ukončení
        })

        return self.async_show_form(step_id="hass_config", data_schema=data_schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Vrací objekt `OptionsFlow` pro úpravu konfigurace."""
        return SSCPOptionsFlow(config_entry)

class SSCPOptionsFlow(config_entries.OptionsFlow):
    """Nastavení možností pro SSCP integraci."""

    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.selected_entity = None  # Pro uložení aktuálně vybrané entity

    async def async_step_init(self, user_input=None):
        """První krok při editaci nastavení."""
        if user_input is not None:
            if user_input["action"] == "edit_entities":
                return await self.async_step_manage_entities()
            elif user_input["action"] == "reload_from_vlist":
                await self.reload_from_vlist()
                return self.async_create_entry(title="", data={})
            elif user_input["action"] == "add_entity_from_vlist":
                return await self.async_step_add_entity_from_vlist()

        data_schema = vol.Schema({
            vol.Optional("host", default=self.config_entry.data["host"]): str,
            vol.Optional("port", default=self.config_entry.data["port"]): str,
            vol.Optional("username", default=self.config_entry.data["username"]): str,
            vol.Optional("password", default=self.config_entry.data["password"]): str,
            vol.Optional("sscp_address", default=self.config_entry.data["sscp_address"]): str,
            vol.Required("action", default="edit_entities"): vol.In({
                "edit_entities": "Editovat entity",
                "reload_from_vlist": "Načíst znovu z .vlist",
                "add_entity_from_vlist": "Přidat entitu z .vlist",
                "save": "Uložit a ukončit"
            })
        })

        return self.async_show_form(step_id="init", data_schema=data_schema)

    async def async_step_manage_entities(self, user_input=None):
        """Správa entit."""
        if user_input is not None:
            if user_input["action"] == "edit_entity":
                self.selected_entity = user_input["entity"]
                return await self.async_step_edit_entity()
            elif user_input["action"] == "delete_entity":
                self.selected_entity = user_input["entity"]
                return await self.async_step_confirm_delete_entity()

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
                "delete_entity": "Smazat entitu"
            })
        })

        return self.async_show_form(step_id="manage_entities", data_schema=data_schema)

    async def async_step_add_entity(self, user_input=None):
        """Přidání nové entity."""
        if user_input is not None:
            # Přidání nové entity do seznamu
            variables = self.config_entry.data.get("variables", [])
            variables.append({
                "name": user_input["name"],
                "uid": user_input["uid"],
                "offset": user_input["offset"],
                "length": user_input["length"],
                "type": user_input["type"],
                "entity_type": user_input["entity_type"],
            })

            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, "variables": variables}
            )
            return await self.async_step_manage_entities()

        data_schema = vol.Schema({
            vol.Required("name"): str,
            vol.Required("uid"): int,
            vol.Required("offset", default=0): int,
            vol.Required("length", default=1): int,
            vol.Required("type", default="int"): str,
            vol.Required("entity_type", default="sensor"): vol.In(["sensor", "binary_sensor", "switch", "number", "select"]),
        })

        return self.async_show_form(step_id="add_entity", data_schema=data_schema)

    async def async_step_edit_entity(self, user_input=None):
        """Editace vybrané entity."""
        variables = self.config_entry.data.get("variables", [])
        entity = next(
            (var for var in variables if f"{var['name']} (UID: {var['uid']})" == self.selected_entity), 
            None
        )

        if not entity:
            return self.async_abort(reason="entity_not_found")

        if user_input is not None:
            # Aktualizace hodnot entity
            entity.update(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, "variables": variables}
            )
            return await self.async_step_manage_entities()

        data_schema = vol.Schema({
            vol.Optional("name", default=entity["name"]): str,
            vol.Optional("uid", default=entity["uid"]): int,
            vol.Optional("offset", default=entity["offset"]): int,
            vol.Optional("length", default=entity["length"]): int,
            vol.Optional("type", default=entity["type"]): str,
            vol.Optional("entity_type", default=entity["entity_type"]): vol.In(["sensor", "binary_sensor", "switch", "number", "select"]),
        })

        return self.async_show_form(step_id="edit_entity", data_schema=data_schema)

    async def async_step_confirm_delete_entity(self, user_input=None):
        """Potvrzení smazání vybrané entity."""
        variables = self.config_entry.data.get("variables", [])
        entity = next(
            (var for var in variables if f"{var['name']} (UID: {var['uid']})" == self.selected_entity), 
            None
        )

        if not entity:
            return self.async_abort(reason="entity_not_found")

        if user_input is not None:
            if user_input["confirm"]:
                # Odstranění entity
                variables.remove(entity)
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data, "variables": variables}
                )
            return await self.async_step_manage_entities()

        data_schema = vol.Schema({
            vol.Required("confirm", default=False): bool
        })

        return self.async_show_form(
            step_id="confirm_delete_entity",
            data_schema=data_schema,
            description_placeholders={"name": entity["name"]},
        )

    async def reload_from_vlist(self):
        """Načte aktuální hodnoty UID, offset a length z .vlist."""
        vlist_file = self.config_entry.data.get("vlist_file")
        if not vlist_file:
            _LOGGER.error("No .vlist file specified.")
            return

        try:
            with open(vlist_file, "r") as f:
                lines = f.readlines()[2:]  # Přeskočit hlavičku souboru
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

                # Aktualizace existujících entit
                for entity in self.config_entry.data.get("variables", []):
                    if entity["name"] in new_data:
                        entity.update(new_data[entity["name"]])

                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={**self.config_entry.data}
                )
                _LOGGER.info("Entities updated from .vlist")
        except Exception as e:
            _LOGGER.error("Failed to reload from .vlist: %s", e)
    
    async def async_step_add_entity_from_vlist(self, user_input=None):
        """Přidání nové entity výběrem ze souboru .vlist."""
        """Reset vlist_data to empty"""
        vlist_data = {}

        if not vlist_data:
            try:
                vlist_file = self.config_entry.data.get("vlist_file")
                if not vlist_file:
                    return self.async_abort(reason="no_vlist_file")
                lines = await self.hass.async_add_executor_job(read_vlist_file, vlist_file)
                for idx, line in enumerate(lines[2:], start=3):  # Načítáme proměnné od třetího řádku
                    parts = line.strip().split(";")
                    if len(parts) >= 6:
                        name = parts[1].replace("$", "")
                        vlist_data[name] = {
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
            var_data = vlist_data[selected_var]
            var_data["name"] = selected_var  # Nastavení názvu
            var_data["entity_type"] = user_input["entity_type"]  # Typ entity
            variables = self.config_entry.data.get("variables", [])
            variables.append(var_data)  # Přidání nové entity
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, "variables": variables}
            )
            return self.async_create_entry(title="", data={})

        variable_options = list(vlist_data.keys())
        if not variable_options:
            return self.async_abort(reason="no_variables")

        data_schema = vol.Schema({
            vol.Required("variable"): vol.In(variable_options),
            vol.Required("entity_type", default="sensor"): vol.In(["sensor", "binary_sensor", "switch", "number", "select"]),
        })

        return self.async_show_form(step_id="add_entity_from_vlist", data_schema=data_schema)
