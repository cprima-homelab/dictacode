"""UART protocol for STT <-> HID communication.

Supports multiple wire formats via adapter pattern:
- JsonProtocol: Human readable, newline-delimited JSON
- MsgpackProtocol: Binary, length-prefixed MessagePack
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Union

import msgpack


@dataclass(frozen=True)
class TextMessage:
    """Text to be typed as keyboard input."""

    payload: str
    request_id: str | None = None  # v0.3.0: Optional request ID for tracking


@dataclass(frozen=True)
class CommandMessage:
    """Control command (keymap, pause, etc.)."""

    command: str
    argument: str | None = None
    request_id: str | None = None  # v0.3.0: Optional request ID for tracking


@dataclass(frozen=True)
class ProbeMessage:
    """Sent during HANDSHAKE_INIT to verify peer is alive."""

    timestamp: float
    protocol_version: str
    component: str
    component_version: str


@dataclass(frozen=True)
class ProbeAckMessage:
    """Response to probe from peer."""

    timestamp: float
    protocol_version: str
    component: str
    component_version: str


@dataclass(frozen=True)
class ResponseMessage:
    """Response from HID to STT (v0.3.0 Phase 4).

    Acknowledges receipt and processing status of TextMessage or CommandMessage.

    Attributes:
        request_id: ID from original TextMessage/CommandMessage
        status: "ok", "error", or "buffered"
        message: Optional human-readable status message
    """

    request_id: str
    status: str  # "ok", "error", "buffered"
    message: str | None = None


Message = Union[
    TextMessage, CommandMessage, ProbeMessage, ProbeAckMessage, ResponseMessage
]


class ProtocolAdapter(ABC):
    """Abstract protocol encoder/decoder."""

    @abstractmethod
    def encode(self, msg: Message) -> bytes:
        """Encode message to wire format."""

    @abstractmethod
    def decode(self, data: bytes) -> Message:
        """Decode wire format to message."""


class JsonProtocol(ProtocolAdapter):
    """JSON-lines protocol: one JSON object per line.

    Human readable, good for debugging.
    Wire format: {"t":"text","p":"hello"}\\n

    Field names kept short to minimize UART overhead:
    - t = type (text, cmd)
    - p = payload (text content)
    - c = command name
    - a = argument
    """

    def encode(self, msg: Message) -> bytes:
        if isinstance(msg, TextMessage):
            obj = {"t": "text", "p": msg.payload}
            if msg.request_id is not None:
                obj["id"] = msg.request_id
        elif isinstance(msg, CommandMessage):
            obj = {"t": "cmd", "c": msg.command}
            if msg.argument is not None:
                obj["a"] = msg.argument
            if msg.request_id is not None:
                obj["id"] = msg.request_id
        elif isinstance(msg, ProbeMessage):
            obj = {
                "t": "probe",
                "ts": msg.timestamp,
                "pv": msg.protocol_version,
                "cmp": msg.component,
                "cv": msg.component_version,
            }
        elif isinstance(msg, ProbeAckMessage):
            obj = {
                "t": "probe_ack",
                "ts": msg.timestamp,
                "pv": msg.protocol_version,
                "cmp": msg.component,
                "cv": msg.component_version,
            }
        elif isinstance(msg, ResponseMessage):
            obj = {"t": "rsp", "id": msg.request_id, "s": msg.status}
            if msg.message is not None:
                obj["m"] = msg.message
        else:
            raise TypeError(f"Unknown message type: {type(msg)}")
        return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")

    def decode(self, data: bytes) -> Message:
        line = data.decode("utf-8").rstrip("\r\n")
        obj = json.loads(line)
        msg_type = obj.get("t")
        if msg_type == "text":
            return TextMessage(payload=obj["p"], request_id=obj.get("id"))
        elif msg_type == "cmd":
            return CommandMessage(
                command=obj["c"], argument=obj.get("a"), request_id=obj.get("id")
            )
        elif msg_type == "probe":
            return ProbeMessage(
                timestamp=obj["ts"],
                protocol_version=obj.get("pv", "0.0.0"),
                component=obj.get("cmp", "unknown"),
                component_version=obj.get("cv", "0.0.0"),
            )
        elif msg_type == "probe_ack":
            return ProbeAckMessage(
                timestamp=obj["ts"],
                protocol_version=obj.get("pv", "0.0.0"),
                component=obj.get("cmp", "unknown"),
                component_version=obj.get("cv", "0.0.0"),
            )
        elif msg_type == "rsp":
            return ResponseMessage(
                request_id=obj["id"],
                status=obj["s"],
                message=obj.get("m"),
            )
        else:
            raise ValueError(f"Unknown message type: {msg_type}")


class MsgpackProtocol(ProtocolAdapter):
    """MessagePack protocol: length-prefixed binary.

    Compact, efficient, good for non-ASCII (CJK, etc.).
    Wire format: [2-byte big-endian length][msgpack blob]

    Same field names as JsonProtocol for consistency.
    """

    def encode(self, msg: Message) -> bytes:
        if isinstance(msg, TextMessage):
            obj = {"t": "text", "p": msg.payload}
            if msg.request_id is not None:
                obj["id"] = msg.request_id
        elif isinstance(msg, CommandMessage):
            obj = {"t": "cmd", "c": msg.command}
            if msg.argument is not None:
                obj["a"] = msg.argument
            if msg.request_id is not None:
                obj["id"] = msg.request_id
        elif isinstance(msg, ProbeMessage):
            obj = {
                "t": "probe",
                "ts": msg.timestamp,
                "pv": msg.protocol_version,
                "cmp": msg.component,
                "cv": msg.component_version,
            }
        elif isinstance(msg, ProbeAckMessage):
            obj = {
                "t": "probe_ack",
                "ts": msg.timestamp,
                "pv": msg.protocol_version,
                "cmp": msg.component,
                "cv": msg.component_version,
            }
        elif isinstance(msg, ResponseMessage):
            obj = {"t": "rsp", "id": msg.request_id, "s": msg.status}
            if msg.message is not None:
                obj["m"] = msg.message
        else:
            raise TypeError(f"Unknown message type: {type(msg)}")

        packed = msgpack.packb(obj, use_bin_type=True)
        length = len(packed)
        if length > 65535:
            raise ValueError(f"Message too large: {length} bytes (max 65535)")
        return length.to_bytes(2, "big") + packed

    def decode(self, data: bytes) -> Message:
        """Decode msgpack data (without length prefix).

        Caller is responsible for reading the 2-byte length prefix
        and passing only the msgpack blob.
        """
        obj = msgpack.unpackb(data, raw=False)
        msg_type = obj.get("t")
        if msg_type == "text":
            return TextMessage(payload=obj["p"], request_id=obj.get("id"))
        elif msg_type == "cmd":
            return CommandMessage(
                command=obj["c"], argument=obj.get("a"), request_id=obj.get("id")
            )
        elif msg_type == "probe":
            return ProbeMessage(
                timestamp=obj["ts"],
                protocol_version=obj.get("pv", "0.0.0"),
                component=obj.get("cmp", "unknown"),
                component_version=obj.get("cv", "0.0.0"),
            )
        elif msg_type == "probe_ack":
            return ProbeAckMessage(
                timestamp=obj["ts"],
                protocol_version=obj.get("pv", "0.0.0"),
                component=obj.get("cmp", "unknown"),
                component_version=obj.get("cv", "0.0.0"),
            )
        elif msg_type == "rsp":
            return ResponseMessage(
                request_id=obj["id"],
                status=obj["s"],
                message=obj.get("m"),
            )
        else:
            raise ValueError(f"Unknown message type: {msg_type}")


def get_protocol(name: str) -> ProtocolAdapter:
    """Factory function to get protocol adapter by name.

    Args:
        name: Protocol name ("json" or "msgpack")

    Returns:
        Protocol adapter instance

    Raises:
        ValueError: If protocol name is unknown
    """
    protocols: dict[str, type[ProtocolAdapter]] = {
        "json": JsonProtocol,
        "msgpack": MsgpackProtocol,
    }
    if name not in protocols:
        available = ", ".join(protocols.keys())
        raise ValueError(f"Unknown protocol: {name}. Available: {available}")
    return protocols[name]()
