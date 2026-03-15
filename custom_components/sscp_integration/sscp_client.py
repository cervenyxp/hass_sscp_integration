from __future__ import annotations

import binascii
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import logging
import socket
import struct
import threading
from typing import Any, Sequence

from .const import (
    DEFAULT_CLIENT_MAX_DATA_SIZE,
    DEFAULT_PROTOCOL_VERSION,
    DEFAULT_SOCKET_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

TYPE_LENGTHS = {
    "BOOL": 1,
    "BYTE": 1,
    "WORD": 2,
    "INT": 2,
    "UINT": 2,
    "DINT": 4,
    "UDINT": 4,
    "LINT": 8,
    "REAL": 4,
    "LREAL": 8,
    "DT": 8,
}

RIGHT_GROUPS = {
    0x10: "Read only",
    0x80: "Full control",
    0xFF: "Engineering",
}

ERROR_CODES = {
    0x0000: "NoError",
    0x0001: "NoResponse",
    0x0002: "FailedToConnect",
    0x0003: "NotImplemented",
    0x0004: "InvalidFunctionReceived",
    0x0101: "WrongLogin",
    0x0102: "NoSuchFile",
    0x0103: "NoSuchVariable",
    0x0104: "NoSuchTask",
    0x0105: "WrongOrder",
    0x0106: "WrongParameter",
    0x0107: "InvalidGroupId",
    0x0108: "TransmissionInProgress",
    0x0109: "NotRegistered",
    0x010A: "WriteFailed",
    0x010B: "NotAllDataReceived",
    0x010C: "InvalidCrc",
    0x010D: "DataTooLong",
    0x010E: "TooLongUseFileTransfer",
    0x010F: "FileNameTooLong",
    0x0110: "VariableCountLimitExceed",
    0x0111: "OutOfBounds",
    0x0112: "SizeMismatch",
    0x0113: "OperationDenied",
    0x0114: "NotLogged",
    0x0115: "InvalidState",
    0x0116: "UnknownChannel",
    0x0117: "DriverCommandTimeout",
    0x0118: "UnknownDriverCommand",
    0x0119: "NoResourcesAvailable",
    0x011A: "ChunkReadFailed",
    0x011B: "ChunkWriteFailed",
    0x011C: "NoSuchMetadata",
    0x011D: "Async",
    0x0801: "SysCmd_NewImage",
    0x0802: "SysCmd_InvalidImageArea",
    0x0803: "SysCmd_CreateBootImage",
    0x0804: "SysCmd_WarmReboot",
    0x0805: "SysCmd_ColdReboot",
    0x0806: "SysCmd_StartPlc",
    0x0807: "SysCmd_StopPlc",
    0x0808: "SysCmd_SetMacAddress",
    0x0809: "SysCmd_Timeout",
    0x080A: "AlreadyRunning",
    0x080B: "AlreadyStopped",
    0x080C: "SysCmdRequestActive",
    0x080D: "SysCmdWaitTimeout",
}

EVALUATOR_STATES = {
    0: "Stopped",
    1: "RunningNormalTasks",
    2: "StoppingExecution",
    3: "RunningExceptionStateTask",
    4: "ExceptionStateTaskFailed",
    5: "NoExceptionStateTaskDefined",
    6: "Commissioning",
    7: "InvalidImage",
    8: "NoImage",
    9: "WaitingForDebugger",
    10: "PreparedForStart",
}

RUN_MODES = {
    0: "FullRun",
    1: "CommunicationOnly",
    2: "EvaluationOnly",
    3: "Commissioning",
    4: "CommunicationsWithTransform",
    5: "PrepareOnly",
    32: "StartDisabledBySwitch",
    33: "InvalidImageVersion",
    34: "NoMemoryForImage",
}

CLIENT_STATUSES = {
    0: "Disabled",
    1: "NotUsed",
    2: "Idle",
    3: "Connected",
    4: "Unauthorized",
    5: "NotAvailable",
    6: "FailedToConnect",
    7: "HostNotFound",
    8: "Connecting",
    9: "PageNotFound",
    10: "DbError",
}


@dataclass(frozen=True)
class SSCPResponse:
    address: int
    function_id: int
    data: bytes


class SSCPError(Exception):
    """Base SSCP error."""


class SSCPConnectionError(SSCPError):
    """Raised on connection issues."""


class SSCPProtocolError(SSCPError):
    """Raised when the protocol response is malformed."""


class SSCPCommandError(SSCPError):
    """Raised when the PLC returns a command-specific error."""

    def __init__(
        self,
        function_id: int,
        error_code: int | None,
        message: str,
        *,
        optional_data: bytes = b"",
    ) -> None:
        super().__init__(message)
        self.function_id = function_id
        self.error_code = error_code
        self.message = message
        self.optional_data = optional_data


def _parse_address(value: str | int) -> int:
    if isinstance(value, int):
        return value
    raw = str(value).strip().lower()
    if raw.startswith("0x"):
        return int(raw, 16)
    return int(raw)


def _format_guid(raw: bytes) -> str:
    if len(raw) != 16:
        return raw.hex()
    hexed = raw.hex()
    return (
        f"{hexed[0:8]}-{hexed[8:12]}-{hexed[12:16]}-"
        f"{hexed[16:20]}-{hexed[20:32]}"
    )


def datetime_to_ticks(value: datetime | int | float) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    value = value.astimezone(UTC)
    epoch = datetime(1, 1, 1, tzinfo=UTC)
    delta = value - epoch
    return int(delta.total_seconds() * 10_000_000)


def ticks_to_datetime(value: int | None) -> datetime | None:
    if value is None:
        return None
    epoch = datetime(1, 1, 1, tzinfo=UTC)
    return epoch + timedelta(microseconds=value / 10)


def ticks_to_timedelta(value: int) -> timedelta:
    return timedelta(microseconds=value / 10)


def crc16(data: bytes) -> int:
    return binascii.crc_hqx(data, 0xFFFF)


def fnv1_32(value: str) -> int:
    result = 0x811C9DC5
    for byte in value.encode("utf-8"):
        result = (result * 0x01000193) & 0xFFFFFFFF
        result ^= byte
    return result


def _read_u16(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from(">H", data, offset)[0], offset + 2


def _read_u32(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from(">I", data, offset)[0], offset + 4


def _read_u64(data: bytes, offset: int) -> tuple[int, int]:
    return struct.unpack_from(">Q", data, offset)[0], offset + 8


def _decode_best_effort_text(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-16-le", "utf-16-be", "latin-1"):
        try:
            return raw.decode(encoding).rstrip("\x00")
        except UnicodeDecodeError:
            continue
    return raw.hex()


class SSCPClient:
    def __init__(
        self,
        host: str,
        port: int | str,
        username: str,
        password: str,
        sscp_address: str | int,
        name_plc: str,
    ) -> None:
        self.host = str(host)
        self.port = int(port)
        self.username = username
        self.password = password
        self.sscp_address = _parse_address(sscp_address)
        self.name_plc = name_plc

        self.socket: socket.socket | None = None
        self.connected = False
        self.loggedin = False

        self.protocol_version = DEFAULT_PROTOCOL_VERSION
        self.client_max_data_size = DEFAULT_CLIENT_MAX_DATA_SIZE
        self.server_max_data_size = DEFAULT_CLIENT_MAX_DATA_SIZE
        self.right_group: int | None = None
        self.image_guid: str | None = None
        self.device_tags: dict[str, Any] = {}
        self._lock = threading.RLock()

    @property
    def max_data_size(self) -> int:
        return min(self.client_max_data_size, self.server_max_data_size)

    @property
    def right_group_label(self) -> str:
        if self.right_group is None:
            return "Unknown"
        return RIGHT_GROUPS.get(self.right_group, f"0x{self.right_group:02X}")

    def connect(self) -> None:
        with self._lock:
            if self.connected and self.socket is not None:
                return
            _LOGGER.debug("Connecting to SSCP server at %s:%s", self.host, self.port)
            self.socket = socket.create_connection(
                (self.host, self.port),
                timeout=DEFAULT_SOCKET_TIMEOUT,
            )
            self.socket.settimeout(DEFAULT_SOCKET_TIMEOUT)
            self.connected = True
            self.loggedin = False

    def disconnect(self) -> None:
        with self._lock:
            if self.socket is not None:
                try:
                    self.socket.close()
                except OSError:
                    pass
            self.socket = None
            self.connected = False
            self.loggedin = False

    def reconnect(self) -> None:
        with self._lock:
            self.disconnect()
            self.connect()
            self.login()

    def ensure_connected(self) -> None:
        if not self.connected or self.socket is None:
            self.connect()
        if not self.loggedin:
            self.login()

    def _require_socket(self) -> socket.socket:
        if self.socket is None:
            raise SSCPConnectionError("Socket is not connected.")
        return self.socket

    def _recv_exact(self, size: int) -> bytes:
        sock = self._require_socket()
        chunks = bytearray()
        while len(chunks) < size:
            chunk = sock.recv(size - len(chunks))
            if not chunk:
                raise SSCPConnectionError("Connection closed by remote host.")
            chunks.extend(chunk)
        return bytes(chunks)

    def _read_frame(self) -> SSCPResponse:
        address = self._recv_exact(1)[0]
        header = self._recv_exact(4)
        function_id, data_length = struct.unpack(">HH", header)
        data = self._recv_exact(data_length)
        return SSCPResponse(address=address, function_id=function_id, data=data)

    def _send_frame(
        self,
        function_id: int,
        data: bytes = b"",
        *,
        expect_response: bool = True,
        require_login: bool = True,
    ) -> SSCPResponse | None:
        attempts = 2 if require_login else 1
        last_error: Exception | None = None

        for attempt in range(attempts):
            with self._lock:
                if require_login:
                    self.ensure_connected()
                elif not self.connected or self.socket is None:
                    self.connect()

                frame = bytearray()
                frame.append(self.sscp_address)
                frame.extend(struct.pack(">HH", function_id, len(data)))
                frame.extend(data)

                try:
                    self._require_socket().sendall(frame)
                    if not expect_response:
                        return None
                    response = self._read_frame()
                    self._validate_response(function_id, response)
                    return response
                except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError) as err:
                    last_error = err
                    self.disconnect()
                    if attempt + 1 < attempts:
                        continue
                    raise SSCPConnectionError(str(err)) from err

        if last_error is not None:
            raise SSCPConnectionError(str(last_error)) from last_error
        raise SSCPConnectionError("Unable to communicate with PLC.")

    def _validate_response(self, function_id: int, response: SSCPResponse) -> None:
        if response.address != self.sscp_address:
            raise SSCPProtocolError(
                f"Response address mismatch: expected {self.sscp_address}, got {response.address}"
            )

        if response.function_id == 0xFFFF:
            raise SSCPCommandError(function_id, None, "Insufficient rights", optional_data=response.data)
        if response.function_id == 0xFFFE:
            raise SSCPCommandError(function_id, None, "Invalid function", optional_data=response.data)
        if response.function_id == 0xFFFD:
            raise SSCPCommandError(function_id, None, "Invalid protocol version", optional_data=response.data)

        if response.function_id == (function_id | 0xC000):
            if len(response.data) < 4:
                raise SSCPProtocolError("Command-specific error response is too short.")
            error_code = struct.unpack(">I", response.data[:4])[0]
            error_name = ERROR_CODES.get(error_code, f"0x{error_code:04X}")
            raise SSCPCommandError(
                function_id,
                error_code,
                f"{error_name} (0x{error_code:04X})",
                optional_data=response.data[4:],
            )

        expected_response = function_id | 0x8000
        if response.function_id != expected_response:
            raise SSCPProtocolError(
                f"Unexpected function id 0x{response.function_id:04X}, expected 0x{expected_response:04X}"
            )

    def login(self) -> dict[str, Any]:
        username_bytes = self.username.encode("utf-8")
        password_hash = hashlib.md5(self.password.encode("utf-8")).digest()

        payload = bytearray()
        payload.append(DEFAULT_PROTOCOL_VERSION)
        payload.extend(struct.pack(">H", self.client_max_data_size))
        payload.append(len(username_bytes))
        payload.extend(username_bytes)
        payload.append(len(password_hash))
        payload.extend(password_hash)
        payload.append(0x00)

        response = self._send_frame(0x0100, bytes(payload), require_login=False)
        if response is None:
            raise SSCPProtocolError("Missing login response.")

        data = response.data
        if len(data) < 20:
            raise SSCPProtocolError("Login response is shorter than expected.")

        self.protocol_version = data[0]
        self.server_max_data_size = struct.unpack_from(">H", data, 1)[0]
        self.right_group = data[3]
        self.image_guid = _format_guid(data[4:20])
        self.device_tags = self._parse_login_tags(data[20:])
        self.loggedin = True

        return {
            "protocol_version": self.protocol_version,
            "server_max_data_size": self.server_max_data_size,
            "right_group": self.right_group,
            "right_group_label": self.right_group_label,
            "image_guid": self.image_guid,
            "device_tags": self.device_tags,
        }

    def logout(self) -> None:
        if not self.connected:
            return
        try:
            self._send_frame(0x0101, expect_response=False)
        finally:
            self.disconnect()

    def _parse_login_tags(self, data: bytes) -> dict[str, Any]:
        tags: dict[str, Any] = {}
        if not data or data[0] != 0x3E:
            return tags

        index = 1
        while index < len(data):
            tag = data[index]
            index += 1
            if tag == 0x3F:
                break
            if tag == 0x02 and index + 1 <= len(data):
                tags["sscp_address"] = data[index]
                index += 1
                continue
            if tag == 0x03 and index + 4 <= len(data):
                tags["image_build_id"] = struct.unpack_from(">I", data, index)[0]
                index += 4
                continue
            if tag == 0x04 and index + 2 <= len(data):
                tags["tcp_port"] = struct.unpack_from(">H", data, index)[0]
                index += 2
                continue
            if tag == 0x05 and index + 2 <= len(data):
                tags["ssl_port"] = struct.unpack_from(">H", data, index)[0]
                index += 2
                continue
            if tag == 0x01:
                end = data.find(b"\x00", index)
                if end == -1:
                    end = len(data)
                tags["device_name"] = _decode_best_effort_text(data[index:end])
                index = end + 1
                continue
            tags[f"tag_{tag}"] = data[index:].hex()
            break
        return tags

    def _parse_runtime_version(self, raw: bytes) -> dict[str, Any]:
        if len(raw) != 4:
            return {"raw": raw.hex()}
        packed = struct.unpack(">I", raw)[0]
        return {
            "major": (packed >> 29) & 0x07,
            "minor": (packed >> 26) & 0x07,
            "day": (packed >> 21) & 0x1F,
            "month": (packed >> 17) & 0x0F,
            "revision": packed & 0x1FFFF,
            "raw": packed,
        }

    def _parse_utf16_zero_terminated(self, data: bytes, offset: int) -> tuple[str, int]:
        end = offset
        while end + 1 < len(data):
            if data[end : end + 2] == b"\x00\x00":
                break
            end += 2
        raw = data[offset:end]
        for encoding in ("utf-16-be", "utf-16-le"):
            try:
                return raw.decode(encoding), min(end + 2, len(data))
            except UnicodeDecodeError:
                continue
        return raw.hex(), min(end + 2, len(data))

    def _parse_basic_info_tags(self, data: bytes) -> dict[str, Any]:
        tags: dict[str, Any] = {}
        if not data or data[0] != 0x3E:
            return tags

        index = 1
        while index < len(data):
            tag = data[index]
            index += 1
            if tag == 0x3F:
                break
            if tag == 0x01:
                tags["device_name"], index = self._parse_utf16_zero_terminated(data, index)
                continue
            if tag == 0x02 and index + 1 <= len(data):
                tags["sscp_address"] = data[index]
                index += 1
                continue
            if tag == 0x04 and index + 2 <= len(data):
                tags["tcp_port"] = struct.unpack_from(">H", data, index)[0]
                index += 2
                continue
            if tag == 0x05 and index + 2 <= len(data):
                tags["ssl_port"] = struct.unpack_from(">H", data, index)[0]
                index += 2
                continue
            tags[f"tag_{tag}"] = data[index:].hex()
            break
        return tags

    def get_basic_info(self, *, requested_size: int = 0, start_offset: int = 0) -> dict[str, Any]:
        username_bytes = self.username.encode("utf-8")
        password_hash = hashlib.md5(self.password.encode("utf-8")).digest()

        payload = bytearray()
        payload.append(0x01)
        payload.append(0x00)
        payload.append(len(username_bytes))
        payload.extend(username_bytes)
        payload.append(len(password_hash))
        payload.extend(password_hash)
        payload.extend(struct.pack(">HH", start_offset, requested_size))

        response = self._send_frame(
            0x0000,
            bytes(payload),
            require_login=requested_size != 0,
        )
        if response is None:
            raise SSCPProtocolError("Missing basic info response.")

        data = response.data
        index = 0
        config_size, index = _read_u16(data, index)
        serial_length = data[index]
        index += 1
        serial_number = data[index : index + serial_length]
        index += serial_length
        endianness = data[index]
        index += 1
        platform_id, index = _read_u32(data, index)
        runtime_length = data[index]
        index += 1
        runtime_raw = data[index : index + runtime_length]
        index += runtime_length
        info_tags = self._parse_basic_info_tags(data[index:])

        return {
            "config_size": config_size,
            "serial_number_hex": serial_number.hex(),
            "endianness": "big" if endianness else "little",
            "platform_id": platform_id,
            "runtime_version": self._parse_runtime_version(runtime_raw),
            "info_tags": info_tags,
        }

    def _parse_plc_statistics(self, data: bytes) -> dict[str, Any]:
        if not data:
            return {}

        index = 0
        statistics_version = data[index]
        index += 1
        result: dict[str, Any] = {"statistics_version": statistics_version}

        while index + 4 <= len(data):
            block_type = data[index]
            block_version = data[index + 1]
            block_length = struct.unpack_from(">H", data, index + 2)[0]
            index += 4
            block = data[index : index + block_length]
            index += block_length

            if block_type == 0 and len(block) >= 28:
                uptime = struct.unpack_from(">Q", block, 4)[0]
                result["runtime"] = {
                    "block_version": block_version,
                    "normal_tasks_count": block[0],
                    "max_task_id": block[1],
                    "evaluator_state": block[2],
                    "evaluator_state_label": EVALUATOR_STATES.get(block[2], str(block[2])),
                    "run_mode": block[3],
                    "run_mode_label": RUN_MODES.get(block[3], str(block[3])),
                    "uptime_raw": uptime,
                    "uptime": str(ticks_to_timedelta(uptime)),
                    "running_tasks_mask": struct.unpack_from(">Q", block, 12)[0],
                    "tasks_with_exception_mask": struct.unpack_from(">Q", block, 20)[0],
                }
            elif block_type == 1 and len(block) >= 16:
                values = struct.unpack(">8H", block[:16])
                result["memory"] = {
                    "block_version": block_version,
                    "total_heap_kb": values[0],
                    "free_heap_before_load_kb": values[1],
                    "free_heap_kb": values[2],
                    "total_code_space_kb": values[3],
                    "free_code_space_kb": values[4],
                    "retain_size_kb": values[5],
                    "allocator_total_size_kb": values[6],
                    "allocator_free_space_kb": values[7],
                }
            elif block_type == 2 and len(block) >= 6:
                vmex, rtcm, other = struct.unpack(">3H", block[:6])
                result["sections"] = {
                    "block_version": block_version,
                    "vmex_kb": vmex,
                    "rtcm_kb": rtcm,
                    "other_kb": other,
                }
            elif block_type == 3 and len(block) >= 21:
                result["rcware_db"] = {
                    "block_version": block_version,
                    "client_status": block[0],
                    "client_status_label": CLIENT_STATUSES.get(block[0], str(block[0])),
                    "records_saved": struct.unpack_from(">I", block, 1)[0],
                    "last_save_time": ticks_to_datetime(struct.unpack_from(">Q", block, 5)[0]),
                    "last_request_time": ticks_to_datetime(struct.unpack_from(">Q", block, 13)[0]),
                }
            elif block_type == 4 and len(block) >= 23:
                proxy_id_raw = block[1:21]
                result["proxy"] = {
                    "block_version": block_version,
                    "proxy_status": block[0],
                    "proxy_status_label": CLIENT_STATUSES.get(block[0], str(block[0])),
                    "proxy_id": proxy_id_raw.rstrip(b"\x00").decode("utf-8", errors="ignore"),
                    "slots_total": block[21],
                    "slots_free": block[22],
                }
            else:
                result.setdefault("unknown_blocks", []).append(
                    {
                        "block_type": block_type,
                        "block_version": block_version,
                        "data_hex": block.hex(),
                    }
                )

        return result

    def get_plc_statistics(self) -> dict[str, Any]:
        response = self._send_frame(0x0300)
        if response is None:
            return {}
        return self._parse_plc_statistics(response.data)

    def get_task_statistics(self, task_id: int) -> dict[str, Any]:
        response = self._send_frame(0x0301, bytes([task_id]))
        if response is None:
            return {}
        data = response.data
        if len(data) < 33:
            raise SSCPProtocolError("Task statistics response is too short.")

        index = 0
        version = data[index]
        index += 1
        cycle_count, index = _read_u64(data, index)
        last_cycle, index = _read_u64(data, index)
        average_cycle, index = _read_u64(data, index)
        min_cycle, index = _read_u64(data, index)
        max_cycle, index = _read_u64(data, index)

        result: dict[str, Any] = {
            "statistics_version": version,
            "cycle_count": cycle_count,
            "last_cycle_duration_raw": last_cycle,
            "average_cycle_duration_raw": average_cycle,
            "minimal_cycle_duration_raw": min_cycle,
            "maximal_cycle_duration_raw": max_cycle,
            "last_cycle_duration": str(ticks_to_timedelta(last_cycle)),
            "average_cycle_duration": str(ticks_to_timedelta(average_cycle)),
            "minimal_cycle_duration": str(ticks_to_timedelta(min_cycle)),
            "maximal_cycle_duration": str(ticks_to_timedelta(max_cycle)),
        }

        if version >= 2 and len(data) >= index + 9:
            result["waiting_for_debugger"] = bool(data[index])
            index += 1
            result["debugger_actual_uid"], index = _read_u32(data, index)
            result["debugger_actual_offset"], index = _read_u32(data, index)

        return result

    def get_channel_statistics(self, channel: str | int) -> dict[str, Any]:
        channel_id = fnv1_32(channel) if isinstance(channel, str) else int(channel)
        response = self._send_frame(0x0310, struct.pack(">I", channel_id))
        if response is None:
            return {}

        data = response.data
        if len(data) < 23:
            raise SSCPProtocolError("Channel statistics response is too short.")

        index = 0
        version = data[index]
        index += 1
        sent_packets, index = _read_u32(data, index)
        received_packets, index = _read_u32(data, index)
        wrong_packets, index = _read_u32(data, index)
        sent_bytes, index = _read_u32(data, index)
        received_bytes, index = _read_u32(data, index)
        endpoints_count, index = _read_u16(data, index)

        endpoints: list[dict[str, Any]] = []
        for _unused in range(endpoints_count):
            average_cycle, index = _read_u32(data, index)
            maximal_cycle, index = _read_u32(data, index)
            minimal_cycle, index = _read_u32(data, index)
            endpoints.append(
                {
                    "average_cycle_time_ms": average_cycle,
                    "maximal_cycle_time_ms": maximal_cycle,
                    "minimal_cycle_time_ms": minimal_cycle,
                }
            )

        return {
            "statistics_version": version,
            "channel_id": channel_id,
            "sent_packets": sent_packets,
            "received_packets": received_packets,
            "wrong_packets": wrong_packets,
            "sent_bytes": sent_bytes,
            "received_bytes": received_bytes,
            "endpoints": endpoints,
        }

    def get_time(self, mode: str = "utc") -> datetime | None:
        commands = {"utc": 0x01, "local": 0x02}
        command = commands[mode]
        response = self._send_frame(0x0604, bytes([command, 0x00]))
        if response is None or not response.data:
            return None
        return ticks_to_datetime(struct.unpack(">Q", response.data)[0])

    def get_time_offset(self, mode: str = "timezone") -> timedelta | None:
        commands = {"timezone": 0x20, "daylight": 0x21}
        command = commands[mode]
        response = self._send_frame(0x0604, bytes([command, 0x00]))
        if response is None or not response.data:
            return None
        return ticks_to_timedelta(struct.unpack(">Q", response.data)[0])

    def set_time(self, value: datetime, mode: str = "utc") -> None:
        commands = {"utc": 0x10, "local": 0x11}
        command = commands[mode]
        ticks = datetime_to_ticks(value)
        payload = bytes([command, 0x00]) + struct.pack(">Q", ticks)
        self._send_frame(0x0604, payload)

    def sync_time(self, mode: str = "utc") -> datetime:
        now = datetime.now(UTC)
        if mode == "local":
            now = now.astimezone()
        self.set_time(now, mode=mode)
        refreshed = self.get_time(mode="utc" if mode == "utc" else "local")
        return refreshed or now

    def write_file(
        self,
        file_name: str,
        data: bytes,
        *,
        timestamp: datetime | None = None,
        chunk_size: int | None = None,
    ) -> None:
        if timestamp is None:
            timestamp = datetime.now(UTC)
        file_name_bytes = file_name.encode("utf-8")

        payload = bytearray()
        payload.append(len(file_name_bytes))
        payload.extend(file_name_bytes)
        payload.extend(struct.pack(">I", len(data)))
        payload.extend(struct.pack(">Q", datetime_to_ticks(timestamp)))
        self._send_frame(0x0200, bytes(payload))

        effective_chunk = chunk_size or max(16, self.max_data_size - 4)
        offset = 0
        while offset < len(data):
            chunk = data[offset : offset + effective_chunk]
            response = self._send_frame(0x0201, struct.pack(">I", offset) + chunk)
            if response is None or len(response.data) != 4:
                raise SSCPProtocolError("Invalid send chunk acknowledgement.")
            acknowledged = struct.unpack(">I", response.data)[0]
            if acknowledged != offset:
                raise SSCPProtocolError(
                    f"Chunk acknowledgement mismatch: expected {offset}, got {acknowledged}"
                )
            offset += len(chunk)

        finish_payload = struct.pack(">H", crc16(data))
        self._send_frame(0x0202, finish_payload)

    def read_file(self, file_name: str) -> dict[str, Any]:
        file_name_bytes = file_name.encode("utf-8")
        payload = bytes([len(file_name_bytes)]) + file_name_bytes
        response = self._send_frame(0x0210, payload)
        if response is None or len(response.data) < 14:
            raise SSCPProtocolError("Invalid file receive response.")

        total_size = struct.unpack_from(">I", response.data, 0)[0]
        timestamp = ticks_to_datetime(struct.unpack_from(">Q", response.data, 4)[0])
        expected_crc = struct.unpack_from(">H", response.data, 12)[0]

        offset = 0
        received = bytearray()
        while offset < total_size:
            chunk_response = self._send_frame(0x0211, struct.pack(">I", offset))
            if chunk_response is None or len(chunk_response.data) < 4:
                raise SSCPProtocolError("Invalid file chunk response.")
            chunk_offset = struct.unpack_from(">I", chunk_response.data, 0)[0]
            if chunk_offset != offset:
                raise SSCPProtocolError(
                    f"Chunk offset mismatch: expected {offset}, got {chunk_offset}"
                )
            chunk = chunk_response.data[4:]
            if not chunk:
                break
            received.extend(chunk)
            offset += len(chunk)

        data_bytes = bytes(received[:total_size])
        actual_crc = crc16(data_bytes)
        if actual_crc != expected_crc:
            raise SSCPProtocolError(
                f"CRC mismatch while reading {file_name}: expected 0x{expected_crc:04X}, got 0x{actual_crc:04X}"
            )

        return {
            "file_name": file_name,
            "size": total_size,
            "timestamp": timestamp,
            "crc": expected_crc,
            "data": data_bytes,
        }

    def _resolved_length(self, variable: dict[str, Any]) -> int:
        raw_type = str(variable.get("type", "BYTE")).upper()
        fixed = TYPE_LENGTHS.get(raw_type)
        requested = variable.get("length")
        if requested is None:
            if fixed is None:
                raise ValueError(f"Unsupported variable type {raw_type}")
            return fixed
        return int(requested)

    def _decode_value(self, raw_data: bytes, type_data: str) -> Any:
        type_name = type_data.upper()

        if type_name == "BOOL":
            if len(raw_data) != 1:
                raise ValueError("BOOL type expects exactly 1 byte")
            return raw_data[0] != 0
        if type_name == "BYTE":
            if len(raw_data) == 1:
                return raw_data[0]
            return raw_data.hex()
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
            return struct.unpack(">f", raw_data)[0]
        if type_name == "LREAL":
            return struct.unpack(">d", raw_data)[0]
        if type_name == "DT":
            return ticks_to_datetime(int.from_bytes(raw_data, byteorder="big", signed=False))
        raise ValueError(f"Unsupported type: {type_name}")

    def _encode_value(self, value: Any, type_data: str) -> bytes:
        type_name = type_data.upper()

        if type_name == "BOOL":
            return (1 if bool(value) else 0).to_bytes(1, "big")
        if type_name == "BYTE":
            return int(value).to_bytes(1, "big", signed=False)
        if type_name == "WORD":
            return int(value).to_bytes(2, "big", signed=False)
        if type_name == "INT":
            return int(value).to_bytes(2, "big", signed=True)
        if type_name == "UINT":
            return int(value).to_bytes(2, "big", signed=False)
        if type_name == "DINT":
            return int(value).to_bytes(4, "big", signed=True)
        if type_name == "UDINT":
            return int(value).to_bytes(4, "big", signed=False)
        if type_name == "LINT":
            return int(value).to_bytes(8, "big", signed=True)
        if type_name == "REAL":
            return struct.pack(">f", float(value))
        if type_name == "LREAL":
            return struct.pack(">d", float(value))
        if type_name == "DT":
            return struct.pack(">Q", datetime_to_ticks(value))
        raise ValueError(f"Unsupported type: {type_name}")

    def _build_read_payload(
        self,
        variables: Sequence[dict[str, Any]],
        *,
        response_format: int = 0,
        uid_type_vm: bool = False,
        task_id: int | None = None,
    ) -> bytes:
        flags = response_format & 0x07
        flags |= 0x80
        if uid_type_vm:
            flags |= 0x40
        if task_id is not None:
            flags |= 0x10

        payload = bytearray()
        payload.append(flags)
        if task_id is not None:
            payload.append(task_id)

        for variable in variables:
            payload.extend(struct.pack(">I", int(variable["uid"])))
            payload.extend(struct.pack(">I", int(variable.get("offset", 0))))
            payload.extend(struct.pack(">I", self._resolved_length(variable)))

        return bytes(payload)

    def _split_raw_values(
        self,
        payload: bytes,
        variables: Sequence[dict[str, Any]],
    ) -> list[bytes]:
        index = 0
        result: list[bytes] = []
        for variable in variables:
            value_length = self._resolved_length(variable)
            chunk = payload[index : index + value_length]
            if len(chunk) != value_length:
                raise SSCPProtocolError("Variable response payload is shorter than expected.")
            result.append(chunk)
            index += value_length

        if index != len(payload):
            _LOGGER.debug(
                "Read payload contains %d trailing bytes after decoding %d variables.",
                len(payload) - index,
                len(variables),
            )
        return result

    def read_variables(
        self,
        variables: Sequence[dict[str, Any]],
        *,
        use_file_transfer: bool = True,
    ) -> dict[str, Any]:
        results: dict[str, Any] = {}
        if not variables:
            return results

        for start in range(0, len(variables), 64):
            chunk = list(variables[start : start + 64])
            payload = self._build_read_payload(chunk)

            try:
                response = self._send_frame(0x0500, payload)
                raw_payload = response.data if response is not None else b""
            except SSCPCommandError as err:
                if err.error_code == 0x010E and use_file_transfer:
                    file_payload = self.read_file("/var/direct")
                    raw_payload = file_payload["data"]
                else:
                    raise

            raw_values = self._split_raw_values(raw_payload, chunk)
            for variable, raw_value in zip(chunk, raw_values, strict=True):
                key = str(
                    variable.get("key")
                    or variable.get("name_vlist")
                    or variable.get("name")
                    or f"{variable['uid']}:{variable.get('offset', 0)}"
                )
                results[key] = self._decode_value(raw_value, str(variable["type"]))

        return results

    def read_variable(self, uid: int, offset: int, length: int, type_data: str) -> Any:
        result = self.read_variables(
            [
                {
                    "uid": uid,
                    "offset": offset,
                    "length": length,
                    "type": type_data,
                    "key": "__single__",
                }
            ]
        )
        return result["__single__"]

    def _build_write_payload(
        self,
        variables: Sequence[dict[str, Any]],
        *,
        file_mode: bool,
        uid_type_vm: bool = False,
        task_id: int | None = None,
    ) -> tuple[bytes, bytes]:
        flags = 0x80
        if uid_type_vm:
            flags |= 0x40
        if file_mode:
            flags |= 0x20
        if task_id is not None:
            flags |= 0x10

        payload = bytearray()
        payload.append(flags)
        if task_id is not None:
            payload.append(task_id)
        if not file_mode:
            payload.append(len(variables))

        data_blob = bytearray()
        for variable in variables:
            payload.extend(struct.pack(">I", int(variable["uid"])))
            payload.extend(struct.pack(">I", int(variable.get("offset", 0))))
            payload.extend(struct.pack(">I", self._resolved_length(variable)))
            data_blob.extend(self._encode_value(variable["value"], str(variable["type"])))

        if not file_mode:
            payload.extend(data_blob)

        return bytes(payload), bytes(data_blob)

    def write_variables(
        self,
        variables: Sequence[dict[str, Any]],
        *,
        use_file_transfer: bool = True,
    ) -> None:
        if not variables:
            return

        for start in range(0, len(variables), 64):
            chunk = list(variables[start : start + 64])
            direct_payload, raw_values = self._build_write_payload(chunk, file_mode=False)
            file_mode = len(direct_payload) > self.max_data_size

            if file_mode and not use_file_transfer:
                raise ValueError("Write payload is too large for direct mode and file transfer is disabled.")

            if file_mode:
                file_payload, raw_values = self._build_write_payload(chunk, file_mode=True)
                self.write_file("/var/direct", raw_values)
                self._send_frame(0x0510, file_payload)
            else:
                self._send_frame(0x0510, direct_payload)

    def write_variable(
        self,
        uid: int,
        value: Any,
        *,
        offset: int = 0,
        length: int = 0,
        type_data: str = "BYTE",
    ) -> None:
        variable_length = length or TYPE_LENGTHS.get(type_data.upper(), length or 1)
        self.write_variables(
            [
                {
                    "uid": uid,
                    "offset": offset,
                    "length": variable_length,
                    "type": type_data,
                    "value": value,
                }
            ]
        )

    def capabilities(self) -> dict[str, Any]:
        return {
            "protocol_version": self.protocol_version,
            "server_max_data_size": self.server_max_data_size,
            "client_max_data_size": self.client_max_data_size,
            "right_group": self.right_group,
            "right_group_label": self.right_group_label,
            "image_guid": self.image_guid,
            "device_tags": self.device_tags,
        }
