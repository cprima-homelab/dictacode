"""
transport package - Transport Layer Abstraction (v0.2.8)

Provides unified interface for different transport types:
- UART (serial port) - v0.2.8 Phase 1
- HID (keyboard/mouse output) - v0.2.8 Phase 1
- USB-Serial - v0.2.8 Phase 2 (future)
- WiFi (TCP) - v0.2.8 Phase 3 (future)

Usage:
    from dictacode_hid.transport import UartTransport, UartConfig, HidTransport, HidConfig

    # UART for receiving from STT device
    uart_config = UartConfig(device="/dev/serial0", baud_rate=115200)
    uart = UartTransport(uart_config)

    # HID for sending keyboard events to host
    hid_config = HidConfig(device="/dev/hidg0")
    hid = HidTransport(hid_config)

    with uart, hid:
        data = uart.readline()
        hid.send_key(4)  # 'a' key
"""

# Base classes and types
from .adapter import (
    TransportAdapter,
    TransportConfig,
    TransportError,
    ConnectionStatus,
)

# UART transport (v0.2.8 Phase 1)
from .uart import UartTransport, UartConfig

# HID transport (v0.2.8 Phase 1)
from .hid import HidTransport, HidConfig

# USB-Serial transport (v0.2.8 Phase 2)
from .usb_serial import UsbSerialTransport, UsbSerialConfig, UsbSerialDevice

# WiFi transport server (v0.2.8 Phase 3)
from .wifi import WifiServerTransport, WifiServerConfig

__all__ = [
    # Base classes
    "TransportAdapter",
    "TransportConfig",
    "TransportError",
    "ConnectionStatus",
    # UART
    "UartTransport",
    "UartConfig",
    # HID
    "HidTransport",
    "HidConfig",
    # USB-Serial
    "UsbSerialTransport",
    "UsbSerialConfig",
    "UsbSerialDevice",
    # WiFi Server
    "WifiServerTransport",
    "WifiServerConfig",
]
