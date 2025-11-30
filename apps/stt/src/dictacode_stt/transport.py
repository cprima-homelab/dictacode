"""
transport.py - Layer 2: Raw byte I/O for UART.

Provides clean interface for serial port read/write operations.

Usage:
    uart = UartTransport(device="/dev/serial0", baud_rate=115200)
    uart.open()
    data = uart.read(1024)
    uart.write(b"hello")
    uart.close()

    # Or use as context manager:
    with UartTransport("/dev/serial0") as uart:
        uart.write(b"hello")
"""


class TransportError(Exception):
    """Base exception for transport layer errors."""
    pass


class UartTransport:
    """UART transport layer - raw serial I/O."""

    def __init__(self, device: str, baud_rate: int = 115200, timeout: float = 1.0):
        """
        Initialize UART transport.

        Args:
            device: Serial device path (e.g., /dev/serial0)
            baud_rate: Baud rate (default: 115200)
            timeout: Read timeout in seconds (default: 1.0)
        """
        self.device = device
        self.baud_rate = baud_rate
        self.timeout = timeout
        self._serial = None

    def open(self) -> None:
        """Open serial port."""
        if self._serial is not None:
            raise TransportError("UART already open")

        try:
            import serial
        except ImportError:
            raise TransportError("pyserial not installed. Run: pip install pyserial")

        try:
            self._serial = serial.Serial(
                self.device,
                self.baud_rate,
                timeout=self.timeout,
            )
        except Exception as e:
            raise TransportError(f"Failed to open {self.device}: {e}")

    def close(self) -> None:
        """Close serial port."""
        if self._serial is not None:
            self._serial.close()
            self._serial = None

    def is_open(self) -> bool:
        """Check if port is open."""
        return self._serial is not None and self._serial.is_open

    def read(self, size: int = 1) -> bytes:
        """
        Read bytes from serial port.

        Args:
            size: Number of bytes to read

        Returns:
            Bytes read (may be less than size if timeout)

        Raises:
            TransportError: If port not open or read fails
        """
        if not self.is_open():
            raise TransportError("UART not open")

        try:
            return self._serial.read(size)
        except Exception as e:
            raise TransportError(f"UART read failed: {e}")

    def readline(self) -> bytes:
        """
        Read until newline (for JSON protocol).

        Returns:
            Line including newline, or empty bytes on timeout

        Raises:
            TransportError: If port not open or read fails
        """
        if not self.is_open():
            raise TransportError("UART not open")

        try:
            return self._serial.readline()
        except Exception as e:
            raise TransportError(f"UART readline failed: {e}")

    def write(self, data: bytes) -> int:
        """
        Write bytes to serial port.

        Args:
            data: Bytes to write

        Returns:
            Number of bytes written

        Raises:
            TransportError: If port not open or write fails
        """
        if not self.is_open():
            raise TransportError("UART not open")

        try:
            n = self._serial.write(data)
            self._serial.flush()
            return n
        except Exception as e:
            raise TransportError(f"UART write failed: {e}")

    def flush(self) -> None:
        """Flush write buffer."""
        if self.is_open():
            self._serial.flush()

    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
