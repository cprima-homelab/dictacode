"""dictacode HID - UART to HID keyboard bridge."""

from dictacode_hid.protocol import (
    Message,
    TextMessage,
    CommandMessage,
    ProbeMessage,
    ProbeAckMessage,
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
from dictacode_hid.supervisor import (
    LinkSupervisor,
)

__all__ = [
    # Protocol
    "Message",
    "TextMessage",
    "CommandMessage",
    "ProbeMessage",
    "ProbeAckMessage",
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
    # Supervisor
    "LinkSupervisor",
    # Existing
    "main",
    "keymaps",
    "cli",
]
