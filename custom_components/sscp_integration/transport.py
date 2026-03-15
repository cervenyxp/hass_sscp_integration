from __future__ import annotations

from typing import Any, Protocol

from .const import (
    COMM_MODE_SSCP,
    COMM_MODE_WEBPANEL,
    CONF_COMMUNICATION_MODE,
    CONF_WEBPANEL_CONNECTION,
    CONF_WEBPANEL_SCHEME,
)


class PLCClientProtocol(Protocol):
    host: str
    port: int
    username: str
    password: str
    connected: bool
    loggedin: bool
    right_group: int | None
    right_group_label: str
    transport_name: str

    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def login(self) -> dict[str, Any]: ...
    def capabilities(self) -> dict[str, Any]: ...
    def get_basic_info(self, *, requested_size: int = 0, start_offset: int = 0) -> dict[str, Any]: ...
    def get_plc_statistics(self) -> dict[str, Any]: ...
    def get_time(self, mode: str = "utc"): ...
    def set_time(self, value: Any, mode: str = "utc") -> None: ...
    def get_time_offset(self, mode: str = "timezone"): ...
    def sync_time(self, mode: str = "utc"): ...
    def read_variables(self, variables: list[dict[str, Any]]) -> dict[str, Any]: ...
    def write_variable(
        self,
        uid: int,
        value: Any,
        *,
        offset: int = 0,
        length: int = 0,
        type_data: str = "BYTE",
    ) -> None: ...


def communication_mode_from_data(data: dict[str, Any]) -> str:
    raw_mode = str(data.get(CONF_COMMUNICATION_MODE, COMM_MODE_SSCP) or COMM_MODE_SSCP).strip().lower()
    if raw_mode == COMM_MODE_WEBPANEL:
        return COMM_MODE_WEBPANEL
    return COMM_MODE_SSCP


def has_connection_settings(data: dict[str, Any]) -> bool:
    mode = communication_mode_from_data(data)
    host_ready = bool(data.get("host") and data.get("port"))
    if mode == COMM_MODE_WEBPANEL:
        return host_ready
    return bool(host_ready and data.get("username") and data.get("sscp_address"))


def build_client_from_entry_data(data: dict[str, Any]) -> PLCClientProtocol:
    mode = communication_mode_from_data(data)
    if mode == COMM_MODE_WEBPANEL:
        from .webpanel_client import WebPanelClient

        return WebPanelClient(
            host=data["host"],
            port=data["port"],
            username=data.get("username", ""),
            password=data.get("password", ""),
            name_plc=data.get("PLC_Name", "PLC"),
            scheme=data.get(CONF_WEBPANEL_SCHEME, "http"),
            connection_name=data.get(CONF_WEBPANEL_CONNECTION, "defaultConnection"),
        )

    from .sscp_client import SSCPClient

    return SSCPClient(
        data["host"],
        data["port"],
        data["username"],
        data.get("password", ""),
        data["sscp_address"],
        data.get("PLC_Name", "PLC"),
    )
