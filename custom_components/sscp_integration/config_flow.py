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

# Mapování PLC typu na podporované entity
PLC_TYPE_TO_ENTITIES = {
    "BOOL": ["binary_sensor", "switch", "button", "light", "select"],
    "BYTE": ["sensor", "number", "select"],
    "WORD": ["sensor", "number", "select"],
    "INT":  ["sensor", "number", "select"],
    "UINT": ["sensor", "number", "select"],
    "DINT": ["sensor", "number", "select"],
    "UDINT":["sensor", "number", "select"],
    "REAL": ["sensor", "number", "select"],
    "LREAL":["sensor", "number", "select"],
    # Další typy podle potřeby
}

ALL_ENTITY_TYPES = [
    "sensor", "binary_sensor", "switch", "number", "select", "button", "light"
]
    

class SSCPConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    def __init__(self):
        self.vlist_data = {}
        self.chosen_var = None
        self.chosen_entity_type = None
        self.chosen_type = None
        self.temp_entity = {}

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

        # Pokud nemáme načtený vlist, načti jej do self.vlist_data
        if not self.vlist_data:
            try:
                lines = await self.hass.async_add_executor_job(read_vlist_file, self.config["vlist_file"])
                for idx, line in enumerate(lines[2:], start=3):
                    parts = line.strip().split(";")
                    if len(parts) >= 6:
                        name = parts[1].replace("$", "")
                        self.vlist_data[name] = {
                            "name": name,
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

        # Pokud uživatel vybral proměnnou
        if user_input is not None:
            selected_name = user_input["variable"]
            var_data = self.vlist_data[selected_name]

            # Uložíme výběr pro další kroky
            self.chosen_var = var_data
            self.chosen_type = var_data["type"].upper() if "type" in var_data else None

            # Pokračuj na krok pro výběr entity (jen povolené typy)
            return await self.async_step_entity_type_select()

        # Nabídka výběru proměnné z vlist
        variable_options = list(self.vlist_data.keys())
        if not variable_options:
            errors["base"] = "no_variables"

        data_schema = vol.Schema({
            vol.Required("variable"): vol.In(variable_options),
        })

        return self.async_show_form(
            step_id="vlist_select",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "info": "Vyber proměnnou, kterou chceš přidat do Home Assistant.",
            },
        )

    async def async_step_manual_input(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Vše uložíme stejně jako by to bylo z vlist
            self.chosen_var = {
                "name": user_input["name"],
                "uid": int(user_input["uid"]),
                "offset": int(user_input.get("offset", 0)),
                "length": int(user_input.get("length", 1)),
                "type": user_input["type"].upper(),
                # Další hodnoty lze přidat dle potřeby
            }
            self.chosen_type = user_input["type"].upper()

            # Pokračujeme stejně jako z vlist – výběr typu entity podle PLC typu
            return await self.async_step_entity_type_select()

        # Formulář pro ruční zadání
        data_schema = vol.Schema({
            vol.Required("name", default="Ručně zadaná proměnná"): str,
            vol.Required("uid"): int,
            vol.Optional("offset", default=0): int,
            vol.Optional("length", default=1): int,
            vol.Required("type", default="INT"): vol.In([
                "BOOL", "BYTE", "WORD", "INT", "UINT", "DINT", "UDINT", "REAL", "LREAL"
            ]),
        })

        return self.async_show_form(
            step_id="manual_input",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "info": "Zadej parametry proměnné, poté vyber typ entity."
            },
        )

    async def async_step_entity_type_select(self, user_input=None):
        if not self.chosen_type:
            # failover, pokud by se typ nezjistil
            return self.async_abort(reason="type_not_found")

        allowed_entity_types = PLC_TYPE_TO_ENTITIES.get(self.chosen_type, ["sensor"])
        schema = vol.Schema({
            vol.Required("entity_type", default=allowed_entity_types[0]): vol.In(allowed_entity_types)
        })

        if user_input is not None:
            self.chosen_entity_type = user_input["entity_type"]
            return await self.async_step_entity_detail_config()

        return self.async_show_form(
            step_id="entity_type_select",
            data_schema=schema,
            description_placeholders={"typ": self.chosen_type}
        )

    # 4. krok: Detailní nastavení podle typu entity
    async def async_step_entity_detail_config(self, user_input=None):
        # Připravujeme dynamické schéma podle zvoleného typu entity
        fields = {}

        # Název v HA
        fields[vol.Required("name_ha", default=self.chosen_var["name"])] = str
        # Název z vlist (readonly – uložíme, ale uživatel nemění)
        fields[vol.Optional("name_vlist", default=self.chosen_var["name"])] = str
        # Random kód (unikátní identifikátor)
        fields[vol.Optional("random_code", default=generate_code())] = str

        if self.chosen_entity_type == "number":
            fields[vol.Optional("min_value", default=0.0)] = vol.Coerce(float)
            fields[vol.Optional("max_value", default=100.0)] = vol.Coerce(float)
            fields[vol.Optional("step", default=1.0)] = vol.Coerce(float)
            fields[vol.Optional("mode", default="box")] = vol.In(["box", "slider"])

        if self.chosen_entity_type == "select":
            # Dynamické zadání dvojic: použijeme pole s fixním počtem, nebo ještě lépe – další krok, kde je opakovaně lze přidat/ubrat
            for i in range(5):  # lze nahradit opakovaným krokem pro přidání další volby
                fields[vol.Optional(f"select_key_{i}", default="")] = str
                fields[vol.Optional(f"select_label_{i}", default="")] = str

        if self.chosen_entity_type == "button":
            fields[vol.Optional("press_time", default=0.1)] = float  # v sekundách

        # Pro každý typ ještě volitelné jednotky (sensor, number)
        if self.chosen_entity_type in ["sensor", "number"]:
            known_units = ["°C", "°F", "K", "Pa", "kPa", "bar", "V", "A", "W", "%", "Hz", "s", "m", "kg"]
            fields[vol.Optional("unit_of_measurement", default="")] = vol.In(known_units + [""])

        if user_input is not None:
            # Ulož vše potřebné do self.temp_entity a připrav zápis do configu
            self.temp_entity = {
                "uid": self.chosen_var["uid"],
                "offset": self.chosen_var["offset"],
                "length": self.chosen_var["length"],
                "type": self.chosen_type,
                "entity_type": self.chosen_entity_type,
                "name": user_input["name_ha"],
                "name_vlist": self.chosen_var["name"],
                "random_code": user_input.get("random_code"),
            }
            # Doplň parametry pro typy
            if self.chosen_entity_type == "number":
                self.temp_entity["min_value"] = user_input.get("min_value")
                self.temp_entity["max_value"] = user_input.get("max_value")
                self.temp_entity["step"] = user_input.get("step")
                self.temp_entity["mode"] = user_input.get("mode", "box")
                if user_input.get("unit_of_measurement"):
                    self.temp_entity["unit_of_measurement"] = user_input.get("unit_of_measurement")

            if self.chosen_entity_type == "select":
                options_map = {}
                for i in range(5):
                    key = user_input.get(f"select_key_{i}")
                    label = user_input.get(f"select_label_{i}")
                    if key and label:
                        options_map[key.strip()] = label.strip()
                self.temp_entity["select_options"] = options_map

            if self.chosen_entity_type == "button":
                self.temp_entity["press_time"] = user_input.get("press_time")

            # Přidat entity do configu, pokračovat/přidat další nebo dokončit
            return await self.async_step_confirm_or_next()

        return self.async_show_form(
            step_id="entity_detail_config",
            data_schema=vol.Schema(fields)
        )

    # 5. krok: Potvrzení, přidat další nebo ukončit
    async def async_step_confirm_or_next(self, user_input=None):
        if user_input is not None:
            if user_input.get("finish", False):
                # Dokonči – uložit entry s celým configem
                if "variables" not in self.config:
                    self.config["variables"] = []
                self.config["variables"].append(self.temp_entity)
                return self.async_create_entry(title=self.config["PLC_Name"], data=self.config)
            else:
                # Přidat další entitu (vrátit se na výběr proměnné)
                if "variables" not in self.config:
                    self.config["variables"] = []
                self.config["variables"].append(self.temp_entity)
                return await self.async_step_vlist_select()
        # Nabídka: "Přidat další entitu?" nebo "Dokončit"
        schema = vol.Schema({
            vol.Optional("finish", default=False): bool
        })
        return self.async_show_form(step_id="confirm_or_next", data_schema=schema)

    # ... případně další kroky (ruční zadání, apod.) ...

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
        # Výpis všech entit s random_code pro rozlišení vícenásobného použití
        entities = [
            f"{entity['name']} (UID: {entity['uid']}, RANDOM: {entity.get('random_code', '')})"
            for entity in self.current_variables
        ]
        if not entities:
            return self.async_abort(reason="no_entities")

        if user_input is not None:
            # Najdi index podle přesného stringu
            selected_str = user_input.get("entity")
            idx, ent = next(
                (i, var)
                for i, var in enumerate(self.current_variables)
                if f"{var['name']} (UID: {var['uid']}, RANDOM: {var.get('random_code', '')})" == selected_str
            )
            self.selected_entity = (idx, ent)
            return await self.async_step_edit_entity_type()

        data_schema = vol.Schema({
            vol.Required("entity"): vol.In(entities),
            vol.Required("action", default="edit_entity"): vol.In({
                "edit_entity": "Editovat entitu",
                "delete_entity": "Smazat entitu",
                "save_and_reload": "Uložit změny a reload"
            })
        })

        return self.async_show_form(step_id="manage_entities", data_schema=data_schema)
    
    # Můžeš dát všechny entity (nebo omezit podle PLC typu, pokud budeš chtít)


    async def async_step_edit_entity_type(self, user_input=None):
        idx, entity = self.selected_entity

        if user_input is not None:
            new_entity_type = user_input["entity_type"]
            # Uložíme si nový typ (i kdyby byl stejný, stejně přejdeme na detailní nastavení)
            self.temp_entity = {**entity, "entity_type": new_entity_type}
            return await self.async_step_edit_entity_detail()

        data_schema = vol.Schema({
            vol.Required("entity_type", default=entity["entity_type"]): vol.In(ALL_ENTITY_TYPES)
        })
        return self.async_show_form(
            step_id="edit_entity_type",
            data_schema=data_schema,
            description_placeholders={
                "info": f"Změň typ entity ({entity['name']} – aktuálně {entity['entity_type']})"
            }
        )
    async def async_step_edit_entity_detail(self, user_input=None):
        idx, entity = self.selected_entity
        ent = getattr(self, "temp_entity", entity)
        entity_type = ent["entity_type"]

        # Dynamicky vytvoř schéma pro daný typ entity
        fields = {
            vol.Required("name", default=ent.get("name", "")): str,
            vol.Optional("random_code", default=ent.get("random_code", "")): str,
        }

        if entity_type == "number":
            fields[vol.Optional("min_value", default=ent.get("min_value", 0.0))] = vol.Coerce(float)
            fields[vol.Optional("max_value", default=ent.get("max_value", 100.0))] = vol.Coerce(float)
            fields[vol.Optional("step", default=ent.get("step", 1.0))] = vol.Coerce(float)
            fields[vol.Optional("unit_of_measurement", default=ent.get("unit_of_measurement", ""))] = str
            fields[vol.Optional("mode", default=ent.get("mode", "box"))] = vol.In(["box", "slider"])

        elif entity_type == "select":
            # Pokud chceš podporovat nekonečné možnosti, můžeš udělat vícekrokový flow – zde pro jednoduchost 5 položek:
            select_options = ent.get("select_options", {})
            for i in range(5):
                key = list(select_options.keys())[i] if i < len(select_options) else ""
                label = list(select_options.values())[i] if i < len(select_options) else ""
                fields[vol.Optional(f"select_key_{i}", default=key)] = str
                fields[vol.Optional(f"select_label_{i}", default=label)] = str

        elif entity_type == "button":
            fields[vol.Optional("press_time", default=ent.get("press_time", 0.1))] = vol.Coerce(float)

        elif entity_type in ("sensor", "switch", "binary_sensor", "light"):
            fields[vol.Optional("unit_of_measurement", default=ent.get("unit_of_measurement", ""))] = str

        # ... případně další pole pro jiné typy

        # Akce (uložit/zpět)
        fields[vol.Required("action", default="save_and_exit")]= vol.In({
            "save": "Uložit a zpět",
            "save_and_exit": "Uložit a ukončit",
            "cancel": "Zrušit"
        })

        if user_input is not None:
            action = user_input["action"]
            if action == "cancel":
                return await self.async_step_manage_entities()

            # Sestav novou proměnnou dle aktuálního typu
            new_variable = {
                **ent,  # Základ z původní entity
                "name": user_input["name"],
                "entity_type": entity_type,
                "random_code": user_input.get("random_code", ""),
            }
            if entity_type == "number":
                new_variable["min_value"] = user_input.get("min_value")
                new_variable["max_value"] = user_input.get("max_value")
                new_variable["step"] = user_input.get("step")
                new_variable["mode"] = user_input.get("mode", "box")
                new_variable["unit_of_measurement"] = user_input.get("unit_of_measurement", "")


            elif entity_type == "select":
                select_options = {}
                for i in range(5):
                    key = user_input.get(f"select_key_{i}")
                    label = user_input.get(f"select_label_{i}")
                    if key and label:
                        select_options[str(key).strip()] = label.strip()
                new_variable["select_options"] = select_options

            elif entity_type == "button":
                new_variable["press_time"] = user_input.get("press_time", 0.1)

            elif entity_type in ("sensor", "switch", "binary_sensor", "light"):
                new_variable["unit_of_measurement"] = user_input.get("unit_of_measurement", "")

            # Přepiš starou entitu novou, zachovej index!
            self.current_variables[idx] = new_variable
            await self._update_config_entry(self.current_variables)
            if action == "save_and_exit":
                return self.async_create_entry(title="", data={})
            else:
                return await self.async_step_manage_entities()

        return self.async_show_form(
            step_id="edit_entity_detail",
            data_schema=vol.Schema(fields)
        )

    async def async_step_confirm_delete_entity(self, user_input=None):
        """Potvrdit smazání entity – jen aktualizujeme entry.data a ukončíme Flow."""
        if user_input is None:
            index, entity = self.selected_entity
            return self.async_show_form(
                step_id="confirm_delete_entity",
                data_schema=vol.Schema({vol.Required("confirm", default=False): bool}),
                description_placeholders={"name": entity["name"]},
            )

        if user_input.get("confirm"):
            index, entity = self.selected_entity
            # Najdi entitu podle UID a random_code (pro jistotu)
            remove_idx = None
            for idx, var in enumerate(self.current_variables):
                if (
                    var.get("uid") == entity.get("uid")
                    and var.get("random_code", "") == entity.get("random_code", "")
                    and var.get("name") == entity.get("name")
                ):
                    remove_idx = idx
                    break

            if remove_idx is not None:
                self.current_variables.pop(remove_idx)
                new_data = {**self.config_entry.data, "variables": self.current_variables}
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            else:
                _LOGGER.warning(f"Nepodařilo se najít entitu k odstranění: {entity}")

        return self.async_create_entry(title="", data={})

    async def reload_from_vlist(self):
        vlist_file = self.config_entry.data.get("vlist_file")
        if not vlist_file:
            _LOGGER.error("No .vlist file specified.")
            return

        try:
            with open(vlist_file, "r") as f:
                lines = f.readlines()[2:]  # přeskoč hlavičku
                vlist_map = {}
                for line in lines:
                    parts = line.strip().split(";")
                    if len(parts) >= 6:
                        name = parts[1].replace("$", "")
                        vlist_map[name] = {
                            "uid": int(parts[3]),
                            "offset": int(parts[4]) if parts[4] else 0,
                            "length": int(parts[5]) if parts[5] else 1,
                        }

                # projdi aktuální konfiguraci a podle name (přednostně name_vlist, jinak name) zkontroluj změny
                variables = self.config_entry.data.get("variables", [])
                for entity in variables:
                    # Nejprve podle name_vlist, pokud není tak podle name
                    name_key = entity.get("name_vlist") or entity.get("name")
                    if name_key in vlist_map:
                        vlist_data = vlist_map[name_key]
                        # Pokud se uid nebo offset změnil, přepiš
                        updated = False
                        if entity.get("uid") != vlist_data["uid"]:
                            entity["uid"] = vlist_data["uid"]
                            updated = True
                        if entity.get("offset") != vlist_data["offset"]:
                            entity["offset"] = vlist_data["offset"]
                            updated = True
                        if entity.get("length") != vlist_data["length"]:
                            entity["length"] = vlist_data["length"]
                            updated = True
                        if updated:
                            _LOGGER.info(f"Entity '{name_key}' byla aktualizována podle vlist: {vlist_data}")

                await self._update_config_entry(variables)
        except Exception as e:
            _LOGGER.error("Failed to reload from .vlist: %s", e)

    async def async_step_add_entity_from_vlist(self, user_input=None):
        # Načti vlist pokud není
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
                            "name": name,
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
            # Ulož pro další kroky jako v config flow
            self.chosen_var = var_data
            self.chosen_type = var_data["type"].upper()
            return await self.async_step_add_entity_type_select()

        variable_options = list(self.vlist_data.keys())
        if not variable_options:
            return self.async_abort(reason="no_variables")

        data_schema = vol.Schema({
            vol.Required("variable"): vol.In(variable_options)
        })

        return self.async_show_form(step_id="add_entity_from_vlist", data_schema=data_schema)
    async def async_step_add_entity_type_select(self, user_input=None):
        allowed_entity_types = PLC_TYPE_TO_ENTITIES.get(self.chosen_type, ["sensor"])
        schema = vol.Schema({
            vol.Required("entity_type", default=allowed_entity_types[0]): vol.In(allowed_entity_types)
        })

        if user_input is not None:
            self.chosen_entity_type = user_input["entity_type"]
            return await self.async_step_add_entity_detail()

        return self.async_show_form(
            step_id="add_entity_type_select",
            data_schema=schema,
            description_placeholders={"typ": self.chosen_type}
        )

    async def async_step_add_entity_detail(self, user_input=None):
        fields = {
            vol.Required("name", default=self.chosen_var["name"]): str,
            vol.Optional("random_code", default=generate_code()): str,
        }
        if self.chosen_entity_type == "number":
            fields[vol.Optional("min_value", default=0.0)] = vol.Coerce(float)
            fields[vol.Optional("max_value", default=100.0)] = vol.Coerce(float)
            fields[vol.Optional("step", default=1.0)] = vol.Coerce(float)
            fields[vol.Optional("mode", default="box")] = vol.In(["box", "slider"])
            fields[vol.Optional("unit_of_measurement", default="")] = str
        elif self.chosen_entity_type == "select":
            for i in range(5):
                fields[vol.Optional(f"select_key_{i}", default="")] = str
                fields[vol.Optional(f"select_label_{i}", default="")] = str
        elif self.chosen_entity_type == "button":
            fields[vol.Optional("press_time", default=0.1)] = vol.Coerce(float)
        elif self.chosen_entity_type in ("sensor", "switch", "binary_sensor", "light"):
            fields[vol.Optional("unit_of_measurement", default="")] = str

        if user_input is not None:
            # Sestav novou entitu pro přidání
            new_variable = {
                "uid": self.chosen_var["uid"],
                "offset": self.chosen_var["offset"],
                "length": self.chosen_var["length"],
                "type": self.chosen_type,
                "entity_type": self.chosen_entity_type,
                "name": user_input["name"],
                "random_code": user_input.get("random_code"),
            }
            if self.chosen_entity_type == "number":
                new_variable["min_value"] = user_input.get("min_value")
                new_variable["max_value"] = user_input.get("max_value")
                new_variable["step"] = user_input.get("step")
                new_variable["mode"] = user_input.get("mode", "box")
                new_variable["unit_of_measurement"] = user_input.get("unit_of_measurement", "")
            elif self.chosen_entity_type == "select":
                select_options = {}
                for i in range(5):
                    key = user_input.get(f"select_key_{i}")
                    label = user_input.get(f"select_label_{i}")
                    if key and label:
                        select_options[str(key).strip()] = label.strip()
                new_variable["select_options"] = select_options
            elif self.chosen_entity_type == "button":
                new_variable["press_time"] = user_input.get("press_time", 0.1)
            elif self.chosen_entity_type in ("sensor", "switch", "binary_sensor", "light"):
                new_variable["unit_of_measurement"] = user_input.get("unit_of_measurement", "")

            # Přidej do seznamu
            variables = self.config_entry.data.get("variables", []) + [new_variable]
            await self._update_config_entry(variables)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(step_id="add_entity_detail", data_schema=vol.Schema(fields))

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
