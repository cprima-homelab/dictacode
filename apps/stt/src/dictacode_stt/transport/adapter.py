"""
adapter.py - Transport Adapter Interface (v0.2.8 Phase 1)

Defines abstract base class for transport adapters, enabling multiple
connection types (UART, USB-Serial, WiFi) with a unified interface.

This follows the adapter pattern established in v0.2.6 (TranscriptionAdapter).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ConnectionStatus(Enum):
    """Transport connection status."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class TransportConfig:
    """Base configuration for transport adapters.

    Subclasses should extend this with adapter-specific fields.

    Attributes:
        timeout: Default timeout in seconds for operations
    """

    timeout: float = 1.0


class TransportError(Exception):
    """Base exception for transport layer errors."""

    pass


class TransportAdapter(ABC):
    """Abstract base class for transport adapters.

    Implementations provide connectivity for different transport types:
    - UART (serial port)
    - USB-Serial (USB-to-serial adapters)
    - WiFi (TCP sockets)

    All adapters share a common interface for send/receive operations.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Return transport type name (e.g., 'uart', 'usb-serial', 'wifi').

        Returns:
            Transport type identifier
        """
        pass

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to transport endpoint.

        Returns:
            True if connection successful, False otherwise

        Raises:
            TransportError: On connection failure with details
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection and release resources.

        Should be safe to call multiple times.
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if transport is currently connected.

        Returns:
            True if connected and ready for I/O
        """
        pass

    @abstractmethod
    def get_status(self) -> ConnectionStatus:
        """Get current connection status.

        Returns:
            Current ConnectionStatus
        """
        pass

    @abstractmethod
    def send(self, data: bytes) -> bool:
        """Send data over transport.

        Args:
            data: Bytes to send

        Returns:
            True if send successful, False otherwise

        Raises:
            TransportError: If not connected or send fails
        """
        pass

    @abstractmethod
    def receive(self, size: int = 1, timeout_ms: Optional[int] = None) -> bytes:
        """Receive data from transport.

        Args:
            size: Number of bytes to receive
            timeout_ms: Optional timeout override in milliseconds

        Returns:
            Bytes received (may be less than size on timeout)

        Raises:
            TransportError: If not connected or receive fails
        """
        pass

    @abstractmethod
    def readline(self, timeout_ms: Optional[int] = None) -> bytes:
        """Receive data until newline (for line-based protocols).

        Args:
            timeout_ms: Optional timeout override in milliseconds

        Returns:
            Line including newline, or empty bytes on timeout

        Raises:
            TransportError: If not connected or receive fails
        """
        pass

    @abstractmethod
    def flush(self) -> None:
        """Flush write buffers (implementation-specific).

        Some transports may buffer writes for efficiency.
        """
        pass

    # Context manager support
    def __enter__(self):
        """Context manager entry - establish connection."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close connection."""
        self.disconnect()
