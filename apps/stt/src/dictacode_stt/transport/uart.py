"""
uart.py - UART Transport Adapter (v0.2.8 Phase 1)

UART (serial port) transport with exclusive locking.
Refactored from transport.py to implement TransportAdapter interface.

Usage:
    config = UartConfig(device="/dev/serial0", baud_rate=115200)
    uart = UartTransport(config)
    uart.connect()
    data = uart.receive(1024)
    uart.send(b"hello")
    uart.disconnect()

    # Or use as context manager:
    with UartTransport(config) as uart:
        uart.send(b"hello")
"""

from dataclasses import dataclass
from typing import Optional

from ..lock import SerialLock
from .adapter import ConnectionStatus, TransportAdapter, TransportConfig, TransportError


@dataclass
class UartConfig(TransportConfig):
    """UART transport configuration.

    Attributes:
        device: Serial device path (e.g., /dev/serial0, /dev/ttyUSB0)
        baud_rate: Baud rate (default: 115200)
        timeout: Read timeout in seconds (default: 1.0)
        lock_dir: Optional lock directory override (for testing)
    """

    device: str = "/dev/serial0"
    baud_rate: int = 115200
    timeout: float = 1.0
    lock_dir: Optional[str] = None


class UartTransport(TransportAdapter):
    """UART transport adapter - raw serial I/O with exclusive locking.

    Implements TransportAdapter interface for UART connections.
    Uses SerialLock (v0.2.3) for exclusive port access.
    """

    def __init__(self, config: UartConfig):
        """Initialize UART transport.

        Args:
            config: UART configuration
        """
        self.config = config
        self._serial = None
        self._lock: Optional[SerialLock] = None
        self._status = ConnectionStatus.DISCONNECTED

    def get_name(self) -> str:
        """Return transport type name."""
        return "uart"

    def connect(self) -> bool:
        """Establish UART connection with exclusive lock.

        Returns:
            True if connection successful

        Raises:
            TransportError: If already connected or connection fails
        """
        if self._serial is not None:
            raise TransportError("UART already connected")

        try:
            import serial
        except ImportError:
            raise TransportError("pyserial not installed. Run: pip install pyserial")

        self._status = ConnectionStatus.CONNECTING

        # Acquire exclusive lock before opening serial port
        self._lock = SerialLock(self.config.device, lock_dir=self.config.lock_dir)
        if not self._lock.acquire():
            pid = self._lock.get_owner_pid()
            msg = f"{self.config.device} is locked by another process."
            if pid:
                msg += f"\nCheck {self._lock.lock_path} (PID: {pid})"
            msg += "\n\nTo investigate:"
            msg += f"\n  cat {self._lock.lock_path}  # See owning PID"
            msg += "\n  ps aux | grep <PID>        # Find process"
            msg += "\n  systemctl status dictacode-*  # Check services"
            self._lock = None
            self._status = ConnectionStatus.ERROR
            raise TransportError(msg)

        try:
            self._serial = serial.Serial(
                self.config.device,
                self.config.baud_rate,
                timeout=self.config.timeout,
            )
            self._status = ConnectionStatus.CONNECTED
            return True
        except Exception as e:
            # Release lock on failure
            if self._lock:
                self._lock.release()
                self._lock = None
            self._status = ConnectionStatus.ERROR
            raise TransportError(f"Failed to open {self.config.device}: {e}")

    def disconnect(self) -> None:
        """Close UART connection and release lock."""
        if self._serial is not None:
            self._serial.close()
            self._serial = None
        if self._lock is not None:
            self._lock.release()
            self._lock = None
        self._status = ConnectionStatus.DISCONNECTED

    def is_connected(self) -> bool:
        """Check if UART is connected."""
        return self._serial is not None and self._serial.is_open

    def get_status(self) -> ConnectionStatus:
        """Get current connection status."""
        # Update status based on actual connection state
        if self._serial is not None and self._serial.is_open:
            self._status = ConnectionStatus.CONNECTED
        elif self._serial is None and self._status != ConnectionStatus.CONNECTING:
            self._status = ConnectionStatus.DISCONNECTED
        return self._status

    def send(self, data: bytes) -> bool:
        """Send data over UART.

        Args:
            data: Bytes to send

        Returns:
            True if send successful

        Raises:
            TransportError: If not connected or send fails
        """
        if not self.is_connected():
            raise TransportError("UART not connected")

        try:
            n = self._serial.write(data)
            self._serial.flush()
            return n == len(data)
        except Exception as e:
            self._status = ConnectionStatus.ERROR
            raise TransportError(f"UART send failed: {e}")

    def receive(self, size: int = 1, timeout_ms: Optional[int] = None) -> bytes:
        """Receive data from UART.

        Args:
            size: Number of bytes to receive
            timeout_ms: Optional timeout override in milliseconds

        Returns:
            Bytes received (may be less than size on timeout)

        Raises:
            TransportError: If not connected or receive fails
        """
        if not self.is_connected():
            raise TransportError("UART not connected")

        # Apply timeout override if provided
        original_timeout = None
        if timeout_ms is not None:
            original_timeout = self._serial.timeout
            self._serial.timeout = timeout_ms / 1000.0

        try:
            data = self._serial.read(size)
            return data
        except Exception as e:
            self._status = ConnectionStatus.ERROR
            raise TransportError(f"UART receive failed: {e}")
        finally:
            # Restore original timeout
            if original_timeout is not None:
                self._serial.timeout = original_timeout

    def readline(self, timeout_ms: Optional[int] = None) -> bytes:
        """Receive data until newline (for JSON protocol).

        Args:
            timeout_ms: Optional timeout override in milliseconds

        Returns:
            Line including newline, or empty bytes on timeout

        Raises:
            TransportError: If not connected or receive fails
        """
        if not self.is_connected():
            raise TransportError("UART not connected")

        # Apply timeout override if provided
        original_timeout = None
        if timeout_ms is not None:
            original_timeout = self._serial.timeout
            self._serial.timeout = timeout_ms / 1000.0

        try:
            data = self._serial.readline()
            return data
        except Exception as e:
            self._status = ConnectionStatus.ERROR
            raise TransportError(f"UART readline failed: {e}")
        finally:
            # Restore original timeout
            if original_timeout is not None:
                self._serial.timeout = original_timeout

    def flush(self) -> None:
        """Flush UART write buffer."""
        if self.is_connected():
            self._serial.flush()

    # Legacy compatibility methods (for gradual migration)

    def open(self) -> None:
        """Legacy method - use connect() instead."""
        self.connect()

    def close(self) -> None:
        """Legacy method - use disconnect() instead."""
        self.disconnect()

    def is_open(self) -> bool:
        """Legacy method - use is_connected() instead."""
        return self.is_connected()

    def read(self, size: int = 1) -> bytes:
        """Legacy method - use receive() instead."""
        return self.receive(size)

    def write(self, data: bytes) -> int:
        """Legacy method - use send() instead."""
        if self.send(data):
            return len(data)
        return 0

    @property
    def device(self) -> str:
        """Legacy property - access via config.device instead."""
        return self.config.device

    @property
    def baud_rate(self) -> int:
        """Legacy property - access via config.baud_rate instead."""
        return self.config.baud_rate

    @property
    def timeout(self) -> float:
        """Legacy property - access via config.timeout instead."""
        return self.config.timeout
