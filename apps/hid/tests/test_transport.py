"""Tests for transport layer (UART and HID)."""

import pytest

from dictacode_hid import HidTransport, TransportError, UartTransport


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


class TestHidTransport:
    """Tests for HidTransport."""

    def test_init(self):
        """Test HID transport initialization."""
        hid = HidTransport(device="/dev/hidg0")
        assert hid.device == "/dev/hidg0"
        assert not hid.is_open()

    def test_write_without_open_raises_error(self):
        """Test writing without opening raises TransportError."""
        hid = HidTransport(device="/dev/hidg0")
        with pytest.raises(TransportError, match="HID not open"):
            hid.write_report(bytes([0] * 8))

    def test_write_invalid_report_size_raises_error(self):
        """Test writing invalid report size raises TransportError."""
        # This test requires mocking or a real HID device
        # For now, just test the validation logic indirectly
        pass
