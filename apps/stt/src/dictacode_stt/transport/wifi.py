"""
wifi.py - WiFi/TCP Transport Adapter (v0.2.8 Phase 3)

WiFi transport for wireless communication between STT and HID devices.
Uses TCP sockets with length-prefixed message framing.

Benefits:
- Wireless HID placement (no physical cable connection)
- Longer range than UART/USB cables
- Supports network-based device discovery via mDNS

Usage:
    # Connect to HID device by IP
    config = WifiConfig(host="192.168.1.100", port=9876)
    transport = WifiTransport(config)
    transport.connect()
    transport.send(b"message")
    response = transport.receive()

    # With connection retry
    config = WifiConfig(
        host="pi0-hid.local",
        port=9876,
        connect_timeout=5.0,
        reconnect_attempts=3
    )
    transport = WifiTransport(config)
"""

import logging
import socket
import time
from dataclasses import dataclass
from typing import Optional

from .adapter import TransportAdapter, TransportConfig, TransportError, ConnectionStatus

logger = logging.getLogger(__name__)


@dataclass
class WifiConfig(TransportConfig):
    """WiFi/TCP transport configuration.

    Attributes:
        host: IP address or hostname of HID device (e.g., "192.168.1.100", "pi0-hid.local")
        port: TCP port (default: 9876)
        connect_timeout: Connection timeout in seconds (default: 5.0)
        socket_timeout: Socket I/O timeout in seconds (default: 1.0)
        reconnect_attempts: Number of reconnection attempts on failure (default: 3)
        reconnect_delay: Delay between reconnection attempts in seconds (default: 1.0)
        keepalive: Enable TCP keepalive (default: True)
        nodelay: Disable Nagle's algorithm for lower latency (default: True)
    """
    host: str = ""
    port: int = 9876
    connect_timeout: float = 5.0
    socket_timeout: float = 1.0
    reconnect_attempts: int = 3
    reconnect_delay: float = 1.0
    keepalive: bool = True
    nodelay: bool = True


class WifiTransport(TransportAdapter):
    """WiFi/TCP transport adapter for wireless HID connection.

    Implements TransportAdapter interface using TCP sockets.
    Uses length-prefixed framing (4-byte big-endian length header) for reliable message delivery.

    Protocol:
        [4 bytes: message length][N bytes: message data]

    Supports:
    - Connection retry and reconnection
    - TCP keepalive for connection health monitoring
    - TCP_NODELAY for low-latency communication
    - Configurable timeouts
    """

    # Message framing constants
    LENGTH_PREFIX_SIZE = 4  # 4 bytes for message length (big-endian uint32)
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1 MB max message size

    def __init__(self, config: WifiConfig):
        """Initialize WiFi transport.

        Args:
            config: WiFi configuration
        """
        self.config = config
        self._socket: Optional[socket.socket] = None
        self._status = ConnectionStatus.DISCONNECTED
        self._reconnect_count = 0

    def get_name(self) -> str:
        """Return transport type name."""
        return "wifi"

    def connect(self) -> bool:
        """Establish WiFi/TCP connection to HID device.

        Attempts to connect with retry logic if configured.

        Returns:
            True if connection successful

        Raises:
            TransportError: If already connected or all connection attempts fail
        """
        if self._socket is not None:
            raise TransportError("WiFi already connected")

        if not self.config.host:
            raise TransportError("WiFi host not configured")

        self._status = ConnectionStatus.CONNECTING
        last_error = None

        # Try connection with retry logic
        for attempt in range(self.config.reconnect_attempts + 1):
            if attempt > 0:
                logger.info(
                    f"WiFi reconnection attempt {attempt}/{self.config.reconnect_attempts} "
                    f"to {self.config.host}:{self.config.port}"
                )
                time.sleep(self.config.reconnect_delay)

            try:
                # Create TCP socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

                # Set socket options
                if self.config.keepalive:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

                if self.config.nodelay:
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                # Set connection timeout
                sock.settimeout(self.config.connect_timeout)

                # Connect to remote host
                sock.connect((self.config.host, self.config.port))

                # Set socket timeout for I/O operations
                sock.settimeout(self.config.socket_timeout)

                self._socket = sock
                self._status = ConnectionStatus.CONNECTED
                self._reconnect_count = attempt

                logger.info(
                    f"WiFi connected to {self.config.host}:{self.config.port} "
                    f"(attempt {attempt + 1})"
                )
                return True

            except socket.timeout:
                last_error = f"Connection timeout to {self.config.host}:{self.config.port}"
                logger.warning(last_error)

            except socket.gaierror as e:
                last_error = f"DNS resolution failed for {self.config.host}: {e}"
                logger.error(last_error)
                # Don't retry on DNS errors
                break

            except ConnectionRefusedError:
                last_error = f"Connection refused by {self.config.host}:{self.config.port}"
                logger.warning(last_error)

            except Exception as e:
                last_error = f"WiFi connect failed: {e}"
                logger.warning(last_error)

        # All attempts failed
        self._status = ConnectionStatus.ERROR
        raise TransportError(
            f"Failed to connect to {self.config.host}:{self.config.port} "
            f"after {self.config.reconnect_attempts + 1} attempts. "
            f"Last error: {last_error}"
        )

    def disconnect(self) -> None:
        """Close WiFi/TCP connection."""
        if self._socket is not None:
            try:
                # Graceful shutdown
                self._socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass  # Socket may already be closed

            try:
                self._socket.close()
            except Exception:
                pass

            self._socket = None

        self._status = ConnectionStatus.DISCONNECTED
        self._reconnect_count = 0

    def is_connected(self) -> bool:
        """Check if WiFi is connected."""
        return self._socket is not None

    def get_status(self) -> ConnectionStatus:
        """Get current connection status."""
        return self._status

    def send(self, data: bytes) -> bool:
        """Send data over WiFi with length-prefix framing.

        Message format: [4 bytes: length][N bytes: data]

        Args:
            data: Bytes to send

        Returns:
            True if send successful

        Raises:
            TransportError: If not connected, message too large, or send fails
        """
        if not self.is_connected():
            raise TransportError("WiFi not connected")

        if len(data) > self.MAX_MESSAGE_SIZE:
            raise TransportError(
                f"Message too large: {len(data)} bytes "
                f"(max: {self.MAX_MESSAGE_SIZE} bytes)"
            )

        try:
            # Send length prefix (4 bytes, big-endian)
            length_prefix = len(data).to_bytes(self.LENGTH_PREFIX_SIZE, "big")

            # Send length + data as a single packet
            message = length_prefix + data
            self._socket.sendall(message)

            logger.debug(f"WiFi sent {len(data)} bytes")
            return True

        except socket.timeout:
            logger.error("WiFi send timeout")
            self._status = ConnectionStatus.ERROR
            raise TransportError("WiFi send timeout")

        except Exception as e:
            logger.error(f"WiFi send failed: {e}")
            self._status = ConnectionStatus.ERROR
            raise TransportError(f"WiFi send failed: {e}")

    def receive(self, size: int = 1, timeout_ms: Optional[int] = None) -> bytes:
        """Receive data from WiFi with length-prefix framing.

        Note: size parameter is ignored. WiFi transport reads full messages.

        Args:
            size: Ignored (kept for interface compatibility)
            timeout_ms: Optional timeout override in milliseconds

        Returns:
            Complete message bytes, or empty bytes on timeout

        Raises:
            TransportError: If not connected or receive fails
        """
        if not self.is_connected():
            raise TransportError("WiFi not connected")

        # Apply timeout override if provided
        original_timeout = None
        if timeout_ms is not None:
            original_timeout = self._socket.gettimeout()
            self._socket.settimeout(timeout_ms / 1000.0)

        try:
            # Read length prefix (4 bytes)
            length_bytes = self._recv_exactly(self.LENGTH_PREFIX_SIZE)
            if not length_bytes:
                return b""  # Timeout or connection closed

            # Parse message length
            message_length = int.from_bytes(length_bytes, "big")

            # Validate message length
            if message_length > self.MAX_MESSAGE_SIZE:
                raise TransportError(
                    f"Invalid message length: {message_length} bytes "
                    f"(max: {self.MAX_MESSAGE_SIZE} bytes)"
                )

            if message_length == 0:
                return b""

            # Read message payload
            data = self._recv_exactly(message_length)
            if not data or len(data) != message_length:
                raise TransportError("Incomplete message received")

            logger.debug(f"WiFi received {len(data)} bytes")
            return data

        except socket.timeout:
            return b""  # Timeout is not an error, return empty

        except TransportError:
            raise  # Re-raise transport errors

        except Exception as e:
            logger.error(f"WiFi receive failed: {e}")
            self._status = ConnectionStatus.ERROR
            raise TransportError(f"WiFi receive failed: {e}")

        finally:
            # Restore original timeout
            if original_timeout is not None:
                self._socket.settimeout(original_timeout)

    def _recv_exactly(self, nbytes: int) -> bytes:
        """Receive exactly nbytes from socket.

        Args:
            nbytes: Number of bytes to receive

        Returns:
            Exactly nbytes, or empty bytes on timeout/disconnect

        Raises:
            TransportError: On receive error
        """
        chunks = []
        bytes_received = 0

        while bytes_received < nbytes:
            try:
                chunk = self._socket.recv(nbytes - bytes_received)

                if not chunk:
                    # Connection closed
                    raise TransportError("Connection closed by remote")

                chunks.append(chunk)
                bytes_received += len(chunk)

            except socket.timeout:
                # Timeout - return what we have so far (may be empty)
                if chunks:
                    logger.warning(
                        f"Partial receive: got {bytes_received}/{nbytes} bytes before timeout"
                    )
                return b""

        return b"".join(chunks)

    def readline(self, timeout_ms: Optional[int] = None) -> bytes:
        """Receive line-delimited data from WiFi.

        Note: WiFi transport uses length-prefix framing, not line delimiting.
        This method calls receive() and returns the complete message.

        Args:
            timeout_ms: Optional timeout override in milliseconds

        Returns:
            Complete message bytes, or empty bytes on timeout

        Raises:
            TransportError: If not connected or receive fails
        """
        # For WiFi transport, there's no line concept - just receive a complete message
        return self.receive(timeout_ms=timeout_ms)

    def flush(self) -> None:
        """Flush WiFi write buffers.

        Note: TCP automatically handles buffering. This is a no-op.
        """
        pass  # TCP handles buffering automatically

    def get_connection_info(self) -> dict:
        """Get information about the current connection.

        Returns:
            Dictionary with connection details
        """
        if not self.is_connected():
            return {
                "connected": False,
                "host": self.config.host,
                "port": self.config.port,
            }

        try:
            local_addr = self._socket.getsockname()
            remote_addr = self._socket.getpeername()

            return {
                "connected": True,
                "host": self.config.host,
                "port": self.config.port,
                "local_address": f"{local_addr[0]}:{local_addr[1]}",
                "remote_address": f"{remote_addr[0]}:{remote_addr[1]}",
                "reconnect_count": self._reconnect_count,
            }
        except Exception:
            return {
                "connected": False,
                "host": self.config.host,
                "port": self.config.port,
            }
