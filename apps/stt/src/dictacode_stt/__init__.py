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
from dictacode_stt.transport import (
    TransportError,
    UartTransport,
)
from dictacode_stt.service import (
    SttService,
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
    # Transport
    "TransportError",
    "UartTransport",
    # Service
    "SttService",
    # Existing
    "main",
]
