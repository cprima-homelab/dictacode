"""
transport package - Transport Layer Abstraction (v0.2.8)

Provides unified interface for different transport types:
- UART (serial port) - v0.2.8 Phase 1
- USB-Serial - v0.2.8 Phase 2 (future)
- WiFi (TCP) - v0.2.8 Phase 3 (future)

Usage:
    from dictacode_stt.transport import UartTransport, UartConfig

    config = UartConfig(device="/dev/serial0", baud_rate=115200)
    transport = UartTransport(config)

    with transport:
        transport.send(b"hello")
        response = transport.readline()
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

# USB-Serial transport (v0.2.8 Phase 2)
from .usb_serial import UsbSerialTransport, UsbSerialConfig, UsbSerialDevice

# WiFi transport (v0.2.8 Phase 3)
from .wifi import WifiTransport, WifiConfig

# Factory functions (v0.2.8 Phase 4)
from .factory import (
    create_transport,
    create_transport_from_config,
    list_available_transports,
    get_transport_info,
    list_usb_serial_devices,
    detect_available_transports,
)

__all__ = [
    # Base classes
    "TransportAdapter",
    "TransportConfig",
    "TransportError",
    "ConnectionStatus",
    # UART
    "UartTransport",
    "UartConfig",
    # USB-Serial
    "UsbSerialTransport",
    "UsbSerialConfig",
    "UsbSerialDevice",
    # WiFi
    "WifiTransport",
    "WifiConfig",
    # Factory functions
    "create_transport",
    "create_transport_from_config",
    "list_available_transports",
    "get_transport_info",
    "list_usb_serial_devices",
    "detect_available_transports",
]
