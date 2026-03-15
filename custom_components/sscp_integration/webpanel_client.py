from __future__ import annotations

from datetime import datetime
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from .const import DEFAULT_SOCKET_TIMEOUT
from .sscp_client import TYPE_LENGTHS, datetime_to_ticks, ticks_to_datetime

_LOGGER = logging.getLogger(__name__)


class WebPanelError(Exception):
    """Base error for WebPanel API operations."""


class WebPanelConnectionError(WebPanelError):
    """Raised when the WebPanel endpoint cannot be reached."""


class WebPanelCommandError(WebPanelError):
    """Raised when the WebPanel API returns a non-ok code."""


class WebPanelClient:
    transport_name = "webpanel_api"

    def __init__(
        self,
        *,
        host: str,
        port: int | str,
        username: str,
        password: str,
        name_plc: str,
        scheme: str = "http",
        connection_name: str = "defaultConnection",
    ) -> None:
        self.host = str(host).strip()
        self.port = int(port)
        self.username = username
        self.password = password
        self.name_plc = name_plc
        self.scheme = str(scheme or "http").strip().lower()
        self.connection_name = str(connection_name or "defaultConnection").strip() or "defaultConnection"

        self.connected = False
        self.loggedin = False
        self.right_group: int | None = None
        self._session_credentials: dict[str, Any] | None = None

    @property
    def base_url(self) -> str:
        raw = self.host.rstrip("/")
        if raw.startswith(("http://", "https://")):
            parsed = urlparse(raw)
            if parsed.port is not None:
                return raw
            hostname = parsed.hostname or parsed.netloc
            netloc = f"{hostname}:{self.port}" if hostname else parsed.netloc
            return urlunparse((parsed.scheme, netloc, parsed.path.rstrip("/"), "", "", ""))
        return f"{self.scheme}://{raw}:{self.port}"

    @property
    def right_group_label(self) -> str:
        return "WebPanel API"

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False
        self.loggedin = False
        self._session_credentials = None

    def _request_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=DEFAULT_SOCKET_TIMEOUT) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as err:
            detail = err.read().decode("utf-8", errors="ignore")
            raise WebPanelConnectionError(f"HTTP {err.code} for {endpoint}: {detail or err.reason}") from err
        except URLError as err:
            raise WebPanelConnectionError(str(err.reason)) from err

        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as err:
            raise WebPanelError(f"Neplatna JSON odpoved z {endpoint}.") from err

        if decoded.get("code") not in (None, "ok"):
            raise WebPanelCommandError(str(decoded.get("message") or decoded.get("code")))
        return decoded

    def login(self) -> dict[str, Any]:
        self.connect()

        payload: dict[str, Any] = {"ver": 1}
        if self.username or self.password:
            payload["c"] = {"u": self.username, "p": self.password}

        response = self._request_json("login.cgi", payload)
        credentials = response.get("c")
        if isinstance(credentials, dict):
            self._session_credentials = credentials
        elif self.username or self.password:
            self._session_credentials = {"u": self.username, "p": self.password}
        else:
            self._session_credentials = None

        self.loggedin = True
        return self.capabilities()

    def _authorized_payload(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        result = {"ver": 1, **(payload or {})}
        if self._session_credentials is not None:
            result["c"] = self._session_credentials
        return result

    def capabilities(self) -> dict[str, Any]:
        return {
            "protocol_version": "WebPanel API",
            "transport": self.transport_name,
            "server_max_data_size": None,
            "client_max_data_size": None,
            "right_group": self.right_group,
            "right_group_label": self.right_group_label,
            "image_guid": None,
            "device_tags": {
                "base_url": self.base_url,
                "connection_name": self.connection_name,
                "authenticated": bool(self._session_credentials),
            },
        }

    def get_basic_info(self, *, requested_size: int = 0, start_offset: int = 0) -> dict[str, Any]:
        return {
            "transport": "WebPanel API",
            "requested_size": requested_size,
            "start_offset": start_offset,
            "base_url": self.base_url,
            "connection_name": self.connection_name,
            "authenticated": bool(self._session_credentials),
        }

    def get_plc_statistics(self) -> dict[str, Any]:
        return {
            "runtime": {
                "evaluator_state_label": "WebPanel API",
                "run_mode_label": "HTTP polling",
            },
            "memory": {},
        }

    def get_time(self, mode: str = "utc"):
        raise NotImplementedError("WebPanel API neumi cteni PLC casu v teto integraci.")

    def set_time(self, value: datetime, mode: str = "utc") -> None:
        raise NotImplementedError("WebPanel API neumi nastaveni PLC casu v teto integraci.")

    def get_time_offset(self, mode: str = "timezone"):
        raise NotImplementedError("WebPanel API neumi cteni offsetu casu v teto integraci.")

    def sync_time(self, mode: str = "utc"):
        raise NotImplementedError("WebPanel API neumi synchronizaci PLC casu v teto integraci.")

    def _resolved_length(self, variable: dict[str, Any]) -> int:
        raw_type = str(variable.get("type", "BYTE")).upper()
        requested = variable.get("length")
        if requested not in (None, 0, "0", ""):
            return int(requested)
        if raw_type not in TYPE_LENGTHS:
            raise ValueError(f"Nepodporovany typ {raw_type}")
        return TYPE_LENGTHS[raw_type]

    def _build_variable_id(self, variable: dict[str, Any]) -> str:
        uid = int(variable["uid"])
        offset = int(variable.get("offset", 0))
        length = self._resolved_length(variable)
        return f"svc://{self.connection_name}/{uid}[{offset},{length}]"

    def _decode_value(self, raw_hex: str, type_data: str) -> Any:
        raw_data = bytes.fromhex(raw_hex)
        type_name = str(type_data).upper()

        if type_name == "BOOL":
            return raw_data[0] != 0
        if type_name == "BYTE":
            return raw_data[0] if len(raw_data) == 1 else raw_data.hex()
        if type_name == "WORD":
            return int.from_bytes(raw_data, byteorder="big", signed=False)
        if type_name == "INT":
            return int.from_bytes(raw_data, byteorder="big", signed=True)
        if type_name == "UINT":
            return int.from_bytes(raw_data, byteorder="big", signed=False)
        if type_name == "DINT":
            return int.from_bytes(raw_data, byteorder="big", signed=True)
        if type_name == "UDINT":
            return int.from_bytes(raw_data, byteorder="big", signed=False)
        if type_name == "LINT":
            return int.from_bytes(raw_data, byteorder="big", signed=True)
        if type_name == "REAL":
            import struct

            return struct.unpack(">f", raw_data)[0]
        if type_name == "LREAL":
            import struct

            return struct.unpack(">d", raw_data)[0]
        if type_name == "DT":
            return ticks_to_datetime(int.from_bytes(raw_data, byteorder="big", signed=False))
        raise ValueError(f"Nepodporovany typ {type_name}")

    def _command_value(self, value: Any, type_data: str) -> Any:
        type_name = str(type_data).upper()
        if type_name == "BOOL":
            return 1 if bool(value) else 0
        if type_name in {"BYTE", "WORD", "INT", "UINT", "DINT", "UDINT", "LINT"}:
            return int(value)
        if type_name in {"REAL", "LREAL"}:
            return float(value)
        if type_name == "DT":
            return int(datetime_to_ticks(value if isinstance(value, datetime) else value))
        return value

    def read_variables(self, variables: list[dict[str, Any]]) -> dict[str, Any]:
        if not self.loggedin:
            self.login()

        results: dict[str, Any] = {}
        for start in range(0, len(variables), 64):
            chunk = variables[start : start + 64]
            ids = [self._build_variable_id(variable) for variable in chunk]
            response = self._request_json("values.cgi", self._authorized_payload({"v": ids}))
            values = response.get("v", [])
            value_by_id = {
                str(item.get("i")): item
                for item in values
                if isinstance(item, dict) and item.get("i") is not None
            }

            for variable, variable_id in zip(chunk, ids, strict=True):
                item = value_by_id.get(variable_id)
                if item is None:
                    raise WebPanelError(f"WebPanel API nevratilo hodnotu pro {variable_id}.")
                if item.get("e"):
                    raise WebPanelError(f"WebPanel API chyba pro {variable_id}: {item['e']}")
                key = str(
                    variable.get("key")
                    or variable.get("name_vlist")
                    or variable.get("name")
                    or f"{variable['uid']}:{variable.get('offset', 0)}"
                )
                results[key] = self._decode_value(str(item.get("v", "")), str(variable["type"]))

        return results

    def write_variable(
        self,
        uid: int,
        value: Any,
        *,
        offset: int = 0,
        length: int = 0,
        type_data: str = "BYTE",
    ) -> None:
        if not self.loggedin:
            self.login()

        variable = {
            "uid": uid,
            "offset": offset,
            "length": length,
            "type": type_data,
        }
        command_value = self._command_value(value, type_data)
        command: dict[str, Any] = {
            "i": self._build_variable_id(variable),
            "set": command_value,
        }
        if str(type_data).upper() == "BOOL":
            command["defaultValue"] = 1 if command_value else 0
            command["time"] = "0"

        self._request_json("command.cgi", self._authorized_payload({"v": [command]}))
        _LOGGER.debug("WebPanel write %s=%s", command["i"], command_value)
