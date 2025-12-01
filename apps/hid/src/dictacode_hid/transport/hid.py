"""
hid.py - HID Transport Adapter (v0.2.8 Phase 1)

HID (Human Interface Device) transport for writing keyboard reports to /dev/hidg0.
Refactored from transport.py to implement TransportAdapter interface.

Note: HID is output-only. Receive methods are not applicable and will raise errors.

Usage:
    config = HidConfig(device="/dev/hidg0")
    hid = HidTransport(config)
    hid.connect()
    hid.write_report(bytes([0, 0, 4, 0, 0, 0, 0, 0]))  # 'a' key press
    hid.disconnect()

    # Or use as context manager:
    with HidTransport(config) as hid:
        hid.send_key(4)  # 'a' key
"""

import time
from dataclasses import dataclass
from typing import Optional

from .adapter import TransportAdapter, TransportConfig, TransportError, ConnectionStatus


@dataclass
class HidConfig(TransportConfig):
    """HID transport configuration.

    Attributes:
        device: HID gadget device path (default: /dev/hidg0)
        report_size: HID report size in bytes (default: 8 for keyboard)
        key_delay: Delay between key press and release in seconds (default: 0.02)
    """
    device: str = "/dev/hidg0"
    report_size: int = 8
    key_delay: float = 0.02


class HidTransport(TransportAdapter):
    """HID transport adapter - write HID reports to /dev/hidg0.

    Implements TransportAdapter interface for HID (output-only).
    Used for sending keyboard/mouse events to the host computer.
    """

    def __init__(self, config: HidConfig):
        """Initialize HID transport.

        Args:
            config: HID configuration
        """
        self.config = config
        self._hid_file = None
        self._status = ConnectionStatus.DISCONNECTED

    def get_name(self) -> str:
        """Return transport type name."""
        return "hid"

    def connect(self) -> bool:
        """Establish HID connection (open device file).

        Returns:
            True if connection successful

        Raises:
            TransportError: If already connected or connection fails
        """
        if self._hid_file is not None:
            raise TransportError("HID already connected")

        self._status = ConnectionStatus.CONNECTING

        try:
            self._hid_file = open(self.config.device, "wb")
            self._status = ConnectionStatus.CONNECTED
            return True
        except Exception as e:
            self._status = ConnectionStatus.ERROR
            raise TransportError(f"Failed to open {self.config.device}: {e}")

    def disconnect(self) -> None:
        """Close HID connection."""
        if self._hid_file is not None:
            self._hid_file.close()
            self._hid_file = None
        self._status = ConnectionStatus.DISCONNECTED

    def is_connected(self) -> bool:
        """Check if HID is connected."""
        return self._hid_file is not None

    def get_status(self) -> ConnectionStatus:
        """Get current connection status."""
        # Update status based on actual connection state
        if self._hid_file is not None:
            self._status = ConnectionStatus.CONNECTED
        elif self._hid_file is None and self._status != ConnectionStatus.CONNECTING:
            self._status = ConnectionStatus.DISCONNECTED
        return self._status

    def send(self, data: bytes) -> bool:
        """Send HID report.

        Args:
            data: HID report bytes (must match config.report_size)

        Returns:
            True if send successful

        Raises:
            TransportError: If not connected, invalid report size, or send fails
        """
        if not self.is_connected():
            raise TransportError("HID not connected")

        if len(data) != self.config.report_size:
            raise TransportError(
                f"Invalid HID report size: {len(data)} (expected {self.config.report_size})"
            )

        try:
            self._hid_file.write(data)
            self._hid_file.flush()
            return True
        except Exception as e:
            self._status = ConnectionStatus.ERROR
            raise TransportError(f"HID send failed: {e}")

    def receive(self, size: int = 1, timeout_ms: Optional[int] = None) -> bytes:
        """Receive data from HID.

        Note: HID is output-only. This method always raises TransportError.

        Raises:
            TransportError: Always (HID is output-only)
        """
        raise TransportError("HID is output-only (receive not supported)")

    def readline(self, timeout_ms: Optional[int] = None) -> bytes:
        """Receive line from HID.

        Note: HID is output-only. This method always raises TransportError.

        Raises:
            TransportError: Always (HID is output-only)
        """
        raise TransportError("HID is output-only (readline not supported)")

    def flush(self) -> None:
        """Flush HID write buffer."""
        if self.is_connected():
            self._hid_file.flush()

    # HID-specific convenience methods

    def write_report(self, report: bytes) -> None:
        """Write HID report (convenience wrapper for send()).

        Args:
            report: HID report bytes (must be config.report_size bytes)

        Raises:
            TransportError: If not connected, invalid report, or write fails
        """
        self.send(report)

    def send_key(self, keycode: int, modifier: int = 0, delay: Optional[float] = None) -> None:
        """Send a single key press and release.

        Args:
            keycode: USB HID keycode (4-57 for a-z, 0-9, etc.)
            modifier: Modifier byte (0=none, 2=left shift, etc.)
            delay: Delay between press and release (default: config.key_delay)

        Raises:
            TransportError: If not connected or write fails
        """
        if delay is None:
            delay = self.config.key_delay

        # Key press
        press_report = bytes([modifier, 0, keycode, 0, 0, 0, 0, 0])
        self.write_report(press_report)
        time.sleep(delay)

        # Key release
        release_report = bytes([0, 0, 0, 0, 0, 0, 0, 0])
        self.write_report(release_report)
        time.sleep(delay)

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

    @property
    def device(self) -> str:
        """Legacy property - access via config.device instead."""
        return self.config.device

    @property
    def REPORT_SIZE(self) -> int:
        """Legacy property - access via config.report_size instead."""
        return self.config.report_size
