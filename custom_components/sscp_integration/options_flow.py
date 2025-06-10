# options_flow.py – plně synchronizováno s podporou domény
from homeassistant import config_entries
import voluptuous as vol
import logging
import os

_LOGGER = logging.getLogger(__name__)

ALLOWED_DOMAINS = [
    "sensor", "binary_sensor", "switch", "number", "select",
    "energy", "power", "gas", "water", "voltage", "current", "temperature", "humidity",
    "electric_meter", "water_meter", "gas_meter", "power_meter"
]

class SSCPOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.selected_entity = None
        self.vlist_data = {}
# ... (zbytek kódu je zkrácen pro přehlednost – vložíme plný obsah)
