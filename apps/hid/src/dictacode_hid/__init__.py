"""dictacode HID - UART to HID keyboard bridge."""

from dictacode_hid.protocol import (
    Message,
    TextMessage,
    CommandMessage,
    ProtocolAdapter,
    JsonProtocol,
    MsgpackProtocol,
    get_protocol,
    detect_protocol,
    try_decode,
)
from dictacode_hid.state import (
    DeviceMode,
    HidState,
)
from dictacode_hid.transport import (
    TransportError,
    UartTransport,
    HidTransport,
)
from dictacode_hid.service import (
    HidService,
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
    "detect_protocol",
    "try_decode",
    # State
    "DeviceMode",
    "HidState",
    # Transport
    "TransportError",
    "UartTransport",
    "HidTransport",
    # Service
    "HidService",
    # Existing
    "main",
    "keymaps",
    "cli",
]
