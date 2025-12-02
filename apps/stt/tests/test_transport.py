"""Tests for transport layer (UART)."""

import pytest

from dictacode_stt import TransportError, UartTransport


class TestUartTransport:
    """Tests for UartTransport."""

    def test_init(self):
        """Test UART transport initialization."""
        uart = UartTransport(device="/dev/serial0", baud_rate=115200)
        assert uart.device == "/dev/serial0"
        assert uart.baud_rate == 115200
        assert uart.timeout == 1.0
        assert not uart.is_open()

    def test_open_without_device_raises_error(self):
        """Test opening non-existent device raises TransportError."""
        uart = UartTransport(device="/dev/nonexistent")
        with pytest.raises(TransportError, match="Failed to open"):
            uart.open()

    def test_read_without_open_raises_error(self):
        """Test reading without opening raises TransportError."""
        uart = UartTransport(device="/dev/serial0")
        with pytest.raises(TransportError, match="UART not open"):
            uart.read(1)

    def test_write_without_open_raises_error(self):
        """Test writing without opening raises TransportError."""
        uart = UartTransport(device="/dev/serial0")
        with pytest.raises(TransportError, match="UART not open"):
            uart.write(b"test")

    def test_context_manager(self):
        """Test context manager functionality."""
        # This would require a mock or real device
        pass
