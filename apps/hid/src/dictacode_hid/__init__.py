"""dictacode HID - UART to HID keyboard bridge."""

__version__ = "0.3.2"

from dictacode_hid.protocol import (
    CommandMessage,
    JsonProtocol,
    Message,
    MsgpackProtocol,
    ProbeAckMessage,
    ProbeMessage,
    ProtocolAdapter,
    TextMessage,
    get_protocol,
)
from dictacode_hid.service import (
    HidService,
)
from dictacode_hid.state import (
    DeviceMode,
    HidState,
)
from dictacode_hid.supervisor import (
    LinkSupervisor,
)
from dictacode_hid.transport import (
    HidTransport,
    TransportError,
    UartTransport,
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
