"""
wifi.py - WiFi/TCP Transport Server Adapter (v0.2.8 Phase 3)

WiFi transport server for HID device. Listens for incoming TCP connections
from STT devices and handles communication using length-prefixed message framing.

Benefits:
- Wireless HID placement (no physical cable connection)
- Supports multiple client connections (though only one active at a time)
- Network-based service advertisement via mDNS

Usage:
    # Start WiFi server
    config = WifiServerConfig(port=9876, bind_address="0.0.0.0")
    transport = WifiServerTransport(config)
    transport.connect()  # Starts listening

    # Accept client connection
    if transport.is_connected():
        data = transport.receive()
        transport.send(b"response")
"""

import logging
import socket
from dataclasses import dataclass
from typing import Optional

from .adapter import ConnectionStatus, TransportAdapter, TransportConfig, TransportError


logger = logging.getLogger(__name__)


@dataclass
class WifiServerConfig(TransportConfig):
    """WiFi/TCP server transport configuration.

    Attributes:
        port: TCP port to listen on (default: 9876)
        bind_address: IP address to bind to (default: "0.0.0.0" for all interfaces)
        socket_timeout: Socket I/O timeout in seconds (default: 1.0)
        accept_timeout: Timeout for accepting new connections in seconds (default: 0.1)
        keepalive: Enable TCP keepalive (default: True)
        nodelay: Disable Nagle's algorithm for lower latency (default: True)
        backlog: Socket listen backlog (default: 1)
    """

    port: int = 9876
    bind_address: str = "0.0.0.0"
    socket_timeout: float = 1.0
    accept_timeout: float = 0.1
    keepalive: bool = True
    nodelay: bool = True
    backlog: int = 1


class WifiServerTransport(TransportAdapter):
    """WiFi/TCP server transport adapter for HID device.

    Listens for incoming connections from STT devices.
    Uses length-prefixed framing (4-byte big-endian length header) for reliable message delivery.

    Protocol:
        [4 bytes: message length][N bytes: message data]

    Server lifecycle:
    1. connect() - Start listening for connections
    2. _accept_client() - Accept incoming client (called internally during I/O)
    3. send()/receive() - Communicate with connected client
    4. disconnect() - Close connection and stop listening
    """

    # Message framing constants
    LENGTH_PREFIX_SIZE = 4  # 4 bytes for message length (big-endian uint32)
    MAX_MESSAGE_SIZE = 1024 * 1024  # 1 MB max message size

    def __init__(self, config: WifiServerConfig):
        """Initialize WiFi server transport.

        Args:
            config: WiFi server configuration
        """
        self.config = config
        self._server_socket: Optional[socket.socket] = None
        self._client_socket: Optional[socket.socket] = None
        self._client_address: Optional[tuple] = None
        self._status = ConnectionStatus.DISCONNECTED

    def get_name(self) -> str:
        """Return transport type name."""
        return "wifi-server"

    def connect(self) -> bool:
        """Start listening for incoming WiFi/TCP connections.

        Returns:
            True if server started successfully

        Raises:
            TransportError: If already connected or server start fails
        """
        if self._server_socket is not None:
            raise TransportError("WiFi server already running")

        self._status = ConnectionStatus.CONNECTING

        try:
            # Create TCP server socket
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

            # Set socket options
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to address and port
            server_sock.bind((self.config.bind_address, self.config.port))

            # Start listening
            server_sock.listen(self.config.backlog)

            # Set non-blocking for accept timeout
            server_sock.settimeout(self.config.accept_timeout)

            self._server_socket = server_sock
            self._status = ConnectionStatus.CONNECTED

            logger.info(
                f"WiFi server listening on {self.config.bind_address}:{self.config.port}"
            )
            return True

        except OSError as e:
            if e.errno == 98:  # Address already in use
                error_msg = (
                    f"Port {self.config.port} already in use. "
                    f"Check if another HID service is running."
                )
            else:
                error_msg = f"Failed to bind to {self.config.bind_address}:{self.config.port}: {e}"

            self._status = ConnectionStatus.ERROR
            logger.error(error_msg)
            raise TransportError(error_msg)

        except Exception as e:
            self._status = ConnectionStatus.ERROR
            logger.error(f"WiFi server start failed: {e}")
            raise TransportError(f"WiFi server start failed: {e}")

    def disconnect(self) -> None:
        """Close WiFi/TCP server and any active client connection."""
        # Close client connection if active
        if self._client_socket is not None:
            try:
                self._client_socket.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass

            try:
                self._client_socket.close()
            except Exception:
                pass

            self._client_socket = None
            self._client_address = None
            logger.info("WiFi client disconnected")

        # Close server socket
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except Exception:
                pass

            self._server_socket = None
            logger.info("WiFi server stopped")

        self._status = ConnectionStatus.DISCONNECTED

    def is_connected(self) -> bool:
        """Check if WiFi server is running and has an active client.

        Returns:
            True if server is running (client connection not required)
        """
        return self._server_socket is not None

    def has_client(self) -> bool:
        """Check if a client is currently connected.

        Returns:
            True if client connected
        """
        return self._client_socket is not None

    def get_status(self) -> ConnectionStatus:
        """Get current connection status."""
        return self._status

    def _accept_client(self) -> bool:
        """Accept incoming client connection (non-blocking).

        Returns:
            True if new client accepted, False if no client waiting
        """
        if not self._server_socket:
            return False

        # Already have a client
        if self._client_socket:
            return False

        try:
            # Non-blocking accept
            client_sock, client_addr = self._server_socket.accept()

            # Set socket options
            if self.config.keepalive:
                client_sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            if self.config.nodelay:
                client_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

            # Set socket timeout for I/O
            client_sock.settimeout(self.config.socket_timeout)

            self._client_socket = client_sock
            self._client_address = client_addr

            logger.info(f"WiFi client connected from {client_addr[0]}:{client_addr[1]}")
            return True

        except socket.timeout:
            # No client waiting
            return False

        except Exception as e:
            logger.warning(f"Error accepting client: {e}")
            return False

    def send(self, data: bytes) -> bool:
        """Send data to connected client with length-prefix framing.

        Message format: [4 bytes: length][N bytes: data]

        Args:
            data: Bytes to send

        Returns:
            True if send successful

        Raises:
            TransportError: If not connected, no client, or send fails
        """
        if not self.is_connected():
            raise TransportError("WiFi server not running")

        # Try to accept client if none connected
        if not self.has_client():
            self._accept_client()

        if not self.has_client():
            raise TransportError("No WiFi client connected")

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
            self._client_socket.sendall(message)

            logger.debug(f"WiFi sent {len(data)} bytes to client")
            return True

        except (BrokenPipeError, ConnectionResetError):
            logger.warning("WiFi client disconnected during send")
            self._close_client()
            raise TransportError("Client disconnected")

        except socket.timeout:
            logger.error("WiFi send timeout")
            self._close_client()
            raise TransportError("WiFi send timeout")

        except Exception as e:
            logger.error(f"WiFi send failed: {e}")
            self._close_client()
            raise TransportError(f"WiFi send failed: {e}")

    def receive(self, size: int = 1, timeout_ms: Optional[int] = None) -> bytes:
        """Receive data from connected client with length-prefix framing.

        Note: size parameter is ignored. WiFi transport reads full messages.

        Args:
            size: Ignored (kept for interface compatibility)
            timeout_ms: Optional timeout override in milliseconds

        Returns:
            Complete message bytes, or empty bytes on timeout/no client

        Raises:
            TransportError: If not connected or receive fails
        """
        if not self.is_connected():
            raise TransportError("WiFi server not running")

        # Try to accept client if none connected
        if not self.has_client():
            self._accept_client()

        if not self.has_client():
            return b""  # No client yet

        # Apply timeout override if provided
        original_timeout = None
        if timeout_ms is not None:
            original_timeout = self._client_socket.gettimeout()
            self._client_socket.settimeout(timeout_ms / 1000.0)

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

            logger.debug(f"WiFi received {len(data)} bytes from client")
            return data

        except socket.timeout:
            return b""  # Timeout is not an error

        except (BrokenPipeError, ConnectionResetError):
            logger.info("WiFi client disconnected")
            self._close_client()
            return b""

        except TransportError:
            raise  # Re-raise transport errors

        except Exception as e:
            logger.error(f"WiFi receive failed: {e}")
            self._close_client()
            raise TransportError(f"WiFi receive failed: {e}")

        finally:
            # Restore original timeout
            if original_timeout is not None and self._client_socket:
                self._client_socket.settimeout(original_timeout)

    def _recv_exactly(self, nbytes: int) -> bytes:
        """Receive exactly nbytes from client socket.

        Args:
            nbytes: Number of bytes to receive

        Returns:
            Exactly nbytes, or empty bytes on timeout/disconnect

        Raises:
            TransportError: On receive error
        """
        if not self._client_socket:
            return b""

        chunks = []
        bytes_received = 0

        while bytes_received < nbytes:
            try:
                chunk = self._client_socket.recv(nbytes - bytes_received)

                if not chunk:
                    # Connection closed
                    logger.info("WiFi client closed connection")
                    self._close_client()
                    return b""

                chunks.append(chunk)
                bytes_received += len(chunk)

            except socket.timeout:
                # Timeout
                if chunks:
                    logger.warning(
                        f"Partial receive: got {bytes_received}/{nbytes} bytes before timeout"
                    )
                return b""

        return b"".join(chunks)

    def _close_client(self) -> None:
        """Close current client connection."""
        if self._client_socket:
            try:
                self._client_socket.close()
            except Exception:
                pass

            self._client_socket = None
            self._client_address = None

    def readline(self, timeout_ms: Optional[int] = None) -> bytes:
        """Receive line-delimited data from client.

        Note: WiFi transport uses length-prefix framing, not line delimiting.
        This method calls receive() and returns the complete message.

        Args:
            timeout_ms: Optional timeout override in milliseconds

        Returns:
            Complete message bytes, or empty bytes on timeout

        Raises:
            TransportError: If not connected or receive fails
        """
        return self.receive(timeout_ms=timeout_ms)

    def flush(self) -> None:
        """Flush WiFi write buffers.

        Note: TCP automatically handles buffering. This is a no-op.
        """
        pass

    def get_connection_info(self) -> dict:
        """Get information about the current server and client connection.

        Returns:
            Dictionary with connection details
        """
        info = {
            "server_running": self.is_connected(),
            "bind_address": self.config.bind_address,
            "port": self.config.port,
            "client_connected": self.has_client(),
        }

        if self._server_socket:
            try:
                local_addr = self._server_socket.getsockname()
                info["local_address"] = f"{local_addr[0]}:{local_addr[1]}"
            except Exception:
                pass

        if self._client_address:
            info["client_address"] = (
                f"{self._client_address[0]}:{self._client_address[1]}"
            )

        return info
