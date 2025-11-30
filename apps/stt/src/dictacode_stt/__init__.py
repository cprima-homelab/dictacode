"""dictacode STT - Speech-to-text pipeline."""

from dictacode_stt.protocol import (
    Message,
    TextMessage,
    CommandMessage,
    ProtocolAdapter,
    JsonProtocol,
    MsgpackProtocol,
    get_protocol,
)
from dictacode_stt.state import (
    DeviceMode,
    SttState,
)

__all__ = [
    # Protocol
    "Message",
    "TextMessage",
    "CommandMessage",
    "ProtocolAdapter",
    "JsonProtocol",
    "MsgpackProtocol",
    "get_protocol",
    # State
    "DeviceMode",
    "SttState",
    # Existing
    "main",
]
