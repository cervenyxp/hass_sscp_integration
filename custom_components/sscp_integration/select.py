import logging
from homeassistant.components.select import SelectEntity
from . import DOMAIN
from homeassistant.helpers import entity_registry as er
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from datetime import timedelta

SCAN_INTERVAL = timedelta(seconds=5)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Nastavení select entities pro SSCP Integration."""
    _LOGGER.info("Setting up select entities for SSCP Integration")

    client = hass.data[DOMAIN][config_entry.entry_id]["client"]
    # Zajisti seznam entit
    if "entities" not in hass.data[DOMAIN][config_entry.entry_id]:
        hass.data[DOMAIN][config_entry.entry_id]["entities"] = []
    variables = config_entry.data.get("variables", [])

    selects = [
        SSCPSelectEntity(client, variable, config_entry.entry_id, hass)
        for variable in variables
        if variable.get("entity_type") == "select"
    ]
    for ent in selects:
        hass.data[DOMAIN][config_entry.entry_id]["entities"].append(ent)

    if selects:
        async_add_entities(selects, update_before_add=True)

async def async_unload_entry(hass, entry):
    registry = er.async_get(hass)
    er.async_clear_config_entry(registry, entry.entry_id)
    # await async_unload_platforms(...)
    return True


class SSCPSelectEntity(SelectEntity):
    """Select entita pro SSCP Integration."""
    should_poll = True

    def __init__(self, client, config, entry_id,hass):
        """Inicializace select entity."""
        self._client = client
        self._uid = config["uid"]
        self._offset = config.get("offset", 0)
        self._length = config.get("length", 1)
        self._type = config["type"]
        self._entry_id = entry_id
        self.hass = hass

        self._attr_name = config["name"]
        self._attr_unique_id = f"{entry_id}_{self._uid}_{self._offset}_select"
        self._attr_options = list(config.get("select_options", {}).values())
        self._value_map = config.get("select_options", {})  # key: "0", value: "Vypnuto"
        self._reverse_map = {v: k for k, v in self._value_map.items()}
        self._state = None

    @property
    def current_option(self):
        """Vrátí aktuální volbu."""
        return self._value_map.get(str(self._state))

    @property
    def device_info(self):
        """Vrátí informace o zařízení."""
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": f"PLC {self._entry_id}",
            "manufacturer": "SSCP",
            "model": "PLC Select",
        }

    async def async_update(self):
        """Aktualizuje aktuální hodnotu."""
        _LOGGER.debug("Updating select %s (UID: %s, Offset: %d)", self._attr_name, self._uid, self._offset)
        try:
            value = self._client.read_variable(self._uid, self._offset, self._length, self._type)
            str_value = str(int(value)) if isinstance(value, (bool, int)) else str(value)

            if str_value in self._value_map:
                self._state = str_value
                _LOGGER.info("Updated select %s to option: %s (%s)", self._attr_name, self._value_map[str_value], str_value)
            else:
                self._state = None
                _LOGGER.warning("Received unknown value '%s' for select %s", str_value, self._attr_name)
        except Exception as e:
            _LOGGER.error("Failed to update select %s: %s", self._attr_name, e)
            self._state = None

    async def async_select_option(self, option):
        """Nastaví vybranou možnost."""
        raw_value = self._reverse_map.get(option)
        if raw_value is None:
            _LOGGER.error("Option '%s' not valid for select %s", option, self._attr_name)
            return

        # 🛠 Převod hodnoty podle typu
        try:
            if self._type.upper() == "BOOL":
                converted_value = bool(int(raw_value))
            elif self._type.upper() in ["BYTE", "WORD", "UINT", "DINT", "UDINT", "LINT", "INT"]:
                converted_value = int(raw_value)
            elif self._type.upper() in ["REAL", "LREAL"]:
                converted_value = float(raw_value)
            else:
                converted_value = raw_value  # fallback

            self._client.write_variable(
                self._uid,
                value=converted_value,
                offset=self._offset,
                length=self._length,
                type_data=self._type,
            )
            self._state = str(raw_value)
            self.async_write_ha_state()
            for ent in self.hass.data[DOMAIN][self._entry_id]["entities"]:
                if ent is not self:
                    ent.async_schedule_update_ha_state(force_refresh=True)
            _LOGGER.info("Set select %s to option: %s (%s)", self._attr_name, option, converted_value)
        except Exception as e:
            _LOGGER.error("Failed to set option %s for select %s: %s", option, self._attr_name, e)
