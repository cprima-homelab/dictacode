"""
usb_serial.py - USB-Serial Transport Adapter (v0.2.8 Phase 2)

USB-to-Serial transport for USB TTL cables (FTDI, CH340, CP2102, etc.).
Supports auto-detection of USB devices by vendor/product ID and serial number.

Useful for:
- Development: Connect Pi5 to Pi Zero via USB cable instead of GPIO wiring
- Distance: USB cables can be longer than direct GPIO UART wiring
- Flexibility: Hot-pluggable, no GPIO pin conflicts
- Multi-channel: FTDI FT4232H provides 4 independent serial ports

Usage:
    # Auto-detect FTDI device
    config = UsbSerialConfig(vendor_id=0x0403, product_id=0x6011)
    transport = UsbSerialTransport(config)
    transport.connect()

    # Direct port specification
    config = UsbSerialConfig(port="/dev/ttyUSB0")
    transport = UsbSerialTransport(config)

    # Specific device by serial number
    config = UsbSerialConfig(serial_number="FT1234AB")
    transport = UsbSerialTransport(config)

    # Multi-channel adapter (FT4232H channel 1)
    config = UsbSerialConfig(vendor_id=0x0403, product_id=0x6011, channel=1)
    transport = UsbSerialTransport(config)
"""

import logging
from dataclasses import dataclass
from typing import Optional, List

from ..lock import SerialLock
from .adapter import TransportAdapter, TransportConfig, TransportError, ConnectionStatus

logger = logging.getLogger(__name__)


# Known USB-Serial chip identifiers
# Format: (vendor_id, product_id): "Device Name"
KNOWN_USB_SERIAL_DEVICES = {
    (0x0403, 0x6001): "FTDI FT232R",
    (0x0403, 0x6010): "FTDI FT2232H",
    (0x0403, 0x6011): "FTDI FT4232H",
    (0x0403, 0x6014): "FTDI FT232H",
    (0x1a86, 0x7523): "CH340",
    (0x10c4, 0xea60): "CP2102",
    (0x067b, 0x2303): "Prolific PL2303",
}


@dataclass
class UsbSerialDevice:
    """Detected USB-serial device information."""
    port: str                    # e.g., "/dev/ttyUSB0"
    vendor_id: int               # e.g., 0x0403 (FTDI)
    product_id: int              # e.g., 0x6011 (FT4232H)
    serial_number: Optional[str] # Unique device serial
    description: str             # e.g., "FT4232H"
    manufacturer: Optional[str]  # e.g., "FTDI"
    location: Optional[str]      # USB bus location

    def __str__(self) -> str:
        """Human-readable device description."""
        parts = [self.port]

        # Add recognized chip name if known
        chip_name = KNOWN_USB_SERIAL_DEVICES.get((self.vendor_id, self.product_id))
        if chip_name:
            parts.append(chip_name)
        else:
            parts.append(f"{self.vendor_id:04x}:{self.product_id:04x}")

        if self.serial_number:
            parts.append(f"S/N: {self.serial_number}")

        if self.manufacturer:
            parts.append(f"({self.manufacturer})")

        return " ".join(parts)


@dataclass
class UsbSerialConfig(TransportConfig):
    """USB-Serial transport configuration.

    Device selection priority (first match wins):
    1. Direct port specification (port parameter)
    2. Serial number match (serial_number parameter)
    3. Vendor/Product ID match (vendor_id + product_id)

    For multi-channel adapters (FT4232H), use channel parameter.

    Attributes:
        port: Direct serial port path (e.g., "/dev/ttyUSB0")
        vendor_id: USB vendor ID (e.g., 0x0403 for FTDI)
        product_id: USB product ID (e.g., 0x6011 for FT4232H)
        serial_number: Device serial number for unique identification
        channel: Channel number for multi-channel adapters (0-3 for FT4232H)
        baud_rate: Baud rate (default: 115200)
        timeout: Read timeout in seconds (default: 1.0)
        lock_dir: Optional lock directory override (for testing)
    """
    port: Optional[str] = None
    vendor_id: Optional[int] = None
    product_id: Optional[int] = None
    serial_number: Optional[str] = None
    channel: int = 0
    baud_rate: int = 115200
    timeout: float = 1.0
    lock_dir: Optional[str] = None


class UsbSerialTransport(TransportAdapter):
    """USB-Serial transport adapter for USB TTL cables.

    Automatically detects USB-to-serial devices (FTDI, CH340, CP2102, etc.)
    and establishes serial communication with exclusive locking.

    Supports:
    - Auto-detection by vendor/product ID
    - Device selection by serial number
    - Multi-channel adapters (FT4232H has 4 channels)
    - Hot-plug detection
    """

    def __init__(self, config: UsbSerialConfig):
        """Initialize USB-Serial transport.

        Args:
            config: USB-Serial configuration
        """
        self.config = config
        self._serial = None
        self._lock: Optional[SerialLock] = None
        self._status = ConnectionStatus.DISCONNECTED
        self._detected_port: Optional[str] = None

    def get_name(self) -> str:
        """Return transport type name."""
        return "usb-serial"

    @classmethod
    def list_devices(cls) -> List[UsbSerialDevice]:
        """Enumerate all USB-serial devices.

        Returns:
            List of detected USB-serial devices

        Example:
            devices = UsbSerialTransport.list_devices()
            for device in devices:
                print(f"{device.port}: {device.description}")
        """
        try:
            import serial.tools.list_ports
        except ImportError:
            logger.error("pyserial not installed. Run: pip install pyserial")
            return []

        devices = []
        for port_info in serial.tools.list_ports.comports():
            if port_info.vid is not None:  # USB device
                devices.append(UsbSerialDevice(
                    port=port_info.device,
                    vendor_id=port_info.vid,
                    product_id=port_info.pid,
                    serial_number=port_info.serial_number,
                    description=port_info.description or "",
                    manufacturer=port_info.manufacturer,
                    location=port_info.location,
                ))

        return devices

    def _find_port(self) -> Optional[str]:
        """Find serial port matching configuration.

        Priority:
        1. Direct port specification (config.port)
        2. Serial number match
        3. Vendor/Product ID match (with channel for multi-channel)

        Returns:
            Port path if found, None otherwise
        """
        # Priority 1: Direct port override
        if self.config.port:
            logger.debug(f"Using direct port specification: {self.config.port}")
            return self.config.port

        # Get all USB-serial devices
        devices = self.list_devices()
        if not devices:
            logger.warning("No USB-serial devices found")
            return None

        # Priority 2: Match by serial number
        if self.config.serial_number:
            for device in devices:
                if device.serial_number == self.config.serial_number:
                    logger.info(f"Found device by serial number: {device}")
                    return device.port
            logger.warning(f"No device found with serial number: {self.config.serial_number}")
            return None

        # Priority 3: Match by vendor/product ID
        if self.config.vendor_id and self.config.product_id:
            matching_devices = [
                d for d in devices
                if d.vendor_id == self.config.vendor_id
                and d.product_id == self.config.product_id
            ]

            if not matching_devices:
                logger.warning(
                    f"No device found with VID:PID "
                    f"{self.config.vendor_id:04x}:{self.config.product_id:04x}"
                )
                return None

            # For multi-channel adapters, use channel parameter
            if len(matching_devices) > 1 and self.config.channel > 0:
                if self.config.channel < len(matching_devices):
                    device = matching_devices[self.config.channel]
                    logger.info(
                        f"Found device (channel {self.config.channel}): {device}"
                    )
                    return device.port
                else:
                    logger.warning(
                        f"Channel {self.config.channel} not available "
                        f"(only {len(matching_devices)} channels found)"
                    )
                    return None

            # Use first matching device
            device = matching_devices[0]
            logger.info(f"Found device: {device}")
            if len(matching_devices) > 1:
                logger.info(
                    f"Multiple devices found ({len(matching_devices)}), "
                    f"using first. Specify channel or serial number for others."
                )
            return device.port

        logger.error("No device selection criteria specified (port, serial_number, or vid:pid)")
        return None

    def connect(self) -> bool:
        """Establish USB-Serial connection with exclusive lock.

        Returns:
            True if connection successful

        Raises:
            TransportError: If already connected, device not found, or connection fails
        """
        if self._serial is not None:
            raise TransportError("USB-Serial already connected")

        try:
            import serial
        except ImportError:
            raise TransportError("pyserial not installed. Run: pip install pyserial")

        self._status = ConnectionStatus.CONNECTING

        # Find the serial port
        port = self._find_port()
        if not port:
            self._status = ConnectionStatus.ERROR
            raise TransportError(
                "USB-Serial device not found. "
                "Check device connection and configuration. "
                "Use list_devices() to see available devices."
            )

        self._detected_port = port

        # Acquire exclusive lock
        self._lock = SerialLock(port, lock_dir=self.config.lock_dir)
        if not self._lock.acquire():
            pid = self._lock.get_owner_pid()
            msg = f"{port} is locked by another process."
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
                port,
                self.config.baud_rate,
                timeout=self.config.timeout,
            )
            self._status = ConnectionStatus.CONNECTED
            logger.info(f"USB-Serial connected: {port} @ {self.config.baud_rate}")
            return True
        except Exception as e:
            # Release lock on failure
            if self._lock:
                self._lock.release()
                self._lock = None
            self._status = ConnectionStatus.ERROR
            raise TransportError(f"Failed to open {port}: {e}")

    def disconnect(self) -> None:
        """Close USB-Serial connection and release lock."""
        if self._serial is not None:
            self._serial.close()
            self._serial = None
        if self._lock is not None:
            self._lock.release()
            self._lock = None
        self._status = ConnectionStatus.DISCONNECTED
        self._detected_port = None

    def is_connected(self) -> bool:
        """Check if USB-Serial is connected."""
        return self._serial is not None and self._serial.is_open

    def get_status(self) -> ConnectionStatus:
        """Get current connection status."""
        if self._serial is not None and self._serial.is_open:
            self._status = ConnectionStatus.CONNECTED
        elif self._serial is None and self._status != ConnectionStatus.CONNECTING:
            self._status = ConnectionStatus.DISCONNECTED
        return self._status

    def send(self, data: bytes) -> bool:
        """Send data over USB-Serial.

        Args:
            data: Bytes to send

        Returns:
            True if send successful

        Raises:
            TransportError: If not connected or send fails
        """
        if not self.is_connected():
            raise TransportError("USB-Serial not connected")

        try:
            n = self._serial.write(data)
            self._serial.flush()
            return n == len(data)
        except Exception as e:
            self._status = ConnectionStatus.ERROR
            raise TransportError(f"USB-Serial send failed: {e}")

    def receive(self, size: int = 1, timeout_ms: Optional[int] = None) -> bytes:
        """Receive data from USB-Serial.

        Args:
            size: Number of bytes to receive
            timeout_ms: Optional timeout override in milliseconds

        Returns:
            Bytes received (may be less than size on timeout)

        Raises:
            TransportError: If not connected or receive fails
        """
        if not self.is_connected():
            raise TransportError("USB-Serial not connected")

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
            raise TransportError(f"USB-Serial receive failed: {e}")
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
            raise TransportError("USB-Serial not connected")

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
            raise TransportError(f"USB-Serial readline failed: {e}")
        finally:
            # Restore original timeout
            if original_timeout is not None:
                self._serial.timeout = original_timeout

    def flush(self) -> None:
        """Flush USB-Serial write buffer."""
        if self.is_connected():
            self._serial.flush()

    def get_device_info(self) -> Optional[UsbSerialDevice]:
        """Get information about the connected device.

        Returns:
            UsbSerialDevice info if connected, None otherwise
        """
        if not self._detected_port:
            return None

        devices = self.list_devices()
        for device in devices:
            if device.port == self._detected_port:
                return device

        return None
