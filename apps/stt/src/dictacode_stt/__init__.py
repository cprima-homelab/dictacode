"""dictacode STT - Speech-to-text pipeline."""

__version__ = "0.3.0"

from dictacode_stt.protocol import (
    CommandMessage,
    JsonProtocol,
    Message,
    MsgpackProtocol,
    ProtocolAdapter,
    TextMessage,
    get_protocol,
)
from dictacode_stt.service import (
    SttService,
)
from dictacode_stt.state import (
    SolutionState,
    SttState,
)
from dictacode_stt.supervisor import (
    LinkSupervisor,
)
from dictacode_stt.transport import (
    TransportError,
    UartTransport,
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
    "SolutionState",
    "SttState",
    # Transport
    "TransportError",
    "UartTransport",
    # Service
    "SttService",
    # Supervisor
    "LinkSupervisor",
    # Existing
    "main",
]
