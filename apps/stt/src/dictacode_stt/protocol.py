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


@dataclass(frozen=True)
class CommandMessage:
    """Control command (keymap, pause, etc.)."""

    command: str
    argument: str | None = None


@dataclass(frozen=True)
class ProbeMessage:
    """Sent during HANDSHAKE_INIT to verify peer is alive."""

    timestamp: float


@dataclass(frozen=True)
class ProbeAckMessage:
    """Response to probe from HID."""

    timestamp: float


Message = Union[TextMessage, CommandMessage, ProbeMessage, ProbeAckMessage]


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
        elif isinstance(msg, CommandMessage):
            obj = {"t": "cmd", "c": msg.command}
            if msg.argument is not None:
                obj["a"] = msg.argument
        elif isinstance(msg, ProbeMessage):
            obj = {"t": "probe", "ts": msg.timestamp}
        elif isinstance(msg, ProbeAckMessage):
            obj = {"t": "probe_ack", "ts": msg.timestamp}
        else:
            raise TypeError(f"Unknown message type: {type(msg)}")
        return (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")

    def decode(self, data: bytes) -> Message:
        line = data.decode("utf-8").rstrip("\r\n")
        obj = json.loads(line)
        msg_type = obj.get("t")
        if msg_type == "text":
            return TextMessage(payload=obj["p"])
        elif msg_type == "cmd":
            return CommandMessage(command=obj["c"], argument=obj.get("a"))
        elif msg_type == "probe":
            return ProbeMessage(timestamp=obj["ts"])
        elif msg_type == "probe_ack":
            return ProbeAckMessage(timestamp=obj["ts"])
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
        elif isinstance(msg, CommandMessage):
            obj = {"t": "cmd", "c": msg.command}
            if msg.argument is not None:
                obj["a"] = msg.argument
        elif isinstance(msg, ProbeMessage):
            obj = {"t": "probe", "ts": msg.timestamp}
        elif isinstance(msg, ProbeAckMessage):
            obj = {"t": "probe_ack", "ts": msg.timestamp}
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
            return TextMessage(payload=obj["p"])
        elif msg_type == "cmd":
            return CommandMessage(command=obj["c"], argument=obj.get("a"))
        elif msg_type == "probe":
            return ProbeMessage(timestamp=obj["ts"])
        elif msg_type == "probe_ack":
            return ProbeAckMessage(timestamp=obj["ts"])
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
