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
    SolutionState,
    SttState,
)
from dictacode_stt.transport import (
    TransportError,
    UartTransport,
)
from dictacode_stt.service import (
    SttService,
)
from dictacode_stt.supervisor import (
    LinkSupervisor,
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
