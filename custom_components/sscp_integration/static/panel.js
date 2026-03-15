(() => {
if (customElements.get("sscp-integration-panel")) {
  return;
}

const DEFAULT_ENTITY_CATALOG = {
  BOOL: ["switch", "binary_sensor", "button", "light", "select"],
  BYTE: ["sensor", "number", "select"],
  WORD: ["sensor", "number", "select"],
  INT: ["sensor", "number", "select"],
  UINT: ["sensor", "number", "select"],
  DINT: ["sensor", "number", "select"],
  UDINT: ["sensor", "number", "select"],
  LINT: ["sensor", "number", "select"],
  REAL: ["sensor", "number", "select"],
  LREAL: ["sensor", "number", "select"],
  DT: ["datetime", "sensor"],
};

const DEFAULT_PLC_TYPES = Object.keys(DEFAULT_ENTITY_CATALOG);
const DEFAULT_ENTITY_TYPES = ["sensor", "binary_sensor", "switch", "light", "button", "number", "select", "datetime"];
const ROOT_PATH_KEY = "";
const UNIT_DISPLAY_ALIASES = {
  degc: "°C",
  decc: "°C",
  "°c": "°C",
  degf: "°F",
  decf: "°F",
  "°f": "°F",
};
const SENSOR_DEVICE_CLASS_OPTIONS = [
  "apparent_power",
  "aqi",
  "atmospheric_pressure",
  "battery",
  "blood_glucose_concentration",
  "carbon_dioxide",
  "carbon_monoxide",
  "current",
  "data_rate",
  "data_size",
  "distance",
  "duration",
  "energy",
  "energy_storage",
  "enum",
  "frequency",
  "gas",
  "humidity",
  "illuminance",
  "irradiance",
  "moisture",
  "monetary",
  "nitrogen_dioxide",
  "nitrogen_monoxide",
  "nitrous_oxide",
  "ozone",
  "ph",
  "pm1",
  "pm10",
  "pm25",
  "power",
  "power_factor",
  "precipitation",
  "precipitation_intensity",
  "pressure",
  "reactive_power",
  "signal_strength",
  "sound_pressure",
  "speed",
  "sulphur_dioxide",
  "temperature",
  "timestamp",
  "volatile_organic_compounds",
  "volatile_organic_compounds_parts",
  "voltage",
  "volume",
  "volume_flow_rate",
  "volume_storage",
  "water",
  "weight",
  "wind_speed",
];
const NUMBER_DEVICE_CLASS_OPTIONS = [
  "apparent_power",
  "aqi",
  "atmospheric_pressure",
  "battery",
  "carbon_dioxide",
  "carbon_monoxide",
  "current",
  "data_rate",
  "data_size",
  "distance",
  "duration",
  "energy",
  "frequency",
  "gas",
  "humidity",
  "illuminance",
  "irradiance",
  "moisture",
  "monetary",
  "nitrogen_dioxide",
  "nitrogen_monoxide",
  "nitrous_oxide",
  "ozone",
  "ph",
  "pm1",
  "pm10",
  "pm25",
  "power",
  "power_factor",
  "precipitation",
  "precipitation_intensity",
  "pressure",
  "reactive_power",
  "signal_strength",
  "speed",
  "sulphur_dioxide",
  "temperature",
  "volatile_organic_compounds",
  "volatile_organic_compounds_parts",
  "voltage",
  "volume",
  "volume_flow_rate",
  "water",
  "weight",
  "wind_speed",
];
const SENSOR_STATE_CLASS_OPTIONS = ["measurement", "total", "total_increasing"];
const HASS_UNIT_OPTIONS = [
  "%",
  "ppm",
  "ppb",
  "°C",
  "°F",
  "K",
  "Pa",
  "kPa",
  "bar",
  "mbar",
  "hPa",
  "V",
  "mV",
  "A",
  "mA",
  "Hz",
  "kHz",
  "W",
  "kW",
  "MW",
  "Wh",
  "kWh",
  "MWh",
  "var",
  "kvar",
  "VA",
  "kVA",
  "lx",
  "lm",
  "s",
  "min",
  "h",
  "d",
  "ms",
  "B",
  "kB",
  "MB",
  "GB",
  "TB",
  "bit/s",
  "kbit/s",
  "Mbit/s",
  "mm",
  "cm",
  "m",
  "km",
  "m/s",
  "km/h",
  "mm/h",
  "L",
  "m3",
  "m3/h",
  "L/min",
  "g",
  "kg",
  "ug/m3",
  "mg/m3",
  "dBm",
  "pH",
  "CZK",
  "EUR",
  "USD",
];
const CLIMATE_HVAC_MODE_OPTIONS = ["off", "heat", "cool", "heat_cool", "auto", "dry", "fan_only"];
const CLIMATE_TEMPERATURE_UNITS = ["°C", "°F"];
const COVER_DEVICE_CLASS_OPTIONS = ["awning", "blind", "curtain", "damper", "door", "garage", "gate", "shade", "shutter", "window"];
const FAN_DIRECTION_OPTIONS = ["forward", "reverse"];
const HUMIDIFIER_DEVICE_CLASS_OPTIONS = ["humidifier", "dehumidifier"];
const WATER_HEATER_OPERATION_OPTIONS = ["off", "electric", "gas", "heat_pump", "high_demand", "performance", "eco"];
const LOCK_STATE_OPTIONS = ["locked", "unlocked", "locking", "unlocking", "jammed", "open", "opening"];
const VALVE_DEVICE_CLASS_OPTIONS = ["water", "gas"];
const VACUUM_STATUS_OPTIONS = ["cleaning", "docked", "returning", "idle", "paused", "error"];
const SCHEDULER_DAY_LABELS = ["Pondeli", "Utery", "Streda", "Ctvrtek", "Patek", "Sobota", "Nedele"];

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");

const formatUnitLabel = (value) => {
  const normalized = String(value ?? "").trim();
  if (!normalized) {
    return "";
  }
  return UNIT_DISPLAY_ALIASES[normalized.toLowerCase()] || normalized;
};

const formatDateTimeLocalInput = (value) => {
  if (!value) {
    return "";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  const pad = (number) => String(number).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
};

const formatMinuteOfDay = (value) => {
  const total = Math.max(0, Math.min(1439, Number(value) || 0));
  const hours = String(Math.floor(total / 60)).padStart(2, "0");
  const minutes = String(total % 60).padStart(2, "0");
  return `${hours}:${minutes}`;
};

const parseTimeToMinuteOfDay = (value) => {
  const raw = String(value || "").trim();
  if (!raw) {
    return null;
  }
  const match = raw.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) {
    return null;
  }
  const hours = Number(match[1]);
  const minutes = Number(match[2]);
  if (hours < 0 || hours > 23 || minutes < 0 || minutes > 59) {
    return null;
  }
  return (hours * 60) + minutes;
};

class SSCPIntegrationPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._didInitialHassRefresh = false;
    this._payload = { entries: [] };
    this._selectedEntryId = null;
    this._renderedEntryId = null;
    this._activePage = "studio";
    this._browser = this._createBrowserState();
    this._browserSignature = "";
    this._composerVariablePicker = this._createComposerVariablePickerState();
    this._composerVariablePickerSignature = "";
    this._error = null;
    this._areas = [];
    this._areasLoaded = false;
    this._areasError = null;
    this._pollHandle = null;
    this._treeScrollTop = 0;
    this._configDrafts = {};
    this._manualDrafts = {};
    this._treeEntityDrafts = {};
    this._systemTimeDrafts = {};
    this._vlistVariableOptions = {};
    this._vlistVariableLoading = {};
    this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
    this._treeSensorPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      state_class: "",
      suggested_display_precision: "",
      area_id: "",
      error: "",
    };
    this._treeNumberPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      suggested_display_precision: "",
      area_id: "",
      min_value: "",
      max_value: "",
      step: "",
      mode: "box",
      error: "",
    };
    this._treeBasicPopup = this._treeBasicPopupDefaults();
    this._climatePopup = {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      temperature_unit: "°C",
      suggested_display_precision: "",
      min_temp: "7",
      max_temp: "35",
      temp_step: "0.5",
      current_temperature_name: "",
      target_temperature_name: "",
      current_humidity_name: "",
      power_name: "",
      hvac_mode_name: "",
      preset_name: "",
      hvac_mode_map_raw: "",
      preset_map_raw: "",
      error: "",
    };
    this._lightPopup = this._lightPopupDefaults();
    this._coverPopup = this._coverPopupDefaults();
    this._vacuumPopup = this._vacuumPopupDefaults();
    this._fanPopup = this._fanPopupDefaults();
    this._humidifierPopup = this._humidifierPopupDefaults();
    this._waterHeaterPopup = this._waterHeaterPopupDefaults();
    this._lockPopup = this._lockPopupDefaults();
    this._valvePopup = this._valvePopupDefaults();
    this._sirenPopup = this._sirenPopupDefaults();
    this._schedulerPopup = {
      open: false,
      loading: false,
      root_name: "",
      name: "",
      kind: "bool",
      supports_exceptions: false,
      point_capacity: 0,
      exception_capacity: 0,
      default_value: "",
      weekly_items: [],
      exceptions: [],
      error: "",
    };
    this._schedulerEntityPopup = this._schedulerEntityPopupDefaults();
    this._manualPanelOpenByEntry = {};
    this._manualPlcType = null;
    this._manualEntityType = null;
    this.attachShadow({ mode: "open" });
  }

  connectedCallback() {
    this._render();
    this._startPolling();
  }

  disconnectedCallback() {
    if (this._pollHandle) {
      clearInterval(this._pollHandle);
      this._pollHandle = null;
    }
  }

  set hass(hass) {
    const shouldRefresh = !this._didInitialHassRefresh;
    this._hass = hass;
    if (shouldRefresh) {
      this._didInitialHassRefresh = true;
      this._refreshAll();
    }
  }

  get _activeEntry() {
    const entries = this._payload?.entries || [];
    if (!entries.length) {
      return null;
    }
    return entries.find((entry) => entry.entry_id === this._selectedEntryId) || entries[0];
  }

  _createBrowserState() {
    return { filter_text: "", treeCache: {}, expandedPaths: new Set([ROOT_PATH_KEY]), loadingPaths: new Set() };
  }

  _createComposerVariablePickerState() {
    return {
      open: false,
      popup_key: "",
      field_key: "",
      field_label: "",
      input_id: "",
      filter_text: "",
      treeCache: {},
      expandedPaths: new Set([ROOT_PATH_KEY]),
      loadingPaths: new Set(),
      scroll_top: 0,
      error: "",
    };
  }

  _resetBrowserState({ keepFilter = false } = {}) {
    const filterText = keepFilter ? this._browser?.filter_text || "" : "";
    this._browser = this._createBrowserState();
    this._browser.filter_text = filterText;
    this._treeScrollTop = 0;
  }

  _resetComposerVariablePicker({ keepFilter = false } = {}) {
    const filterText = keepFilter ? this._composerVariablePicker?.filter_text || "" : "";
    this._composerVariablePicker = this._createComposerVariablePickerState();
    this._composerVariablePicker.filter_text = filterText;
  }

  _pathKey(path) {
    return (path || []).join("|");
  }

  _pathFromKey(pathKey) {
    return pathKey ? pathKey.split("|").filter(Boolean) : [];
  }

  _entryDraftKey(entry = this._activeEntry) {
    return entry?.entry_id || "__workspace__";
  }

  _composerPopupStateProperty(popupKey) {
    return {
      climate: "_climatePopup",
      light: "_lightPopup",
      cover: "_coverPopup",
      vacuum: "_vacuumPopup",
      fan: "_fanPopup",
      humidifier: "_humidifierPopup",
      water_heater: "_waterHeaterPopup",
      lock: "_lockPopup",
      valve: "_valvePopup",
      siren: "_sirenPopup",
    }[popupKey] || "";
  }

  _composerPopupFieldValue(popupKey, fieldKey) {
    const stateProperty = this._composerPopupStateProperty(popupKey);
    if (!stateProperty || !fieldKey) {
      return "";
    }
    return this[stateProperty]?.[fieldKey] || "";
  }

  _setComposerPopupFieldValue(popupKey, fieldKey, value) {
    const stateProperty = this._composerPopupStateProperty(popupKey);
    if (!stateProperty || !fieldKey) {
      return;
    }
    this[stateProperty] = {
      ...this[stateProperty],
      [fieldKey]: value || "",
    };
  }

  _isManualPanelOpen(entry = this._activeEntry) {
    return Boolean(this._manualPanelOpenByEntry[this._entryDraftKey(entry)]);
  }

  _browserStateSignature(entry) {
    if (!entry) {
      return "";
    }
    return `${entry.entry_id}:${entry.vlist_summary?.file || ""}`;
  }

  _configuredVariableKeys(entry) {
    return new Set((entry?.variables || []).map((item) => `${item.name_vlist || item.name}::${item.uid}`));
  }

  _startPolling() {
    if (this._pollHandle) {
      return;
    }
    this._pollHandle = setInterval(() => {
      if (this._hass) {
        this._refreshStatus({ preserveFormWhileEditing: true });
      }
    }, 30000);
  }

  _entryCatalog(entry) {
    return entry?.entity_type_catalog || DEFAULT_ENTITY_CATALOG;
  }

  _supportedPlcTypes(entry) {
    return entry?.supported_plc_types?.length ? entry.supported_plc_types : DEFAULT_PLC_TYPES;
  }

  _supportedEntityTypes(entry) {
    return entry?.supported_entity_types?.length ? entry.supported_entity_types : DEFAULT_ENTITY_TYPES;
  }

  _allowedEntityTypes(entry, plcType) {
    return this._entryCatalog(entry)[plcType] || this._supportedEntityTypes(entry);
  }

  _ensureManualDefaults(entry) {
    if (!entry) {
      this._manualPlcType = null;
      this._manualEntityType = null;
      return;
    }
    const plcTypes = this._supportedPlcTypes(entry);
    if (!this._manualPlcType || !plcTypes.includes(this._manualPlcType)) {
      this._manualPlcType = plcTypes.includes("INT") ? "INT" : plcTypes[0];
    }
    const entityTypes = this._allowedEntityTypes(entry, this._manualPlcType);
    if (!this._manualEntityType || !entityTypes.includes(this._manualEntityType)) {
      this._manualEntityType = entityTypes[0];
    }
  }

  async _api(method, path, body = undefined) {
    if (this._hass?.callApi) {
      const apiPath = path.startsWith("/api/") ? path.slice(5) : path;
      return this._hass.callApi(method, apiPath, body);
    }

    const token =
      this._hass?.auth?.data?.accessToken ||
      this._hass?.auth?.data?.access_token ||
      this._hass?.auth?.accessToken ||
      this._hass?.auth?.access_token;

    const headers = {};
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await fetch(path, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      let message = response.statusText;
      try {
        const errorPayload = await response.json();
        message = errorPayload.message || errorPayload.error || message;
      } catch (_error) {
        const text = await response.text();
        message = text || message;
      }
      throw new Error(message);
    }

    return response.json();
  }

  async _ws(message) {
    if (!this._hass?.callWS) {
      throw new Error("WebSocket API Home Assistantu neni v tomhle panelu dostupne.");
    }
    return this._hass.callWS(message);
  }

  async _refreshAreas({ force = false } = {}) {
    if (!this._hass || (this._areasLoaded && !force)) {
      return;
    }
    try {
      const areas = await this._ws({ type: "config/area_registry/list" });
      this._areas = (areas || [])
        .map((area) => ({
          area_id: area.area_id || area.id || "",
          name: area.name || area.alias || area.area_id || area.id || "Area",
        }))
        .filter((area) => area.area_id)
        .sort((left, right) => left.name.localeCompare(right.name, "cs"));
      this._areasLoaded = true;
      this._areasError = null;
    } catch (error) {
      this._areasError = error.message || String(error);
    }
  }

  async _refreshAll() {
    await Promise.all([this._refreshStatus(), this._refreshAreas()]);
    await this._refreshBrowser({ force: true });
  }

  _areaName(areaId) {
    const match = this._areas.find((area) => area.area_id === areaId);
    return match?.name || areaId || "";
  }

  _renderAreaField(fieldId, selectedAreaId, helpText) {
    const areaId = String(selectedAreaId || "");
    if (!this._areas.length) {
      return `
        <label id="${escapeHtml(fieldId)}-wrapper">
          <span>Umisteni / area</span>
          <input id="${escapeHtml(fieldId)}" placeholder="obyvak_area" value="${escapeHtml(areaId)}">
          <small class="field-help">${escapeHtml(helpText)}${
            this._areasError ? ` Aktualni seznam oblasti se nepodarilo nacist: ${escapeHtml(this._areasError)}.` : ""
          }</small>
        </label>
      `;
    }

    const knownAreaIds = new Set(this._areas.map((area) => area.area_id));
    const extraOption =
      areaId && !knownAreaIds.has(areaId)
        ? `<option value="${escapeHtml(areaId)}">${escapeHtml(this._areaName(areaId) || areaId)}</option>`
        : "";

    return `
      <label id="${escapeHtml(fieldId)}-wrapper">
        <span>Umisteni / area</span>
        <select id="${escapeHtml(fieldId)}">
          <option value="" ${!areaId ? "selected" : ""}>bez area</option>
          ${extraOption}
          ${this._areas
            .map(
              (area) =>
                `<option value="${escapeHtml(area.area_id)}" ${
                  area.area_id === areaId ? "selected" : ""
                }>${escapeHtml(area.name)}</option>`,
            )
            .join("")}
        </select>
        <small class="field-help">${escapeHtml(helpText)}</small>
      </label>
    `;
  }

  _renderVariableInputField(fieldId, label, value, helpText, placeholder = "Technology.Room.Point", options = {}) {
    const {
      popup_key: popupKey = "",
      field_key: fieldKey = "",
      help_html: helpHtml = "",
      button_label: buttonLabel = "Vybrat",
    } = options;
    const showPickerButton = Boolean(popupKey && fieldKey);
    const pickerButton = showPickerButton
      ? `
        <button
          type="button"
          class="secondary variable-picker-button"
          data-action="open-composer-variable-picker"
          data-popup="${escapeHtml(popupKey)}"
          data-field="${escapeHtml(fieldKey)}"
          data-label="${escapeHtml(label)}"
          data-input-id="${escapeHtml(fieldId)}"
          ${!this._activeEntry?.vlist_summary?.file ? "disabled" : ""}
        >
          ${escapeHtml(buttonLabel)}
        </button>
      `
      : "";
    const inputMarkup = `<input id="${escapeHtml(fieldId)}" placeholder="${escapeHtml(placeholder)}" value="${escapeHtml(value || "")}">`;
    const helpMarkup = helpHtml || escapeHtml(helpText);
    return `
      <label>
        <span>${escapeHtml(label)}</span>
        ${
          showPickerButton
            ? `
              <div class="variable-picker-row">
                ${inputMarkup}
                ${pickerButton}
              </div>
            `
            : inputMarkup
        }
        <small class="field-help">${helpMarkup}</small>
      </label>
    `;
  }

  _renderCatalogDatalists() {
    return `
      <datalist id="hass-unit-options">
        ${HASS_UNIT_OPTIONS.map((item) => `<option value="${escapeHtml(item)}"></option>`).join("")}
      </datalist>
      <datalist id="sensor-device-class-options">
        ${SENSOR_DEVICE_CLASS_OPTIONS.map((item) => `<option value="${escapeHtml(item)}"></option>`).join("")}
      </datalist>
      <datalist id="number-device-class-options">
        ${NUMBER_DEVICE_CLASS_OPTIONS.map((item) => `<option value="${escapeHtml(item)}"></option>`).join("")}
      </datalist>
      <datalist id="cover-device-class-options">
        ${COVER_DEVICE_CLASS_OPTIONS.map((item) => `<option value="${escapeHtml(item)}"></option>`).join("")}
      </datalist>
      <datalist id="humidifier-device-class-options">
        ${HUMIDIFIER_DEVICE_CLASS_OPTIONS.map((item) => `<option value="${escapeHtml(item)}"></option>`).join("")}
      </datalist>
      <datalist id="valve-device-class-options">
        ${VALVE_DEVICE_CLASS_OPTIONS.map((item) => `<option value="${escapeHtml(item)}"></option>`).join("")}
      </datalist>
    `;
  }

  _isEditingForm() {
    const activeElement = this.shadowRoot?.activeElement;
    return Boolean(activeElement?.matches?.("input, select, textarea"));
  }

  async _refreshStatus({ preserveFormWhileEditing = false } = {}) {
    if (!this._hass) {
      return;
    }
    try {
      this._payload = await this._api("GET", "/api/sscp_integration/status");
      const entries = this._payload.entries || [];
      const activeEntryIds = new Set(entries.map((entry) => entry.entry_id));
      [
        this._configDrafts,
        this._manualDrafts,
        this._treeEntityDrafts,
        this._manualPanelOpenByEntry,
        this._systemTimeDrafts,
        this._vlistVariableOptions,
        this._vlistVariableLoading,
      ].forEach((store) => {
        Object.keys(store).forEach((key) => {
          if (key !== "__workspace__" && !activeEntryIds.has(key)) {
            delete store[key];
          }
        });
      });
      if (this._selectedEntryId && !entries.some((entry) => entry.entry_id === this._selectedEntryId)) {
        this._selectedEntryId = null;
      }
      if (!this._selectedEntryId && entries.length) {
        this._selectedEntryId = entries[0].entry_id;
      }

      const signature = this._browserStateSignature(this._activeEntry);
      if (signature !== this._browserSignature) {
        const currentEntryKey = this._entryDraftKey(this._activeEntry);
        if (currentEntryKey) {
          delete this._vlistVariableOptions[currentEntryKey];
          delete this._vlistVariableLoading[currentEntryKey];
        }
        const filterText = this._browser.filter_text || "";
        this._resetBrowserState();
        this._browser.filter_text = filterText;
        this._browserSignature = signature;
      }

      const pickerSignature = this._browserStateSignature(this._activeEntry);
      if (pickerSignature !== this._composerVariablePickerSignature) {
        this._resetComposerVariablePicker();
        this._composerVariablePickerSignature = pickerSignature;
      }

      this._ensureManualDefaults(this._activeEntry);
      this._error = null;
    } catch (error) {
      this._error = error.message || String(error);
    }

    if (preserveFormWhileEditing && this._isEditingForm()) {
      return;
    }

    this._render();
  }

  async _loadTreeNode(path, { force = false } = {}) {
    const entry = this._activeEntry;
    if (!entry) {
      return null;
    }

    const pathKey = this._pathKey(path);
    if (!force && this._browser.treeCache[pathKey]) {
      return this._browser.treeCache[pathKey];
    }

    this._browser.loadingPaths.add(pathKey);
    this._render();

    try {
      const response = await this._api("POST", "/api/sscp_integration/action", {
        action: "browse_vlist",
        entry_id: entry.entry_id,
        path,
        filter_text: this._browser.filter_text || "",
        limit: 1000,
      });
      this._browser.treeCache[pathKey] = response;
      this._error = null;
      return response;
    } catch (error) {
      this._error = error.message || String(error);
      return null;
    } finally {
      this._browser.loadingPaths.delete(pathKey);
      this._render();
    }
  }

  async _refreshBrowser({ force = false } = {}) {
    const entry = this._activeEntry;
    if (!entry) {
      this._resetBrowserState({ keepFilter: true });
      this._render();
      return;
    }

    const pathKeys = new Set([ROOT_PATH_KEY, ...this._browser.expandedPaths]);
    await Promise.all(
      [...pathKeys].map((pathKey) => this._loadTreeNode(this._pathFromKey(pathKey), { force })),
    );
  }

  async _toggleTreeFolder(path) {
    const pathKey = this._pathKey(path);
    if (this._browser.expandedPaths.has(pathKey)) {
      this._browser.expandedPaths.delete(pathKey);
      this._render();
      return;
    }

    this._browser.expandedPaths.add(pathKey);
    await this._loadTreeNode(path);
  }

  async _applyTreeFilter() {
    const input = this.shadowRoot.querySelector("#filter-input");
    const filterText = input ? input.value : "";
    this._resetBrowserState();
    this._browser.filter_text = filterText;
    await this._refreshBrowser({ force: true });
  }

  async _openComposerVariablePicker(popupKey, fieldKey, fieldLabel = "", inputId = "") {
    if (!this._composerPopupStateProperty(popupKey) || !fieldKey) {
      return;
    }

    const entry = this._activeEntry;
    this._composerVariablePicker = {
      ...this._composerVariablePicker,
      open: true,
      popup_key: popupKey,
      field_key: fieldKey,
      field_label: fieldLabel || fieldKey,
      input_id: inputId || "",
      error: "",
    };
    this._render();

    if (!entry?.vlist_summary?.file) {
      this._composerVariablePicker = {
        ...this._composerVariablePicker,
        error: "Pro stromovy vyber nejdriv nastav nebo nahraj VList.",
      };
      this._render();
      return;
    }

    if (!this._composerVariablePicker.treeCache[ROOT_PATH_KEY]) {
      await this._loadComposerVariablePickerNode([]);
    }
  }

  _closeComposerVariablePicker() {
    this._composerVariablePicker = {
      ...this._composerVariablePicker,
      open: false,
      popup_key: "",
      field_key: "",
      field_label: "",
      input_id: "",
      error: "",
    };
    this._render();
  }

  async _loadComposerVariablePickerNode(path, { force = false } = {}) {
    const entry = this._activeEntry;
    if (!entry?.entry_id) {
      return null;
    }

    const pathKey = this._pathKey(path);
    if (!force && this._composerVariablePicker.treeCache[pathKey]) {
      return this._composerVariablePicker.treeCache[pathKey];
    }

    this._composerVariablePicker.loadingPaths.add(pathKey);
    this._render();

    try {
      const response = await this._api("POST", "/api/sscp_integration/action", {
        action: "browse_vlist",
        entry_id: entry.entry_id,
        path,
        filter_text: this._composerVariablePicker.filter_text || "",
        limit: 1000,
      });
      this._composerVariablePicker.treeCache[pathKey] = response;
      this._composerVariablePicker = {
        ...this._composerVariablePicker,
        error: "",
      };
      return response;
    } catch (error) {
      this._composerVariablePicker = {
        ...this._composerVariablePicker,
        error: error.message || String(error),
      };
      return null;
    } finally {
      this._composerVariablePicker.loadingPaths.delete(pathKey);
      this._render();
    }
  }

  async _refreshComposerVariablePicker({ force = false } = {}) {
    const entry = this._activeEntry;
    if (!entry?.vlist_summary?.file) {
      return;
    }

    const pathKeys = new Set([ROOT_PATH_KEY, ...this._composerVariablePicker.expandedPaths]);
    await Promise.all(
      [...pathKeys].map((pathKey) => this._loadComposerVariablePickerNode(this._pathFromKey(pathKey), { force })),
    );
  }

  async _toggleComposerVariablePickerFolder(path) {
    const pathKey = this._pathKey(path);
    if (this._composerVariablePicker.expandedPaths.has(pathKey)) {
      this._composerVariablePicker.expandedPaths.delete(pathKey);
      this._render();
      return;
    }

    this._composerVariablePicker.expandedPaths.add(pathKey);
    await this._loadComposerVariablePickerNode(path);
  }

  async _applyComposerVariablePickerFilter() {
    const input = this.shadowRoot.querySelector("#composer-variable-filter");
    const filterText = input ? input.value : "";
    this._composerVariablePicker = {
      ...this._createComposerVariablePickerState(),
      open: true,
      popup_key: this._composerVariablePicker.popup_key,
      field_key: this._composerVariablePicker.field_key,
      field_label: this._composerVariablePicker.field_label,
      input_id: this._composerVariablePicker.input_id,
      filter_text: filterText,
    };
    await this._refreshComposerVariablePicker({ force: true });
  }

  _selectComposerVariable(variableName) {
    const popupKey = this._composerVariablePicker.popup_key;
    const fieldKey = this._composerVariablePicker.field_key;
    if (!popupKey || !fieldKey || !variableName) {
      return;
    }

    const liveInput = this._composerVariablePicker.input_id
      ? this.shadowRoot.querySelector(`#${CSS.escape(this._composerVariablePicker.input_id)}`)
      : null;
    if (liveInput) {
      liveInput.value = variableName;
    }

    this._setComposerPopupFieldValue(popupKey, fieldKey, variableName);
    this._closeComposerVariablePicker();
  }

  async _runAction(action, extra = {}, options = {}) {
    const { refreshBrowser = false, allowWithoutEntry = false } = options;
    const entry = this._activeEntry;
    if (!entry && !allowWithoutEntry) {
      return null;
    }

    try {
      const result = await this._api("POST", "/api/sscp_integration/action", {
        action,
        ...(entry ? { entry_id: entry.entry_id } : {}),
        ...extra,
      });
      this._error = null;

      if (result?.entry_id) {
        this._selectedEntryId = result.entry_id;
      }

      await this._refreshStatus();
      if (refreshBrowser && this._activeEntry) {
        await this._refreshBrowser({ force: true });
      }
      return result;
    } catch (error) {
      this._error = error.message || String(error);
      this._render();
      return null;
    }
  }

  _parseSelectOptions(raw) {
    return String(raw || "")
      .split(/\r?\n|,/)
      .map((item) => item.trim())
      .filter(Boolean)
      .reduce((result, item) => {
        const separator = item.includes("=") ? "=" : item.includes(":") ? ":" : null;
        if (!separator) {
          return result;
        }
        const [key, ...labelParts] = item.split(separator);
        const label = labelParts.join(separator).trim();
        if (key.trim() && label) {
          result[key.trim()] = label;
        }
        return result;
      }, {});
  }

  _serializeSelectOptions(options) {
    return Object.entries(options || {})
      .map(([key, label]) => `${key}=${label}`)
      .join("\n");
  }

  _readManualForm() {
    const field = (selector) => this.shadowRoot.querySelector(selector);
    return {
      variable_name: field("#manual-name")?.value || "",
      display_name: field("#manual-display-name")?.value || "",
      uid: Number(field("#manual-uid")?.value || 0),
      offset: Number(field("#manual-offset")?.value || 0),
      length: Number(field("#manual-length")?.value || 1),
      plc_type: field("#manual-plc-type")?.value || this._manualPlcType || "INT",
      entity_type: field("#manual-entity-type")?.value || this._manualEntityType || "sensor",
      unit_of_measurement: field("#manual-unit")?.value || "",
      device_class: field("#manual-device-class")?.value || "",
      state_class: field("#manual-state-class")?.value || "",
      suggested_display_precision: field("#manual-display-precision")?.value || "",
      area_id: field("#manual-area")?.value || "",
      min_value: field("#manual-min")?.value || "",
      max_value: field("#manual-max")?.value || "",
      step: field("#manual-step")?.value || "",
      mode: field("#manual-mode")?.value || "box",
      press_time: field("#manual-press-time")?.value || "",
      select_options: this._parseSelectOptions(field("#manual-select-options")?.value || ""),
    };
  }

  async _fileToBase64(file) {
    const dataUrl = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error || new Error("Soubor se nepodarilo nacist."));
      reader.readAsDataURL(file);
    });
    return String(dataUrl).split(",", 2)[1] || "";
  }

  async _readUploadForm() {
    const fileInput = this.shadowRoot.querySelector("#vlist-upload-file");
    const nameInput = this.shadowRoot.querySelector("#vlist-upload-name");
    const overwriteInput = this.shadowRoot.querySelector("#vlist-upload-overwrite");
    const file = fileInput?.files?.[0];

    if (!file) {
      throw new Error("Vyber VList soubor k nahrani.");
    }

    return {
      file_name: nameInput?.value?.trim() || file.name,
      overwrite: Boolean(overwriteInput?.checked),
      content_base64: await this._fileToBase64(file),
    };
  }

  _configFormState(entry) {
    const draft = this._configDrafts[this._entryDraftKey(entry)] || {};
    return {
      plc_name: entry?.plc_name || "PLC",
      communication_mode: entry?.communication_mode || "sscp",
      host: entry?.host || "",
      port: entry?.port || "12346",
      username: entry?.username || "",
      password: entry?.password || "",
      sscp_address: entry?.sscp_address || "0x01",
      webpanel_connection: entry?.webpanel_connection || "defaultConnection",
      webpanel_scheme: entry?.webpanel_scheme || "http",
      scan_interval: String(entry?.scan_interval ?? 5),
      vlist_file_name: entry?.vlist_summary?.file_name || "",
      ...draft,
    };
  }

  _manualFormState(entry) {
    const draft = this._manualDrafts[this._entryDraftKey(entry)] || {};
    return {
      variable_name: "",
      display_name: "",
      uid: "0",
      offset: "0",
      length: "1",
      plc_type: this._manualPlcType || (this._supportedPlcTypes(entry)[0] || "INT"),
      entity_type: this._manualEntityType || "sensor",
      unit_of_measurement: "",
      device_class: "",
      state_class: "",
      suggested_display_precision: "",
      area_id: "",
      min_value: "",
      max_value: "",
      step: "",
      mode: "box",
      press_time: "",
      select_options_raw: "",
      ...draft,
    };
  }

  _systemTimeFormState(entry = this._activeEntry) {
    const draft = this._systemTimeDrafts[this._entryDraftKey(entry)] || {};
    return {
      mode: draft.mode || "local",
      value: draft.value || formatDateTimeLocalInput(entry?.time?.local || entry?.time?.utc || new Date().toISOString()),
    };
  }

  _variableOptions(entry = this._activeEntry) {
    return this._vlistVariableOptions[this._entryDraftKey(entry)] || [];
  }

  async _ensureVlistVariableOptions(entry = this._activeEntry, { force = false } = {}) {
    if (!entry?.entry_id || !entry.vlist_summary?.file) {
      return;
    }
    const entryKey = this._entryDraftKey(entry);
    if (!force && (this._vlistVariableOptions[entryKey]?.length || this._vlistVariableLoading[entryKey])) {
      return;
    }

    this._vlistVariableLoading[entryKey] = true;
    this._render();
    try {
      const response = await this._api("POST", "/api/sscp_integration/action", {
        action: "list_vlist_variables",
        entry_id: entry.entry_id,
        limit: 5000,
      });
      this._vlistVariableOptions[entryKey] = response?.variables || [];
      this._error = null;
    } catch (error) {
      this._error = error.message || String(error);
    } finally {
      this._vlistVariableLoading[entryKey] = false;
      this._render();
    }
  }

  _climatePopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      temperature_unit: "°C",
      suggested_display_precision: "",
      min_temp: "7",
      max_temp: "35",
      temp_step: "0.5",
      current_temperature_name: "",
      target_temperature_name: "",
      current_humidity_name: "",
      power_name: "",
      hvac_mode_name: "",
      preset_name: "",
      hvac_mode_map_raw: "",
      preset_map_raw: "",
      error: "",
    };
  }

  async _openClimatePopup(climate = null) {
    const popup = this._climatePopupDefaults();
    if (climate) {
      popup.entity_key = climate.entity_key || "";
      popup.name = climate.name || "";
      popup.area_id = climate.area_id || "";
      popup.temperature_unit = climate.temperature_unit || "°C";
      popup.suggested_display_precision =
        climate.suggested_display_precision !== null && climate.suggested_display_precision !== undefined
          ? String(climate.suggested_display_precision)
          : "";
      popup.min_temp = climate.min_temp !== null && climate.min_temp !== undefined ? String(climate.min_temp) : "7";
      popup.max_temp = climate.max_temp !== null && climate.max_temp !== undefined ? String(climate.max_temp) : "35";
      popup.temp_step = climate.temp_step !== null && climate.temp_step !== undefined ? String(climate.temp_step) : "0.5";
      popup.current_temperature_name = climate.current_temperature_name || "";
      popup.target_temperature_name = climate.target_temperature_name || "";
      popup.current_humidity_name = climate.current_humidity_name || "";
      popup.power_name = climate.power_name || "";
      popup.hvac_mode_name = climate.hvac_mode_name || "";
      popup.preset_name = climate.preset_name || "";
      popup.hvac_mode_map_raw = this._serializeSelectOptions(climate.hvac_mode_map || {});
      popup.preset_map_raw = this._serializeSelectOptions(climate.preset_map || {});
    }
    this._climatePopup = { ...popup, open: true };
    this._render();
  }

  _closeClimatePopup() {
    this._climatePopup = this._climatePopupDefaults();
    this._render();
  }

  _lightPopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      suggested_display_precision: "",
      brightness_scale: "100",
      min_mireds: "153",
      max_mireds: "500",
      power_name: "",
      brightness_name: "",
      color_temp_name: "",
      hs_hue_name: "",
      hs_saturation_name: "",
      rgb_red_name: "",
      rgb_green_name: "",
      rgb_blue_name: "",
      white_name: "",
      effect_name: "",
      effect_map_raw: "",
      error: "",
    };
  }

  async _openLightPopup(light = null) {
    const popup = this._lightPopupDefaults();
    if (light) {
      popup.entity_key = light.entity_key || "";
      popup.name = light.name || "";
      popup.area_id = light.area_id || "";
      popup.suggested_display_precision =
        light.suggested_display_precision !== null && light.suggested_display_precision !== undefined
          ? String(light.suggested_display_precision)
          : "";
      popup.brightness_scale = light.brightness_scale !== null && light.brightness_scale !== undefined ? String(light.brightness_scale) : "100";
      popup.min_mireds = light.min_mireds !== null && light.min_mireds !== undefined ? String(light.min_mireds) : "153";
      popup.max_mireds = light.max_mireds !== null && light.max_mireds !== undefined ? String(light.max_mireds) : "500";
      popup.power_name = light.power_name || "";
      popup.brightness_name = light.brightness_name || "";
      popup.color_temp_name = light.color_temp_name || "";
      popup.hs_hue_name = light.hs_hue_name || "";
      popup.hs_saturation_name = light.hs_saturation_name || "";
      popup.rgb_red_name = light.rgb_red_name || "";
      popup.rgb_green_name = light.rgb_green_name || "";
      popup.rgb_blue_name = light.rgb_blue_name || "";
      popup.white_name = light.white_name || "";
      popup.effect_name = light.effect_name || "";
      popup.effect_map_raw = this._serializeSelectOptions(light.effect_map || {});
    }
    this._lightPopup = { ...popup, open: true };
    this._render();
  }

  _closeLightPopup() {
    this._lightPopup = this._lightPopupDefaults();
    this._render();
  }

  _coverPopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      device_class: "",
      invert_position: false,
      current_position_name: "",
      target_position_name: "",
      open_name: "",
      close_name: "",
      stop_name: "",
      current_tilt_name: "",
      target_tilt_name: "",
      tilt_open_name: "",
      tilt_close_name: "",
      tilt_stop_name: "",
      error: "",
    };
  }

  async _openCoverPopup(cover = null) {
    const popup = this._coverPopupDefaults();
    if (cover) {
      popup.entity_key = cover.entity_key || "";
      popup.name = cover.name || "";
      popup.area_id = cover.area_id || "";
      popup.device_class = cover.device_class || "";
      popup.invert_position = Boolean(cover.invert_position);
      popup.current_position_name = cover.current_position_name || "";
      popup.target_position_name = cover.target_position_name || "";
      popup.open_name = cover.open_name || "";
      popup.close_name = cover.close_name || "";
      popup.stop_name = cover.stop_name || "";
      popup.current_tilt_name = cover.current_tilt_name || "";
      popup.target_tilt_name = cover.target_tilt_name || "";
      popup.tilt_open_name = cover.tilt_open_name || "";
      popup.tilt_close_name = cover.tilt_close_name || "";
      popup.tilt_stop_name = cover.tilt_stop_name || "";
    }
    this._coverPopup = { ...popup, open: true };
    this._render();
  }

  _closeCoverPopup() {
    this._coverPopup = this._coverPopupDefaults();
    this._render();
  }

  _vacuumPopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      status_name: "",
      battery_level_name: "",
      battery_charging_name: "",
      fan_speed_name: "",
      start_name: "",
      pause_name: "",
      stop_name: "",
      return_to_base_name: "",
      locate_name: "",
      status_map_raw: "",
      fan_speed_map_raw: "",
      error: "",
    };
  }

  async _openVacuumPopup(vacuum = null) {
    const popup = this._vacuumPopupDefaults();
    if (vacuum) {
      popup.entity_key = vacuum.entity_key || "";
      popup.name = vacuum.name || "";
      popup.area_id = vacuum.area_id || "";
      popup.status_name = vacuum.status_name || "";
      popup.battery_level_name = vacuum.battery_level_name || "";
      popup.battery_charging_name = vacuum.battery_charging_name || "";
      popup.fan_speed_name = vacuum.fan_speed_name || "";
      popup.start_name = vacuum.start_name || "";
      popup.pause_name = vacuum.pause_name || "";
      popup.stop_name = vacuum.stop_name || "";
      popup.return_to_base_name = vacuum.return_to_base_name || "";
      popup.locate_name = vacuum.locate_name || "";
      popup.status_map_raw = this._serializeSelectOptions(vacuum.status_map || {});
      popup.fan_speed_map_raw = this._serializeSelectOptions(vacuum.fan_speed_map || {});
    }
    this._vacuumPopup = { ...popup, open: true };
    this._render();
  }

  _closeVacuumPopup() {
    this._vacuumPopup = this._vacuumPopupDefaults();
    this._render();
  }

  _fanPopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      percentage_step: "1",
      power_name: "",
      percentage_name: "",
      preset_name: "",
      preset_map_raw: "",
      oscillate_name: "",
      direction_name: "",
      direction_map_raw: "",
      error: "",
    };
  }

  async _openFanPopup(fan = null) {
    const popup = this._fanPopupDefaults();
    if (fan) {
      popup.entity_key = fan.entity_key || "";
      popup.name = fan.name || "";
      popup.area_id = fan.area_id || "";
      popup.percentage_step = fan.percentage_step !== null && fan.percentage_step !== undefined ? String(fan.percentage_step) : "1";
      popup.power_name = fan.power_name || "";
      popup.percentage_name = fan.percentage_name || "";
      popup.preset_name = fan.preset_name || "";
      popup.preset_map_raw = this._serializeSelectOptions(fan.preset_map || {});
      popup.oscillate_name = fan.oscillate_name || "";
      popup.direction_name = fan.direction_name || "";
      popup.direction_map_raw = this._serializeSelectOptions(fan.direction_map || {});
    }
    this._fanPopup = { ...popup, open: true };
    this._render();
  }

  _closeFanPopup() {
    this._fanPopup = this._fanPopupDefaults();
    this._render();
  }

  _humidifierPopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      device_class: "",
      min_humidity: "0",
      max_humidity: "100",
      target_humidity_step: "1",
      current_humidity_name: "",
      target_humidity_name: "",
      power_name: "",
      mode_name: "",
      mode_map_raw: "",
      error: "",
    };
  }

  async _openHumidifierPopup(entity = null) {
    const popup = this._humidifierPopupDefaults();
    if (entity) {
      popup.entity_key = entity.entity_key || "";
      popup.name = entity.name || "";
      popup.area_id = entity.area_id || "";
      popup.device_class = entity.device_class || "";
      popup.min_humidity = entity.min_humidity !== null && entity.min_humidity !== undefined ? String(entity.min_humidity) : "0";
      popup.max_humidity = entity.max_humidity !== null && entity.max_humidity !== undefined ? String(entity.max_humidity) : "100";
      popup.target_humidity_step =
        entity.target_humidity_step !== null && entity.target_humidity_step !== undefined
          ? String(entity.target_humidity_step)
          : "1";
      popup.current_humidity_name = entity.current_humidity_name || "";
      popup.target_humidity_name = entity.target_humidity_name || "";
      popup.power_name = entity.power_name || "";
      popup.mode_name = entity.mode_name || "";
      popup.mode_map_raw = this._serializeSelectOptions(entity.mode_map || {});
    }
    this._humidifierPopup = { ...popup, open: true };
    this._render();
  }

  _closeHumidifierPopup() {
    this._humidifierPopup = this._humidifierPopupDefaults();
    this._render();
  }

  _waterHeaterPopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      temperature_unit: "Â°C",
      suggested_display_precision: "",
      min_temp: "30",
      max_temp: "90",
      temp_step: "0.5",
      current_temperature_name: "",
      target_temperature_name: "",
      power_name: "",
      operation_mode_name: "",
      operation_mode_map_raw: "",
      error: "",
    };
  }

  async _openWaterHeaterPopup(entity = null) {
    const popup = this._waterHeaterPopupDefaults();
    if (entity) {
      popup.entity_key = entity.entity_key || "";
      popup.name = entity.name || "";
      popup.area_id = entity.area_id || "";
      popup.temperature_unit = entity.temperature_unit || "Â°C";
      popup.suggested_display_precision =
        entity.suggested_display_precision !== null && entity.suggested_display_precision !== undefined
          ? String(entity.suggested_display_precision)
          : "";
      popup.min_temp = entity.min_temp !== null && entity.min_temp !== undefined ? String(entity.min_temp) : "30";
      popup.max_temp = entity.max_temp !== null && entity.max_temp !== undefined ? String(entity.max_temp) : "90";
      popup.temp_step = entity.temp_step !== null && entity.temp_step !== undefined ? String(entity.temp_step) : "0.5";
      popup.current_temperature_name = entity.current_temperature_name || "";
      popup.target_temperature_name = entity.target_temperature_name || "";
      popup.power_name = entity.power_name || "";
      popup.operation_mode_name = entity.operation_mode_name || "";
      popup.operation_mode_map_raw = this._serializeSelectOptions(entity.operation_mode_map || {});
    }
    this._waterHeaterPopup = { ...popup, open: true };
    this._render();
  }

  _closeWaterHeaterPopup() {
    this._waterHeaterPopup = this._waterHeaterPopupDefaults();
    this._render();
  }

  _lockPopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      state_name: "",
      lock_name: "",
      unlock_name: "",
      open_name: "",
      state_map_raw: "",
      error: "",
    };
  }

  async _openLockPopup(entity = null) {
    const popup = this._lockPopupDefaults();
    if (entity) {
      popup.entity_key = entity.entity_key || "";
      popup.name = entity.name || "";
      popup.area_id = entity.area_id || "";
      popup.state_name = entity.state_name || "";
      popup.lock_name = entity.lock_name || "";
      popup.unlock_name = entity.unlock_name || "";
      popup.open_name = entity.open_name || "";
      popup.state_map_raw = this._serializeSelectOptions(entity.state_map || {});
    }
    this._lockPopup = { ...popup, open: true };
    this._render();
  }

  _closeLockPopup() {
    this._lockPopup = this._lockPopupDefaults();
    this._render();
  }

  _valvePopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      device_class: "",
      invert_position: false,
      current_position_name: "",
      target_position_name: "",
      open_name: "",
      close_name: "",
      stop_name: "",
      error: "",
    };
  }

  async _openValvePopup(entity = null) {
    const popup = this._valvePopupDefaults();
    if (entity) {
      popup.entity_key = entity.entity_key || "";
      popup.name = entity.name || "";
      popup.area_id = entity.area_id || "";
      popup.device_class = entity.device_class || "";
      popup.invert_position = Boolean(entity.invert_position);
      popup.current_position_name = entity.current_position_name || "";
      popup.target_position_name = entity.target_position_name || "";
      popup.open_name = entity.open_name || "";
      popup.close_name = entity.close_name || "";
      popup.stop_name = entity.stop_name || "";
    }
    this._valvePopup = { ...popup, open: true };
    this._render();
  }

  _closeValvePopup() {
    this._valvePopup = this._valvePopupDefaults();
    this._render();
  }

  _sirenPopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      area_id: "",
      state_name: "",
      turn_on_name: "",
      turn_off_name: "",
      tone_name: "",
      tone_map_raw: "",
      duration_name: "",
      volume_name: "",
      volume_scale: "100",
      error: "",
    };
  }

  async _openSirenPopup(entity = null) {
    const popup = this._sirenPopupDefaults();
    if (entity) {
      popup.entity_key = entity.entity_key || "";
      popup.name = entity.name || "";
      popup.area_id = entity.area_id || "";
      popup.state_name = entity.state_name || "";
      popup.turn_on_name = entity.turn_on_name || "";
      popup.turn_off_name = entity.turn_off_name || "";
      popup.tone_name = entity.tone_name || "";
      popup.tone_map_raw = this._serializeSelectOptions(entity.tone_map || {});
      popup.duration_name = entity.duration_name || "";
      popup.volume_name = entity.volume_name || "";
      popup.volume_scale = entity.volume_scale !== null && entity.volume_scale !== undefined ? String(entity.volume_scale) : "100";
    }
    this._sirenPopup = { ...popup, open: true };
    this._render();
  }

  _closeSirenPopup() {
    this._sirenPopup = this._sirenPopupDefaults();
    this._render();
  }

  _schedulerEntityPopupDefaults() {
    return {
      open: false,
      entity_key: "",
      name: "",
      root_name: "",
      area_id: "",
      suggested_display_precision: "",
      error: "",
    };
  }

  _openSchedulerEntityPopup(entity = null, rootName = "") {
    const popup = this._schedulerEntityPopupDefaults();
    if (entity) {
      popup.entity_key = entity.entity_key || "";
      popup.name = entity.name || "";
      popup.root_name = entity.root_name || "";
      popup.area_id = entity.area_id || "";
      popup.suggested_display_precision =
        entity.suggested_display_precision !== null && entity.suggested_display_precision !== undefined
          ? String(entity.suggested_display_precision)
          : "";
    } else {
      popup.root_name = rootName || "";
      popup.name = rootName ? rootName.split(".").slice(-1)[0] : "";
    }
    this._schedulerEntityPopup = { ...popup, open: true };
    this._render();
  }

  _closeSchedulerEntityPopup() {
    this._schedulerEntityPopup = this._schedulerEntityPopupDefaults();
    this._render();
  }

  _schedulerPopupDefaults() {
    return {
      open: false,
      loading: false,
      root_name: "",
      name: "",
      kind: "bool",
      supports_exceptions: false,
      point_capacity: 0,
      exception_capacity: 0,
      default_value: "",
      weekly_items: [],
      exceptions: [],
      error: "",
    };
  }

  async _openSchedulerPopup(rootName) {
    this._schedulerPopup = {
      ...this._schedulerPopupDefaults(),
      open: true,
      loading: true,
      root_name: rootName,
      name: rootName?.split(".")?.slice(-1)?.[0] || rootName || "",
    };
    this._render();
    try {
      const response = await this._runAction("get_scheduler", { root_name: rootName });
      if (!response) {
        this._schedulerPopup = {
          ...this._schedulerPopup,
          loading: false,
          error: this._error || "Tydenni program se nepodarilo nacist.",
        };
      } else {
        this._schedulerPopup = {
          open: true,
          loading: false,
          root_name: response.root_name || rootName,
          name: response.name || rootName,
          kind: response.kind || "bool",
          supports_exceptions: Boolean(response.supports_exceptions),
          point_capacity: response.point_capacity || 0,
          exception_capacity: response.exception_capacity || 0,
          default_value:
            response.default_value !== null && response.default_value !== undefined ? String(response.default_value) : "",
          weekly_items: (response.weekly_items || []).map((item) => ({
            ...item,
            day: Number(item.day) || 0,
            minute_of_day: Number(item.minute_of_day) || 0,
            value: item.value,
          })),
          exceptions: response.exceptions || [],
          error: "",
        };
      }
    } catch (error) {
      this._schedulerPopup = {
        ...this._schedulerPopup,
        loading: false,
        error: error.message || String(error),
      };
    }
    this._render();
  }

  _closeSchedulerPopup() {
    this._schedulerPopup = this._schedulerPopupDefaults();
    this._render();
  }

  _schedulerDayItems(day) {
    return (this._schedulerPopup.weekly_items || [])
      .filter((item) => Number(item.day) === Number(day))
      .sort((left, right) => Number(left.minute_of_day) - Number(right.minute_of_day));
  }

  _schedulerItemValue(item) {
    if (this._schedulerPopup.kind === "bool") {
      return item?.value ? "1" : "0";
    }
    return item?.value ?? "";
  }

  _schedulerValueInput(kind, fieldName, value, itemId) {
    if (kind === "bool") {
      return `
        <select data-action="scheduler-update-item" data-item-id="${escapeHtml(itemId)}" data-field="${escapeHtml(fieldName)}">
          <option value="0" ${String(value) === "0" ? "selected" : ""}>Off</option>
          <option value="1" ${String(value) === "1" ? "selected" : ""}>On</option>
        </select>
      `;
    }
    return `<input type="number" step="${kind === "real" ? "0.1" : "1"}" value="${escapeHtml(value)}" data-action="scheduler-update-item" data-item-id="${escapeHtml(itemId)}" data-field="${escapeHtml(fieldName)}">`;
  }

  _findVariableByKey(entry, variableEntryKey) {
    return (entry?.variables || []).find((item) => item.key === variableEntryKey) || null;
  }

  _treeVariableState(entry, variableName, defaultEntityType) {
    const entryDrafts = this._treeEntityDrafts[this._entryDraftKey(entry)] || {};
    const draft = entryDrafts[variableName] || {};
    return {
      entity_type: draft.entity_type || defaultEntityType || "sensor",
      display_name: draft.display_name || "",
      select_options_raw: draft.select_options_raw || "",
      unit_of_measurement: draft.unit_of_measurement || "",
      device_class: draft.device_class || "",
      state_class: draft.state_class || "",
      suggested_display_precision: draft.suggested_display_precision || "",
      area_id: draft.area_id || "",
      min_value: draft.min_value || "",
      max_value: draft.max_value || "",
      step: draft.step || "",
      mode: draft.mode || "box",
      press_time: draft.press_time || "",
    };
  }

  _openTreeSelectPopup(variableName) {
    const state = this._treeVariableState(this._activeEntry, variableName, "select");
    this._treeSelectPopup = {
      open: true,
      variable_name: variableName,
      variable_entry_key: "",
      select_options_raw: state.select_options_raw || "",
      error: "",
    };
    this._treeNumberPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      suggested_display_precision: "",
      area_id: "",
      min_value: "",
      max_value: "",
      step: "",
      mode: "box",
      error: "",
    };
    this._treeSensorPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      state_class: "",
      suggested_display_precision: "",
      area_id: "",
      error: "",
    };
    this._render();
  }

  _openSelectEditPopup(variable) {
    this._treeSelectPopup = {
      open: true,
      variable_name: variable.name_vlist || variable.name || "",
      variable_entry_key: variable.key || "",
      select_options_raw: this._serializeSelectOptions(variable.select_options || {}),
      error: "",
    };
    this._treeSensorPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      state_class: "",
      suggested_display_precision: "",
      area_id: "",
      error: "",
    };
    this._treeNumberPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      suggested_display_precision: "",
      area_id: "",
      min_value: "",
      max_value: "",
      step: "",
      mode: "box",
      error: "",
    };
    this._render();
  }

  _closeTreeSelectPopup() {
    this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
    this._render();
  }

  _openTreeSensorPopup(variableName) {
    const state = this._treeVariableState(this._activeEntry, variableName, "sensor");
    this._treeSensorPopup = {
      open: true,
      variable_name: variableName,
      variable_entry_key: "",
      unit_of_measurement: state.unit_of_measurement || "",
      device_class: state.device_class || "",
      state_class: state.state_class || "",
      suggested_display_precision: state.suggested_display_precision || "",
      area_id: state.area_id || "",
      error: "",
    };
    this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
    this._treeNumberPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      suggested_display_precision: "",
      area_id: "",
      min_value: "",
      max_value: "",
      step: "",
      mode: "box",
      error: "",
    };
    this._render();
  }

  _openSensorEditPopup(variable) {
    this._treeSensorPopup = {
      open: true,
      variable_name: variable.name_vlist || variable.name || "",
      variable_entry_key: variable.key || "",
      unit_of_measurement: variable.unit_of_measurement || "",
      device_class: variable.device_class || "",
      state_class: variable.state_class || "",
      suggested_display_precision:
        variable.suggested_display_precision !== null && variable.suggested_display_precision !== undefined
          ? String(variable.suggested_display_precision)
          : "",
      area_id: variable.area_id || "",
      error: "",
    };
    this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
    this._treeNumberPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      suggested_display_precision: "",
      area_id: "",
      min_value: "",
      max_value: "",
      step: "",
      mode: "box",
      error: "",
    };
    this._render();
  }

  _closeTreeSensorPopup() {
    this._treeSensorPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      state_class: "",
      suggested_display_precision: "",
      area_id: "",
      error: "",
    };
    this._render();
  }

  _openTreeNumberPopup(variableName) {
    const state = this._treeVariableState(this._activeEntry, variableName, "number");
    this._treeNumberPopup = {
      open: true,
      variable_name: variableName,
      variable_entry_key: "",
      unit_of_measurement: state.unit_of_measurement || "",
      device_class: state.device_class || "",
      suggested_display_precision: state.suggested_display_precision || "",
      area_id: state.area_id || "",
      min_value: state.min_value || "",
      max_value: state.max_value || "",
      step: state.step || "",
      mode: state.mode || "box",
      error: "",
    };
    this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
    this._treeSensorPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      state_class: "",
      suggested_display_precision: "",
      area_id: "",
      error: "",
    };
    this._render();
  }

  _openNumberEditPopup(variable) {
    this._treeNumberPopup = {
      open: true,
      variable_name: variable.name_vlist || variable.name || "",
      variable_entry_key: variable.key || "",
      unit_of_measurement: variable.unit_of_measurement || "",
      device_class: variable.device_class || "",
      suggested_display_precision:
        variable.suggested_display_precision !== null && variable.suggested_display_precision !== undefined
          ? String(variable.suggested_display_precision)
          : "",
      area_id: variable.area_id || "",
      min_value: variable.min_value !== null && variable.min_value !== undefined ? String(variable.min_value) : "",
      max_value: variable.max_value !== null && variable.max_value !== undefined ? String(variable.max_value) : "",
      step: variable.step !== null && variable.step !== undefined ? String(variable.step) : "",
      mode: variable.mode || "box",
      error: "",
    };
    this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
    this._treeSensorPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      state_class: "",
      suggested_display_precision: "",
      area_id: "",
      error: "",
    };
    this._render();
  }

  _closeTreeNumberPopup() {
    this._treeNumberPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      suggested_display_precision: "",
      area_id: "",
      min_value: "",
      max_value: "",
      step: "",
      mode: "box",
      error: "",
    };
    this._render();
  }

  _treeBasicPopupDefaults() {
    return {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      entity_type: "switch",
      display_name: "",
      area_id: "",
      press_time: "",
      error: "",
    };
  }

  _openTreeBasicPopup(variableName, entityType) {
    const state = this._treeVariableState(this._activeEntry, variableName, entityType);
    this._treeBasicPopup = {
      open: true,
      variable_name: variableName,
      variable_entry_key: "",
      entity_type: entityType || "switch",
      display_name: state.display_name || "",
      area_id: state.area_id || "",
      press_time: state.press_time || "",
      error: "",
    };
    this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
    this._treeSensorPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      state_class: "",
      suggested_display_precision: "",
      area_id: "",
      error: "",
    };
    this._treeNumberPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      suggested_display_precision: "",
      area_id: "",
      min_value: "",
      max_value: "",
      step: "",
      mode: "box",
      error: "",
    };
    this._render();
  }

  _openBasicEditPopup(variable) {
    this._treeBasicPopup = {
      open: true,
      variable_name: variable.name_vlist || variable.name || "",
      variable_entry_key: variable.key || "",
      entity_type: variable.entity_type || "switch",
      display_name: variable.name || "",
      area_id: variable.area_id || "",
      press_time: variable.press_time !== null && variable.press_time !== undefined ? String(variable.press_time) : "",
      error: "",
    };
    this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
    this._treeSensorPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      state_class: "",
      suggested_display_precision: "",
      area_id: "",
      error: "",
    };
    this._treeNumberPopup = {
      open: false,
      variable_name: "",
      variable_entry_key: "",
      unit_of_measurement: "",
      device_class: "",
      suggested_display_precision: "",
      area_id: "",
      min_value: "",
      max_value: "",
      step: "",
      mode: "box",
      error: "",
    };
    this._render();
  }

  _closeTreeBasicPopup() {
    this._treeBasicPopup = this._treeBasicPopupDefaults();
    this._render();
  }

  _openVariableEditor(variableEntryKey) {
    const variable = this._findVariableByKey(this._activeEntry, variableEntryKey);
    if (!variable) {
      this._error = "Vybrana entita uz v konfiguraci neexistuje.";
      this._render();
      return;
    }

    if (variable.entity_type === "select") {
      this._openSelectEditPopup(variable);
      return;
    }
    if (variable.entity_type === "sensor") {
      this._openSensorEditPopup(variable);
      return;
    }
    if (variable.entity_type === "number") {
      this._openNumberEditPopup(variable);
      return;
    }
    if (["switch", "button", "light", "binary_sensor", "datetime"].includes(variable.entity_type)) {
      this._openBasicEditPopup(variable);
      return;
    }

    this._error = `Editace pres popup zatim neumi typ ${variable.entity_type}.`;
    this._render();
  }

  _captureUiState() {
    if (!this.shadowRoot) {
      return;
    }

    const treeShell = this.shadowRoot.querySelector(".tree-shell");
    if (treeShell) {
      this._treeScrollTop = treeShell.scrollTop;
    }

    const composerPickerShell = this.shadowRoot.querySelector(".composer-picker-tree-shell");
    if (composerPickerShell && this._composerVariablePicker.open) {
      this._composerVariablePicker.scroll_top = composerPickerShell.scrollTop;
    }

    const entryKey = this._renderedEntryId || this._entryDraftKey();
    const field = (selector) => this.shadowRoot.querySelector(selector);

    if (field("#cfg-plc-name")) {
      this._configDrafts[entryKey] = {
        plc_name: field("#cfg-plc-name")?.value || "PLC",
        communication_mode: field("#cfg-communication-mode")?.value || "sscp",
        host: field("#cfg-host")?.value || "",
        port: field("#cfg-port")?.value || "12346",
        username: field("#cfg-username")?.value || "",
        password: field("#cfg-password")?.value || "",
        sscp_address: field("#cfg-address")?.value || "0x01",
        webpanel_connection: field("#cfg-webpanel-connection")?.value || "defaultConnection",
        webpanel_scheme: field("#cfg-webpanel-scheme")?.value || "http",
        scan_interval: field("#cfg-scan")?.value || "5",
        vlist_file_name: field("#cfg-vlist")?.value || "",
      };
    }

    if (field("#manual-name")) {
      this._manualDrafts[entryKey] = {
        variable_name: field("#manual-name")?.value || "",
        display_name: field("#manual-display-name")?.value || "",
        uid: field("#manual-uid")?.value || "0",
        offset: field("#manual-offset")?.value || "0",
        length: field("#manual-length")?.value || "1",
        plc_type: field("#manual-plc-type")?.value || this._manualPlcType || "INT",
        entity_type: field("#manual-entity-type")?.value || this._manualEntityType || "sensor",
        unit_of_measurement: field("#manual-unit")?.value || "",
        device_class: field("#manual-device-class")?.value || "",
        state_class: field("#manual-state-class")?.value || "",
        suggested_display_precision: field("#manual-display-precision")?.value || "",
        area_id: field("#manual-area")?.value || "",
        min_value: field("#manual-min")?.value || "",
        max_value: field("#manual-max")?.value || "",
        step: field("#manual-step")?.value || "",
        mode: field("#manual-mode")?.value || "box",
        press_time: field("#manual-press-time")?.value || "",
        select_options_raw: field("#manual-select-options")?.value || "",
      };
    }

    if (field("#plc-time-value")) {
      this._systemTimeDrafts[entryKey] = {
        mode: field("#plc-time-mode")?.value || "local",
        value: field("#plc-time-value")?.value || "",
      };
    }

    const currentTreeDrafts = { ...(this._treeEntityDrafts[entryKey] || {}) };
    this.shadowRoot.querySelectorAll(".tree-entity-select").forEach((selectNode) => {
      const variableName = selectNode.dataset.treeVariable || "";
      if (!variableName) {
        return;
      }
      currentTreeDrafts[variableName] = {
        ...(currentTreeDrafts[variableName] || {}),
        entity_type: selectNode.value || "sensor",
      };
    });
    this.shadowRoot.querySelectorAll(".tree-select-options").forEach((textareaNode) => {
      const variableName = textareaNode.dataset.treeVariable || "";
      if (!variableName) {
        return;
      }
      currentTreeDrafts[variableName] = {
        ...(currentTreeDrafts[variableName] || {}),
        select_options_raw: textareaNode.value || "",
      };
    });
    if (this._treeSelectPopup.open && this._treeSelectPopup.variable_name) {
      const popupRaw = field("#tree-select-popup-options")?.value ?? this._treeSelectPopup.select_options_raw ?? "";
      currentTreeDrafts[this._treeSelectPopup.variable_name] = {
        ...(currentTreeDrafts[this._treeSelectPopup.variable_name] || {}),
        entity_type: "select",
        select_options_raw: popupRaw,
      };
      this._treeSelectPopup = {
        ...this._treeSelectPopup,
        select_options_raw: popupRaw,
      };
    }
    if (this._treeSensorPopup.open && this._treeSensorPopup.variable_name) {
      const popupUnit = field("#tree-sensor-popup-unit")?.value ?? this._treeSensorPopup.unit_of_measurement ?? "";
      const popupDeviceClass = field("#tree-sensor-popup-device-class")?.value ?? this._treeSensorPopup.device_class ?? "";
      const popupStateClass = field("#tree-sensor-popup-state-class")?.value ?? this._treeSensorPopup.state_class ?? "";
      const popupPrecision =
        field("#tree-sensor-popup-display-precision")?.value ?? this._treeSensorPopup.suggested_display_precision ?? "";
      const popupAreaId = field("#tree-sensor-popup-area")?.value ?? this._treeSensorPopup.area_id ?? "";
      currentTreeDrafts[this._treeSensorPopup.variable_name] = {
        ...(currentTreeDrafts[this._treeSensorPopup.variable_name] || {}),
        entity_type: "sensor",
        unit_of_measurement: popupUnit,
        device_class: popupDeviceClass,
        state_class: popupStateClass,
        suggested_display_precision: popupPrecision,
        area_id: popupAreaId,
      };
      this._treeSensorPopup = {
        ...this._treeSensorPopup,
        unit_of_measurement: popupUnit,
        device_class: popupDeviceClass,
        state_class: popupStateClass,
        suggested_display_precision: popupPrecision,
        area_id: popupAreaId,
      };
    }
    if (this._treeNumberPopup.open && this._treeNumberPopup.variable_name) {
      const popupUnit = field("#tree-number-popup-unit")?.value ?? this._treeNumberPopup.unit_of_measurement ?? "";
      const popupDeviceClass = field("#tree-number-popup-device-class")?.value ?? this._treeNumberPopup.device_class ?? "";
      const popupPrecision =
        field("#tree-number-popup-display-precision")?.value ?? this._treeNumberPopup.suggested_display_precision ?? "";
      const popupAreaId = field("#tree-number-popup-area")?.value ?? this._treeNumberPopup.area_id ?? "";
      const popupMin = field("#tree-number-popup-min")?.value ?? this._treeNumberPopup.min_value ?? "";
      const popupMax = field("#tree-number-popup-max")?.value ?? this._treeNumberPopup.max_value ?? "";
      const popupStep = field("#tree-number-popup-step")?.value ?? this._treeNumberPopup.step ?? "";
      const popupMode = field("#tree-number-popup-mode")?.value ?? this._treeNumberPopup.mode ?? "box";
      currentTreeDrafts[this._treeNumberPopup.variable_name] = {
        ...(currentTreeDrafts[this._treeNumberPopup.variable_name] || {}),
        entity_type: "number",
        unit_of_measurement: popupUnit,
        device_class: popupDeviceClass,
        suggested_display_precision: popupPrecision,
        area_id: popupAreaId,
        min_value: popupMin,
        max_value: popupMax,
        step: popupStep,
        mode: popupMode,
      };
      this._treeNumberPopup = {
        ...this._treeNumberPopup,
        unit_of_measurement: popupUnit,
        device_class: popupDeviceClass,
        suggested_display_precision: popupPrecision,
        area_id: popupAreaId,
        min_value: popupMin,
        max_value: popupMax,
        step: popupStep,
        mode: popupMode,
      };
    }
    if (this._treeBasicPopup.open && this._treeBasicPopup.variable_name) {
      const popupDisplayName = field("#tree-basic-popup-display-name")?.value ?? this._treeBasicPopup.display_name ?? "";
      const popupAreaId = field("#tree-basic-popup-area")?.value ?? this._treeBasicPopup.area_id ?? "";
      const popupPressTime = field("#tree-basic-popup-press-time")?.value ?? this._treeBasicPopup.press_time ?? "";
      currentTreeDrafts[this._treeBasicPopup.variable_name] = {
        ...(currentTreeDrafts[this._treeBasicPopup.variable_name] || {}),
        entity_type: this._treeBasicPopup.entity_type || "switch",
        display_name: popupDisplayName,
        area_id: popupAreaId,
        press_time: popupPressTime,
      };
      this._treeBasicPopup = {
        ...this._treeBasicPopup,
        display_name: popupDisplayName,
        area_id: popupAreaId,
        press_time: popupPressTime,
      };
    }
    if (this._composerVariablePicker.open) {
      this._composerVariablePicker = {
        ...this._composerVariablePicker,
        filter_text: field("#composer-variable-filter")?.value ?? this._composerVariablePicker.filter_text ?? "",
      };
    }
    if (this._climatePopup.open) {
      this._climatePopup = {
        ...this._climatePopup,
        name: field("#climate-popup-name")?.value ?? this._climatePopup.name ?? "",
        area_id: field("#climate-popup-area")?.value ?? this._climatePopup.area_id ?? "",
        temperature_unit: field("#climate-popup-temperature-unit")?.value ?? this._climatePopup.temperature_unit ?? "°C",
        suggested_display_precision:
          field("#climate-popup-precision")?.value ?? this._climatePopup.suggested_display_precision ?? "",
        min_temp: field("#climate-popup-min-temp")?.value ?? this._climatePopup.min_temp ?? "7",
        max_temp: field("#climate-popup-max-temp")?.value ?? this._climatePopup.max_temp ?? "35",
        temp_step: field("#climate-popup-step")?.value ?? this._climatePopup.temp_step ?? "0.5",
        current_temperature_name:
          field("#climate-popup-current-temperature")?.value ?? this._climatePopup.current_temperature_name ?? "",
        target_temperature_name:
          field("#climate-popup-target-temperature")?.value ?? this._climatePopup.target_temperature_name ?? "",
        current_humidity_name:
          field("#climate-popup-current-humidity")?.value ?? this._climatePopup.current_humidity_name ?? "",
        power_name: field("#climate-popup-power")?.value ?? this._climatePopup.power_name ?? "",
        hvac_mode_name: field("#climate-popup-hvac-mode")?.value ?? this._climatePopup.hvac_mode_name ?? "",
        preset_name: field("#climate-popup-preset")?.value ?? this._climatePopup.preset_name ?? "",
        hvac_mode_map_raw: field("#climate-popup-hvac-map")?.value ?? this._climatePopup.hvac_mode_map_raw ?? "",
        preset_map_raw: field("#climate-popup-preset-map")?.value ?? this._climatePopup.preset_map_raw ?? "",
      };
    }
    if (this._lightPopup.open) {
      this._lightPopup = {
        ...this._lightPopup,
        name: field("#light-popup-name")?.value ?? this._lightPopup.name ?? "",
        area_id: field("#light-popup-area")?.value ?? this._lightPopup.area_id ?? "",
        suggested_display_precision:
          field("#light-popup-precision")?.value ?? this._lightPopup.suggested_display_precision ?? "",
        brightness_scale: field("#light-popup-brightness-scale")?.value ?? this._lightPopup.brightness_scale ?? "100",
        min_mireds: field("#light-popup-min-mireds")?.value ?? this._lightPopup.min_mireds ?? "153",
        max_mireds: field("#light-popup-max-mireds")?.value ?? this._lightPopup.max_mireds ?? "500",
        power_name: field("#light-popup-power")?.value ?? this._lightPopup.power_name ?? "",
        brightness_name: field("#light-popup-brightness")?.value ?? this._lightPopup.brightness_name ?? "",
        color_temp_name: field("#light-popup-color-temp")?.value ?? this._lightPopup.color_temp_name ?? "",
        hs_hue_name: field("#light-popup-hue")?.value ?? this._lightPopup.hs_hue_name ?? "",
        hs_saturation_name: field("#light-popup-saturation")?.value ?? this._lightPopup.hs_saturation_name ?? "",
        rgb_red_name: field("#light-popup-rgb-red")?.value ?? this._lightPopup.rgb_red_name ?? "",
        rgb_green_name: field("#light-popup-rgb-green")?.value ?? this._lightPopup.rgb_green_name ?? "",
        rgb_blue_name: field("#light-popup-rgb-blue")?.value ?? this._lightPopup.rgb_blue_name ?? "",
        white_name: field("#light-popup-white")?.value ?? this._lightPopup.white_name ?? "",
        effect_name: field("#light-popup-effect")?.value ?? this._lightPopup.effect_name ?? "",
        effect_map_raw: field("#light-popup-effect-map")?.value ?? this._lightPopup.effect_map_raw ?? "",
      };
    }
    if (this._coverPopup.open) {
      this._coverPopup = {
        ...this._coverPopup,
        name: field("#cover-popup-name")?.value ?? this._coverPopup.name ?? "",
        area_id: field("#cover-popup-area")?.value ?? this._coverPopup.area_id ?? "",
        device_class: field("#cover-popup-device-class")?.value ?? this._coverPopup.device_class ?? "",
        invert_position: field("#cover-popup-invert")?.checked ?? this._coverPopup.invert_position ?? false,
        current_position_name: field("#cover-popup-current-position")?.value ?? this._coverPopup.current_position_name ?? "",
        target_position_name: field("#cover-popup-target-position")?.value ?? this._coverPopup.target_position_name ?? "",
        open_name: field("#cover-popup-open")?.value ?? this._coverPopup.open_name ?? "",
        close_name: field("#cover-popup-close")?.value ?? this._coverPopup.close_name ?? "",
        stop_name: field("#cover-popup-stop")?.value ?? this._coverPopup.stop_name ?? "",
        current_tilt_name: field("#cover-popup-current-tilt")?.value ?? this._coverPopup.current_tilt_name ?? "",
        target_tilt_name: field("#cover-popup-target-tilt")?.value ?? this._coverPopup.target_tilt_name ?? "",
        tilt_open_name: field("#cover-popup-tilt-open")?.value ?? this._coverPopup.tilt_open_name ?? "",
        tilt_close_name: field("#cover-popup-tilt-close")?.value ?? this._coverPopup.tilt_close_name ?? "",
        tilt_stop_name: field("#cover-popup-tilt-stop")?.value ?? this._coverPopup.tilt_stop_name ?? "",
      };
    }
    if (this._vacuumPopup.open) {
      this._vacuumPopup = {
        ...this._vacuumPopup,
        name: field("#vacuum-popup-name")?.value ?? this._vacuumPopup.name ?? "",
        area_id: field("#vacuum-popup-area")?.value ?? this._vacuumPopup.area_id ?? "",
        status_name: field("#vacuum-popup-status")?.value ?? this._vacuumPopup.status_name ?? "",
        battery_level_name: field("#vacuum-popup-battery-level")?.value ?? this._vacuumPopup.battery_level_name ?? "",
        battery_charging_name: field("#vacuum-popup-battery-charging")?.value ?? this._vacuumPopup.battery_charging_name ?? "",
        fan_speed_name: field("#vacuum-popup-fan-speed")?.value ?? this._vacuumPopup.fan_speed_name ?? "",
        start_name: field("#vacuum-popup-start")?.value ?? this._vacuumPopup.start_name ?? "",
        pause_name: field("#vacuum-popup-pause")?.value ?? this._vacuumPopup.pause_name ?? "",
        stop_name: field("#vacuum-popup-stop")?.value ?? this._vacuumPopup.stop_name ?? "",
        return_to_base_name: field("#vacuum-popup-return")?.value ?? this._vacuumPopup.return_to_base_name ?? "",
        locate_name: field("#vacuum-popup-locate")?.value ?? this._vacuumPopup.locate_name ?? "",
        status_map_raw: field("#vacuum-popup-status-map")?.value ?? this._vacuumPopup.status_map_raw ?? "",
        fan_speed_map_raw: field("#vacuum-popup-fan-map")?.value ?? this._vacuumPopup.fan_speed_map_raw ?? "",
      };
    }
    if (this._fanPopup.open) {
      this._fanPopup = {
        ...this._fanPopup,
        name: field("#fan-popup-name")?.value ?? this._fanPopup.name ?? "",
        area_id: field("#fan-popup-area")?.value ?? this._fanPopup.area_id ?? "",
        percentage_step: field("#fan-popup-step")?.value ?? this._fanPopup.percentage_step ?? "1",
        power_name: field("#fan-popup-power")?.value ?? this._fanPopup.power_name ?? "",
        percentage_name: field("#fan-popup-percentage")?.value ?? this._fanPopup.percentage_name ?? "",
        preset_name: field("#fan-popup-preset")?.value ?? this._fanPopup.preset_name ?? "",
        preset_map_raw: field("#fan-popup-preset-map")?.value ?? this._fanPopup.preset_map_raw ?? "",
        oscillate_name: field("#fan-popup-oscillate")?.value ?? this._fanPopup.oscillate_name ?? "",
        direction_name: field("#fan-popup-direction")?.value ?? this._fanPopup.direction_name ?? "",
        direction_map_raw: field("#fan-popup-direction-map")?.value ?? this._fanPopup.direction_map_raw ?? "",
      };
    }
    if (this._humidifierPopup.open) {
      this._humidifierPopup = {
        ...this._humidifierPopup,
        name: field("#humidifier-popup-name")?.value ?? this._humidifierPopup.name ?? "",
        area_id: field("#humidifier-popup-area")?.value ?? this._humidifierPopup.area_id ?? "",
        device_class: field("#humidifier-popup-device-class")?.value ?? this._humidifierPopup.device_class ?? "",
        min_humidity: field("#humidifier-popup-min")?.value ?? this._humidifierPopup.min_humidity ?? "0",
        max_humidity: field("#humidifier-popup-max")?.value ?? this._humidifierPopup.max_humidity ?? "100",
        target_humidity_step: field("#humidifier-popup-step")?.value ?? this._humidifierPopup.target_humidity_step ?? "1",
        current_humidity_name:
          field("#humidifier-popup-current")?.value ?? this._humidifierPopup.current_humidity_name ?? "",
        target_humidity_name:
          field("#humidifier-popup-target")?.value ?? this._humidifierPopup.target_humidity_name ?? "",
        power_name: field("#humidifier-popup-power")?.value ?? this._humidifierPopup.power_name ?? "",
        mode_name: field("#humidifier-popup-mode")?.value ?? this._humidifierPopup.mode_name ?? "",
        mode_map_raw: field("#humidifier-popup-mode-map")?.value ?? this._humidifierPopup.mode_map_raw ?? "",
      };
    }
    if (this._waterHeaterPopup.open) {
      this._waterHeaterPopup = {
        ...this._waterHeaterPopup,
        name: field("#water-heater-popup-name")?.value ?? this._waterHeaterPopup.name ?? "",
        area_id: field("#water-heater-popup-area")?.value ?? this._waterHeaterPopup.area_id ?? "",
        temperature_unit:
          field("#water-heater-popup-temperature-unit")?.value ?? this._waterHeaterPopup.temperature_unit ?? "Â°C",
        suggested_display_precision:
          field("#water-heater-popup-precision")?.value ?? this._waterHeaterPopup.suggested_display_precision ?? "",
        min_temp: field("#water-heater-popup-min")?.value ?? this._waterHeaterPopup.min_temp ?? "30",
        max_temp: field("#water-heater-popup-max")?.value ?? this._waterHeaterPopup.max_temp ?? "90",
        temp_step: field("#water-heater-popup-step")?.value ?? this._waterHeaterPopup.temp_step ?? "0.5",
        current_temperature_name:
          field("#water-heater-popup-current")?.value ?? this._waterHeaterPopup.current_temperature_name ?? "",
        target_temperature_name:
          field("#water-heater-popup-target")?.value ?? this._waterHeaterPopup.target_temperature_name ?? "",
        power_name: field("#water-heater-popup-power")?.value ?? this._waterHeaterPopup.power_name ?? "",
        operation_mode_name:
          field("#water-heater-popup-operation-mode")?.value ?? this._waterHeaterPopup.operation_mode_name ?? "",
        operation_mode_map_raw:
          field("#water-heater-popup-operation-map")?.value ?? this._waterHeaterPopup.operation_mode_map_raw ?? "",
      };
    }
    if (this._lockPopup.open) {
      this._lockPopup = {
        ...this._lockPopup,
        name: field("#lock-popup-name")?.value ?? this._lockPopup.name ?? "",
        area_id: field("#lock-popup-area")?.value ?? this._lockPopup.area_id ?? "",
        state_name: field("#lock-popup-state")?.value ?? this._lockPopup.state_name ?? "",
        lock_name: field("#lock-popup-lock")?.value ?? this._lockPopup.lock_name ?? "",
        unlock_name: field("#lock-popup-unlock")?.value ?? this._lockPopup.unlock_name ?? "",
        open_name: field("#lock-popup-open")?.value ?? this._lockPopup.open_name ?? "",
        state_map_raw: field("#lock-popup-state-map")?.value ?? this._lockPopup.state_map_raw ?? "",
      };
    }
    if (this._valvePopup.open) {
      this._valvePopup = {
        ...this._valvePopup,
        name: field("#valve-popup-name")?.value ?? this._valvePopup.name ?? "",
        area_id: field("#valve-popup-area")?.value ?? this._valvePopup.area_id ?? "",
        device_class: field("#valve-popup-device-class")?.value ?? this._valvePopup.device_class ?? "",
        invert_position: field("#valve-popup-invert")?.checked ?? this._valvePopup.invert_position ?? false,
        current_position_name:
          field("#valve-popup-current-position")?.value ?? this._valvePopup.current_position_name ?? "",
        target_position_name:
          field("#valve-popup-target-position")?.value ?? this._valvePopup.target_position_name ?? "",
        open_name: field("#valve-popup-open")?.value ?? this._valvePopup.open_name ?? "",
        close_name: field("#valve-popup-close")?.value ?? this._valvePopup.close_name ?? "",
        stop_name: field("#valve-popup-stop")?.value ?? this._valvePopup.stop_name ?? "",
      };
    }
    if (this._sirenPopup.open) {
      this._sirenPopup = {
        ...this._sirenPopup,
        name: field("#siren-popup-name")?.value ?? this._sirenPopup.name ?? "",
        area_id: field("#siren-popup-area")?.value ?? this._sirenPopup.area_id ?? "",
        state_name: field("#siren-popup-state")?.value ?? this._sirenPopup.state_name ?? "",
        turn_on_name: field("#siren-popup-turn-on")?.value ?? this._sirenPopup.turn_on_name ?? "",
        turn_off_name: field("#siren-popup-turn-off")?.value ?? this._sirenPopup.turn_off_name ?? "",
        tone_name: field("#siren-popup-tone")?.value ?? this._sirenPopup.tone_name ?? "",
        tone_map_raw: field("#siren-popup-tone-map")?.value ?? this._sirenPopup.tone_map_raw ?? "",
        duration_name: field("#siren-popup-duration")?.value ?? this._sirenPopup.duration_name ?? "",
        volume_name: field("#siren-popup-volume")?.value ?? this._sirenPopup.volume_name ?? "",
        volume_scale: field("#siren-popup-volume-scale")?.value ?? this._sirenPopup.volume_scale ?? "100",
      };
    }
    if (this._schedulerEntityPopup.open) {
      this._schedulerEntityPopup = {
        ...this._schedulerEntityPopup,
        name: field("#scheduler-entity-popup-name")?.value ?? this._schedulerEntityPopup.name ?? "",
        root_name: field("#scheduler-entity-popup-root")?.value ?? this._schedulerEntityPopup.root_name ?? "",
        area_id: field("#scheduler-entity-popup-area")?.value ?? this._schedulerEntityPopup.area_id ?? "",
        suggested_display_precision:
          field("#scheduler-entity-popup-precision")?.value ?? this._schedulerEntityPopup.suggested_display_precision ?? "",
      };
    }
    if (this._schedulerPopup.open && !this._schedulerPopup.loading) {
      const defaultInput = this.shadowRoot.querySelector('[data-item-id="default"][data-field="default_value"]');
      if (defaultInput) {
        this._schedulerPopup.default_value = defaultInput.value;
      }
      const itemValues = {};
      this.shadowRoot.querySelectorAll('[data-action="scheduler-update-item"][data-item-id]').forEach((node) => {
        const itemId = node.dataset.itemId || "";
        const fieldName = node.dataset.field || "";
        if (!itemId || itemId === "default" || !fieldName) {
          return;
        }
        itemValues[itemId] = {
          ...(itemValues[itemId] || {}),
          [fieldName]: node.value,
        };
      });
      this._schedulerPopup.weekly_items = (this._schedulerPopup.weekly_items || []).map((item) => {
        const itemId = `${item.day}-${item.index ?? item.starttime ?? item.minute_of_day}`;
        const captured = itemValues[itemId];
        if (!captured) {
          return item;
        }
        const minuteOfDay = captured.time ? parseTimeToMinuteOfDay(captured.time) : item.minute_of_day;
        return {
          ...item,
          minute_of_day: minuteOfDay === null ? item.minute_of_day : minuteOfDay,
          value: captured.value !== undefined ? captured.value : item.value,
        };
      });
    }
    if (Object.keys(currentTreeDrafts).length) {
      this._treeEntityDrafts[entryKey] = currentTreeDrafts;
    }

    const manualPanel = this.shadowRoot.querySelector("#manual-point-panel");
    if (manualPanel) {
      this._manualPanelOpenByEntry[entryKey] = Boolean(manualPanel.open);
    }
  }

  _setCommunicationMode(mode) {
    const normalizedMode = mode === "webpanel_api" ? "webpanel_api" : "sscp";
    const entryKey = this._entryDraftKey();
    const current = this._configFormState(this._activeEntry);
    this._configDrafts[entryKey] = {
      ...current,
      communication_mode: normalizedMode,
    };
    this._render();
  }

  _renderPageTabs() {
    return `
      <div class="page-tabs">
        <button class="${this._activePage === "studio" ? "secondary is-active" : "secondary"}" data-action="show-studio">Studio</button>
        <button class="${this._activePage === "help" ? "secondary is-active" : "secondary"}" data-action="show-help">Napoveda</button>
      </div>
    `;
  }

  _renderTreeSelectPopup() {
    if (!this._treeSelectPopup.open || !this._treeSelectPopup.variable_name) {
      return "";
    }
    const editing = Boolean(this._treeSelectPopup.variable_entry_key);

    return `
      <div class="modal-backdrop">
        <section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="tree-select-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Enumerated Select</p>
              <h2 id="tree-select-popup-title">${escapeHtml(this._treeSelectPopup.variable_name)}</h2>
              <p class="muted">Nastav mapovani hodnot pro vyberovou entitu. Kazdy radek je ve formatu <code>hodnota=popis</code>, napr. <code>0=Automat</code>.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-tree-select-popup">Zrusit</button>
            </div>
          </div>
          <label class="textarea-field">
            <span>Vyberove hodnoty</span>
            <textarea id="tree-select-popup-options" rows="8" placeholder="0=Automat&#10;1=Off&#10;2=On">${escapeHtml(this._treeSelectPopup.select_options_raw || "")}</textarea>
            <small class="field-help">Podporovane jsou tvoje vlastni ciselne hodnoty i vlastni popisy. Neni to fixne dane jen na 0/1/2.</small>
          </label>
          ${this._treeSelectPopup.error ? `<p class="error">${escapeHtml(this._treeSelectPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-tree-select-popup">Zrusit</button>
            <button data-action="confirm-tree-select-popup">${editing ? "Ulozit zmeny" : "Ulozit a pridat entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderTreeSensorPopup() {
    if (!this._treeSensorPopup.open || !this._treeSensorPopup.variable_name) {
      return "";
    }
    const editing = Boolean(this._treeSensorPopup.variable_entry_key);

    return `
      <div class="modal-backdrop">
        <section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="tree-sensor-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Sensor Setup</p>
              <h2 id="tree-sensor-popup-title">${escapeHtml(this._treeSensorPopup.variable_name)}</h2>
              <p class="muted">Nastav jednotku, HA tridy, presnost zobrazeni a umisteni senzoru.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-tree-sensor-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label>
              <span>Fyzikalni jednotka</span>
              <input id="tree-sensor-popup-unit" list="hass-unit-options" placeholder="ppm, %, °C, kWh" value="${escapeHtml(this._treeSensorPopup.unit_of_measurement || "")}">
              <small class="field-help">Jednotka stavu senzoru. Mas k dispozici i HA napovedu typu <code>ppm</code>, <code>%</code>, <code>°C</code>, <code>kWh</code>.</small>
            </label>
            <label>
              <span>Device class</span>
              <input id="tree-sensor-popup-device-class" list="sensor-device-class-options" placeholder="temperature, humidity, carbon_dioxide" value="${escapeHtml(this._treeSensorPopup.device_class || "")}">
              <small class="field-help">HA device class ovlivnuje interpretaci hodnoty i vhodne zobrazeni.</small>
            </label>
            <label>
              <span>State class</span>
              <select id="tree-sensor-popup-state-class">
                <option value="" ${!this._treeSensorPopup.state_class ? "selected" : ""}>bez state class</option>
                ${SENSOR_STATE_CLASS_OPTIONS.map(
                  (item) =>
                    `<option value="${escapeHtml(item)}" ${
                      item === this._treeSensorPopup.state_class ? "selected" : ""
                    }>${escapeHtml(item)}</option>`,
                ).join("")}
              </select>
              <small class="field-help">Pro statistiky a energie typicky <code>measurement</code>, <code>total</code> nebo <code>total_increasing</code>.</small>
            </label>
            <label>
              <span>Presnost zobrazeni</span>
              <input id="tree-sensor-popup-display-precision" type="number" min="0" step="1" placeholder="0, 1, 2..." value="${escapeHtml(this._treeSensorPopup.suggested_display_precision || "")}">
              <small class="field-help">Doporucena presnost zobrazeni v HA. Prazdne = ponechat na defaultu.</small>
            </label>
            ${this._renderAreaField(
              "tree-sensor-popup-area",
              this._treeSensorPopup.area_id,
              "Oblast v Home Assistantu, pod kterou se ma entita po vytvoreni priradit.",
            )}
          </div>
          ${this._treeSensorPopup.error ? `<p class="error">${escapeHtml(this._treeSensorPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-tree-sensor-popup">Zrusit</button>
            <button data-action="confirm-tree-sensor-popup">${editing ? "Ulozit zmeny" : "Ulozit a pridat entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderTreeNumberPopup() {
    if (!this._treeNumberPopup.open || !this._treeNumberPopup.variable_name) {
      return "";
    }
    const editing = Boolean(this._treeNumberPopup.variable_entry_key);

    return `
      <div class="modal-backdrop">
        <section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="tree-number-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Number Setup</p>
              <h2 id="tree-number-popup-title">${escapeHtml(this._treeNumberPopup.variable_name)}</h2>
              <p class="muted">Nastav rozsah a zpusob ovladani number entity. Muze to byt slider nebo prime zadani hodnoty.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-tree-number-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label>
              <span>Fyzikalni jednotka</span>
              <input id="tree-number-popup-unit" list="hass-unit-options" placeholder="ppm, %, °C, kWh" value="${escapeHtml(this._treeNumberPopup.unit_of_measurement || "")}">
              <small class="field-help">Jednotka hodnoty number entity. Muze byt i <code>ppm</code> nebo jina vlastni jednotka.</small>
            </label>
            <label>
              <span>Device class</span>
              <input id="tree-number-popup-device-class" list="number-device-class-options" placeholder="temperature, power, humidity" value="${escapeHtml(this._treeNumberPopup.device_class || "")}">
              <small class="field-help">HA device class pro vhodne chovani number entity.</small>
            </label>
            <label>
              <span>Presnost zobrazeni</span>
              <input id="tree-number-popup-display-precision" type="number" min="0" step="1" placeholder="0, 1, 2..." value="${escapeHtml(this._treeNumberPopup.suggested_display_precision || "")}">
              <small class="field-help">Doporucena presnost zobrazeni v HA. Prazdne = ponechat na defaultu.</small>
            </label>
            <label><span>Min</span><input id="tree-number-popup-min" type="number" step="any" placeholder="0" value="${escapeHtml(this._treeNumberPopup.min_value || "")}"><small class="field-help">Minimalni hodnota number entity.</small></label>
            <label><span>Max</span><input id="tree-number-popup-max" type="number" step="any" placeholder="100" value="${escapeHtml(this._treeNumberPopup.max_value || "")}"><small class="field-help">Maximalni hodnota number entity.</small></label>
            <label><span>Step</span><input id="tree-number-popup-step" type="number" step="any" placeholder="1" value="${escapeHtml(this._treeNumberPopup.step || "")}"><small class="field-help">Krok zmeny. Kdyz nechces resit detail, nech klidne <code>1</code>.</small></label>
            <label>
              <span>Number mode</span>
              <select id="tree-number-popup-mode">
                <option value="box" ${this._treeNumberPopup.mode === "box" ? "selected" : ""}>box</option>
                <option value="slider" ${this._treeNumberPopup.mode === "slider" ? "selected" : ""}>slider</option>
              </select>
              <small class="field-help"><code>box</code> = prime zadani hodnoty, <code>slider</code> = posuvnik.</small>
            </label>
            ${this._renderAreaField(
              "tree-number-popup-area",
              this._treeNumberPopup.area_id,
              "Oblast v Home Assistantu, pod kterou se ma entita po vytvoreni priradit.",
            )}
          </div>
          ${this._treeNumberPopup.error ? `<p class="error">${escapeHtml(this._treeNumberPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-tree-number-popup">Zrusit</button>
            <button data-action="confirm-tree-number-popup">${editing ? "Ulozit zmeny" : "Ulozit a pridat entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderTreeBasicPopup() {
    if (!this._treeBasicPopup.open || !this._treeBasicPopup.variable_name) {
      return "";
    }

    const editing = Boolean(this._treeBasicPopup.variable_entry_key);
    const entityType = this._treeBasicPopup.entity_type || "switch";
    const titleMap = {
      switch: "Switch Setup",
      button: "Button Setup",
      light: "Light Setup",
      binary_sensor: "Binary Sensor Setup",
      datetime: "Datetime Setup",
    };
    const descriptionMap = {
      switch: "Nastav nazev a area pro zapisovatelnou switch entitu.",
      button: "Nastav nazev, area a delku impulsu pro button entitu.",
      light: "Nastav nazev a area pro jednoduche 1:1 light ovladani.",
      binary_sensor: "Nastav nazev a area pro binary sensor entitu.",
      datetime: "Nastav nazev a area pro datetime entitu.",
    };

    return `
      <div class="modal-backdrop">
        <section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="tree-basic-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">${escapeHtml(entityType)}</p>
              <h2 id="tree-basic-popup-title">${escapeHtml(titleMap[entityType] || "Entity Setup")}</h2>
              <p class="muted">${escapeHtml(descriptionMap[entityType] || "Nastav nazev a umisteni entity.")}</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-tree-basic-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label>
              <span>Nazev entity</span>
              <input id="tree-basic-popup-display-name" placeholder="Volitelny vlastni nazev" value="${escapeHtml(this._treeBasicPopup.display_name || "")}">
              <small class="field-help">Kdyz nechas prazdne, pouzije se nazev datoveho bodu z VListu.</small>
            </label>
            ${this._renderAreaField(
              "tree-basic-popup-area",
              this._treeBasicPopup.area_id,
              "Oblast v Home Assistantu, pod kterou se ma entita po vytvoreni nebo uprave priradit.",
            )}
            ${
              entityType === "button"
                ? `
                  <label>
                    <span>Button press s</span>
                    <input id="tree-basic-popup-press-time" type="number" min="0.01" step="0.01" placeholder="0.10" value="${escapeHtml(this._treeBasicPopup.press_time || "")}">
                    <small class="field-help">Jak dlouho zustane button po stisku v aktivnim stavu. Prazdne = default 0.1 s.</small>
                  </label>
                `
                : ""
            }
          </div>
          ${this._treeBasicPopup.error ? `<p class="error">${escapeHtml(this._treeBasicPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-tree-basic-popup">Zrusit</button>
            <button data-action="confirm-tree-basic-popup">${editing ? "Ulozit zmeny" : "Ulozit a pridat entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderComposerVariablePickerLeaf(item, depth) {
    const variableName = item.name_vlist || item.name;
    return `
      <div class="tree-node">
        <div class="tree-row tree-picker-row" style="--tree-depth:${depth}">
          <span class="tree-indent-spacer"></span>
          <div class="tree-leaf-btn">
            <span class="tree-name">${escapeHtml(variableName)}</span>
            <span class="tree-meta">${escapeHtml(item.type)} | UID ${escapeHtml(item.uid)} | offset ${escapeHtml(item.offset)} | len ${escapeHtml(item.length)}</span>
          </div>
          <button class="secondary tree-add-btn" data-action="select-composer-variable" data-variable="${escapeHtml(variableName)}">Vybrat</button>
        </div>
      </div>
    `;
  }

  _renderComposerVariablePickerFolder(folder, depth) {
    const path = folder.path || [];
    const pathKey = this._pathKey(path);
    const expanded = this._composerVariablePicker.expandedPaths.has(pathKey);
    const loading = this._composerVariablePicker.loadingPaths.has(pathKey);

    return `
      <div class="tree-node">
        <div class="tree-row tree-folder-row" style="--tree-depth:${depth}">
          <button class="tree-toggle" data-action="toggle-composer-variable-folder" data-path="${escapeHtml(pathKey)}">
            ${expanded ? "-" : "+"}
          </button>
          <button class="tree-folder-label" data-action="toggle-composer-variable-folder" data-path="${escapeHtml(pathKey)}">
            <span class="tree-name">${escapeHtml(folder.name)}</span>
            <span class="tree-meta">${loading ? "Nacitam..." : "struktura"}</span>
          </button>
        </div>
        ${
          expanded
            ? `
              <div class="tree-children">
                ${
                  loading && !this._composerVariablePicker.treeCache[pathKey]
                    ? "<p class='muted tree-status'>Nacitam obsah...</p>"
                    : this._renderComposerVariablePickerBranch(path, depth + 1)
                }
              </div>
            `
            : ""
        }
      </div>
    `;
  }

  _renderComposerVariablePickerBranch(path, depth) {
    const pathKey = this._pathKey(path);
    const node = this._composerVariablePicker.treeCache[pathKey];

    if (!node) {
      return "<p class='muted tree-status'>Obsah zatim neni nacteny.</p>";
    }

    const foldersHtml = (node.folders || [])
      .map((folder) => this._renderComposerVariablePickerFolder(folder, depth))
      .join("");

    const variablesHtml = (node.variables || [])
      .map((item) => this._renderComposerVariablePickerLeaf(item, depth))
      .join("");

    const noteHtml = node.truncated
      ? "<p class='muted tree-note'>Vysledek je zkraceny. Pouzij filtr pro uzsi vyber.</p>"
      : "";

    return foldersHtml || variablesHtml || noteHtml
      ? `${foldersHtml}${variablesHtml}${noteHtml}`
      : "<p class='muted tree-status'>V teto vetvi nejsou zadne datove body.</p>";
  }

  _renderComposerVariablePicker() {
    if (!this._composerVariablePicker.open) {
      return "";
    }

    const entry = this._activeEntry;
    const rootExpanded = this._composerVariablePicker.expandedPaths.has(ROOT_PATH_KEY);
    const rootLoading = this._composerVariablePicker.loadingPaths.has(ROOT_PATH_KEY);
    const rootNode = this._composerVariablePicker.treeCache[ROOT_PATH_KEY];
    const matchCount = rootNode?.total_matches ?? entry?.vlist_summary?.total_variables ?? 0;
    const currentValue = this._composerPopupFieldValue(
      this._composerVariablePicker.popup_key,
      this._composerVariablePicker.field_key,
    );

    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-xl" role="dialog" aria-modal="true" aria-labelledby="composer-variable-picker-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">VList Picker</p>
              <h2 id="composer-variable-picker-title">Vybrat datovy bod</h2>
              <p class="muted">Pole <strong>${escapeHtml(this._composerVariablePicker.field_label || "Datovy bod")}</strong>. Kliknuti na <code>Vybrat</code> doplni nazev bodu zpet do formularoveho pole.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-composer-variable-picker">Zrusit</button>
            </div>
          </div>
          ${
            entry?.vlist_summary?.file
              ? `
                <div class="tree-summary">
                  <span>Soubor: <strong>${escapeHtml(entry.vlist_summary.file_name || "VList")}</strong></span>
                  <span>Shod: <strong>${escapeHtml(matchCount)}</strong></span>
                  <span>Aktualne: <strong>${escapeHtml(currentValue || "-")}</strong></span>
                </div>
                <div class="tools">
                  <input id="composer-variable-filter" placeholder="Filtr struktury nebo bodu" value="${escapeHtml(this._composerVariablePicker.filter_text || "")}">
                  <button class="secondary" data-action="apply-composer-variable-filter">Filtrovat</button>
                </div>
                <p class="field-help top-gap">Pouzij strom stejne jako v hlavnim exploreru. Vetve rozbalis pres + a u pozadovane promenne kliknes na <code>Vybrat</code>.</p>
                <div class="tree-shell composer-picker-tree-shell">
                  <div class="tree-row tree-root-row" style="--tree-depth:0">
                    <button class="tree-toggle" data-action="toggle-composer-variable-folder" data-path="">
                      ${rootExpanded ? "-" : "+"}
                    </button>
                    <button class="tree-root-label" data-action="toggle-composer-variable-folder" data-path="">
                      <span class="tree-name">${escapeHtml(entry.vlist_summary.file_name || "VList")}</span>
                      <span class="tree-meta">${rootLoading ? "Nacitam..." : "root"}</span>
                    </button>
                  </div>
                  ${
                    rootExpanded
                      ? `
                        <div class="tree-children root-children">
                          ${
                            rootLoading && !rootNode
                              ? "<p class='muted tree-status'>Nacitam koren stromu...</p>"
                              : this._renderComposerVariablePickerBranch([], 1)
                          }
                        </div>
                      `
                      : ""
                  }
                </div>
              `
              : "<p class='muted'>Bez aktivniho VListu neni stromovy vyber k dispozici. Point muzes zatim zadat rucne.</p>"
          }
          ${this._composerVariablePicker.error ? `<p class="error top-gap">${escapeHtml(this._composerVariablePicker.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-composer-variable-picker">Zavrit</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderVlistVariableDatalist(entry) {
    const options = this._variableOptions(entry);
    if (!options.length) {
      return "";
    }
    return `
      <datalist id="composer-variable-options">
        ${options
          .map(
            (item) =>
              `<option value="${escapeHtml(item.name_vlist || item.name)}" label="${escapeHtml(
                `${item.type} | UID ${item.uid}`,
              )}"></option>`,
          )
          .join("")}
      </datalist>
    `;
  }

  _renderClimateCards(entry) {
    const climates = entry?.climate_entities || [];
    if (!climates.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna climate entita.</p>";
    }

    return climates
      .map(
        (item) => `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">target ${escapeHtml(item.target_temperature_name || "-")} | current ${escapeHtml(item.current_temperature_name || "-")}</p>
              <p class="muted">power ${escapeHtml(item.power_name || "-")} | hvac ${escapeHtml(item.hvac_mode_name || "-")} | preset ${escapeHtml(item.preset_name || "-")}</p>
              <p class="muted">unit ${escapeHtml(formatUnitLabel(item.temperature_unit || "°C"))} | area ${escapeHtml(this._areaName(item.area_id) || "-")}</p>
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-climate-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-climate-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `,
      )
      .join("");
  }

  _renderClimateComposer(entry) {
    const climateCount = (entry?.climate_entities || []).length;
    const loadingVariables = Boolean(this._vlistVariableLoading[this._entryDraftKey(entry)]);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Climate Composer</p>
            <h2>${escapeHtml(String(climateCount))} climate ${climateCount === 1 ? "entity" : "entit"}</h2>
            <p class="muted">Poskladej climate z vice PLC bodu podobne jako u Modbus climate. Neni nutne zakladat kazdy vstup jako samostatnou HA entitu.</p>
          </div>
          <div class="tools">
            <button class="secondary" data-action="open-climate-popup" ${!entry?.vlist_summary?.file ? "disabled" : ""}>Nova climate entita</button>
          </div>
        </div>
        <p class="field-help">Doporuceny zaklad: <code>current_temperature</code> + <code>target_temperature</code>. Volitelne muzes doplnit <code>power</code>, <code>hvac mode</code>, <code>preset</code> nebo aktualni vlhkost. ${loadingVariables ? "Nacitam katalog datovych bodu..." : "Promenne se vybiraji primo z VListu."}</p>
        <div class="entity-list">${this._renderClimateCards(entry)}</div>
      </section>
    `;
  }

  _renderClimatePopup(entry) {
    if (!this._climatePopup.open) {
      return "";
    }
    const editing = Boolean(this._climatePopup.entity_key);
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-wide" role="dialog" aria-modal="true" aria-labelledby="climate-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Climate Composer</p>
              <h2 id="climate-popup-title">${editing ? "Upravit climate entitu" : "Nova climate entita"}</h2>
              <p class="muted">Sklada se z vice promennych PLC. Minimalne vypln cilovou teplotu, idealne i aktualni teplotu.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-climate-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="climate-popup-name" value="${escapeHtml(this._climatePopup.name)}"><small class="field-help">Nazev climate entity v Home Assistantu.</small></label>
            <label>
              <span>Teplotni jednotka</span>
              <select id="climate-popup-temperature-unit">
                ${CLIMATE_TEMPERATURE_UNITS.map(
                  (item) => `<option value="${escapeHtml(item)}" ${item === this._climatePopup.temperature_unit ? "selected" : ""}>${escapeHtml(item)}</option>`,
                ).join("")}
              </select>
              <small class="field-help">Native temperature unit climate entity.</small>
            </label>
            <label><span>Presnost zobrazeni</span><input id="climate-popup-precision" type="number" min="0" step="1" value="${escapeHtml(this._climatePopup.suggested_display_precision)}"><small class="field-help">0 = cele stupne, 1 = desetiny, 2 = setiny.</small></label>
            <label><span>Min teplota</span><input id="climate-popup-min-temp" type="number" step="0.1" value="${escapeHtml(this._climatePopup.min_temp)}"><small class="field-help">Minimalni nastavitelna teplota climate entity.</small></label>
            <label><span>Max teplota</span><input id="climate-popup-max-temp" type="number" step="0.1" value="${escapeHtml(this._climatePopup.max_temp)}"><small class="field-help">Maximalni nastavitelna teplota climate entity.</small></label>
            <label><span>Krok teploty</span><input id="climate-popup-step" type="number" step="0.1" value="${escapeHtml(this._climatePopup.temp_step)}"><small class="field-help">Krok zmeny cilove teploty v Home Assistantu.</small></label>
            ${this._renderAreaField("climate-popup-area", this._climatePopup.area_id, "Oblast v Home Assistantu, pod kterou se ma climate entita priradit.")}
            ${this._renderVariableInputField(
              "climate-popup-current-temperature",
              "Aktualni teplota",
              this._climatePopup.current_temperature_name,
              "Volitelne, ale pro plnohodnotny climate silne doporucene.",
              "Technology.Room.Temp.Actual",
              { popup_key: "climate", field_key: "current_temperature_name" },
            )}
            ${this._renderVariableInputField(
              "climate-popup-target-temperature",
              "Cilova teplota",
              this._climatePopup.target_temperature_name,
              "Povinne. Na tento bod climate zapisuje novou pozadovanou teplotu.",
              "Technology.Room.Temp.Setpoint",
              { popup_key: "climate", field_key: "target_temperature_name" },
            )}
            ${this._renderVariableInputField(
              "climate-popup-current-humidity",
              "Aktualni vlhkost",
              this._climatePopup.current_humidity_name,
              "Volitelne. Kdyz je k dispozici, climate ji zobrazi v detailu entity.",
              "Technology.Room.Humidity",
              { popup_key: "climate", field_key: "current_humidity_name" },
            )}
            ${this._renderVariableInputField(
              "climate-popup-power",
              "Power point",
              this._climatePopup.power_name,
              "Volitelny on/off bod. Kdyz neni vyplneny HVAC mode, bude se pouzivat pro zapnuto/vypnuto.",
              "Technology.Room.Enable",
              { popup_key: "climate", field_key: "power_name" },
            )}
            ${this._renderVariableInputField(
              "climate-popup-hvac-mode",
              "HVAC mode point",
              this._climatePopup.hvac_mode_name,
              "",
              "Technology.Room.Mode",
              {
                popup_key: "climate",
                field_key: "hvac_mode_name",
                help_html: "Volitelny bod pro rezimy <code>off/heat/cool/auto...</code>.",
              },
            )}
            ${this._renderVariableInputField(
              "climate-popup-preset",
              "Preset point",
              this._climatePopup.preset_name,
              "",
              "Technology.Room.Preset",
              {
                popup_key: "climate",
                field_key: "preset_name",
                help_html: "Volitelny bod pro preset rezimy typu <code>comfort</code>, <code>eco</code>, <code>party</code>.",
              },
            )}
          </div>
          <label class="textarea-field">
            <span>HVAC mode map</span>
            <textarea id="climate-popup-hvac-map" rows="5" placeholder="0=off&#10;1=heat&#10;2=auto">${escapeHtml(this._climatePopup.hvac_mode_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=hvac_mode</code>. Povinne, pokud vyplnis HVAC mode point. Podporovane hodnoty jsou ${escapeHtml(CLIMATE_HVAC_MODE_OPTIONS.join(", "))}.</small>
          </label>
          <label class="textarea-field">
            <span>Preset map</span>
            <textarea id="climate-popup-preset-map" rows="5" placeholder="0=comfort&#10;1=eco">${escapeHtml(this._climatePopup.preset_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=popis presetu</code>. Povinne, pokud vyplnis preset point.</small>
          </label>
          ${this._climatePopup.error ? `<p class="error">${escapeHtml(this._climatePopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-climate-popup">Zrusit</button>
            <button data-action="confirm-climate-popup">${editing ? "Ulozit zmeny" : "Vytvorit climate entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderLightCards(entry) {
    const lights = entry?.light_entities || [];
    if (!lights.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna light composer entita.</p>";
    }

    return lights
      .map((item) => {
        const channels = [
          item.power_name ? `power ${item.power_name}` : "",
          item.brightness_name ? `brightness ${item.brightness_name}` : "",
          item.color_temp_name ? `ct ${item.color_temp_name}` : "",
          item.hs_hue_name && item.hs_saturation_name ? `hs ${item.hs_hue_name} / ${item.hs_saturation_name}` : "",
          item.rgb_red_name && item.rgb_green_name && item.rgb_blue_name
            ? `rgb ${item.rgb_red_name} / ${item.rgb_green_name} / ${item.rgb_blue_name}`
            : "",
          item.white_name ? `white ${item.white_name}` : "",
          item.effect_name ? `effect ${item.effect_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const metadata = [
          item.brightness_scale !== null && item.brightness_scale !== undefined ? `scale ${item.brightness_scale}` : "",
          item.min_mireds !== null && item.min_mireds !== undefined ? `min mireds ${item.min_mireds}` : "",
          item.max_mireds !== null && item.max_mireds !== undefined ? `max mireds ${item.max_mireds}` : "",
          item.suggested_display_precision !== null && item.suggested_display_precision !== undefined && item.suggested_display_precision !== ""
            ? `precision ${item.suggested_display_precision}`
            : "",
          item.area_id ? `area ${this._areaName(item.area_id)}` : "",
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(channels || "Zatim nejsou prirazene zadne pointy.")}</p>
              ${item.effect_name ? `<p class="muted">effect map ${escapeHtml(Object.values(item.effect_map || {}).join(", ") || "-")}</p>` : ""}
              ${metadata ? `<p class="muted">${escapeHtml(metadata)}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-light-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-light-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  _renderLightComposer(entry) {
    const lightCount = (entry?.light_entities || []).length;
    const loadingVariables = Boolean(this._vlistVariableLoading[this._entryDraftKey(entry)]);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Light Composer</p>
            <h2>${escapeHtml(String(lightCount))} light ${lightCount === 1 ? "entity" : "entit"}</h2>
            <p class="muted">Poskladej pokrocile svetlo z vice PLC bodu. Muze obsahovat power, jas, color temperature, HS, RGB, white i effect mapu.</p>
          </div>
          <div class="tools">
            <button class="secondary" data-action="open-light-popup" ${!entry?.vlist_summary?.file ? "disabled" : ""}>Nova light entita</button>
          </div>
        </div>
        <p class="field-help">Minimalne staci <code>power</code> nebo <code>brightness</code>. Pro barevne svetlo dopln HS nebo RGB pointy. ${loadingVariables ? "Nacitam katalog datovych bodu..." : "Promenne vybiras primo z VListu."}</p>
        <div class="entity-list">${this._renderLightCards(entry)}</div>
      </section>
    `;
  }

  _renderLightPopup(entry) {
    if (!this._lightPopup.open) {
      return "";
    }
    const editing = Boolean(this._lightPopup.entity_key);
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-wide" role="dialog" aria-modal="true" aria-labelledby="light-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Light Composer</p>
              <h2 id="light-popup-title">${editing ? "Upravit light entitu" : "Nova light entita"}</h2>
              <p class="muted">Sloz jednu Home Assistant light entitu z vice PLC bodu. Vhodne pro dimmer, CCT i RGB svetla.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-light-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="light-popup-name" value="${escapeHtml(this._lightPopup.name)}"><small class="field-help">Nazev light entity v Home Assistantu.</small></label>
            ${this._renderAreaField("light-popup-area", this._lightPopup.area_id, "Oblast v Home Assistantu, pod kterou se ma light entita priradit.")}
            <label><span>Presnost zobrazeni</span><input id="light-popup-precision" type="number" min="0" step="1" value="${escapeHtml(this._lightPopup.suggested_display_precision)}"><small class="field-help">Doporucena presnost pri prevodu hodnot, hlavne u procentnich nebo desetinnnych pointu.</small></label>
            <label><span>Brightness scale</span><input id="light-popup-brightness-scale" type="number" min="1" step="any" value="${escapeHtml(this._lightPopup.brightness_scale)}"><small class="field-help">Maksimum PLC hodnoty jasu. HA si ji prevede na interni rozsah 0-255.</small></label>
            <label><span>Min mireds</span><input id="light-popup-min-mireds" type="number" min="1" step="1" value="${escapeHtml(this._lightPopup.min_mireds)}"><small class="field-help">Nejmensi podporovana hodnota color temperature v mireds.</small></label>
            <label><span>Max mireds</span><input id="light-popup-max-mireds" type="number" min="1" step="1" value="${escapeHtml(this._lightPopup.max_mireds)}"><small class="field-help">Nejvyssi podporovana hodnota color temperature v mireds.</small></label>
            ${this._renderVariableInputField("light-popup-power", "Power point", this._lightPopup.power_name, "Volitelny zapinaci point. Kdyz chybi, svetlo muze byt rizene jen jasem nebo white hodnotou.", "Technology.Room.Point", { popup_key: "light", field_key: "power_name" })}
            ${this._renderVariableInputField("light-popup-brightness", "Brightness point", this._lightPopup.brightness_name, "Point pro jas. Typicky 0-100, 0-255 nebo jiny rozsah definovany v Brightness scale.", "Technology.Room.Point", { popup_key: "light", field_key: "brightness_name" })}
            ${this._renderVariableInputField("light-popup-color-temp", "Color temperature point", this._lightPopup.color_temp_name, "Point pro color temperature. Ocekava se hodnota v mireds.", "Technology.Room.Point", { popup_key: "light", field_key: "color_temp_name" })}
            ${this._renderVariableInputField("light-popup-hue", "HS hue point", this._lightPopup.hs_hue_name, "Point pro hue slozku. Pokud ho vyplnis, pridej i saturation point.", "Technology.Room.Point", { popup_key: "light", field_key: "hs_hue_name" })}
            ${this._renderVariableInputField("light-popup-saturation", "HS saturation point", this._lightPopup.hs_saturation_name, "Point pro saturation slozku. Pouziva se spolu s hue pointem.", "Technology.Room.Point", { popup_key: "light", field_key: "hs_saturation_name" })}
            ${this._renderVariableInputField("light-popup-rgb-red", "RGB red point", this._lightPopup.rgb_red_name, "Cervena slozka RGB. Pro RGB svetlo dopln i green a blue point.", "Technology.Room.Point", { popup_key: "light", field_key: "rgb_red_name" })}
            ${this._renderVariableInputField("light-popup-rgb-green", "RGB green point", this._lightPopup.rgb_green_name, "Zelena slozka RGB.", "Technology.Room.Point", { popup_key: "light", field_key: "rgb_green_name" })}
            ${this._renderVariableInputField("light-popup-rgb-blue", "RGB blue point", this._lightPopup.rgb_blue_name, "Modra slozka RGB.", "Technology.Room.Point", { popup_key: "light", field_key: "rgb_blue_name" })}
            ${this._renderVariableInputField("light-popup-white", "White point", this._lightPopup.white_name, "Samostatny white kanal, pokud ho PLC projekt pouziva.", "Technology.Room.Point", { popup_key: "light", field_key: "white_name" })}
            ${this._renderVariableInputField("light-popup-effect", "Effect point", this._lightPopup.effect_name, "Volitelny point pro efekty. Pokud ho vyplnis, dopln i mapovani efektu.", "Technology.Room.Point", { popup_key: "light", field_key: "effect_name" })}
          </div>
          <label class="textarea-field">
            <span>Effect map</span>
            <textarea id="light-popup-effect-map" rows="5" placeholder="0=Read&#10;1=Relax&#10;2=Party">${escapeHtml(this._lightPopup.effect_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=popis efektu</code>. Povinne jen tehdy, kdyz vyplnis effect point.</small>
          </label>
          ${this._lightPopup.error ? `<p class="error">${escapeHtml(this._lightPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-light-popup">Zrusit</button>
            <button data-action="confirm-light-popup">${editing ? "Ulozit zmeny" : "Vytvorit light entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderCoverCards(entry) {
    const covers = entry?.cover_entities || [];
    if (!covers.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna cover composer entita.</p>";
    }

    return covers
      .map((item) => {
        const positionBits = [
          item.current_position_name ? `current ${item.current_position_name}` : "",
          item.target_position_name ? `target ${item.target_position_name}` : "",
          item.open_name ? `open ${item.open_name}` : "",
          item.close_name ? `close ${item.close_name}` : "",
          item.stop_name ? `stop ${item.stop_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const tiltBits = [
          item.current_tilt_name ? `current tilt ${item.current_tilt_name}` : "",
          item.target_tilt_name ? `target tilt ${item.target_tilt_name}` : "",
          item.tilt_open_name ? `tilt open ${item.tilt_open_name}` : "",
          item.tilt_close_name ? `tilt close ${item.tilt_close_name}` : "",
          item.tilt_stop_name ? `tilt stop ${item.tilt_stop_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const metadata = [
          item.device_class ? `class ${item.device_class}` : "",
          item.invert_position ? "invertovana poloha" : "",
          item.area_id ? `area ${this._areaName(item.area_id)}` : "",
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(positionBits || "Zatim nejsou prirazene hlavni position pointy.")}</p>
              ${tiltBits ? `<p class="muted">${escapeHtml(tiltBits)}</p>` : ""}
              ${metadata ? `<p class="muted">${escapeHtml(metadata)}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-cover-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-cover-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  _renderCoverComposer(entry) {
    const coverCount = (entry?.cover_entities || []).length;
    const loadingVariables = Boolean(this._vlistVariableLoading[this._entryDraftKey(entry)]);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Cover Composer</p>
            <h2>${escapeHtml(String(coverCount))} cover ${coverCount === 1 ? "entity" : "entit"}</h2>
            <p class="muted">Poskladej rolety, zaluzie nebo brany z vice PLC bodu. Umi open/close/stop, position i tilt.</p>
          </div>
          <div class="tools">
            <button class="secondary" data-action="open-cover-popup" ${!entry?.vlist_summary?.file ? "disabled" : ""}>Nova cover entita</button>
          </div>
        </div>
        <p class="field-help">Muzes pouzit bud prikazove pointy <code>open/close</code>, nebo primo <code>target position</code>. ${loadingVariables ? "Nacitam katalog datovych bodu..." : "Promenne vybiras primo z VListu."}</p>
        <div class="entity-list">${this._renderCoverCards(entry)}</div>
      </section>
    `;
  }

  _renderCoverPopup(entry) {
    if (!this._coverPopup.open) {
      return "";
    }
    const editing = Boolean(this._coverPopup.entity_key);
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-wide" role="dialog" aria-modal="true" aria-labelledby="cover-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Cover Composer</p>
              <h2 id="cover-popup-title">${editing ? "Upravit cover entitu" : "Nova cover entita"}</h2>
              <p class="muted">Vhodne pro rolety, zaluzie, okenni pohony, vrata nebo brany. Muze kombinovat prikazove i polohove pointy.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-cover-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="cover-popup-name" value="${escapeHtml(this._coverPopup.name)}"><small class="field-help">Nazev cover entity v Home Assistantu.</small></label>
            ${this._renderAreaField("cover-popup-area", this._coverPopup.area_id, "Oblast v Home Assistantu, pod kterou se ma cover entita priradit.")}
            <label>
              <span>Device class</span>
              <input id="cover-popup-device-class" list="cover-device-class-options" placeholder="blind, shutter, gate, garage" value="${escapeHtml(this._coverPopup.device_class)}">
              <small class="field-help">HA device class kvuli vhodnemu ikonam a chovani cover entity.</small>
            </label>
            <label class="checkbox-field">
              <input id="cover-popup-invert" type="checkbox" ${this._coverPopup.invert_position ? "checked" : ""}>
              <span>Invertovat polohu 0-100</span>
            </label>
            ${this._renderVariableInputField("cover-popup-current-position", "Current position point", this._coverPopup.current_position_name, "Aktualni poloha 0-100. Kdyz chybi, HA muze zit z target position nebo jen prikazu.", "Technology.Room.Point", { popup_key: "cover", field_key: "current_position_name" })}
            ${this._renderVariableInputField("cover-popup-target-position", "Target position point", this._coverPopup.target_position_name, "Cilova poloha 0-100 pro prime nastavovani pozice.", "Technology.Room.Point", { popup_key: "cover", field_key: "target_position_name" })}
            ${this._renderVariableInputField("cover-popup-open", "Open command point", this._coverPopup.open_name, "Povel pro otevreni rolety nebo zakladniho cover pohybu.", "Technology.Room.Point", { popup_key: "cover", field_key: "open_name" })}
            ${this._renderVariableInputField("cover-popup-close", "Close command point", this._coverPopup.close_name, "Povel pro zavreni rolety nebo zakladniho cover pohybu.", "Technology.Room.Point", { popup_key: "cover", field_key: "close_name" })}
            ${this._renderVariableInputField("cover-popup-stop", "Stop command point", this._coverPopup.stop_name, "Volitelny stop point pro zastaveni pohybu.", "Technology.Room.Point", { popup_key: "cover", field_key: "stop_name" })}
            ${this._renderVariableInputField("cover-popup-current-tilt", "Current tilt point", this._coverPopup.current_tilt_name, "Aktualni naklopeni lamel 0-100.", "Technology.Room.Point", { popup_key: "cover", field_key: "current_tilt_name" })}
            ${this._renderVariableInputField("cover-popup-target-tilt", "Target tilt point", this._coverPopup.target_tilt_name, "Cilove naklopeni 0-100.", "Technology.Room.Point", { popup_key: "cover", field_key: "target_tilt_name" })}
            ${this._renderVariableInputField("cover-popup-tilt-open", "Tilt open command point", this._coverPopup.tilt_open_name, "Povel pro otevreni nebo zvednuti naklopeni.", "Technology.Room.Point", { popup_key: "cover", field_key: "tilt_open_name" })}
            ${this._renderVariableInputField("cover-popup-tilt-close", "Tilt close command point", this._coverPopup.tilt_close_name, "Povel pro zavreni nebo sklopeni naklopeni.", "Technology.Room.Point", { popup_key: "cover", field_key: "tilt_close_name" })}
            ${this._renderVariableInputField("cover-popup-tilt-stop", "Tilt stop command point", this._coverPopup.tilt_stop_name, "Volitelny stop point pro naklopeni.", "Technology.Room.Point", { popup_key: "cover", field_key: "tilt_stop_name" })}
          </div>
          ${this._coverPopup.error ? `<p class="error">${escapeHtml(this._coverPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-cover-popup">Zrusit</button>
            <button data-action="confirm-cover-popup">${editing ? "Ulozit zmeny" : "Vytvorit cover entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderVacuumCards(entry) {
    const vacuums = entry?.vacuum_entities || [];
    if (!vacuums.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna vacuum composer entita.</p>";
    }

    return vacuums
      .map((item) => {
        const stateBits = [
          item.status_name ? `status ${item.status_name}` : "",
          item.battery_level_name ? `battery ${item.battery_level_name}` : "",
          item.battery_charging_name ? `charging ${item.battery_charging_name}` : "",
          item.fan_speed_name ? `fan ${item.fan_speed_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const commandBits = [
          item.start_name ? `start ${item.start_name}` : "",
          item.pause_name ? `pause ${item.pause_name}` : "",
          item.stop_name ? `stop ${item.stop_name}` : "",
          item.return_to_base_name ? `return ${item.return_to_base_name}` : "",
          item.locate_name ? `locate ${item.locate_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const metadata = [
          item.status_name ? `status map ${Object.keys(item.status_map || {}).length}` : "",
          item.fan_speed_name ? `fan map ${Object.keys(item.fan_speed_map || {}).length}` : "",
          item.area_id ? `area ${this._areaName(item.area_id)}` : "",
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(stateBits || "Zatim nejsou prirazene stavove pointy.")}</p>
              ${commandBits ? `<p class="muted">${escapeHtml(commandBits)}</p>` : ""}
              ${metadata ? `<p class="muted">${escapeHtml(metadata)}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-vacuum-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-vacuum-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  _renderVacuumComposer(entry) {
    const vacuumCount = (entry?.vacuum_entities || []).length;
    const loadingVariables = Boolean(this._vlistVariableLoading[this._entryDraftKey(entry)]);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Vacuum Composer</p>
            <h2>${escapeHtml(String(vacuumCount))} vacuum ${vacuumCount === 1 ? "entity" : "entit"}</h2>
            <p class="muted">Sloz vysavac nebo specialni servisni stroj z PLC statusu, prikazu, baterie a fan speed map.</p>
          </div>
          <div class="tools">
            <button class="secondary" data-action="open-vacuum-popup" ${!entry?.vlist_summary?.file ? "disabled" : ""}>Nova vacuum entita</button>
          </div>
        </div>
        <p class="field-help">Kdyz vyplnis <code>status point</code>, dopln i mapovani stavovych hodnot. To same plati pro <code>fan speed</code>. ${loadingVariables ? "Nacitam katalog datovych bodu..." : "Promenne vybiras primo z VListu."}</p>
        <div class="entity-list">${this._renderVacuumCards(entry)}</div>
      </section>
    `;
  }

  _renderVacuumPopup(entry) {
    if (!this._vacuumPopup.open) {
      return "";
    }
    const editing = Boolean(this._vacuumPopup.entity_key);
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-wide" role="dialog" aria-modal="true" aria-labelledby="vacuum-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Vacuum Composer</p>
              <h2 id="vacuum-popup-title">${editing ? "Upravit vacuum entitu" : "Nova vacuum entita"}</h2>
              <p class="muted">Kompozitni vacuum entita pro roboticky vysavac nebo jine cistici zarizeni. Umi stav, prikazy, baterii i rychlost.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-vacuum-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="vacuum-popup-name" value="${escapeHtml(this._vacuumPopup.name)}"><small class="field-help">Nazev vacuum entity v Home Assistantu.</small></label>
            ${this._renderAreaField("vacuum-popup-area", this._vacuumPopup.area_id, "Oblast v Home Assistantu, pod kterou se ma vacuum entita priradit.")}
            ${this._renderVariableInputField("vacuum-popup-status", "Status point", this._vacuumPopup.status_name, "Stavovy point. Kdyz ho vyplnis, dopln i mapovani vacuum stavu.", "Technology.Room.Point", { popup_key: "vacuum", field_key: "status_name" })}
            ${this._renderVariableInputField("vacuum-popup-battery-level", "Battery level point", this._vacuumPopup.battery_level_name, "Volitelna uroven baterie v procentech nebo na stupnici 0-100.", "Technology.Room.Point", { popup_key: "vacuum", field_key: "battery_level_name" })}
            ${this._renderVariableInputField("vacuum-popup-battery-charging", "Battery charging point", this._vacuumPopup.battery_charging_name, "Bool point pro informaci, ze je stroj pripojeny k nabijeni.", "Technology.Room.Point", { popup_key: "vacuum", field_key: "battery_charging_name" })}
            ${this._renderVariableInputField("vacuum-popup-fan-speed", "Fan speed point", this._vacuumPopup.fan_speed_name, "Volitelny point pro rychlost vysavani. Kdyz ho vyplnis, dopln i mapovani rychlosti.", "Technology.Room.Point", { popup_key: "vacuum", field_key: "fan_speed_name" })}
            ${this._renderVariableInputField("vacuum-popup-start", "Start command point", this._vacuumPopup.start_name, "Povel ke spusteni uklidu nebo provozu.", "Technology.Room.Point", { popup_key: "vacuum", field_key: "start_name" })}
            ${this._renderVariableInputField("vacuum-popup-pause", "Pause command point", this._vacuumPopup.pause_name, "Volitelny point pro pozastaveni.", "Technology.Room.Point", { popup_key: "vacuum", field_key: "pause_name" })}
            ${this._renderVariableInputField("vacuum-popup-stop", "Stop command point", this._vacuumPopup.stop_name, "Volitelny point pro zastaveni.", "Technology.Room.Point", { popup_key: "vacuum", field_key: "stop_name" })}
            ${this._renderVariableInputField("vacuum-popup-return", "Return to base point", this._vacuumPopup.return_to_base_name, "Volitelny point pro navrat na zakladnu nebo home pozici.", "Technology.Room.Point", { popup_key: "vacuum", field_key: "return_to_base_name" })}
            ${this._renderVariableInputField("vacuum-popup-locate", "Locate command point", this._vacuumPopup.locate_name, "Volitelny point pro lokalizaci zarizeni.", "Technology.Room.Point", { popup_key: "vacuum", field_key: "locate_name" })}
          </div>
          <label class="textarea-field">
            <span>Status map</span>
            <textarea id="vacuum-popup-status-map" rows="5" placeholder="0=docked&#10;1=cleaning&#10;2=returning&#10;3=idle">${escapeHtml(this._vacuumPopup.status_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=stav</code>. Podporovane stavy jsou ${escapeHtml(VACUUM_STATUS_OPTIONS.join(", "))}.</small>
          </label>
          <label class="textarea-field">
            <span>Fan speed map</span>
            <textarea id="vacuum-popup-fan-map" rows="5" placeholder="0=Quiet&#10;1=Standard&#10;2=Turbo">${escapeHtml(this._vacuumPopup.fan_speed_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=popis rychlosti</code>. Pouziva se jen pokud vyplnis fan speed point.</small>
          </label>
          ${this._vacuumPopup.error ? `<p class="error">${escapeHtml(this._vacuumPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-vacuum-popup">Zrusit</button>
            <button data-action="confirm-vacuum-popup">${editing ? "Ulozit zmeny" : "Vytvorit vacuum entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderFanCards(entry) {
    const fans = entry?.fan_entities || [];
    if (!fans.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna fan composer entita.</p>";
    }

    return fans
      .map((item) => {
        const controlBits = [
          item.power_name ? `power ${item.power_name}` : "",
          item.percentage_name ? `percentage ${item.percentage_name}` : "",
          item.preset_name ? `preset ${item.preset_name}` : "",
          item.oscillate_name ? `oscillate ${item.oscillate_name}` : "",
          item.direction_name ? `direction ${item.direction_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const metadata = [
          item.percentage_step !== null && item.percentage_step !== undefined ? `step ${item.percentage_step}%` : "",
          item.preset_name ? `preset map ${Object.keys(item.preset_map || {}).length}` : "",
          item.direction_name ? `direction map ${Object.keys(item.direction_map || {}).length}` : "",
          item.area_id ? `area ${this._areaName(item.area_id)}` : "",
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(controlBits || "Zatim nejsou prirazene ovladaci pointy.")}</p>
              ${metadata ? `<p class="muted">${escapeHtml(metadata)}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-fan-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-fan-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  _renderFanComposer(entry) {
    const fanCount = (entry?.fan_entities || []).length;
    const loadingVariables = Boolean(this._vlistVariableLoading[this._entryDraftKey(entry)]);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Fan Composer</p>
            <h2>${escapeHtml(String(fanCount))} fan ${fanCount === 1 ? "entity" : "entit"}</h2>
            <p class="muted">Poskladej ventilator z power, percentage, preset, direction a oscillate pointu. Hodi se pro VZT, fan-coily i technologicke ventilatory.</p>
          </div>
          <div class="tools">
            <button class="secondary" data-action="open-fan-popup" ${!entry?.vlist_summary?.file ? "disabled" : ""}>Nova fan entita</button>
          </div>
        </div>
        <p class="field-help">Minimalne staci jeden ridici point. Kdyz vyplnis <code>preset</code> nebo <code>direction</code>, dopln i mapovani hodnot. ${loadingVariables ? "Nacitam katalog datovych bodu..." : "Promenne vybiras primo z VListu."}</p>
        <div class="entity-list">${this._renderFanCards(entry)}</div>
      </section>
    `;
  }

  _renderFanPopup(entry) {
    if (!this._fanPopup.open) {
      return "";
    }
    const editing = Boolean(this._fanPopup.entity_key);
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-wide" role="dialog" aria-modal="true" aria-labelledby="fan-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Fan Composer</p>
              <h2 id="fan-popup-title">${editing ? "Upravit fan entitu" : "Nova fan entita"}</h2>
              <p class="muted">Vhodne pro ventilatory s procenty, preset rezimy, smerem otaceni nebo oscilaci. Muze to byt jednoduche i velmi pokrocile skladani.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-fan-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="fan-popup-name" value="${escapeHtml(this._fanPopup.name)}"><small class="field-help">Nazev fan entity v Home Assistantu.</small></label>
            ${this._renderAreaField("fan-popup-area", this._fanPopup.area_id, "Oblast v Home Assistantu, pod kterou se ma fan entita priradit.")}
            <label><span>Percentage step</span><input id="fan-popup-step" type="number" min="1" step="1" value="${escapeHtml(this._fanPopup.percentage_step)}"><small class="field-help">Krok procent v HA UI. Typicky 1, 5 nebo 10.</small></label>
            ${this._renderVariableInputField("fan-popup-power", "Power point", this._fanPopup.power_name, "Bool nebo zapisovatelny point pro zapnuti a vypnuti ventilatoru.", "Technology.Room.Point", { popup_key: "fan", field_key: "power_name" })}
            ${this._renderVariableInputField("fan-popup-percentage", "Percentage point", this._fanPopup.percentage_name, "Point pro rychlost ventilatoru v procentech 0-100.", "Technology.Room.Point", { popup_key: "fan", field_key: "percentage_name" })}
            ${this._renderVariableInputField("fan-popup-preset", "Preset point", this._fanPopup.preset_name, "Volitelny point pro preset rezimy typu auto, low, medium, high.", "Technology.Room.Point", { popup_key: "fan", field_key: "preset_name" })}
            ${this._renderVariableInputField("fan-popup-oscillate", "Oscillate point", this._fanPopup.oscillate_name, "Volitelny bool point pro oscilaci.", "Technology.Room.Point", { popup_key: "fan", field_key: "oscillate_name" })}
            ${this._renderVariableInputField("fan-popup-direction", "Direction point", this._fanPopup.direction_name, "Volitelny point pro smer otaceni ventilatoru.", "Technology.Room.Point", { popup_key: "fan", field_key: "direction_name" })}
          </div>
          <label class="textarea-field">
            <span>Preset map</span>
            <textarea id="fan-popup-preset-map" rows="5" placeholder="0=Auto&#10;1=Low&#10;2=High">${escapeHtml(this._fanPopup.preset_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=popis presetu</code>. Povinne jen kdyz vyplnis preset point.</small>
          </label>
          <label class="textarea-field">
            <span>Direction map</span>
            <textarea id="fan-popup-direction-map" rows="4" placeholder="0=forward&#10;1=reverse">${escapeHtml(this._fanPopup.direction_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=smer</code>. Podporovane smery jsou ${escapeHtml(FAN_DIRECTION_OPTIONS.join(", "))}.</small>
          </label>
          ${this._fanPopup.error ? `<p class="error">${escapeHtml(this._fanPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-fan-popup">Zrusit</button>
            <button data-action="confirm-fan-popup">${editing ? "Ulozit zmeny" : "Vytvorit fan entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderHumidifierCards(entry) {
    const humidifiers = entry?.humidifier_entities || [];
    if (!humidifiers.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna humidifier composer entita.</p>";
    }

    return humidifiers
      .map((item) => {
        const pointBits = [
          item.current_humidity_name ? `current ${item.current_humidity_name}` : "",
          item.target_humidity_name ? `target ${item.target_humidity_name}` : "",
          item.power_name ? `power ${item.power_name}` : "",
          item.mode_name ? `mode ${item.mode_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const metadata = [
          item.device_class ? `class ${item.device_class}` : "",
          item.min_humidity !== null && item.min_humidity !== undefined ? `min ${item.min_humidity}` : "",
          item.max_humidity !== null && item.max_humidity !== undefined ? `max ${item.max_humidity}` : "",
          item.target_humidity_step !== null && item.target_humidity_step !== undefined ? `step ${item.target_humidity_step}` : "",
          item.mode_name ? `mode map ${Object.keys(item.mode_map || {}).length}` : "",
          item.area_id ? `area ${this._areaName(item.area_id)}` : "",
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(pointBits || "Zatim nejsou prirazene pointy pro vlhkost ani ovladani.")}</p>
              ${metadata ? `<p class="muted">${escapeHtml(metadata)}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-humidifier-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-humidifier-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  _renderHumidifierComposer(entry) {
    const humidifierCount = (entry?.humidifier_entities || []).length;
    const loadingVariables = Boolean(this._vlistVariableLoading[this._entryDraftKey(entry)]);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Humidifier Composer</p>
            <h2>${escapeHtml(String(humidifierCount))} humidifier ${humidifierCount === 1 ? "entity" : "entit"}</h2>
            <p class="muted">Sloz humidifier nebo dehumidifier z pointu pro cilovou vlhkost, aktualni vlhkost, power a rezimy.</p>
          </div>
          <div class="tools">
            <button class="secondary" data-action="open-humidifier-popup" ${!entry?.vlist_summary?.file ? "disabled" : ""}>Nova humidifier entita</button>
          </div>
        </div>
        <p class="field-help">Kdyz vyplnis <code>mode point</code>, dopln i mapovani modu. ${loadingVariables ? "Nacitam katalog datovych bodu..." : "Promenne vybiras primo z VListu."}</p>
        <div class="entity-list">${this._renderHumidifierCards(entry)}</div>
      </section>
    `;
  }

  _renderHumidifierPopup(entry) {
    if (!this._humidifierPopup.open) {
      return "";
    }
    const editing = Boolean(this._humidifierPopup.entity_key);
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-wide" role="dialog" aria-modal="true" aria-labelledby="humidifier-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Humidifier Composer</p>
              <h2 id="humidifier-popup-title">${editing ? "Upravit humidifier entitu" : "Nova humidifier entita"}</h2>
              <p class="muted">Vhodne pro zvlhcovace, odvlhcovace a podobne technologie. Umi cilovou vlhkost, aktualni vlhkost, power i mapovane rezimy.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-humidifier-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="humidifier-popup-name" value="${escapeHtml(this._humidifierPopup.name)}"><small class="field-help">Nazev humidifier entity v Home Assistantu.</small></label>
            ${this._renderAreaField("humidifier-popup-area", this._humidifierPopup.area_id, "Oblast v Home Assistantu, pod kterou se ma humidifier entita priradit.")}
            <label>
              <span>Device class</span>
              <input id="humidifier-popup-device-class" list="humidifier-device-class-options" placeholder="humidifier, dehumidifier" value="${escapeHtml(this._humidifierPopup.device_class)}">
              <small class="field-help">Vyber, jestli jde o zvlhcovac nebo odvlhcovac.</small>
            </label>
            <label><span>Min humidity</span><input id="humidifier-popup-min" type="number" step="any" value="${escapeHtml(this._humidifierPopup.min_humidity)}"><small class="field-help">Nejnizsi nastavitelna cilova vlhkost.</small></label>
            <label><span>Max humidity</span><input id="humidifier-popup-max" type="number" step="any" value="${escapeHtml(this._humidifierPopup.max_humidity)}"><small class="field-help">Nejvyssi nastavitelna cilova vlhkost.</small></label>
            <label><span>Target step</span><input id="humidifier-popup-step" type="number" step="any" min="0.1" value="${escapeHtml(this._humidifierPopup.target_humidity_step)}"><small class="field-help">Krok zmeny cilove vlhkosti v HA UI.</small></label>
            ${this._renderVariableInputField("humidifier-popup-current", "Current humidity point", this._humidifierPopup.current_humidity_name, "Volitelny point aktualni vlhkosti.", "Technology.Room.Point", { popup_key: "humidifier", field_key: "current_humidity_name" })}
            ${this._renderVariableInputField("humidifier-popup-target", "Target humidity point", this._humidifierPopup.target_humidity_name, "Point pro nastaveni cilove vlhkosti.", "Technology.Room.Point", { popup_key: "humidifier", field_key: "target_humidity_name" })}
            ${this._renderVariableInputField("humidifier-popup-power", "Power point", this._humidifierPopup.power_name, "Point pro zapnuti a vypnuti zarizeni.", "Technology.Room.Point", { popup_key: "humidifier", field_key: "power_name" })}
            ${this._renderVariableInputField("humidifier-popup-mode", "Mode point", this._humidifierPopup.mode_name, "Volitelny point pro prepinani rezimu zarizeni.", "Technology.Room.Point", { popup_key: "humidifier", field_key: "mode_name" })}
          </div>
          <label class="textarea-field">
            <span>Mode map</span>
            <textarea id="humidifier-popup-mode-map" rows="5" placeholder="0=auto&#10;1=manual&#10;2=boost">${escapeHtml(this._humidifierPopup.mode_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=popis modu</code>. Povinne jen kdyz vyplnis mode point.</small>
          </label>
          ${this._humidifierPopup.error ? `<p class="error">${escapeHtml(this._humidifierPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-humidifier-popup">Zrusit</button>
            <button data-action="confirm-humidifier-popup">${editing ? "Ulozit zmeny" : "Vytvorit humidifier entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderWaterHeaterCards(entry) {
    const waterHeaters = entry?.water_heater_entities || [];
    if (!waterHeaters.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna water heater composer entita.</p>";
    }

    return waterHeaters
      .map((item) => {
        const pointBits = [
          item.current_temperature_name ? `current ${item.current_temperature_name}` : "",
          item.target_temperature_name ? `target ${item.target_temperature_name}` : "",
          item.power_name ? `power ${item.power_name}` : "",
          item.operation_mode_name ? `mode ${item.operation_mode_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const metadata = [
          item.temperature_unit ? `unit ${formatUnitLabel(item.temperature_unit)}` : "",
          item.min_temp !== null && item.min_temp !== undefined ? `min ${item.min_temp}` : "",
          item.max_temp !== null && item.max_temp !== undefined ? `max ${item.max_temp}` : "",
          item.temp_step !== null && item.temp_step !== undefined ? `step ${item.temp_step}` : "",
          item.suggested_display_precision !== null && item.suggested_display_precision !== undefined && item.suggested_display_precision !== ""
            ? `precision ${item.suggested_display_precision}`
            : "",
          item.operation_mode_name ? `mode map ${Object.keys(item.operation_mode_map || {}).length}` : "",
          item.area_id ? `area ${this._areaName(item.area_id)}` : "",
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(pointBits || "Zatim nejsou prirazene teplotni ani ridici pointy.")}</p>
              ${metadata ? `<p class="muted">${escapeHtml(metadata)}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-water-heater-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-water-heater-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  _renderWaterHeaterComposer(entry) {
    const entityCount = (entry?.water_heater_entities || []).length;
    const loadingVariables = Boolean(this._vlistVariableLoading[this._entryDraftKey(entry)]);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Water Heater Composer</p>
            <h2>${escapeHtml(String(entityCount))} water heater ${entityCount === 1 ? "entity" : "entit"}</h2>
            <p class="muted">Sloz zasobnik, boiler nebo ohrivac z aktualni a cilove teploty, power pointu a operation modu.</p>
          </div>
          <div class="tools">
            <button class="secondary" data-action="open-water-heater-popup" ${!entry?.vlist_summary?.file ? "disabled" : ""}>Nova water heater entita</button>
          </div>
        </div>
        <p class="field-help">Kdyz vyplnis <code>operation mode point</code>, dopln i mapovani modu. ${loadingVariables ? "Nacitam katalog datovych bodu..." : "Promenne vybiras primo z VListu."}</p>
        <div class="entity-list">${this._renderWaterHeaterCards(entry)}</div>
      </section>
    `;
  }

  _renderWaterHeaterPopup(entry) {
    if (!this._waterHeaterPopup.open) {
      return "";
    }
    const editing = Boolean(this._waterHeaterPopup.entity_key);
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-wide" role="dialog" aria-modal="true" aria-labelledby="water-heater-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Water Heater Composer</p>
              <h2 id="water-heater-popup-title">${editing ? "Upravit water heater entitu" : "Nova water heater entita"}</h2>
              <p class="muted">Vhodne pro zasobniky, boilery a ohrivace. Umi cilovou teplotu, aktualni teplotu, power i operation mode mapu.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-water-heater-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="water-heater-popup-name" value="${escapeHtml(this._waterHeaterPopup.name)}"><small class="field-help">Nazev water heater entity v Home Assistantu.</small></label>
            ${this._renderAreaField("water-heater-popup-area", this._waterHeaterPopup.area_id, "Oblast v Home Assistantu, pod kterou se ma water heater entita priradit.")}
            <label>
              <span>Temperature unit</span>
              <select id="water-heater-popup-temperature-unit">
                ${CLIMATE_TEMPERATURE_UNITS.map(
                  (item) =>
                    `<option value="${escapeHtml(item)}" ${
                      item === this._waterHeaterPopup.temperature_unit ? "selected" : ""
                    }>${escapeHtml(item)}</option>`,
                ).join("")}
              </select>
              <small class="field-help">Jednotka cilove a aktualni teploty v HA.</small>
            </label>
            <label><span>Presnost zobrazeni</span><input id="water-heater-popup-precision" type="number" min="0" step="1" value="${escapeHtml(this._waterHeaterPopup.suggested_display_precision)}"><small class="field-help">Doporucena presnost zobrazeni teploty v HA.</small></label>
            <label><span>Min temp</span><input id="water-heater-popup-min" type="number" step="any" value="${escapeHtml(this._waterHeaterPopup.min_temp)}"><small class="field-help">Nejnizsi nastavitelna cilova teplota.</small></label>
            <label><span>Max temp</span><input id="water-heater-popup-max" type="number" step="any" value="${escapeHtml(this._waterHeaterPopup.max_temp)}"><small class="field-help">Nejvyssi nastavitelna cilova teplota.</small></label>
            <label><span>Temp step</span><input id="water-heater-popup-step" type="number" step="any" min="0.1" value="${escapeHtml(this._waterHeaterPopup.temp_step)}"><small class="field-help">Krok zmeny cilove teploty v HA UI.</small></label>
            ${this._renderVariableInputField("water-heater-popup-current", "Current temperature point", this._waterHeaterPopup.current_temperature_name, "Volitelny point aktualni teploty vody.", "Technology.Room.Point", { popup_key: "water_heater", field_key: "current_temperature_name" })}
            ${this._renderVariableInputField("water-heater-popup-target", "Target temperature point", this._waterHeaterPopup.target_temperature_name, "Point pro nastaveni cilove teploty.", "Technology.Room.Point", { popup_key: "water_heater", field_key: "target_temperature_name" })}
            ${this._renderVariableInputField("water-heater-popup-power", "Power point", this._waterHeaterPopup.power_name, "Point pro zapnuti a vypnuti ohrivu.", "Technology.Room.Point", { popup_key: "water_heater", field_key: "power_name" })}
            ${this._renderVariableInputField("water-heater-popup-operation-mode", "Operation mode point", this._waterHeaterPopup.operation_mode_name, "Volitelny point pro rezim ohrivace.", "Technology.Room.Point", { popup_key: "water_heater", field_key: "operation_mode_name" })}
          </div>
          <label class="textarea-field">
            <span>Operation mode map</span>
            <textarea id="water-heater-popup-operation-map" rows="5" placeholder="0=off&#10;1=electric&#10;2=eco">${escapeHtml(this._waterHeaterPopup.operation_mode_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=operation_mode</code>. Podporovane hodnoty jsou ${escapeHtml(WATER_HEATER_OPERATION_OPTIONS.join(", "))}.</small>
          </label>
          ${this._waterHeaterPopup.error ? `<p class="error">${escapeHtml(this._waterHeaterPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-water-heater-popup">Zrusit</button>
            <button data-action="confirm-water-heater-popup">${editing ? "Ulozit zmeny" : "Vytvorit water heater entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderLockCards(entry) {
    const locks = entry?.lock_entities || [];
    if (!locks.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna lock composer entita.</p>";
    }

    return locks
      .map((item) => {
        const pointBits = [
          item.state_name ? `state ${item.state_name}` : "",
          item.lock_name ? `lock ${item.lock_name}` : "",
          item.unlock_name ? `unlock ${item.unlock_name}` : "",
          item.open_name ? `open ${item.open_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const metadata = [
          item.state_name ? `state map ${Object.keys(item.state_map || {}).length}` : "",
          item.area_id ? `area ${this._areaName(item.area_id)}` : "",
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(pointBits || "Zatim nejsou prirazene pointy pro stav ani prikazy zamku.")}</p>
              ${metadata ? `<p class="muted">${escapeHtml(metadata)}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-lock-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-lock-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  _renderLockComposer(entry) {
    const entityCount = (entry?.lock_entities || []).length;
    const loadingVariables = Boolean(this._vlistVariableLoading[this._entryDraftKey(entry)]);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Lock Composer</p>
            <h2>${escapeHtml(String(entityCount))} lock ${entityCount === 1 ? "entity" : "entit"}</h2>
            <p class="muted">Poskladej zamek, dvere nebo pristupovy modul ze stavoveho pointu a prikazu lock, unlock nebo open.</p>
          </div>
          <div class="tools">
            <button class="secondary" data-action="open-lock-popup" ${!entry?.vlist_summary?.file ? "disabled" : ""}>Nova lock entita</button>
          </div>
        </div>
        <p class="field-help">Pro bool stavovy point neni mapovani nutne, pro ciselne nebo enum pointy dopln <code>state map</code>. ${loadingVariables ? "Nacitam katalog datovych bodu..." : "Promenne vybiras primo z VListu."}</p>
        <div class="entity-list">${this._renderLockCards(entry)}</div>
      </section>
    `;
  }

  _renderLockPopup(entry) {
    if (!this._lockPopup.open) {
      return "";
    }
    const editing = Boolean(this._lockPopup.entity_key);
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-wide" role="dialog" aria-modal="true" aria-labelledby="lock-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Lock Composer</p>
              <h2 id="lock-popup-title">${editing ? "Upravit lock entitu" : "Nova lock entita"}</h2>
              <p class="muted">Vhodne pro zamky, dvere, elektromagnety a pristupove moduly. Umi cist stav i posilat povely lock/unlock/open.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-lock-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="lock-popup-name" value="${escapeHtml(this._lockPopup.name)}"><small class="field-help">Nazev lock entity v Home Assistantu.</small></label>
            ${this._renderAreaField("lock-popup-area", this._lockPopup.area_id, "Oblast v Home Assistantu, pod kterou se ma lock entita priradit.")}
            ${this._renderVariableInputField("lock-popup-state", "State point", this._lockPopup.state_name, "Volitelny stavovy point zamku. Pro bool point muze zustat bez mapovani.", "Technology.Room.Point", { popup_key: "lock", field_key: "state_name" })}
            ${this._renderVariableInputField("lock-popup-lock", "Lock command point", this._lockPopup.lock_name, "Povel pro zamceni.", "Technology.Room.Point", { popup_key: "lock", field_key: "lock_name" })}
            ${this._renderVariableInputField("lock-popup-unlock", "Unlock command point", this._lockPopup.unlock_name, "Povel pro odemceni.", "Technology.Room.Point", { popup_key: "lock", field_key: "unlock_name" })}
            ${this._renderVariableInputField("lock-popup-open", "Open command point", this._lockPopup.open_name, "Volitelny povel pro otevreni dveri nebo strelky.", "Technology.Room.Point", { popup_key: "lock", field_key: "open_name" })}
          </div>
          <label class="textarea-field">
            <span>State map</span>
            <textarea id="lock-popup-state-map" rows="5" placeholder="0=locked&#10;1=unlocked&#10;2=opening">${escapeHtml(this._lockPopup.state_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=stav</code>. Podporovane stavy jsou ${escapeHtml(LOCK_STATE_OPTIONS.join(", "))}.</small>
          </label>
          ${this._lockPopup.error ? `<p class="error">${escapeHtml(this._lockPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-lock-popup">Zrusit</button>
            <button data-action="confirm-lock-popup">${editing ? "Ulozit zmeny" : "Vytvorit lock entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderValveCards(entry) {
    const valves = entry?.valve_entities || [];
    if (!valves.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna valve composer entita.</p>";
    }

    return valves
      .map((item) => {
        const pointBits = [
          item.current_position_name ? `current ${item.current_position_name}` : "",
          item.target_position_name ? `target ${item.target_position_name}` : "",
          item.open_name ? `open ${item.open_name}` : "",
          item.close_name ? `close ${item.close_name}` : "",
          item.stop_name ? `stop ${item.stop_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const metadata = [
          item.device_class ? `class ${item.device_class}` : "",
          item.invert_position ? "invertovana poloha" : "",
          item.area_id ? `area ${this._areaName(item.area_id)}` : "",
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(pointBits || "Zatim nejsou prirazene pointy pro polohu ani prikazy ventilu.")}</p>
              ${metadata ? `<p class="muted">${escapeHtml(metadata)}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-valve-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-valve-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  _renderValveComposer(entry) {
    const valveCount = (entry?.valve_entities || []).length;
    const loadingVariables = Boolean(this._vlistVariableLoading[this._entryDraftKey(entry)]);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Valve Composer</p>
            <h2>${escapeHtml(String(valveCount))} valve ${valveCount === 1 ? "entity" : "entit"}</h2>
            <p class="muted">Sloz ventil nebo technologickou klapku z pointu pro polohu, open/close/stop a pripadne target position.</p>
          </div>
          <div class="tools">
            <button class="secondary" data-action="open-valve-popup" ${!entry?.vlist_summary?.file ? "disabled" : ""}>Nova valve entita</button>
          </div>
        </div>
        <p class="field-help">Muzes pouzit jak prikazove pointy, tak prime nastavovani procent polohy. ${loadingVariables ? "Nacitam katalog datovych bodu..." : "Promenne vybiras primo z VListu."}</p>
        <div class="entity-list">${this._renderValveCards(entry)}</div>
      </section>
    `;
  }

  _renderValvePopup(entry) {
    if (!this._valvePopup.open) {
      return "";
    }
    const editing = Boolean(this._valvePopup.entity_key);
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-wide" role="dialog" aria-modal="true" aria-labelledby="valve-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Valve Composer</p>
              <h2 id="valve-popup-title">${editing ? "Upravit valve entitu" : "Nova valve entita"}</h2>
              <p class="muted">Vhodne pro ventily, klapky a podobne pohony. Umi open/close/stop i prime nastavovani polohy.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-valve-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="valve-popup-name" value="${escapeHtml(this._valvePopup.name)}"><small class="field-help">Nazev valve entity v Home Assistantu.</small></label>
            ${this._renderAreaField("valve-popup-area", this._valvePopup.area_id, "Oblast v Home Assistantu, pod kterou se ma valve entita priradit.")}
            <label>
              <span>Device class</span>
              <input id="valve-popup-device-class" list="valve-device-class-options" placeholder="water, gas" value="${escapeHtml(this._valvePopup.device_class)}">
              <small class="field-help">HA device class kvuli vhodnemu zobrazeni ventilu.</small>
            </label>
            <label class="checkbox-field">
              <input id="valve-popup-invert" type="checkbox" ${this._valvePopup.invert_position ? "checked" : ""}>
              <span>Invertovat polohu 0-100</span>
            </label>
            ${this._renderVariableInputField("valve-popup-current-position", "Current position point", this._valvePopup.current_position_name, "Aktualni poloha ventilu v procentech.", "Technology.Room.Point", { popup_key: "valve", field_key: "current_position_name" })}
            ${this._renderVariableInputField("valve-popup-target-position", "Target position point", this._valvePopup.target_position_name, "Cilova poloha ventilu v procentech.", "Technology.Room.Point", { popup_key: "valve", field_key: "target_position_name" })}
            ${this._renderVariableInputField("valve-popup-open", "Open command point", this._valvePopup.open_name, "Povel pro otevreni ventilu.", "Technology.Room.Point", { popup_key: "valve", field_key: "open_name" })}
            ${this._renderVariableInputField("valve-popup-close", "Close command point", this._valvePopup.close_name, "Povel pro zavreni ventilu.", "Technology.Room.Point", { popup_key: "valve", field_key: "close_name" })}
            ${this._renderVariableInputField("valve-popup-stop", "Stop command point", this._valvePopup.stop_name, "Volitelny point pro zastaveni pohybu.", "Technology.Room.Point", { popup_key: "valve", field_key: "stop_name" })}
          </div>
          ${this._valvePopup.error ? `<p class="error">${escapeHtml(this._valvePopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-valve-popup">Zrusit</button>
            <button data-action="confirm-valve-popup">${editing ? "Ulozit zmeny" : "Vytvorit valve entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderSirenCards(entry) {
    const sirens = entry?.siren_entities || [];
    if (!sirens.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna siren composer entita.</p>";
    }

    return sirens
      .map((item) => {
        const pointBits = [
          item.state_name ? `state ${item.state_name}` : "",
          item.turn_on_name ? `on ${item.turn_on_name}` : "",
          item.turn_off_name ? `off ${item.turn_off_name}` : "",
          item.tone_name ? `tone ${item.tone_name}` : "",
          item.duration_name ? `duration ${item.duration_name}` : "",
          item.volume_name ? `volume ${item.volume_name}` : "",
        ]
          .filter(Boolean)
          .join(" | ");
        const metadata = [
          item.tone_name ? `tone map ${Object.keys(item.tone_map || {}).length}` : "",
          item.volume_scale !== null && item.volume_scale !== undefined ? `volume scale ${item.volume_scale}` : "",
          item.area_id ? `area ${this._areaName(item.area_id)}` : "",
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(pointBits || "Zatim nejsou prirazene pointy pro sirenu.")}</p>
              ${metadata ? `<p class="muted">${escapeHtml(metadata)}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-siren-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-siren-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  _renderSirenComposer(entry) {
    const sirenCount = (entry?.siren_entities || []).length;
    const loadingVariables = Boolean(this._vlistVariableLoading[this._entryDraftKey(entry)]);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Siren Composer</p>
            <h2>${escapeHtml(String(sirenCount))} siren ${sirenCount === 1 ? "entity" : "entit"}</h2>
            <p class="muted">Sloz sirenu nebo akusticky alarm z pointu pro stav, on/off, ton, delku a hlasitost.</p>
          </div>
          <div class="tools">
            <button class="secondary" data-action="open-siren-popup" ${!entry?.vlist_summary?.file ? "disabled" : ""}>Nova siren entita</button>
          </div>
        </div>
        <p class="field-help">Kdyz vyplnis <code>tone point</code>, dopln i mapovani tonu. Volume scale rika, jake maximum ma PLC hodnota hlasitosti. ${loadingVariables ? "Nacitam katalog datovych bodu..." : "Promenne vybiras primo z VListu."}</p>
        <div class="entity-list">${this._renderSirenCards(entry)}</div>
      </section>
    `;
  }

  _renderSirenPopup(entry) {
    if (!this._sirenPopup.open) {
      return "";
    }
    const editing = Boolean(this._sirenPopup.entity_key);
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-wide" role="dialog" aria-modal="true" aria-labelledby="siren-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Siren Composer</p>
              <h2 id="siren-popup-title">${editing ? "Upravit siren entitu" : "Nova siren entita"}</h2>
              <p class="muted">Vhodne pro sireny, alarmy a akusticke signalizace. Umi ton, delku, hlasitost i samostatne on/off pointy.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-siren-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="siren-popup-name" value="${escapeHtml(this._sirenPopup.name)}"><small class="field-help">Nazev siren entity v Home Assistantu.</small></label>
            ${this._renderAreaField("siren-popup-area", this._sirenPopup.area_id, "Oblast v Home Assistantu, pod kterou se ma siren entita priradit.")}
            <label><span>Volume scale</span><input id="siren-popup-volume-scale" type="number" min="0.1" step="any" value="${escapeHtml(this._sirenPopup.volume_scale)}"><small class="field-help">Maximum PLC hodnoty pro hlasitost. HA pracuje s rozsahem 0.0-1.0.</small></label>
            ${this._renderVariableInputField("siren-popup-state", "State point", this._sirenPopup.state_name, "Volitelny stavovy point sireny.", "Technology.Room.Point", { popup_key: "siren", field_key: "state_name" })}
            ${this._renderVariableInputField("siren-popup-turn-on", "Turn on point", this._sirenPopup.turn_on_name, "Povel pro zapnuti sireny.", "Technology.Room.Point", { popup_key: "siren", field_key: "turn_on_name" })}
            ${this._renderVariableInputField("siren-popup-turn-off", "Turn off point", this._sirenPopup.turn_off_name, "Povel pro vypnuti sireny.", "Technology.Room.Point", { popup_key: "siren", field_key: "turn_off_name" })}
            ${this._renderVariableInputField("siren-popup-tone", "Tone point", this._sirenPopup.tone_name, "Volitelny point pro vyber tonu sireny.", "Technology.Room.Point", { popup_key: "siren", field_key: "tone_name" })}
            ${this._renderVariableInputField("siren-popup-duration", "Duration point", this._sirenPopup.duration_name, "Volitelny point pro delku sireny v sekundach.", "Technology.Room.Point", { popup_key: "siren", field_key: "duration_name" })}
            ${this._renderVariableInputField("siren-popup-volume", "Volume point", this._sirenPopup.volume_name, "Volitelny point pro hlasitost sireny.", "Technology.Room.Point", { popup_key: "siren", field_key: "volume_name" })}
          </div>
          <label class="textarea-field">
            <span>Tone map</span>
            <textarea id="siren-popup-tone-map" rows="5" placeholder="0=Alarm&#10;1=Evacuation&#10;2=Warning">${escapeHtml(this._sirenPopup.tone_map_raw)}</textarea>
            <small class="field-help">Kazdy radek je <code>hodnota=popis tonu</code>. Povinne jen kdyz vyplnis tone point.</small>
          </label>
          ${this._sirenPopup.error ? `<p class="error">${escapeHtml(this._sirenPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-siren-popup">Zrusit</button>
            <button data-action="confirm-siren-popup">${editing ? "Ulozit zmeny" : "Vytvorit siren entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderSchedulerEntityCards(entry) {
    const entities = entry?.scheduler_entities || [];
    if (!entities.length) {
      return "<p class='muted'>Zatim neni vytvorena zadna scheduler entita pro dashboard a automatizace.</p>";
    }

    return entities
      .map((item) => {
        const metadata = [
          item.kind ? `kind ${item.kind}` : "",
          item.point_capacity !== null && item.point_capacity !== undefined ? `body ${item.point_capacity}` : "",
          item.exception_capacity !== null && item.exception_capacity !== undefined ? `exceptions ${item.exception_capacity}` : "",
          item.suggested_display_precision !== null && item.suggested_display_precision !== undefined && item.suggested_display_precision !== ""
            ? `precision ${item.suggested_display_precision}`
            : "",
          item.area_id ? `area ${this._areaName(item.area_id)}` : "",
        ]
          .filter(Boolean)
          .join(" | ");

        return `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(item.root_name || "-")}</p>
              <p class="muted">output ${escapeHtml(item.output_name || "-")} | default ${escapeHtml(item.default_value_name || "-")}</p>
              ${metadata ? `<p class="muted">${escapeHtml(metadata)}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-scheduler-entity" data-key="${escapeHtml(item.entity_key || "")}">Upravit</button>
              <button class="secondary" data-action="delete-scheduler-entity" data-key="${escapeHtml(item.entity_key || "")}">Smazat</button>
            </div>
          </article>
        `;
      })
      .join("");
  }

  _renderSchedulerEntityPopup(entry) {
    if (!this._schedulerEntityPopup.open) {
      return "";
    }

    const editing = Boolean(this._schedulerEntityPopup.entity_key);
    const blocks = entry?.scheduler_blocks || [];
    const selectedRoot = this._schedulerEntityPopup.root_name || "";
    const knownRoots = new Set(blocks.map((item) => item.root_name));
    const selectedBlock = blocks.find((item) => item.root_name === selectedRoot) || null;
    const extraOption =
      selectedRoot && !knownRoots.has(selectedRoot)
        ? `<option value="${escapeHtml(selectedRoot)}">${escapeHtml(selectedRoot)}</option>`
        : "";

    return `
      <div class="modal-backdrop">
        <section class="modal-card" role="dialog" aria-modal="true" aria-labelledby="scheduler-entity-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Scheduler Entity</p>
              <h2 id="scheduler-entity-popup-title">${editing ? "Upravit scheduler entitu" : "Nova scheduler entita"}</h2>
              <p class="muted">Vytvori reprezentacni entitu nad scheduler blokem, aby slo jeho stav jednoduse pouzit v dashboardu, automatizacich a budoucich kartach.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-scheduler-entity-popup">Zrusit</button>
            </div>
          </div>
          <div class="settings-grid modal-grid">
            <label><span>Nazev</span><input id="scheduler-entity-popup-name" value="${escapeHtml(this._schedulerEntityPopup.name)}"><small class="field-help">Nazev scheduler entity v Home Assistantu.</small></label>
            <label>
              <span>Scheduler blok</span>
              <select id="scheduler-entity-popup-root">
                <option value="">Vyber blok</option>
                ${extraOption}
                ${blocks
                  .map(
                    (block) =>
                      `<option value="${escapeHtml(block.root_name)}" ${
                        block.root_name === selectedRoot ? "selected" : ""
                      }>${escapeHtml(block.root_name)} (${escapeHtml(block.kind)})</option>`,
                  )
                  .join("")}
              </select>
              <small class="field-help">Vyber detekovany blok <code>T17/T18/T19</code>, nad kterym se entita vytvori.</small>
            </label>
            <label><span>Presnost zobrazeni</span><input id="scheduler-entity-popup-precision" type="number" min="0" step="1" value="${escapeHtml(this._schedulerEntityPopup.suggested_display_precision)}"><small class="field-help">Hodi se hlavne pro scheduler s real nebo int hodnotami.</small></label>
            ${this._renderAreaField("scheduler-entity-popup-area", this._schedulerEntityPopup.area_id, "Oblast v Home Assistantu, pod kterou se ma scheduler entita priradit.")}
          </div>
          ${
            selectedBlock
              ? `
                <div class="scheduler-summary-card top-gap">
                  <strong>${escapeHtml(selectedBlock.root_name)}</strong>
                  <p>kind ${escapeHtml(selectedBlock.kind)} | body ${escapeHtml(String(selectedBlock.point_capacity))} | exceptions ${escapeHtml(String(selectedBlock.exception_capacity))}</p>
                  <p>output ${escapeHtml(selectedBlock.output_name || "-")} | default ${escapeHtml(selectedBlock.default_value_name || "-")}</p>
                </div>
              `
              : `<p class="field-help top-gap">Po vybrani scheduler bloku se tady zobrazi jeho kapacita a navazane pointy.</p>`
          }
          ${this._schedulerEntityPopup.error ? `<p class="error">${escapeHtml(this._schedulerEntityPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-scheduler-entity-popup">Zrusit</button>
            <button data-action="confirm-scheduler-entity-popup">${editing ? "Ulozit zmeny" : "Vytvorit scheduler entitu"}</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderSchedulerDayColumn(day) {
    const items = this._schedulerDayItems(day);
    const previewSegments = [];
    let lastMinute = 0;
    let lastValue = this._schedulerPopup.default_value;
    items.forEach((item) => {
      previewSegments.push({
        start: lastMinute,
        end: Number(item.minute_of_day) || 0,
        value: lastValue,
      });
      lastMinute = Number(item.minute_of_day) || 0;
      lastValue = item.value;
    });
    previewSegments.push({ start: lastMinute, end: 1440, value: lastValue });

    return `
      <div class="scheduler-day">
        <div class="scheduler-day-head">
          <strong>${escapeHtml(SCHEDULER_DAY_LABELS[day])}</strong>
          <button class="secondary scheduler-small-btn" data-action="scheduler-add-point" data-day="${escapeHtml(day)}">Pridat bod</button>
        </div>
        <div class="scheduler-preview">
          ${previewSegments
            .filter((segment) => segment.end > segment.start)
            .map((segment) => {
              const width = ((segment.end - segment.start) / 1440) * 100;
              const active =
                this._schedulerPopup.kind === "bool"
                  ? String(segment.value) === "1" || segment.value === true
                  : Number(segment.value) !== 0;
              return `<span class="scheduler-preview-segment ${active ? "is-active" : ""}" style="width:${width}%"><span>${escapeHtml(String(segment.value ?? ""))}</span></span>`;
            })
            .join("")}
        </div>
        <div class="scheduler-items">
          ${items.length
            ? items
                .map((item) => {
                  const itemId = `${day}-${item.index ?? item.starttime ?? item.minute_of_day}`;
                  return `
                    <div class="scheduler-item">
                      <input type="time" value="${escapeHtml(formatMinuteOfDay(item.minute_of_day))}" data-action="scheduler-update-item" data-item-id="${escapeHtml(itemId)}" data-field="time">
                      ${this._schedulerValueInput(this._schedulerPopup.kind, "value", this._schedulerItemValue(item), itemId)}
                      <button class="secondary scheduler-small-btn" data-action="scheduler-remove-point" data-item-id="${escapeHtml(itemId)}">Smazat</button>
                    </div>
                  `;
                })
                .join("")
            : "<p class='muted'>Pro tenhle den zatim nejsou definovane zadne zlomy.</p>"}
        </div>
      </div>
    `;
  }

  _renderSchedulerStudio(entry) {
    const blocks = entry?.scheduler_blocks || [];
    const schedulerEntityCount = (entry?.scheduler_entities || []).length;
    const configuredRoots = new Set((entry?.scheduler_entities || []).map((item) => item.root_name));
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Weekly Programs</p>
            <h2>${escapeHtml(String(blocks.length))} detekovanych scheduleru</h2>
            <p class="muted">Detekce je postavena nad bloky <code>T17/T18/T19 Scheduler</code> z Mervis/Domat projektu. Editor upravuje zakladni tydenni body a defaultni hodnotu, a vedle toho muzes vytvaret i scheduler entity pro dashboard a automatizace.</p>
          </div>
        </div>
        <div class="section-head top-gap">
          <div>
            <p class="eyebrow">Scheduler Entities</p>
            <h2>${escapeHtml(String(schedulerEntityCount))} pripravenych scheduler entit</h2>
            <p class="muted">Tyhle entity reprezentuji scheduler bloky v HA. Pozdeji nad nimi pujde postavit i vlastni dashboard karta.</p>
          </div>
        </div>
        <div class="entity-list">${this._renderSchedulerEntityCards(entry)}</div>
        <div class="section-head top-gap">
          <div>
            <p class="eyebrow">Detected Blocks</p>
            <h2>Scheduler bloky z VListu</h2>
            <p class="muted">Ke kazdemu bloku muzes otevrit editor programu a jednim klikem nad nim vytvorit i scheduler entitu.</p>
          </div>
        </div>
        ${blocks.length
          ? `<div class="entity-list">
              ${blocks
                .map(
                  (block) => `
                    <article class="entity-row">
                      <div>
                        <strong>${escapeHtml(block.root_name)}</strong>
                        <p class="muted">kind ${escapeHtml(block.kind)} | body ${escapeHtml(block.point_capacity)} | exceptions ${escapeHtml(block.exception_capacity)}</p>
                        <p class="muted">output ${escapeHtml(block.output_name || "-")} | default ${escapeHtml(block.default_value_name || "-")}</p>
                      </div>
                      <div class="entity-actions">
                        <button class="secondary" data-action="open-scheduler-entity-popup" data-root="${escapeHtml(block.root_name)}">${
                          configuredRoots.has(block.root_name) ? "Vytvorit dalsi entitu" : "Vytvorit entitu"
                        }</button>
                        <button class="secondary" data-action="open-scheduler-popup" data-root="${escapeHtml(block.root_name)}">Upravit program</button>
                      </div>
                    </article>
                  `,
                )
                .join("")}
            </div>`
          : "<p class='muted'>Ve vybranem VListu zatim nebyly nalezeny scheduler bloky. Nahraj nebo vyber VList s tydennimi programy.</p>"}
      </section>
    `;
  }

  _renderSchedulerPopup() {
    if (!this._schedulerPopup.open) {
      return "";
    }
    return `
      <div class="modal-backdrop">
        <section class="modal-card modal-card-xl" role="dialog" aria-modal="true" aria-labelledby="scheduler-popup-title">
          <div class="section-head modal-head">
            <div>
              <p class="eyebrow">Weekly Program Studio</p>
              <h2 id="scheduler-popup-title">${escapeHtml(this._schedulerPopup.root_name || this._schedulerPopup.name)}</h2>
              <p class="muted">Editor uklada tydenni zlomy primo do scheduler bloku v PLC. Pokud mas v bloku i exceptions, ty se jen zobrazi a pri ulozeni zakladniho programu zustavaji zachovane.</p>
            </div>
            <div class="inline-actions">
              <button class="secondary" data-action="close-scheduler-popup">Zrusit</button>
            </div>
          </div>
          ${this._schedulerPopup.loading
            ? "<p class='muted'>Nacitam tydenni program z PLC...</p>"
            : `
                <div class="settings-grid modal-grid">
                  <label>
                    <span>Defaultni hodnota</span>
                    ${this._schedulerValueInput(this._schedulerPopup.kind, "default_value", this._schedulerPopup.default_value, "default")}
                    <small class="field-help">Pouzije se mimo definovane body programu a take jako vychozi hodnota nevyuzitych slotu.</small>
                  </label>
                  <div class="scheduler-summary-card">
                    <strong>Kapacita</strong>
                    <p>${escapeHtml(String(this._schedulerPopup.weekly_items.length))} / ${escapeHtml(String(this._schedulerPopup.point_capacity))} bodu</p>
                    <p>${escapeHtml(String((this._schedulerPopup.exceptions || []).length))} aktivnich exceptions</p>
                  </div>
                </div>
                <div class="scheduler-days">
                  ${SCHEDULER_DAY_LABELS.map((_, day) => this._renderSchedulerDayColumn(day)).join("")}
                </div>
                ${
                  this._schedulerPopup.exceptions?.length
                    ? `<div class="help-section scheduler-exceptions">
                        <h3>Detekovane exceptions</h3>
                        <p>Tyhle vyjimky zustavaji v PLC zachovane. Samostatny editor vyjimek muzu dodelat v dalsim kroku.</p>
                        <div class="entity-list">
                          ${this._schedulerPopup.exceptions
                            .map(
                              (item) => `
                                <article class="feature warning">
                                  <strong>Exception ${escapeHtml(String(item.index))}</strong>
                                  <p>${escapeHtml(String(item.starttime))} - ${escapeHtml(String(item.endtime))} => ${escapeHtml(String(item.value))}</p>
                                </article>
                              `,
                            )
                            .join("")}
                        </div>
                      </div>`
                    : ""
                }
              `}
          ${this._schedulerPopup.error ? `<p class="error">${escapeHtml(this._schedulerPopup.error)}</p>` : ""}
          <div class="inline-actions modal-actions">
            <button class="secondary" data-action="close-scheduler-popup">Zrusit</button>
            <button data-action="save-scheduler-popup" ${this._schedulerPopup.loading ? "disabled" : ""}>Ulozit do PLC</button>
          </div>
        </section>
      </div>
    `;
  }

  _renderPLCControl(entry) {
    const timeState = this._systemTimeFormState(entry);
    return `
      <article class="panel">
        <p class="eyebrow">PLC Control</p>
        <h2>${entry?.supports_plc_time_control ? "System DateTime Setter" : "WebPanel omezeni"}</h2>
        <p class="muted">${
          entry?.supports_plc_time_control
            ? "Podle SSCP dokumentace je k dispozici systemove nastaveni casu PLC. V Home Assistantu se zaroven vytvari systemove datetime entity pro UTC i local time."
            : "Aktualni backend neumi zapis systemoveho casu PLC. Pro tenhle typ ovladani pouzij SSCP protokol."
        }</p>
        <div class="settings-grid">
          <label><span>Time mode</span><select id="plc-time-mode" ${entry?.supports_plc_time_control ? "" : "disabled"}><option value="local" ${timeState.mode === "local" ? "selected" : ""}>local</option><option value="utc" ${timeState.mode === "utc" ? "selected" : ""}>utc</option></select></label>
          <label><span>PLC time</span><input id="plc-time-value" type="datetime-local" value="${escapeHtml(timeState.value)}" ${entry?.supports_plc_time_control ? "" : "disabled"}><small class="field-help">Pri local modu zadavas lokalni cas PLC, pri UTC modu UTC cas. Pro rychle srovnani z Home Assistantu muzes pouzit i tlacitko <code>Sync casu</code> v hlavicce.</small></label>
        </div>
        <div class="inline-actions top-gap">
          <button class="secondary" data-action="set-plc-time" ${entry?.supports_plc_time_control ? "" : "disabled"}>Nastavit PLC cas</button>
        </div>
      </article>
    `;
  }
  _renderEntryCards(entry) {
    const variables = entry.variables || [];
    if (!variables.length) {
      return "<p class='muted'>Zatim neni nakonfigurovana zadna entita.</p>";
    }

    const metadataBits = (item) =>
      [
        item.unit_of_measurement ? `unit ${formatUnitLabel(item.unit_of_measurement)}` : "",
        item.device_class ? `device ${item.device_class}` : "",
        item.state_class ? `state ${item.state_class}` : "",
        item.suggested_display_precision !== null && item.suggested_display_precision !== undefined && item.suggested_display_precision !== ""
          ? `precision ${item.suggested_display_precision}`
          : "",
        item.press_time !== null && item.press_time !== undefined && item.press_time !== ""
          ? `press ${item.press_time}s`
          : "",
        item.area_id ? `area ${this._areaName(item.area_id)}` : "",
      ]
        .filter(Boolean)
        .join(" | ");

    return variables
      .map(
        (item) => `
          <article class="entity-row">
            <div>
              <strong>${escapeHtml(item.name)}</strong>
              <p class="muted">${escapeHtml(item.entity_type)} | ${escapeHtml(item.type)} | UID ${escapeHtml(item.uid)}</p>
              <p class="muted">${escapeHtml(item.name_vlist || "-")}</p>
              ${metadataBits(item) ? `<p class="muted">${escapeHtml(metadataBits(item))}</p>` : ""}
            </div>
            <div class="entity-actions">
              <button class="secondary" data-action="edit-variable" data-key="${escapeHtml(item.key)}">Upravit</button>
              <button class="secondary" data-action="delete-variable" data-key="${escapeHtml(item.key)}">Smazat</button>
            </div>
          </article>
        `,
      )
      .join("");
  }

  _renderConfigLegend(entry) {
    const communicationLabel = entry.communication_mode === "webpanel_api" ? "WebPanel API" : "SSCP";
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Popisky</p>
            <h2>Co ktere pole znamena</h2>
            <p class="muted">Strucna legenda ke konfiguraci aktualniho PLC. Aktivni komunikace je <strong>${escapeHtml(communicationLabel)}</strong>.</p>
          </div>
        </div>
        <div class="guide-grid">
          <article class="guide-card">
            <strong>Komunikace</strong>
            <p>Vyber backend, pres ktery se bude cist a zapisovat. SSCP umi hlubsi diagnostiku a cas. WebPanel API je vhodne pro HTTP pristup.</p>
          </article>
          <article class="guide-card">
            <strong>Host a Port</strong>
            <p>Adresa PLC nebo WebPanelu. U SSCP je to TCP endpoint SSCP serveru, u WebPanel API HTTP nebo HTTPS endpoint panelu.</p>
          </article>
          <article class="guide-card">
            <strong>Username a Password</strong>
            <p>Prihlaseni k PLC nebo WebPanel API. Pokud panel pouziva anonymni pristup, muzou zustat prazdne.</p>
          </article>
          <article class="guide-card">
            <strong>SSCP address</strong>
            <p>Adresa zarizeni na SSCP vrstve, typicky <code>0x01</code>. Pouziva se jen v SSCP rezimu.</p>
          </article>
          <article class="guide-card">
            <strong>WebPanel connection</strong>
            <p>Nazev spojeni z WebPanelu, ze ktereho se sklada identifikator <code>svc://connection/uid[offset,length]</code>. Pouziva se jen ve WebPanel API rezimu.</p>
          </article>
          <article class="guide-card">
            <strong>Polling</strong>
            <p>Jak casto se hromadne ctou hodnoty entit. Kratsi interval = rychlejsi reakce, ale vetsi zatez komunikace.</p>
          </article>
          <article class="guide-card">
            <strong>VList file</strong>
            <p>Zdroj struktury datovych bodu. Z tohoto souboru se plni stromovy explorer i metadata UID, offset, delka a typ.</p>
          </article>
          <article class="guide-card">
            <strong>Diagnostika PLC</strong>
            <p>Automaticke entity sleduji stav spojeni, delku cteni, pocet pollu a v SSCP i runtime, pamet, uptime a proxy stav.</p>
          </article>
          <article class="guide-card">
            <strong>Climate Composer</strong>
            <p>Slozi jednu climate entitu z vice PLC bodu, typicky aktualni teploty, cilove teploty, power pointu a rezimu HVAC.</p>
          </article>
          <article class="guide-card">
            <strong>Light / Cover / Vacuum Composer</strong>
            <p>Slozene entity z vice pointu. Light umi jas, barvu a efekty, cover polohu a tilt, vacuum stavy, prikazy a rychlosti. Vedle toho jsou k dispozici i composery pro fan, humidifier, water heater, lock, valve a siren.</p>
          </article>
          <article class="guide-card">
            <strong>Weekly Programs</strong>
            <p>Detekuje scheduler bloky z VListu a umozni menit tydenni zlomy i defaultni hodnotu primo v PLC.</p>
          </article>
          <article class="guide-card">
            <strong>Scheduler Entity</strong>
            <p>Reprezentacni HA entita nad scheduler blokem. Hodit se bude pro dashboardy, automatizace i budouci specialni kartu editoru.</p>
          </article>
          <article class="guide-card">
            <strong>System DateTime Setter</strong>
            <p>V SSCP rezimu umi integrace nastavovat systemovy cas PLC jak z UI, tak pres automaticky vytvorene datetime entity.</p>
          </article>
        </div>
      </section>
    `;
  }

  _renderHelpPage(entry) {
    const communicationLabel = entry?.communication_mode === "webpanel_api" ? "WebPanel API" : "SSCP";
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">Napoveda</p>
            <h2>Jak SSCP Studio pouzivat</h2>
            <p class="muted">Prakticky navod pro nastaveni PLC, import VList, pridani entit a cteni diagnostiky. Aktivni ukazka je postavena nad rezimem <strong>${escapeHtml(communicationLabel)}</strong>.</p>
          </div>
        </div>
        <div class="help-layout">
          <article class="help-section">
            <h3>1. Rychly start</h3>
            <ol class="help-list">
              <li>Vytvor nove PLC tlacitkem <code>Pridat PLC</code>.</li>
              <li>V sekci <code>PLC Setup</code> vyber komunikaci, dopln host, port a prihlaseni.</li>
              <li>Nahraj nebo vyber <code>VList file</code> a uloz konfiguraci.</li>
              <li>Ve <code>VList Exploreru</code> rozklikni strom pres <code>+</code>, vyber typ entity a tlacitkem <code>Pridat</code> vloz bod do konfigurace. Otevre se popup s doplnujicim nastavenim, minimalne pro nazev a area, a u specialnich typu i s dalsimi volbami.</li>
              <li>V <code>Configured</code> a v diagnostickych entitach over, ze se hodnoty nacitaji.</li>
              <li>V composerech muzes slozit <code>climate</code>, <code>light</code>, <code>fan</code>, <code>cover</code>, <code>valve</code>, <code>humidifier</code>, <code>water heater</code>, <code>lock</code>, <code>siren</code> nebo <code>vacuum</code> z vice bodu a ve <code>Weekly Programs</code> upravit scheduler bloky i vytvaret scheduler entity.</li>
            </ol>
          </article>
          <article class="help-section">
            <h3>2. Komunikacni rezimy</h3>
            <div class="guide-grid">
              <article class="guide-card">
                <strong>SSCP</strong>
                <p>Plny protokol s batch read/write, detailni diagnostikou PLC, informacemi o runtime, pameti a synchronizaci casu.</p>
              </article>
              <article class="guide-card">
                <strong>WebPanel API</strong>
                <p>HTTP pristup pres <code>login.cgi</code>, <code>values.cgi</code> a <code>command.cgi</code>. Je vhodny tam, kde nechces nebo nemuzes pouzit SSCP socket.</p>
              </article>
            </div>
          </article>
          <article class="help-section">
            <h3>3. VList Explorer</h3>
            <p>Explorer funguje jako strom ve Windows. Tlacitko <code>+</code> vetev rozbali, <code>-</code> ji sbali, select vedle bodu urcuje typ entity a tlacitko <code>Pridat</code> vlozi bod do konfigurace. Pro bezne i pokrocile entity se po stisku otevre popup s doplnujicimi parametry, alespon pro nazev a area.</p>
            <p>Filtr prohledava nazvy vetvi i bodu. Kdyz je vysledek moc velky, pomuze zkratit filtr na cast technologie nebo mistnosti.</p>
          </article>
          <article class="help-section">
            <h3>4. Rucni pridani bodu</h3>
            <p>Sekce <code>Manual Point</code> je pro body, ktere nejsou ve VListu. <code>UID</code> je identifikator promenne, <code>Offset</code> je posun uvnitr dat a <code>Length</code> je velikost prenesene hodnoty v bajtech.</p>
            <p><code>PLC typ</code> rika, jak se hodnota koduje. <code>Entita</code> urcuje, jak se bod bude chovat v Home Assistantu.</p>
          </article>
          <article class="help-section">
            <h3>5. Diagnosticke entity</h3>
            <p>Ke kazdemu PLC se vytvari systemove entity. Vzdy uvidis spojeni, backend, delku posledniho cteni, pocty uspesnych a neuspesnych pollu. V SSCP rezimu navic uvidis runtime state, run mode, uptime, pamet a dalsi diagnostiku PLC.</p>
          </article>
          <article class="help-section">
            <h3>6. Climate Composer a PLC control</h3>
            <p><code>Climate Composer</code> sklada jednu climate entitu z vice surovych bodu. Muze pouzivat aktualni a cilovou teplotu, power point, rezim HVAC i presety. Neni nutne nejdriv vytvaret vsechny body jako samostatne entity.</p>
            <p>Karta <code>PLC Control</code> pridava podle SSCP dokumentace i systemove nastaveni casu PLC. V SSCP rezimu se navic na device objevi systemove datetime entity pro local i UTC cas.</p>
          </article>
          <article class="help-section">
            <h3>7. Light, Cover a Vacuum Composer</h3>
            <p><code>Light Composer</code> umi skladat pokrocila svetla vcetne jasu, color temperature, HS, RGB, white a effect map. <code>Cover Composer</code> umi prikazove pointy i prime nastavovani pozice a tiltu.</p>
            <p><code>Vacuum Composer</code> umi statusy, prikazy, baterii i mapovani rychlosti. Vedle nej jsou k dispozici i <code>Fan</code>, <code>Humidifier</code>, <code>Water Heater</code>, <code>Lock</code>, <code>Valve</code> a <code>Siren</code> composery pro dalsi slozene PLC technologie.</p>
          </article>
          <article class="help-section">
            <h3>8. Weekly Programs a scheduler entity</h3>
            <p>Studio tydennich programu detekuje scheduler bloky <code>T17/T18/T19</code> z VListu a umi menit tydenni zlomy i defaultni hodnotu. Pokud scheduler obsahuje vyjimky, editor je zatim zobrazi informativne a pri ulozeni je zachova.</p>
            <p>Nad kazdym blokem muzes vytvorit i samostatnou scheduler entitu, aby slo snadno pracovat s vystupem scheduleru v dashboardu nebo automatizacich.</p>
          </article>
          <article class="help-section">
            <h3>9. Jak cist hlavni karty</h3>
            <div class="guide-grid">
              <article class="guide-card">
                <strong>Connection</strong>
                <p>Jaky backend se pouziva a jake jsou schopnosti spojeni. U SSCP uvidis protocol version a rights group.</p>
              </article>
              <article class="guide-card">
                <strong>Runtime</strong>
                <p>Stav PLC, run mode, uptime a pamet. Kdyz je pole prazdne, backend nebo cilove zarizeni tu informaci neposkytuje.</p>
              </article>
              <article class="guide-card">
                <strong>Clock</strong>
                <p>Cas PLC. V WebPanel API rezimu muze zustat prazdny, protoze tato data nejsou standardne k dispozici.</p>
              </article>
            </div>
          </article>
          <article class="help-section">
            <h3>10. Doporuceny postup pri problemech</h3>
            <ol class="help-list">
              <li>Zkontroluj, ze je vybrany spravny backend a port.</li>
              <li>Over, ze VList odpovida aktualnimu projektu v PLC.</li>
              <li>Spust <code>Obnovit diagnostiku</code> a podivej se na diagnosticke entity.</li>
              <li>U WebPanel API zkontroluj <code>WebPanel connection</code> a dostupnost <code>values.cgi</code>.</li>
              <li>U SSCP zkontroluj <code>SSCP address</code>, prava uzivatele a dosazitelnost socketu.</li>
            </ol>
          </article>
        </div>
      </section>
    `;
  }

  _renderTreeVariable(entry, item, depth, configuredKeys) {
    const variableName = item.name_vlist || item.name;
    const configured = configuredKeys.has(`${variableName}::${item.uid}`);
    const variableState = this._treeVariableState(entry, variableName, item.default_entity_type);
    const selectedEntityType = variableState.entity_type;
    const showEntityConfigHint = !configured;
    let entityConfigHint = "";
    if (selectedEntityType === "select") {
      entityConfigHint = variableState.select_options_raw
        ? "Definice vyberu je pripravena. Tlacitkem Pridat ji otevres a ulozis."
        : "Pro select se po kliknuti na Pridat otevre popup pro definici hodnot.";
    } else if (selectedEntityType === "sensor") {
      entityConfigHint =
        variableState.unit_of_measurement ||
        variableState.device_class ||
        variableState.state_class ||
        variableState.suggested_display_precision ||
        variableState.area_id
          ? "Nastaveni senzoru je pripravene. Tlacitkem Pridat ho otevres a ulozis."
          : "Pro sensor se po kliknuti na Pridat otevre popup pro jednotku, HA tridy, presnost a area.";
    } else if (selectedEntityType === "number") {
      entityConfigHint =
        variableState.unit_of_measurement ||
        variableState.device_class ||
        variableState.suggested_display_precision ||
        variableState.area_id ||
        variableState.min_value ||
        variableState.max_value ||
        variableState.step ||
        variableState.mode !== "box"
          ? "Nastaveni number entity je pripraveno. Tlacitkem Pridat ho otevres a ulozis."
          : "Pro number se po kliknuti na Pridat otevre popup pro rozsah, jednotku, HA tridy a volbu slideru nebo primeho zadani.";
    } else if (["switch", "button", "light", "binary_sensor", "datetime"].includes(selectedEntityType)) {
      entityConfigHint =
        variableState.display_name || variableState.area_id || (selectedEntityType === "button" && variableState.press_time)
          ? "Popup pro nazev a area je pripraveny. Tlacitkem Pridat ho otevres a ulozis."
          : `Pro ${selectedEntityType} se po kliknuti na Pridat otevre popup pro nazev a area.`;
    }

    return `
      <div class="tree-node">
        <div class="tree-row tree-variable-row ${configured ? "is-configured" : ""}" style="--tree-depth:${depth}">
          <span class="tree-indent-spacer"></span>
          <div class="tree-leaf-btn">
            <span class="tree-name">${escapeHtml(variableName)}</span>
            <span class="tree-meta">
              ${escapeHtml(item.type)} | UID ${escapeHtml(item.uid)} | offset ${escapeHtml(item.offset)} | len ${escapeHtml(item.length)}
              ${configured ? " | jiz pridano" : ""}
            </span>
          </div>
          <select class="tree-entity-select" data-tree-variable="${escapeHtml(variableName)}" ${configured ? "disabled" : ""}>
            ${(item.quick_entity_types || item.allowed_entity_types || [])
              .map(
                (entityType) =>
                  `<option value="${escapeHtml(entityType)}" ${
                    entityType === selectedEntityType ? "selected" : ""
                  }>${escapeHtml(entityType)}</option>`,
              )
              .join("")}
          </select>
          <button
            class="secondary tree-add-btn"
            data-action="tree-add-variable"
            data-variable="${escapeHtml(variableName)}"
            ${configured ? "disabled" : ""}
          >
            ${configured ? "Pridano" : "Pridat"}
          </button>
        </div>
        <div class="tree-select-config" data-tree-variable="${escapeHtml(variableName)}" data-configured="${configured ? "1" : "0"}" style="--tree-depth:${depth}" ${showEntityConfigHint && entityConfigHint ? "" : "hidden"}>
          <small class="field-help">${escapeHtml(entityConfigHint)}</small>
        </div>
      </div>
    `;
  }

  _renderTreeFolder(entry, folder, depth, configuredKeys) {
    const path = folder.path || [];
    const pathKey = this._pathKey(path);
    const expanded = this._browser.expandedPaths.has(pathKey);
    const loading = this._browser.loadingPaths.has(pathKey);

    return `
      <div class="tree-node">
        <div class="tree-row tree-folder-row" style="--tree-depth:${depth}">
          <button class="tree-toggle" data-action="toggle-tree-folder" data-path="${escapeHtml(pathKey)}">
            ${expanded ? "-" : "+"}
          </button>
          <button class="tree-folder-label" data-action="toggle-tree-folder" data-path="${escapeHtml(pathKey)}">
            <span class="tree-name">${escapeHtml(folder.name)}</span>
            <span class="tree-meta">${loading ? "Nacitam..." : "struktura"}</span>
          </button>
        </div>
        ${
          expanded
            ? `
              <div class="tree-children">
                ${
                  loading && !this._browser.treeCache[pathKey]
                    ? "<p class='muted tree-status'>Nacitam obsah...</p>"
                    : this._renderTreeBranch(entry, path, depth + 1, configuredKeys)
                }
              </div>
            `
            : ""
        }
      </div>
    `;
  }

  _renderTreeBranch(entry, path, depth, configuredKeys) {
    const pathKey = this._pathKey(path);
    const node = this._browser.treeCache[pathKey];

    if (!node) {
      return "<p class='muted tree-status'>Obsah zatim neni nacteny.</p>";
    }

    const foldersHtml = (node.folders || [])
      .map((folder) => this._renderTreeFolder(entry, folder, depth, configuredKeys))
      .join("");

    const variablesHtml = (node.variables || [])
      .map((item) => this._renderTreeVariable(entry, item, depth, configuredKeys))
      .join("");

    const noteHtml = node.truncated
      ? "<p class='muted tree-note'>Vysledek je zkraceny. Pouzij filtr pro uzsi vyber.</p>"
      : "";

    return foldersHtml || variablesHtml || noteHtml
      ? `${foldersHtml}${variablesHtml}${noteHtml}`
      : "<p class='muted tree-status'>V teto vetvi nejsou zadne datove body.</p>";
  }

  _renderBrowser(entry) {
    const rootExpanded = this._browser.expandedPaths.has(ROOT_PATH_KEY);
    const rootLoading = this._browser.loadingPaths.has(ROOT_PATH_KEY);
    const rootNode = this._browser.treeCache[ROOT_PATH_KEY];
    const configuredKeys = this._configuredVariableKeys(entry);
    const matchCount = rootNode?.total_matches ?? entry.vlist_summary?.total_variables ?? 0;

    if (!entry.vlist_summary?.file) {
      return `
        <section class="panel wide">
          <div class="section-head">
            <div>
              <p class="eyebrow">VList Browser</p>
              <h2>Bez vlistu</h2>
              <p class="muted">Nejdriv vyber nebo nahraj VList v PLC konfiguraci.</p>
            </div>
          </div>
        </section>
      `;
    }

    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">VList Explorer</p>
            <h2>SSCP strom datovych bodu</h2>
            <p class="muted">Vyber typ entity a tlacitkem Pridat vloz datovy bod do konfigurace. Rodicovske vetve rozbalis pres + a sbalis pres -.</p>
          </div>
          <div class="tools">
            <input id="filter-input" placeholder="Filtr struktury nebo bodu" value="${escapeHtml(this._browser.filter_text || "")}">
            <button class="secondary" data-action="apply-filter">Filtrovat</button>
          </div>
        </div>
        <div class="tree-summary">
          <span>Soubor: <strong>${escapeHtml(entry.vlist_summary.file_name || "VList")}</strong></span>
          <span>Shod: <strong>${escapeHtml(matchCount)}</strong></span>
        </div>
        <p class="field-help">Postup: 1. rozbal vetve pres +, 2. u bodu vyber typ entity, 3. klikni na tlacitko <code>Pridat</code>. Pro pokrocile i bezne typy se otevre popup s doplnujicim nastavenim, minimalne pro nazev a area. Strom ma vlastni svisly posuvnik, takze muzes projet cely obsah.</p>
        <div class="tree-shell">
          <div class="tree-row tree-root-row" style="--tree-depth:0">
            <button class="tree-toggle" data-action="toggle-tree-folder" data-path="">
              ${rootExpanded ? "-" : "+"}
            </button>
            <button class="tree-root-label" data-action="toggle-tree-folder" data-path="">
              <span class="tree-name">${escapeHtml(entry.vlist_summary.file_name || "VList")}</span>
              <span class="tree-meta">${rootLoading ? "Nacitam..." : "root"}</span>
            </button>
          </div>
          ${
            rootExpanded
              ? `
                <div class="tree-children root-children">
                  ${
                    rootLoading && !rootNode
                      ? "<p class='muted tree-status'>Nacitam koren stromu...</p>"
                      : this._renderTreeBranch(entry, [], 1, configuredKeys)
                  }
                </div>
              `
              : ""
          }
        </div>
      </section>
    `;
  }
  _renderSettings(entry) {
    const availableVlists = entry.vlist_summary?.available_files || [];
    const communicationModes = entry.supported_communication_modes || ["sscp", "webpanel_api"];
    const config = this._configFormState(entry);
    return `
      <section class="panel wide">
        <div class="section-head">
          <div>
            <p class="eyebrow">PLC Setup</p>
            <h2>${entry.connected ? "Pripojeno" : "Konfigurace pripojeni"}</h2>
            <p class="muted">${
              entry.connection_ready
                ? "Nastaveni muzes kdykoli upravit a znovu ulozit."
                : "Tahle PLC entry je prazdna. Vypln parametry a uloz."
            }</p>
            ${entry.last_error ? `<p class="error">Posledni chyba: ${escapeHtml(entry.last_error)}</p>` : ""}
          </div>
          <div class="tools">
            <button data-action="save-config">Ulozit a reload</button>
          </div>
        </div>
        <div class="settings-grid">
          <div class="mode-cards" role="group" aria-label="Komunikacni backend">
            <button
              type="button"
              class="${config.communication_mode === "sscp" ? "secondary mode-card is-active" : "secondary mode-card"}"
              data-action="set-communication-mode"
              data-mode="sscp"
            >
              <strong>SSCP protokol</strong>
              <span class="mode-meta">Socket komunikace, detailni diagnostika PLC, runtime a sync casu.</span>
            </button>
            <button
              type="button"
              class="${config.communication_mode === "webpanel_api" ? "secondary mode-card is-active" : "secondary mode-card"}"
              data-action="set-communication-mode"
              data-mode="webpanel_api"
            >
              <strong>WebPanel API</strong>
              <span class="mode-meta">HTTP/HTTPS backend pres WebPanel, vhodny kdyz nechces pouzit SSCP socket.</span>
            </button>
          </div>
          <label><span>PLC name</span><input id="cfg-plc-name" value="${escapeHtml(config.plc_name)}"><small class="field-help">Nazev zarizeni v Home Assistantu a v panelu.</small></label>
          <label>
            <span>Komunikace</span>
            <select id="cfg-communication-mode">
              ${communicationModes
                .map(
                  (mode) =>
                    `<option value="${escapeHtml(mode)}" ${
                      mode === config.communication_mode ? "selected" : ""
                    }>${escapeHtml(mode === "webpanel_api" ? "WebPanel API" : "SSCP")}</option>`,
                )
                .join("")}
            </select>
            <small class="field-help">Vyber transport, pres ktery bude integrace s PLC komunikovat.</small>
          </label>
          <label><span>Host</span><input id="cfg-host" value="${escapeHtml(config.host)}"><small class="field-help">IP adresa nebo DNS jmeno PLC nebo WebPanelu.</small></label>
          <label><span>Port</span><input id="cfg-port" value="${escapeHtml(config.port)}"><small class="field-help">SSCP TCP port nebo HTTP/HTTPS port WebPanelu.</small></label>
          <label><span>Username</span><input id="cfg-username" value="${escapeHtml(config.username)}"><small class="field-help">Prihlasovaci jmeno pro SSCP nebo WebPanel API.</small></label>
          <label><span>Password</span><input id="cfg-password" type="password" value="${escapeHtml(config.password)}"><small class="field-help">Heslo k vybranemu backendu.</small></label>
          <label id="cfg-sscp-address-wrapper"><span>SSCP address</span><input id="cfg-address" value="${escapeHtml(config.sscp_address)}"><small class="field-help">Adresa SSCP zarizeni, typicky <code>0x01</code>.</small></label>
          <label id="cfg-webpanel-connection-wrapper"><span>WebPanel connection</span><input id="cfg-webpanel-connection" value="${escapeHtml(config.webpanel_connection)}"><small class="field-help">Jmeno WebPanel connection pouzite v identifikatoru <code>svc://...</code>.</small></label>
          <label id="cfg-webpanel-scheme-wrapper">
            <span>WebPanel scheme</span>
            <select id="cfg-webpanel-scheme">
              <option value="http" ${config.webpanel_scheme === "http" ? "selected" : ""}>http</option>
              <option value="https" ${config.webpanel_scheme === "https" ? "selected" : ""}>https</option>
            </select>
            <small class="field-help">Vol protokol, pod kterym bezi WebPanel.</small>
          </label>
          <label><span>Polling s</span><input id="cfg-scan" type="number" min="1" max="300" value="${escapeHtml(config.scan_interval)}"><small class="field-help">Interval hromadneho cteni hodnot v sekundach.</small></label>
          <label>
            <span>VList file</span>
            <select id="cfg-vlist">
              <option value="">Bez vlistu</option>
              ${availableVlists
                .map(
                  (fileName) =>
                    `<option value="${escapeHtml(fileName)}" ${
                      fileName === config.vlist_file_name ? "selected" : ""
                    }>${escapeHtml(fileName)}</option>`,
                )
                .join("")}
            </select>
            <small class="field-help">Vybrany VList zdroj pro explorer, metadata bodu a reload konfigurace.</small>
          </label>
        </div>
        <div class="upload-grid">
          <label>
            <span>Upload VList</span>
            <input id="vlist-upload-file" type="file" accept=".vlist,.txt,text/plain">
          </label>
          <label>
            <span>Ulozit jako</span>
            <input id="vlist-upload-name" placeholder="projekt.vlist">
          </label>
          <label class="checkbox-field">
            <input id="vlist-upload-overwrite" type="checkbox">
            <span>Prepsat existujici soubor</span>
          </label>
          <div class="upload-actions">
            <button class="secondary" data-action="upload-vlist">Nahrat VList</button>
          </div>
        </div>
        <p class="muted">Soubor se ulozi do <code>vlist_files</code>. Potom ho muzes vybrat v poli VList file a ulozit PLC konfiguraci.</p>
      </section>
    `;
  }

  _renderManualEntityForm(entry) {
    this._ensureManualDefaults(entry);
    const manual = this._manualFormState(entry);
    const isOpen = this._isManualPanelOpen(entry);
    this._manualPlcType = manual.plc_type;
    this._manualEntityType = manual.entity_type;
    const plcTypes = this._supportedPlcTypes(entry);
    const entityTypes = this._allowedEntityTypes(entry, this._manualPlcType);

    return `
      <details id="manual-point-panel" class="panel wide collapsible-panel" ${isOpen ? "open" : ""}>
        <summary class="collapsible-summary">
          <div>
            <p class="eyebrow">Manual Point</p>
            <h2>Rucni datovy bod a entita</h2>
            <p class="muted">Pouzij jen kdyz bod neni ve VListu nebo ho potrebujes zalozit uplne rucne.</p>
          </div>
          <span class="collapse-indicator">${isOpen ? "-" : "+"}</span>
        </summary>
        <div class="collapsible-body">
          <div class="section-head">
            <div>
              <p class="eyebrow">Advanced</p>
              <h2>Datovy bod a entita</h2>
              <p class="muted">Rucni konfigurace pro PLC body, ktere nejsou ve vlistu nebo je chces zalozit presne rucne.</p>
            </div>
            <div class="tools">
              <button data-action="add-manual-variable">Pridat datovy bod</button>
            </div>
          </div>
          <div class="settings-grid">
            <label><span>Datovy bod</span><input id="manual-name" placeholder="Room1.Temp" value="${escapeHtml(manual.variable_name)}"><small class="field-help">Nazev technologicke promenne nebo vlastni identifikace bodu.</small></label>
            <label><span>Nazev entity</span><input id="manual-display-name" placeholder="Pokoj teplota" value="${escapeHtml(manual.display_name)}"><small class="field-help">Uzivatelsky nazev entity v Home Assistantu.</small></label>
            <label><span>UID</span><input id="manual-uid" type="number" min="0" value="${escapeHtml(manual.uid)}"><small class="field-help">Jedinecny identifikator promenne v PLC.</small></label>
            <label><span>Offset</span><input id="manual-offset" type="number" min="0" value="${escapeHtml(manual.offset)}"><small class="field-help">Posun uvnitr datove struktury nebo pole.</small></label>
            <label><span>Length</span><input id="manual-length" type="number" min="1" value="${escapeHtml(manual.length)}"><small class="field-help">Velikost ctene nebo zapisovane hodnoty v bajtech.</small></label>
            <label>
              <span>PLC typ</span>
              <select id="manual-plc-type">
                ${plcTypes
                  .map(
                    (plcType) =>
                      `<option value="${escapeHtml(plcType)}" ${
                        plcType === manual.plc_type ? "selected" : ""
                      }>${escapeHtml(plcType)}</option>`,
                  )
                  .join("")}
              </select>
              <small class="field-help">Datovy typ bodu v PLC, podle ktereho se hodnota dekoduje.</small>
            </label>
            <label>
              <span>Entita</span>
              <select id="manual-entity-type">
                ${entityTypes
                  .map(
                    (entityType) =>
                      `<option value="${escapeHtml(entityType)}" ${
                        entityType === manual.entity_type ? "selected" : ""
                      }>${escapeHtml(entityType)}</option>`,
                  )
                  .join("")}
              </select>
              <small class="field-help">Jak se bude bod chovat v Home Assistantu: senzor, switch, number, select a podobne.</small>
            </label>
            <label id="manual-unit-wrapper"><span>Jednotka</span><input id="manual-unit" list="hass-unit-options" placeholder="ppm, °C, %, kWh" value="${escapeHtml(manual.unit_of_measurement)}"><small class="field-help">Volitelna fyzikalni jednotka pro sensor, datetime nebo number.</small></label>
            <label id="manual-device-class-wrapper"><span>Device class</span><input id="manual-device-class" list="${manual.entity_type === "number" ? "number-device-class-options" : "sensor-device-class-options"}" placeholder="temperature, humidity, carbon_dioxide" value="${escapeHtml(manual.device_class)}"><small class="field-help">HA device class pro lepsi interpretaci a zobrazeni entity.</small></label>
            <label id="manual-state-class-wrapper">
              <span>State class</span>
              <select id="manual-state-class">
                <option value="" ${!manual.state_class ? "selected" : ""}>bez state class</option>
                ${SENSOR_STATE_CLASS_OPTIONS.map(
                  (item) =>
                    `<option value="${escapeHtml(item)}" ${
                      item === manual.state_class ? "selected" : ""
                    }>${escapeHtml(item)}</option>`,
                ).join("")}
              </select>
              <small class="field-help">Sensor state class pro statistiky a energy dashboard.</small>
            </label>
            <label id="manual-display-precision-wrapper"><span>Presnost zobrazeni</span><input id="manual-display-precision" type="number" min="0" step="1" placeholder="0, 1, 2..." value="${escapeHtml(manual.suggested_display_precision)}"><small class="field-help">Doporucena presnost zobrazeni v HA. Prazdne = default.</small></label>
            ${this._renderAreaField("manual-area", manual.area_id, "Oblast v Home Assistantu, pod kterou se ma entita po vytvoreni priradit.")}
            <label id="manual-min-wrapper"><span>Min</span><input id="manual-min" type="number" step="any" placeholder="0" value="${escapeHtml(manual.min_value)}"><small class="field-help">Minimalni hodnota pro entity typu number.</small></label>
            <label id="manual-max-wrapper"><span>Max</span><input id="manual-max" type="number" step="any" placeholder="100" value="${escapeHtml(manual.max_value)}"><small class="field-help">Maximalni hodnota pro entity typu number.</small></label>
            <label id="manual-step-wrapper"><span>Step</span><input id="manual-step" type="number" step="any" placeholder="1" value="${escapeHtml(manual.step)}"><small class="field-help">Krok zmeny pro entity typu number.</small></label>
            <label id="manual-mode-wrapper">
              <span>Number mode</span>
              <select id="manual-mode">
                <option value="box" ${manual.mode === "box" ? "selected" : ""}>box</option>
                <option value="slider" ${manual.mode === "slider" ? "selected" : ""}>slider</option>
              </select>
              <small class="field-help">Zpusob ovladani number entity v UI.</small>
            </label>
            <label id="manual-press-time-wrapper"><span>Button press s</span><input id="manual-press-time" type="number" step="0.1" min="0" placeholder="0.1" value="${escapeHtml(manual.press_time)}"><small class="field-help">Jak dlouho zustane tlacitko v aktivnim stavu pri stisku.</small></label>
          </div>
          <label id="manual-select-options-wrapper" class="textarea-field">
            <span>Select options</span>
            <textarea id="manual-select-options" rows="4" placeholder="0=Vypnuto&#10;1=Zapnuto">${escapeHtml(manual.select_options_raw)}</textarea>
            <small class="field-help">Jedna volba na radek nebo oddelena carkou, vzdy ve formatu <code>hodnota=popis</code>.</small>
          </label>
          <p class="muted">Poznamka: pokrocila pole se pouziji jen pro odpovidajici typ entity.</p>
        </div>
      </details>
    `;
  }

  _render() {
    this._captureUiState();

    const entry = this._activeEntry;
    const entries = this._payload?.entries || [];
    const communicationLabel = entry?.communication_mode === "webpanel_api" ? "WebPanel API" : "SSCP";
    const statusLabel = entry?.connected
      ? "pripojeno"
      : entry?.connection_ready
        ? entry?.entry_state_label || "offline"
        : "bez nastaveneho spojeni";
    const summaryText = entry
      ? `${escapeHtml(entry.plc_name)} (${escapeHtml(communicationLabel)})${entry.host ? ` na ${escapeHtml(entry.host)}:${escapeHtml(entry.port)}` : ""} | ${escapeHtml(statusLabel)}`
      : "Zadna PLC entry zatim neexistuje.";

    this.shadowRoot.innerHTML = `
      <link rel="stylesheet" href="/sscp_integration_static/app.css">
      <div id="sscp-studio">
        <section class="hero">
          <div>
            <p class="eyebrow">Mervis / Domat</p>
            <h1>SSCP Studio</h1>
            <p>${summaryText}</p>
            ${this._error ? `<p class="error">${escapeHtml(this._error)}</p>` : ""}
            ${!this._error && entry?.last_error ? `<p class="error">${escapeHtml(entry.last_error)}</p>` : ""}
          </div>
          <div class="hero-actions">
            ${
              entries.length
                ? `
                  <select id="entry-select">
                    ${entries
                      .map(
                        (item) =>
                          `<option value="${escapeHtml(item.entry_id)}" ${
                            item.entry_id === entry?.entry_id ? "selected" : ""
                          }>${escapeHtml(item.plc_name)}</option>`,
                      )
                      .join("")}
                  </select>
                  <button data-action="refresh-runtime">Obnovit diagnostiku</button>
                  <button class="secondary" data-action="sync-time" ${entry?.communication_mode === "webpanel_api" ? "disabled" : ""}>Sync casu</button>
                  <button class="secondary" data-action="reload-from-vlist">Reload z vlist</button>
                `
                : ""
            }
            <button data-action="create-plc">Pridat PLC</button>
          </div>
        </section>

        ${this._renderPageTabs()}

        ${
          this._activePage === "help"
            ? this._renderHelpPage(entry)
            : entry
            ? `
              ${this._renderSettings(entry)}
              ${this._renderConfigLegend(entry)}

              <section class="grid">
                <article class="panel">
                  <p class="eyebrow">Connection</p>
                  <h2>${escapeHtml(entry.connected ? entry.capabilities?.right_group_label || "Connected" : entry.entry_state_label || "Offline")}</h2>
                  <p>Runtime ${escapeHtml(entry.runtime_available ? "available" : "fallback")}</p>
                  <p>Protocol ${escapeHtml(entry.capabilities?.protocol_version || "-")}</p>
                  <p>Max telegram ${escapeHtml(entry.capabilities?.server_max_data_size || "-")} B</p>
                  <p>Last refresh ${escapeHtml(entry.last_updated || "-")}</p>
                  ${entry.last_error ? `<p class="error">${escapeHtml(entry.last_error)}</p>` : ""}
                  <p class="field-help">Shrnuti backendu, prav a posledniho stavu spojeni.</p>
                </article>
                <article class="panel">
                  <p class="eyebrow">Runtime</p>
                  <h2>${escapeHtml(entry.plc_statistics?.runtime?.evaluator_state_label || "Unknown")}</h2>
                  <p>Run mode ${escapeHtml(entry.plc_statistics?.runtime?.run_mode_label || "-")}</p>
                  <p>Uptime ${escapeHtml(entry.plc_statistics?.runtime?.uptime || "-")}</p>
                  <p>Heap free ${escapeHtml(entry.plc_statistics?.memory?.free_heap_kb || "-")} kB</p>
                  <p class="field-help">V SSCP rezimu ukazuje provozni stav PLC, uptime a zakladni pametove statistiky.</p>
                </article>
                <article class="panel">
                  <p class="eyebrow">Clock</p>
                  <h2>${escapeHtml(entry.time?.utc || "-")}</h2>
                  <p>Local ${escapeHtml(entry.time?.local || "-")}</p>
                  <p>TZ ${escapeHtml(entry.time?.timezone_offset || "-")}</p>
                  <p>DST ${escapeHtml(entry.time?.daylight_offset || "-")}</p>
                  <p class="field-help">Casove informace dostupne hlavne v SSCP rezimu. V WebPanel API mohou byt prazdne.</p>
                </article>
                ${this._renderPLCControl(entry)}
              </section>
              <section class="grid">
                <article class="panel">
                  <p class="eyebrow">Configured</p>
                  <h2>${Object.values(entry.entity_counts || {}).reduce((sum, value) => sum + value, 0)}</h2>
                  <p>${
                    Object.entries(entry.entity_counts || {})
                      .map(([key, value]) => `${key}: ${value}`)
                      .join(" | ") || "Zadne entity"
                  }</p>
                  <p class="field-help">Prehled vsech uz nakonfigurovanych bodu a jejich typu.</p>
                  <div class="entity-list">${this._renderEntryCards(entry)}</div>
                </article>
                <article class="panel">
                  <p class="eyebrow">Protocol Coverage</p>
                  <div class="feature-list">
                    ${(entry.protocol_features || [])
                      .map(
                        (feature) => `
                          <div class="feature ${escapeHtml(feature.status)}">
                            <strong>${escapeHtml(feature.label)}</strong>
                            <p>${escapeHtml(feature.detail)}</p>
                          </div>
                        `,
                      )
                      .join("")}
                  </div>
                  <p class="field-help">Co aktualni backend umi plne, co jen castecne a ktere funkce nejsou k dispozici.</p>
                </article>
              </section>

              ${this._renderClimateComposer(entry)}
              ${this._renderHumidifierComposer(entry)}
              ${this._renderWaterHeaterComposer(entry)}
              ${this._renderLightComposer(entry)}
              ${this._renderFanComposer(entry)}
              ${this._renderCoverComposer(entry)}
              ${this._renderValveComposer(entry)}
              ${this._renderLockComposer(entry)}
              ${this._renderSirenComposer(entry)}
              ${this._renderVacuumComposer(entry)}
              ${this._renderSchedulerStudio(entry)}
              ${this._renderBrowser(entry)}
              ${this._renderManualEntityForm(entry)}
            `
            : `
              <section class="panel">
                <p class="eyebrow">Workspace</p>
                <h2>Zadne PLC</h2>
                <p class="muted">Vytvor prvni PLC entry tlacitkem Pridat PLC a potom v ni nastav spojeni, vlist a entity.</p>
              </section>
            `
        }
      </div>
      ${this._renderCatalogDatalists()}
      ${entry ? this._renderVlistVariableDatalist(entry) : ""}
      ${this._renderTreeSelectPopup()}
      ${this._renderTreeSensorPopup()}
      ${this._renderTreeNumberPopup()}
      ${this._renderTreeBasicPopup()}
      ${this._renderClimatePopup(entry)}
      ${this._renderHumidifierPopup(entry)}
      ${this._renderWaterHeaterPopup(entry)}
      ${this._renderLightPopup(entry)}
      ${this._renderFanPopup(entry)}
      ${this._renderCoverPopup(entry)}
      ${this._renderValvePopup(entry)}
      ${this._renderLockPopup(entry)}
      ${this._renderSirenPopup(entry)}
      ${this._renderVacuumPopup(entry)}
      ${this._renderSchedulerPopup()}
      ${this._renderSchedulerEntityPopup(entry)}
      ${this._renderComposerVariablePicker()}
    `;

    const entrySelect = this.shadowRoot.querySelector("#entry-select");
    if (entrySelect) {
      entrySelect.onchange = async (event) => {
        this._selectedEntryId = event.target.value;
        this._resetBrowserState({ keepFilter: true });
        this._manualPlcType = null;
        this._manualEntityType = null;
        this._climatePopup = this._climatePopupDefaults();
        this._humidifierPopup = this._humidifierPopupDefaults();
        this._waterHeaterPopup = this._waterHeaterPopupDefaults();
        this._lightPopup = this._lightPopupDefaults();
        this._fanPopup = this._fanPopupDefaults();
        this._coverPopup = this._coverPopupDefaults();
        this._valvePopup = this._valvePopupDefaults();
        this._lockPopup = this._lockPopupDefaults();
        this._sirenPopup = this._sirenPopupDefaults();
        this._vacuumPopup = this._vacuumPopupDefaults();
        this._schedulerPopup = this._schedulerPopupDefaults();
        this._schedulerEntityPopup = this._schedulerEntityPopupDefaults();
        this._resetComposerVariablePicker();
        this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
        this._treeSensorPopup = {
          open: false,
          variable_name: "",
          variable_entry_key: "",
          unit_of_measurement: "",
          device_class: "",
          state_class: "",
          suggested_display_precision: "",
          area_id: "",
          error: "",
        };
        this._treeNumberPopup = {
          open: false,
          variable_name: "",
          variable_entry_key: "",
          unit_of_measurement: "",
          device_class: "",
          suggested_display_precision: "",
          area_id: "",
          min_value: "",
          max_value: "",
          step: "",
          mode: "box",
          error: "",
        };
        this._treeBasicPopup = this._treeBasicPopupDefaults();
        await this._refreshAll();
      };
    }

    const uploadFile = this.shadowRoot.querySelector("#vlist-upload-file");
    if (uploadFile) {
      uploadFile.onchange = () => {
        const file = uploadFile.files?.[0];
        const nameInput = this.shadowRoot.querySelector("#vlist-upload-name");
        if (file && nameInput) {
          nameInput.value = file.name;
        }
      };
    }

    const communicationSelect = this.shadowRoot.querySelector("#cfg-communication-mode");
    if (communicationSelect) {
      communicationSelect.onchange = () => {
        this._syncCommunicationFieldVisibility();
      };
    }

    this._syncCommunicationFieldVisibility();

    const filterInput = this.shadowRoot.querySelector("#filter-input");
    if (filterInput) {
      filterInput.onkeydown = async (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          await this._applyTreeFilter();
        }
      };
    }

    const composerVariableFilterInput = this.shadowRoot.querySelector("#composer-variable-filter");
    if (composerVariableFilterInput) {
      composerVariableFilterInput.onkeydown = async (event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          await this._applyComposerVariablePickerFilter();
        }
      };
    }

    const manualPlcType = this.shadowRoot.querySelector("#manual-plc-type");
    if (manualPlcType) {
      manualPlcType.onchange = () => {
        this._manualPlcType = manualPlcType.value;
        this._syncManualEntityOptions();
      };
    }

    const manualEntityType = this.shadowRoot.querySelector("#manual-entity-type");
    if (manualEntityType) {
      manualEntityType.onchange = () => {
        this._manualEntityType = manualEntityType.value;
        this._syncManualFieldVisibility();
      };
    }

    this.shadowRoot.querySelectorAll(".tree-entity-select").forEach((node) => {
      node.onchange = () => {
        this._syncTreeSelectOptionVisibility();
      };
    });

    this._syncManualEntityOptions();
    this._syncTreeSelectOptionVisibility();

    const treeShell = this.shadowRoot.querySelector(".tree-shell");
    if (treeShell) {
      treeShell.scrollTop = this._treeScrollTop;
    }

    const composerPickerShell = this.shadowRoot.querySelector(".composer-picker-tree-shell");
    if (composerPickerShell) {
      composerPickerShell.scrollTop = this._composerVariablePicker.scroll_top || 0;
    }

    this._renderedEntryId = entry?.entry_id || null;

    this.shadowRoot.querySelectorAll("[data-action]").forEach((node) => {
      node.onclick = async () => {
        const action = node.dataset.action;
        if (action === "show-studio") {
          this._activePage = "studio";
          this._render();
          return;
        }

        if (action === "show-help") {
          this._activePage = "help";
          this._render();
          return;
        }

        if (action === "open-climate-popup") {
          this._captureUiState();
          await this._openClimatePopup();
          return;
        }

        if (action === "open-light-popup") {
          this._captureUiState();
          await this._openLightPopup();
          return;
        }

        if (action === "open-fan-popup") {
          this._captureUiState();
          await this._openFanPopup();
          return;
        }

        if (action === "open-humidifier-popup") {
          this._captureUiState();
          await this._openHumidifierPopup();
          return;
        }

        if (action === "open-water-heater-popup") {
          this._captureUiState();
          await this._openWaterHeaterPopup();
          return;
        }

        if (action === "open-cover-popup") {
          this._captureUiState();
          await this._openCoverPopup();
          return;
        }

        if (action === "open-lock-popup") {
          this._captureUiState();
          await this._openLockPopup();
          return;
        }

        if (action === "open-valve-popup") {
          this._captureUiState();
          await this._openValvePopup();
          return;
        }

        if (action === "open-siren-popup") {
          this._captureUiState();
          await this._openSirenPopup();
          return;
        }

        if (action === "open-vacuum-popup") {
          this._captureUiState();
          await this._openVacuumPopup();
          return;
        }

        if (action === "close-climate-popup") {
          this._captureUiState();
          this._closeClimatePopup();
          return;
        }

        if (action === "close-light-popup") {
          this._captureUiState();
          this._closeLightPopup();
          return;
        }

        if (action === "close-fan-popup") {
          this._captureUiState();
          this._closeFanPopup();
          return;
        }

        if (action === "close-humidifier-popup") {
          this._captureUiState();
          this._closeHumidifierPopup();
          return;
        }

        if (action === "close-water-heater-popup") {
          this._captureUiState();
          this._closeWaterHeaterPopup();
          return;
        }

        if (action === "close-cover-popup") {
          this._captureUiState();
          this._closeCoverPopup();
          return;
        }

        if (action === "close-lock-popup") {
          this._captureUiState();
          this._closeLockPopup();
          return;
        }

        if (action === "close-valve-popup") {
          this._captureUiState();
          this._closeValvePopup();
          return;
        }

        if (action === "close-siren-popup") {
          this._captureUiState();
          this._closeSirenPopup();
          return;
        }

        if (action === "close-vacuum-popup") {
          this._captureUiState();
          this._closeVacuumPopup();
          return;
        }

        if (action === "open-scheduler-popup") {
          this._captureUiState();
          await this._openSchedulerPopup(node.dataset.root || "");
          return;
        }

        if (action === "open-scheduler-entity-popup") {
          this._captureUiState();
          this._openSchedulerEntityPopup(null, node.dataset.root || "");
          return;
        }

        if (action === "close-scheduler-popup") {
          this._captureUiState();
          this._closeSchedulerPopup();
          return;
        }

        if (action === "close-scheduler-entity-popup") {
          this._captureUiState();
          this._closeSchedulerEntityPopup();
          return;
        }

        if (action === "close-tree-select-popup") {
          this._captureUiState();
          this._closeTreeSelectPopup();
          return;
        }

        if (action === "close-tree-number-popup") {
          this._captureUiState();
          this._closeTreeNumberPopup();
          return;
        }

        if (action === "close-tree-sensor-popup") {
          this._captureUiState();
          this._closeTreeSensorPopup();
          return;
        }

        if (action === "close-tree-basic-popup") {
          this._captureUiState();
          this._closeTreeBasicPopup();
          return;
        }

        if (action === "open-composer-variable-picker") {
          this._captureUiState();
          await this._openComposerVariablePicker(
            node.dataset.popup || "",
            node.dataset.field || "",
            node.dataset.label || "",
            node.dataset.inputId || "",
          );
          return;
        }

        if (action === "close-composer-variable-picker") {
          this._captureUiState();
          this._closeComposerVariablePicker();
          return;
        }

        if (action === "apply-composer-variable-filter") {
          await this._applyComposerVariablePickerFilter();
          return;
        }

        if (action === "toggle-composer-variable-folder") {
          await this._toggleComposerVariablePickerFolder(this._pathFromKey(node.dataset.path || ""));
          return;
        }

        if (action === "select-composer-variable") {
          this._captureUiState();
          this._selectComposerVariable(node.dataset.variable || "");
          return;
        }

        if (action === "confirm-tree-select-popup") {
          this._captureUiState();
          const variableName = this._treeSelectPopup.variable_name;
          const variableEntryKey = this._treeSelectPopup.variable_entry_key;
          const selectOptions = this._parseSelectOptions(this._treeSelectPopup.select_options_raw || "");
          if (!Object.keys(selectOptions).length) {
            this._treeSelectPopup = {
              ...this._treeSelectPopup,
              error: "Vyberova entita potrebuje alespon jednu definovanou hodnotu ve formatu hodnota=popis.",
            };
            this._render();
            return;
          }

          const result = await this._runAction(
            variableEntryKey ? "update_variable" : "add_variable",
            variableEntryKey
              ? {
                  variable_entry_key: variableEntryKey,
                  select_options: selectOptions,
                }
              : {
                  variable_name: variableName,
                  entity_type: "select",
                  select_options: selectOptions,
                },
            { refreshBrowser: true },
          );
          if (result) {
            const entryKey = this._entryDraftKey();
            this._treeEntityDrafts[entryKey] = {
              ...(this._treeEntityDrafts[entryKey] || {}),
              [variableName]: {
                ...(this._treeEntityDrafts[entryKey]?.[variableName] || {}),
                entity_type: "select",
                select_options_raw: this._treeSelectPopup.select_options_raw || "",
              },
            };
            this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
            this._render();
          }
          return;
        }

        if (action === "confirm-tree-sensor-popup") {
          this._captureUiState();
          const variableName = this._treeSensorPopup.variable_name;
          const variableEntryKey = this._treeSensorPopup.variable_entry_key;
          const precisionRaw = this._treeSensorPopup.suggested_display_precision;
          const precisionValue = precisionRaw === "" ? null : Number(precisionRaw);

          if (precisionValue !== null && (!Number.isInteger(precisionValue) || precisionValue < 0)) {
            this._treeSensorPopup = {
              ...this._treeSensorPopup,
              error: "Presnost zobrazeni musi byt cele cislo 0 nebo vetsi.",
            };
            this._render();
            return;
          }

          const result = await this._runAction(
            variableEntryKey ? "update_variable" : "add_variable",
            variableEntryKey
              ? {
                  variable_entry_key: variableEntryKey,
                  unit_of_measurement: this._treeSensorPopup.unit_of_measurement || "",
                  device_class: this._treeSensorPopup.device_class || "",
                  state_class: this._treeSensorPopup.state_class || "",
                  suggested_display_precision: precisionValue,
                  area_id: this._treeSensorPopup.area_id || "",
                }
              : {
                  variable_name: variableName,
                  entity_type: "sensor",
                  unit_of_measurement: this._treeSensorPopup.unit_of_measurement || "",
                  device_class: this._treeSensorPopup.device_class || "",
                  state_class: this._treeSensorPopup.state_class || "",
                  suggested_display_precision: precisionValue,
                  area_id: this._treeSensorPopup.area_id || "",
                },
            { refreshBrowser: true },
          );
          if (result) {
            const entryKey = this._entryDraftKey();
            this._treeEntityDrafts[entryKey] = {
              ...(this._treeEntityDrafts[entryKey] || {}),
              [variableName]: {
                ...(this._treeEntityDrafts[entryKey]?.[variableName] || {}),
                entity_type: "sensor",
                unit_of_measurement: this._treeSensorPopup.unit_of_measurement || "",
                device_class: this._treeSensorPopup.device_class || "",
                state_class: this._treeSensorPopup.state_class || "",
                suggested_display_precision: this._treeSensorPopup.suggested_display_precision || "",
                area_id: this._treeSensorPopup.area_id || "",
              },
            };
            this._treeSensorPopup = {
              open: false,
              variable_name: "",
              variable_entry_key: "",
              unit_of_measurement: "",
              device_class: "",
              state_class: "",
              suggested_display_precision: "",
              area_id: "",
              error: "",
            };
            this._render();
          }
          return;
        }

        if (action === "confirm-tree-number-popup") {
          this._captureUiState();
          const variableName = this._treeNumberPopup.variable_name;
          const variableEntryKey = this._treeNumberPopup.variable_entry_key;
          const precisionRaw = this._treeNumberPopup.suggested_display_precision;
          const precisionValue = precisionRaw === "" ? null : Number(precisionRaw);
          const minValue = this._treeNumberPopup.min_value === "" ? null : Number(this._treeNumberPopup.min_value);
          const maxValue = this._treeNumberPopup.max_value === "" ? null : Number(this._treeNumberPopup.max_value);
          const stepValue = this._treeNumberPopup.step === "" ? null : Number(this._treeNumberPopup.step);
          const modeValue = this._treeNumberPopup.mode || "box";

          if (precisionValue !== null && (!Number.isInteger(precisionValue) || precisionValue < 0)) {
            this._treeNumberPopup = {
              ...this._treeNumberPopup,
              error: "Presnost zobrazeni musi byt cele cislo 0 nebo vetsi.",
            };
            this._render();
            return;
          }
          if ((minValue !== null && Number.isNaN(minValue)) || (maxValue !== null && Number.isNaN(maxValue))) {
            this._treeNumberPopup = {
              ...this._treeNumberPopup,
              error: "Min a Max musi byt platna cisla.",
            };
            this._render();
            return;
          }
          if (minValue !== null && maxValue !== null && minValue > maxValue) {
            this._treeNumberPopup = {
              ...this._treeNumberPopup,
              error: "Minimalni hodnota nesmi byt vetsi nez maximalni.",
            };
            this._render();
            return;
          }
          if (stepValue !== null && (Number.isNaN(stepValue) || stepValue <= 0)) {
            this._treeNumberPopup = {
              ...this._treeNumberPopup,
              error: "Krok musi byt platne cislo vetsi nez 0.",
            };
            this._render();
            return;
          }

          const result = await this._runAction(
            variableEntryKey ? "update_variable" : "add_variable",
            variableEntryKey
              ? {
                  variable_entry_key: variableEntryKey,
                  unit_of_measurement: this._treeNumberPopup.unit_of_measurement || "",
                  device_class: this._treeNumberPopup.device_class || "",
                  suggested_display_precision: precisionValue,
                  area_id: this._treeNumberPopup.area_id || "",
                  min_value: minValue,
                  max_value: maxValue,
                  step: stepValue,
                  mode: modeValue,
                }
              : {
                  variable_name: variableName,
                  entity_type: "number",
                  unit_of_measurement: this._treeNumberPopup.unit_of_measurement || "",
                  device_class: this._treeNumberPopup.device_class || "",
                  suggested_display_precision: precisionValue,
                  area_id: this._treeNumberPopup.area_id || "",
                  min_value: minValue,
                  max_value: maxValue,
                  step: stepValue,
                  mode: modeValue,
                },
            { refreshBrowser: true },
          );
          if (result) {
            const entryKey = this._entryDraftKey();
            this._treeEntityDrafts[entryKey] = {
              ...(this._treeEntityDrafts[entryKey] || {}),
              [variableName]: {
                ...(this._treeEntityDrafts[entryKey]?.[variableName] || {}),
                entity_type: "number",
                unit_of_measurement: this._treeNumberPopup.unit_of_measurement || "",
                device_class: this._treeNumberPopup.device_class || "",
                suggested_display_precision: this._treeNumberPopup.suggested_display_precision || "",
                area_id: this._treeNumberPopup.area_id || "",
                min_value: this._treeNumberPopup.min_value || "",
                max_value: this._treeNumberPopup.max_value || "",
                step: this._treeNumberPopup.step || "",
                mode: this._treeNumberPopup.mode || "box",
              },
            };
            this._treeNumberPopup = {
              open: false,
              variable_name: "",
              variable_entry_key: "",
              unit_of_measurement: "",
              device_class: "",
              suggested_display_precision: "",
              area_id: "",
              min_value: "",
              max_value: "",
              step: "",
              mode: "box",
              error: "",
            };
            this._render();
          }
          return;
        }

        if (action === "confirm-tree-basic-popup") {
          this._captureUiState();
          const variableName = this._treeBasicPopup.variable_name;
          const variableEntryKey = this._treeBasicPopup.variable_entry_key;
          const entityType = this._treeBasicPopup.entity_type || "switch";
          const displayName = (this._treeBasicPopup.display_name || "").trim();
          const pressTimeRaw = this._treeBasicPopup.press_time;
          const pressTime = pressTimeRaw === "" ? null : Number(pressTimeRaw);

          if (pressTime !== null && (Number.isNaN(pressTime) || pressTime <= 0)) {
            this._treeBasicPopup = {
              ...this._treeBasicPopup,
              error: "Button press time musi byt platne cislo vetsi nez 0.",
            };
            this._render();
            return;
          }

          const result = await this._runAction(
            variableEntryKey ? "update_variable" : "add_variable",
            variableEntryKey
              ? {
                  variable_entry_key: variableEntryKey,
                  display_name: displayName || undefined,
                  area_id: this._treeBasicPopup.area_id || "",
                  press_time: entityType === "button" ? pressTime : undefined,
                }
              : {
                  variable_name: variableName,
                  entity_type: entityType,
                  display_name: displayName || undefined,
                  area_id: this._treeBasicPopup.area_id || "",
                  press_time: entityType === "button" ? pressTime : undefined,
                },
            { refreshBrowser: true },
          );
          if (result) {
            const entryKey = this._entryDraftKey();
            this._treeEntityDrafts[entryKey] = {
              ...(this._treeEntityDrafts[entryKey] || {}),
              [variableName]: {
                ...(this._treeEntityDrafts[entryKey]?.[variableName] || {}),
                entity_type: entityType,
                display_name: displayName,
                area_id: this._treeBasicPopup.area_id || "",
                press_time: this._treeBasicPopup.press_time || "",
              },
            };
            this._treeBasicPopup = this._treeBasicPopupDefaults();
            this._render();
          }
          return;
        }

        if (action === "confirm-climate-popup") {
          this._captureUiState();
          const precisionRaw = this._climatePopup.suggested_display_precision;
          const precisionValue = precisionRaw === "" ? null : Number(precisionRaw);
          const minTemp = this._climatePopup.min_temp === "" ? null : Number(this._climatePopup.min_temp);
          const maxTemp = this._climatePopup.max_temp === "" ? null : Number(this._climatePopup.max_temp);
          const tempStep = this._climatePopup.temp_step === "" ? null : Number(this._climatePopup.temp_step);
          if (!this._climatePopup.name.trim()) {
            this._climatePopup = { ...this._climatePopup, error: "Climate entita potrebuje nazev." };
            this._render();
            return;
          }
          if (!this._climatePopup.target_temperature_name.trim()) {
            this._climatePopup = { ...this._climatePopup, error: "Climate composer potrebuje cilovou teplotu." };
            this._render();
            return;
          }
          if (precisionValue !== null && (!Number.isInteger(precisionValue) || precisionValue < 0)) {
            this._climatePopup = { ...this._climatePopup, error: "Presnost zobrazeni musi byt cele cislo 0 nebo vetsi." };
            this._render();
            return;
          }
          if ((minTemp !== null && Number.isNaN(minTemp)) || (maxTemp !== null && Number.isNaN(maxTemp))) {
            this._climatePopup = { ...this._climatePopup, error: "Min a Max teplota musi byt platna cisla." };
            this._render();
            return;
          }
          if (minTemp !== null && maxTemp !== null && minTemp > maxTemp) {
            this._climatePopup = { ...this._climatePopup, error: "Minimalni teplota nesmi byt vetsi nez maximalni." };
            this._render();
            return;
          }
          if (tempStep !== null && (Number.isNaN(tempStep) || tempStep <= 0)) {
            this._climatePopup = { ...this._climatePopup, error: "Krok teploty musi byt vetsi nez 0." };
            this._render();
            return;
          }

          const result = await this._runAction("save_climate_entity", {
            entity_key: this._climatePopup.entity_key || undefined,
            name: this._climatePopup.name,
            area_id: this._climatePopup.area_id || "",
            temperature_unit: this._climatePopup.temperature_unit || "°C",
            suggested_display_precision: precisionValue,
            min_temp: minTemp,
            max_temp: maxTemp,
            temp_step: tempStep,
            current_temperature_name: this._climatePopup.current_temperature_name || "",
            target_temperature_name: this._climatePopup.target_temperature_name || "",
            current_humidity_name: this._climatePopup.current_humidity_name || "",
            power_name: this._climatePopup.power_name || "",
            hvac_mode_name: this._climatePopup.hvac_mode_name || "",
            preset_name: this._climatePopup.preset_name || "",
            hvac_mode_map: this._parseSelectOptions(this._climatePopup.hvac_mode_map_raw || ""),
            preset_map: this._parseSelectOptions(this._climatePopup.preset_map_raw || ""),
          });
          if (result) {
            this._closeClimatePopup();
          }
          return;
        }

        if (action === "confirm-light-popup") {
          this._captureUiState();
          const precisionRaw = this._lightPopup.suggested_display_precision;
          const precisionValue = precisionRaw === "" ? null : Number(precisionRaw);
          const brightnessScale =
            this._lightPopup.brightness_scale === "" ? null : Number(this._lightPopup.brightness_scale);
          const minMireds = this._lightPopup.min_mireds === "" ? null : Number(this._lightPopup.min_mireds);
          const maxMireds = this._lightPopup.max_mireds === "" ? null : Number(this._lightPopup.max_mireds);

          if (!this._lightPopup.name.trim()) {
            this._lightPopup = { ...this._lightPopup, error: "Light entita potrebuje nazev." };
            this._render();
            return;
          }
          if (precisionValue !== null && (!Number.isInteger(precisionValue) || precisionValue < 0)) {
            this._lightPopup = { ...this._lightPopup, error: "Presnost zobrazeni musi byt cele cislo 0 nebo vetsi." };
            this._render();
            return;
          }
          if (brightnessScale !== null && (Number.isNaN(brightnessScale) || brightnessScale <= 0)) {
            this._lightPopup = { ...this._lightPopup, error: "Brightness scale musi byt platne cislo vetsi nez 0." };
            this._render();
            return;
          }
          if ((minMireds !== null && (!Number.isInteger(minMireds) || minMireds <= 0)) || (maxMireds !== null && (!Number.isInteger(maxMireds) || maxMireds <= 0))) {
            this._lightPopup = { ...this._lightPopup, error: "Min a Max mireds musi byt kladna cela cisla." };
            this._render();
            return;
          }
          if (minMireds !== null && maxMireds !== null && minMireds > maxMireds) {
            this._lightPopup = { ...this._lightPopup, error: "Min mireds nesmi byt vetsi nez Max mireds." };
            this._render();
            return;
          }

          const result = await this._runAction("save_light_entity", {
            entity_key: this._lightPopup.entity_key || undefined,
            name: this._lightPopup.name,
            area_id: this._lightPopup.area_id || "",
            suggested_display_precision: precisionValue,
            brightness_scale: brightnessScale,
            min_mireds: minMireds,
            max_mireds: maxMireds,
            power_name: this._lightPopup.power_name || "",
            brightness_name: this._lightPopup.brightness_name || "",
            color_temp_name: this._lightPopup.color_temp_name || "",
            hs_hue_name: this._lightPopup.hs_hue_name || "",
            hs_saturation_name: this._lightPopup.hs_saturation_name || "",
            rgb_red_name: this._lightPopup.rgb_red_name || "",
            rgb_green_name: this._lightPopup.rgb_green_name || "",
            rgb_blue_name: this._lightPopup.rgb_blue_name || "",
            white_name: this._lightPopup.white_name || "",
            effect_name: this._lightPopup.effect_name || "",
            effect_map: this._parseSelectOptions(this._lightPopup.effect_map_raw || ""),
          });
          if (result) {
            this._closeLightPopup();
          }
          return;
        }

        if (action === "confirm-fan-popup") {
          this._captureUiState();
          const percentageStep = this._fanPopup.percentage_step === "" ? null : Number(this._fanPopup.percentage_step);
          const presetMap = this._parseSelectOptions(this._fanPopup.preset_map_raw || "");
          const directionMap = this._parseSelectOptions(this._fanPopup.direction_map_raw || "");

          if (!this._fanPopup.name.trim()) {
            this._fanPopup = { ...this._fanPopup, error: "Fan entita potrebuje nazev." };
            this._render();
            return;
          }
          if (percentageStep !== null && (!Number.isInteger(percentageStep) || percentageStep <= 0)) {
            this._fanPopup = { ...this._fanPopup, error: "Percentage step musi byt cele cislo vetsi nez 0." };
            this._render();
            return;
          }
          if (this._fanPopup.preset_name.trim() && !Object.keys(presetMap).length) {
            this._fanPopup = { ...this._fanPopup, error: "Kdyz vyplnis preset point, dopln i preset map." };
            this._render();
            return;
          }
          if (this._fanPopup.direction_name.trim() && !Object.keys(directionMap).length) {
            this._fanPopup = { ...this._fanPopup, error: "Kdyz vyplnis direction point, dopln i direction map." };
            this._render();
            return;
          }

          const result = await this._runAction("save_fan_entity", {
            entity_key: this._fanPopup.entity_key || undefined,
            name: this._fanPopup.name,
            area_id: this._fanPopup.area_id || "",
            percentage_step: percentageStep,
            power_name: this._fanPopup.power_name || "",
            percentage_name: this._fanPopup.percentage_name || "",
            preset_name: this._fanPopup.preset_name || "",
            preset_map: presetMap,
            oscillate_name: this._fanPopup.oscillate_name || "",
            direction_name: this._fanPopup.direction_name || "",
            direction_map: directionMap,
          });
          if (result) {
            this._closeFanPopup();
          }
          return;
        }

        if (action === "confirm-humidifier-popup") {
          this._captureUiState();
          const minHumidity = this._humidifierPopup.min_humidity === "" ? null : Number(this._humidifierPopup.min_humidity);
          const maxHumidity = this._humidifierPopup.max_humidity === "" ? null : Number(this._humidifierPopup.max_humidity);
          const targetStep =
            this._humidifierPopup.target_humidity_step === "" ? null : Number(this._humidifierPopup.target_humidity_step);
          const modeMap = this._parseSelectOptions(this._humidifierPopup.mode_map_raw || "");

          if (!this._humidifierPopup.name.trim()) {
            this._humidifierPopup = { ...this._humidifierPopup, error: "Humidifier entita potrebuje nazev." };
            this._render();
            return;
          }
          if ((minHumidity !== null && Number.isNaN(minHumidity)) || (maxHumidity !== null && Number.isNaN(maxHumidity))) {
            this._humidifierPopup = { ...this._humidifierPopup, error: "Min a Max humidity musi byt platna cisla." };
            this._render();
            return;
          }
          if (minHumidity !== null && maxHumidity !== null && minHumidity > maxHumidity) {
            this._humidifierPopup = { ...this._humidifierPopup, error: "Minimalni vlhkost nesmi byt vetsi nez maximalni." };
            this._render();
            return;
          }
          if (targetStep !== null && (Number.isNaN(targetStep) || targetStep <= 0)) {
            this._humidifierPopup = { ...this._humidifierPopup, error: "Target step musi byt cislo vetsi nez 0." };
            this._render();
            return;
          }
          if (this._humidifierPopup.mode_name.trim() && !Object.keys(modeMap).length) {
            this._humidifierPopup = { ...this._humidifierPopup, error: "Kdyz vyplnis mode point, dopln i mode map." };
            this._render();
            return;
          }

          const result = await this._runAction("save_humidifier_entity", {
            entity_key: this._humidifierPopup.entity_key || undefined,
            name: this._humidifierPopup.name,
            area_id: this._humidifierPopup.area_id || "",
            device_class: this._humidifierPopup.device_class || "",
            min_humidity: minHumidity,
            max_humidity: maxHumidity,
            target_humidity_step: targetStep,
            current_humidity_name: this._humidifierPopup.current_humidity_name || "",
            target_humidity_name: this._humidifierPopup.target_humidity_name || "",
            power_name: this._humidifierPopup.power_name || "",
            mode_name: this._humidifierPopup.mode_name || "",
            mode_map: modeMap,
          });
          if (result) {
            this._closeHumidifierPopup();
          }
          return;
        }

        if (action === "confirm-water-heater-popup") {
          this._captureUiState();
          const precisionRaw = this._waterHeaterPopup.suggested_display_precision;
          const precisionValue = precisionRaw === "" ? null : Number(precisionRaw);
          const minTemp = this._waterHeaterPopup.min_temp === "" ? null : Number(this._waterHeaterPopup.min_temp);
          const maxTemp = this._waterHeaterPopup.max_temp === "" ? null : Number(this._waterHeaterPopup.max_temp);
          const tempStep = this._waterHeaterPopup.temp_step === "" ? null : Number(this._waterHeaterPopup.temp_step);
          const operationModeMap = this._parseSelectOptions(this._waterHeaterPopup.operation_mode_map_raw || "");

          if (!this._waterHeaterPopup.name.trim()) {
            this._waterHeaterPopup = { ...this._waterHeaterPopup, error: "Water heater entita potrebuje nazev." };
            this._render();
            return;
          }
          if (precisionValue !== null && (!Number.isInteger(precisionValue) || precisionValue < 0)) {
            this._waterHeaterPopup = { ...this._waterHeaterPopup, error: "Presnost zobrazeni musi byt cele cislo 0 nebo vetsi." };
            this._render();
            return;
          }
          if ((minTemp !== null && Number.isNaN(minTemp)) || (maxTemp !== null && Number.isNaN(maxTemp))) {
            this._waterHeaterPopup = { ...this._waterHeaterPopup, error: "Min a Max teplota musi byt platna cisla." };
            this._render();
            return;
          }
          if (minTemp !== null && maxTemp !== null && minTemp > maxTemp) {
            this._waterHeaterPopup = { ...this._waterHeaterPopup, error: "Minimalni teplota nesmi byt vetsi nez maximalni." };
            this._render();
            return;
          }
          if (tempStep !== null && (Number.isNaN(tempStep) || tempStep <= 0)) {
            this._waterHeaterPopup = { ...this._waterHeaterPopup, error: "Krok teploty musi byt vetsi nez 0." };
            this._render();
            return;
          }
          if (this._waterHeaterPopup.operation_mode_name.trim() && !Object.keys(operationModeMap).length) {
            this._waterHeaterPopup = { ...this._waterHeaterPopup, error: "Kdyz vyplnis operation mode point, dopln i operation mode map." };
            this._render();
            return;
          }

          const result = await this._runAction("save_water_heater_entity", {
            entity_key: this._waterHeaterPopup.entity_key || undefined,
            name: this._waterHeaterPopup.name,
            area_id: this._waterHeaterPopup.area_id || "",
            temperature_unit: this._waterHeaterPopup.temperature_unit || "Â°C",
            suggested_display_precision: precisionValue,
            min_temp: minTemp,
            max_temp: maxTemp,
            temp_step: tempStep,
            current_temperature_name: this._waterHeaterPopup.current_temperature_name || "",
            target_temperature_name: this._waterHeaterPopup.target_temperature_name || "",
            power_name: this._waterHeaterPopup.power_name || "",
            operation_mode_name: this._waterHeaterPopup.operation_mode_name || "",
            operation_mode_map: operationModeMap,
          });
          if (result) {
            this._closeWaterHeaterPopup();
          }
          return;
        }

        if (action === "confirm-cover-popup") {
          this._captureUiState();
          if (!this._coverPopup.name.trim()) {
            this._coverPopup = { ...this._coverPopup, error: "Cover entita potrebuje nazev." };
            this._render();
            return;
          }

          const result = await this._runAction("save_cover_entity", {
            entity_key: this._coverPopup.entity_key || undefined,
            name: this._coverPopup.name,
            area_id: this._coverPopup.area_id || "",
            device_class: this._coverPopup.device_class || "",
            invert_position: Boolean(this._coverPopup.invert_position),
            current_position_name: this._coverPopup.current_position_name || "",
            target_position_name: this._coverPopup.target_position_name || "",
            open_name: this._coverPopup.open_name || "",
            close_name: this._coverPopup.close_name || "",
            stop_name: this._coverPopup.stop_name || "",
            current_tilt_name: this._coverPopup.current_tilt_name || "",
            target_tilt_name: this._coverPopup.target_tilt_name || "",
            tilt_open_name: this._coverPopup.tilt_open_name || "",
            tilt_close_name: this._coverPopup.tilt_close_name || "",
            tilt_stop_name: this._coverPopup.tilt_stop_name || "",
          });
          if (result) {
            this._closeCoverPopup();
          }
          return;
        }

        if (action === "confirm-lock-popup") {
          this._captureUiState();
          const stateMap = this._parseSelectOptions(this._lockPopup.state_map_raw || "");

          if (!this._lockPopup.name.trim()) {
            this._lockPopup = { ...this._lockPopup, error: "Lock entita potrebuje nazev." };
            this._render();
            return;
          }

          const result = await this._runAction("save_lock_entity", {
            entity_key: this._lockPopup.entity_key || undefined,
            name: this._lockPopup.name,
            area_id: this._lockPopup.area_id || "",
            state_name: this._lockPopup.state_name || "",
            lock_name: this._lockPopup.lock_name || "",
            unlock_name: this._lockPopup.unlock_name || "",
            open_name: this._lockPopup.open_name || "",
            state_map: stateMap,
          });
          if (result) {
            this._closeLockPopup();
          }
          return;
        }

        if (action === "confirm-valve-popup") {
          this._captureUiState();
          if (!this._valvePopup.name.trim()) {
            this._valvePopup = { ...this._valvePopup, error: "Valve entita potrebuje nazev." };
            this._render();
            return;
          }

          const result = await this._runAction("save_valve_entity", {
            entity_key: this._valvePopup.entity_key || undefined,
            name: this._valvePopup.name,
            area_id: this._valvePopup.area_id || "",
            device_class: this._valvePopup.device_class || "",
            invert_position: Boolean(this._valvePopup.invert_position),
            current_position_name: this._valvePopup.current_position_name || "",
            target_position_name: this._valvePopup.target_position_name || "",
            open_name: this._valvePopup.open_name || "",
            close_name: this._valvePopup.close_name || "",
            stop_name: this._valvePopup.stop_name || "",
          });
          if (result) {
            this._closeValvePopup();
          }
          return;
        }

        if (action === "confirm-vacuum-popup") {
          this._captureUiState();
          const statusMap = this._parseSelectOptions(this._vacuumPopup.status_map_raw || "");
          const fanSpeedMap = this._parseSelectOptions(this._vacuumPopup.fan_speed_map_raw || "");

          if (!this._vacuumPopup.name.trim()) {
            this._vacuumPopup = { ...this._vacuumPopup, error: "Vacuum entita potrebuje nazev." };
            this._render();
            return;
          }
          if (this._vacuumPopup.status_name.trim() && !Object.keys(statusMap).length) {
            this._vacuumPopup = { ...this._vacuumPopup, error: "Kdyz vyplnis status point, dopln i status map." };
            this._render();
            return;
          }
          if (this._vacuumPopup.fan_speed_name.trim() && !Object.keys(fanSpeedMap).length) {
            this._vacuumPopup = { ...this._vacuumPopup, error: "Kdyz vyplnis fan speed point, dopln i mapovani rychlosti." };
            this._render();
            return;
          }

          const result = await this._runAction("save_vacuum_entity", {
            entity_key: this._vacuumPopup.entity_key || undefined,
            name: this._vacuumPopup.name,
            area_id: this._vacuumPopup.area_id || "",
            status_name: this._vacuumPopup.status_name || "",
            battery_level_name: this._vacuumPopup.battery_level_name || "",
            battery_charging_name: this._vacuumPopup.battery_charging_name || "",
            fan_speed_name: this._vacuumPopup.fan_speed_name || "",
            start_name: this._vacuumPopup.start_name || "",
            pause_name: this._vacuumPopup.pause_name || "",
            stop_name: this._vacuumPopup.stop_name || "",
            return_to_base_name: this._vacuumPopup.return_to_base_name || "",
            locate_name: this._vacuumPopup.locate_name || "",
            status_map: statusMap,
            fan_speed_map: fanSpeedMap,
          });
          if (result) {
            this._closeVacuumPopup();
          }
          return;
        }

        if (action === "confirm-siren-popup") {
          this._captureUiState();
          const toneMap = this._parseSelectOptions(this._sirenPopup.tone_map_raw || "");
          const volumeScale = this._sirenPopup.volume_scale === "" ? null : Number(this._sirenPopup.volume_scale);

          if (!this._sirenPopup.name.trim()) {
            this._sirenPopup = { ...this._sirenPopup, error: "Siren entita potrebuje nazev." };
            this._render();
            return;
          }
          if (volumeScale !== null && (Number.isNaN(volumeScale) || volumeScale <= 0)) {
            this._sirenPopup = { ...this._sirenPopup, error: "Volume scale musi byt cislo vetsi nez 0." };
            this._render();
            return;
          }
          if (this._sirenPopup.tone_name.trim() && !Object.keys(toneMap).length) {
            this._sirenPopup = { ...this._sirenPopup, error: "Kdyz vyplnis tone point, dopln i tone map." };
            this._render();
            return;
          }

          const result = await this._runAction("save_siren_entity", {
            entity_key: this._sirenPopup.entity_key || undefined,
            name: this._sirenPopup.name,
            area_id: this._sirenPopup.area_id || "",
            state_name: this._sirenPopup.state_name || "",
            turn_on_name: this._sirenPopup.turn_on_name || "",
            turn_off_name: this._sirenPopup.turn_off_name || "",
            tone_name: this._sirenPopup.tone_name || "",
            tone_map: toneMap,
            duration_name: this._sirenPopup.duration_name || "",
            volume_name: this._sirenPopup.volume_name || "",
            volume_scale: volumeScale,
          });
          if (result) {
            this._closeSirenPopup();
          }
          return;
        }

        if (action === "confirm-scheduler-entity-popup") {
          this._captureUiState();
          const precisionRaw = this._schedulerEntityPopup.suggested_display_precision;
          const precisionValue = precisionRaw === "" ? null : Number(precisionRaw);
          if (!this._schedulerEntityPopup.name.trim()) {
            this._schedulerEntityPopup = { ...this._schedulerEntityPopup, error: "Scheduler entita potrebuje nazev." };
            this._render();
            return;
          }
          if (!this._schedulerEntityPopup.root_name.trim()) {
            this._schedulerEntityPopup = { ...this._schedulerEntityPopup, error: "Vyber scheduler blok, nad kterym se ma entita vytvorit." };
            this._render();
            return;
          }
          if (precisionValue !== null && (!Number.isInteger(precisionValue) || precisionValue < 0)) {
            this._schedulerEntityPopup = { ...this._schedulerEntityPopup, error: "Presnost zobrazeni musi byt cele cislo 0 nebo vetsi." };
            this._render();
            return;
          }

          const result = await this._runAction("save_scheduler_entity", {
            entity_key: this._schedulerEntityPopup.entity_key || undefined,
            name: this._schedulerEntityPopup.name,
            root_name: this._schedulerEntityPopup.root_name,
            area_id: this._schedulerEntityPopup.area_id || "",
            suggested_display_precision: precisionValue,
          });
          if (result) {
            this._closeSchedulerEntityPopup();
          }
          return;
        }

        if (action === "save-scheduler-popup") {
          this._captureUiState();
          const defaultValue = this._schedulerPopup.default_value;
          const weeklyItems = (this._schedulerPopup.weekly_items || []).map((item) => ({
            starttime: (Number(item.day) * 1440) + Number(item.minute_of_day || 0),
            value: this._schedulerPopup.kind === "bool" ? String(item.value) === "1" : item.value,
          }));
          const result = await this._runAction("save_scheduler", {
            root_name: this._schedulerPopup.root_name,
            default_value: this._schedulerPopup.kind === "bool" ? String(defaultValue) === "1" : defaultValue,
            weekly_items: weeklyItems,
          });
          if (result) {
            this._closeSchedulerPopup();
          }
          return;
        }

        if (action === "set-communication-mode") {
          this._captureUiState();
          this._setCommunicationMode(node.dataset.mode || "sscp");
          return;
        }

        if (action === "create-plc") {
          this._resetBrowserState();
          this._manualPlcType = null;
          this._manualEntityType = null;
          this._climatePopup = this._climatePopupDefaults();
          this._humidifierPopup = this._humidifierPopupDefaults();
          this._waterHeaterPopup = this._waterHeaterPopupDefaults();
          this._lightPopup = this._lightPopupDefaults();
          this._fanPopup = this._fanPopupDefaults();
          this._coverPopup = this._coverPopupDefaults();
          this._valvePopup = this._valvePopupDefaults();
          this._lockPopup = this._lockPopupDefaults();
          this._sirenPopup = this._sirenPopupDefaults();
          this._vacuumPopup = this._vacuumPopupDefaults();
          this._schedulerPopup = this._schedulerPopupDefaults();
          this._schedulerEntityPopup = this._schedulerEntityPopupDefaults();
          this._treeSelectPopup = { open: false, variable_name: "", variable_entry_key: "", select_options_raw: "", error: "" };
          this._treeSensorPopup = {
            open: false,
            variable_name: "",
            variable_entry_key: "",
            unit_of_measurement: "",
            device_class: "",
            state_class: "",
            suggested_display_precision: "",
            area_id: "",
            error: "",
          };
          this._treeNumberPopup = {
            open: false,
            variable_name: "",
            variable_entry_key: "",
            unit_of_measurement: "",
            device_class: "",
            suggested_display_precision: "",
            area_id: "",
            min_value: "",
            max_value: "",
            step: "",
            mode: "box",
            error: "",
          };
          this._treeBasicPopup = this._treeBasicPopupDefaults();
          await this._runAction("create_plc", {}, { allowWithoutEntry: true });
          await this._refreshBrowser({ force: true });
          return;
        }

        if (action === "refresh-runtime") {
          await this._runAction("refresh");
          return;
        }

        if (action === "save-config") {
          await this._runAction(
            "save_config",
            {
              plc_name: this.shadowRoot.querySelector("#cfg-plc-name")?.value || "PLC",
              communication_mode: this.shadowRoot.querySelector("#cfg-communication-mode")?.value || "sscp",
              host: this.shadowRoot.querySelector("#cfg-host")?.value || "",
              port: this.shadowRoot.querySelector("#cfg-port")?.value || "12346",
              username: this.shadowRoot.querySelector("#cfg-username")?.value || "",
              password: this.shadowRoot.querySelector("#cfg-password")?.value || "",
              sscp_address: this.shadowRoot.querySelector("#cfg-address")?.value || "0x01",
              webpanel_connection: this.shadowRoot.querySelector("#cfg-webpanel-connection")?.value || "defaultConnection",
              webpanel_scheme: this.shadowRoot.querySelector("#cfg-webpanel-scheme")?.value || "http",
              scan_interval: Number(this.shadowRoot.querySelector("#cfg-scan")?.value || 5),
              vlist_file_name: this.shadowRoot.querySelector("#cfg-vlist")?.value || "",
              configuration_mode: "vlist",
            },
            { refreshBrowser: true },
          );
          return;
        }

        if (action === "upload-vlist") {
          try {
            const payload = await this._readUploadForm();
            const result = await this._runAction("upload_vlist", payload, { refreshBrowser: true });
            const vlistSelect = this.shadowRoot.querySelector("#cfg-vlist");
            if (result?.file_name && vlistSelect) {
              vlistSelect.value = result.file_name;
            }
          } catch (error) {
            this._error = error.message || String(error);
            this._render();
          }
          return;
        }

        if (action === "add-manual-variable") {
          await this._runAction("add_manual_variable", this._readManualForm(), { refreshBrowser: true });
          return;
        }

        if (action === "sync-time") {
          await this._runAction("sync_time");
          return;
        }

        if (action === "set-plc-time") {
          this._captureUiState();
          const systemTime = this._systemTimeFormState();
          await this._runAction("set_plc_time", {
            mode: systemTime.mode || "local",
            value: systemTime.value || "",
          });
          return;
        }

        if (action === "reload-from-vlist") {
          await this._runAction("reload_from_vlist", {}, { refreshBrowser: true });
          return;
        }

        if (action === "delete-variable") {
          await this._runAction("delete_variable", { variable_entry_key: node.dataset.key }, { refreshBrowser: true });
          return;
        }

        if (action === "edit-variable") {
          this._captureUiState();
          this._openVariableEditor(node.dataset.key || "");
          return;
        }

        if (action === "edit-climate-entity") {
          this._captureUiState();
          const climate = (this._activeEntry?.climate_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (climate) {
            await this._openClimatePopup(climate);
          }
          return;
        }

        if (action === "edit-light-entity") {
          this._captureUiState();
          const light = (this._activeEntry?.light_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (light) {
            await this._openLightPopup(light);
          }
          return;
        }

        if (action === "edit-fan-entity") {
          this._captureUiState();
          const fan = (this._activeEntry?.fan_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (fan) {
            await this._openFanPopup(fan);
          }
          return;
        }

        if (action === "edit-humidifier-entity") {
          this._captureUiState();
          const entity = (this._activeEntry?.humidifier_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (entity) {
            await this._openHumidifierPopup(entity);
          }
          return;
        }

        if (action === "edit-water-heater-entity") {
          this._captureUiState();
          const entity = (this._activeEntry?.water_heater_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (entity) {
            await this._openWaterHeaterPopup(entity);
          }
          return;
        }

        if (action === "edit-cover-entity") {
          this._captureUiState();
          const cover = (this._activeEntry?.cover_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (cover) {
            await this._openCoverPopup(cover);
          }
          return;
        }

        if (action === "edit-lock-entity") {
          this._captureUiState();
          const entity = (this._activeEntry?.lock_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (entity) {
            await this._openLockPopup(entity);
          }
          return;
        }

        if (action === "edit-valve-entity") {
          this._captureUiState();
          const entity = (this._activeEntry?.valve_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (entity) {
            await this._openValvePopup(entity);
          }
          return;
        }

        if (action === "edit-siren-entity") {
          this._captureUiState();
          const entity = (this._activeEntry?.siren_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (entity) {
            await this._openSirenPopup(entity);
          }
          return;
        }

        if (action === "edit-vacuum-entity") {
          this._captureUiState();
          const vacuum = (this._activeEntry?.vacuum_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (vacuum) {
            await this._openVacuumPopup(vacuum);
          }
          return;
        }

        if (action === "edit-scheduler-entity") {
          this._captureUiState();
          const schedulerEntity = (this._activeEntry?.scheduler_entities || []).find((item) => item.entity_key === node.dataset.key);
          if (schedulerEntity) {
            this._openSchedulerEntityPopup(schedulerEntity, schedulerEntity.root_name || "");
          }
          return;
        }

        if (action === "delete-climate-entity") {
          await this._runAction("delete_climate_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "delete-light-entity") {
          await this._runAction("delete_light_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "delete-fan-entity") {
          await this._runAction("delete_fan_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "delete-humidifier-entity") {
          await this._runAction("delete_humidifier_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "delete-water-heater-entity") {
          await this._runAction("delete_water_heater_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "delete-cover-entity") {
          await this._runAction("delete_cover_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "delete-lock-entity") {
          await this._runAction("delete_lock_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "delete-valve-entity") {
          await this._runAction("delete_valve_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "delete-siren-entity") {
          await this._runAction("delete_siren_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "delete-vacuum-entity") {
          await this._runAction("delete_vacuum_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "delete-scheduler-entity") {
          await this._runAction("delete_scheduler_entity", { entity_key: node.dataset.key || "" });
          return;
        }

        if (action === "scheduler-add-point") {
          this._captureUiState();
          const day = Number(node.dataset.day || 0);
          if ((this._schedulerPopup.weekly_items || []).length >= Number(this._schedulerPopup.point_capacity || 0)) {
            this._schedulerPopup = {
              ...this._schedulerPopup,
              error: `Scheduler uz ma maximalni pocet ${this._schedulerPopup.point_capacity} bodu.`,
            };
            this._render();
            return;
          }
          this._schedulerPopup = {
            ...this._schedulerPopup,
            weekly_items: [
              ...(this._schedulerPopup.weekly_items || []),
              {
                index: `${Date.now()}-${day}`,
                day,
                minute_of_day: 360,
                value: this._schedulerPopup.kind === "bool" ? false : 0,
              },
            ],
            error: "",
          };
          this._render();
          return;
        }

        if (action === "scheduler-remove-point") {
          this._captureUiState();
          const itemId = node.dataset.itemId || "";
          this._schedulerPopup = {
            ...this._schedulerPopup,
            weekly_items: (this._schedulerPopup.weekly_items || []).filter((item) => {
              const currentId = `${item.day}-${item.index ?? item.starttime ?? item.minute_of_day}`;
              return currentId !== itemId;
            }),
            error: "",
          };
          this._render();
          return;
        }

        if (action === "apply-filter") {
          await this._applyTreeFilter();
          return;
        }

        if (action === "toggle-tree-folder") {
          await this._toggleTreeFolder(this._pathFromKey(node.dataset.path || ""));
          return;
        }

        if (action === "tree-add-variable") {
          const variableName = node.dataset.variable;
          const selector = `select[data-tree-variable="${CSS.escape(variableName)}"]`;
          const select = this.shadowRoot.querySelector(selector);
          const selectedEntityType = select ? select.value : undefined;
          if (select && select.value === "select") {
            this._captureUiState();
            this._openTreeSelectPopup(variableName);
            return;
          }
          if (select && select.value === "number") {
            this._captureUiState();
            this._openTreeNumberPopup(variableName);
            return;
          }
          if (select && select.value === "sensor") {
            this._captureUiState();
            this._openTreeSensorPopup(variableName);
            return;
          }
          if (selectedEntityType && ["switch", "button", "light", "binary_sensor", "datetime"].includes(selectedEntityType)) {
            this._captureUiState();
            this._openTreeBasicPopup(variableName, selectedEntityType);
            return;
          }

          await this._runAction(
            "add_variable",
            {
              variable_name: variableName,
              entity_type: selectedEntityType,
            },
            { refreshBrowser: true },
          );
        }
      };
    });
  }

  _syncManualEntityOptions() {
    const entry = this._activeEntry;
    const plcSelect = this.shadowRoot.querySelector("#manual-plc-type");
    const entitySelect = this.shadowRoot.querySelector("#manual-entity-type");
    if (!entry || !plcSelect || !entitySelect) {
      return;
    }

    const plcType = plcSelect.value || this._manualPlcType || this._supportedPlcTypes(entry)[0];
    const allowed = this._allowedEntityTypes(entry, plcType);
    const current = allowed.includes(entitySelect.value)
      ? entitySelect.value
      : allowed.includes(this._manualEntityType)
        ? this._manualEntityType
        : allowed[0];

    entitySelect.innerHTML = allowed
      .map(
        (entityType) =>
          `<option value="${escapeHtml(entityType)}" ${entityType === current ? "selected" : ""}>${escapeHtml(entityType)}</option>`,
      )
      .join("");

    this._manualPlcType = plcType;
    this._manualEntityType = current;
    this._syncManualFieldVisibility();
  }

  _syncCommunicationFieldVisibility() {
    const mode = this.shadowRoot.querySelector("#cfg-communication-mode")?.value || "sscp";
    const toggle = (selector, visible) => {
      const node = this.shadowRoot.querySelector(selector);
      if (node) {
        node.hidden = !visible;
      }
    };

    toggle("#cfg-sscp-address-wrapper", mode === "sscp");
    toggle("#cfg-webpanel-connection-wrapper", mode === "webpanel_api");
    toggle("#cfg-webpanel-scheme-wrapper", mode === "webpanel_api");
  }

  _syncTreeSelectOptionVisibility() {
    const selectedEntityTypes = {};
    this.shadowRoot.querySelectorAll(".tree-entity-select").forEach((node) => {
      const variableName = node.dataset.treeVariable || "";
      if (variableName) {
        selectedEntityTypes[variableName] = node.value;
      }
    });

    this.shadowRoot.querySelectorAll(".tree-select-config").forEach((node) => {
      const variableName = node.dataset.treeVariable || "";
      node.hidden =
        node.dataset.configured === "1" ||
        !["select", "number", "sensor", "switch", "button", "light", "binary_sensor", "datetime"].includes(
          selectedEntityTypes[variableName],
        );
    });
  }

  _syncManualFieldVisibility() {
    const entityType = this.shadowRoot.querySelector("#manual-entity-type")?.value || this._manualEntityType;
    const toggle = (selector, visible) => {
      const node = this.shadowRoot.querySelector(selector);
      if (node) {
        node.hidden = !visible;
      }
    };

    toggle("#manual-unit-wrapper", ["sensor", "datetime", "number"].includes(entityType));
    toggle("#manual-device-class-wrapper", ["sensor", "number"].includes(entityType));
    toggle("#manual-state-class-wrapper", entityType === "sensor");
    toggle("#manual-display-precision-wrapper", ["sensor", "number"].includes(entityType));
    toggle("#manual-area-wrapper", true);
    toggle("#manual-min-wrapper", entityType === "number");
    toggle("#manual-max-wrapper", entityType === "number");
    toggle("#manual-step-wrapper", entityType === "number");
    toggle("#manual-mode-wrapper", entityType === "number");
    toggle("#manual-press-time-wrapper", entityType === "button");
    toggle("#manual-select-options-wrapper", entityType === "select");

    const deviceClassInput = this.shadowRoot.querySelector("#manual-device-class");
    if (deviceClassInput) {
      deviceClassInput.setAttribute(
        "list",
        entityType === "number" ? "number-device-class-options" : "sensor-device-class-options",
      );
    }
  }
}

customElements.define("sscp-integration-panel", SSCPIntegrationPanel);
})();
