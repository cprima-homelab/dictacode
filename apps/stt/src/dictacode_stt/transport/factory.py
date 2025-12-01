"""
factory.py - Transport Factory (v0.2.8 Phase 4)

Factory functions for creating transport adapters by name or from configuration.

Usage:
    # Create by name with explicit config
    config = UartConfig(device="/dev/serial0", baud_rate=115200)
    transport = create_transport("uart", config)

    # Create from config dictionary
    transport = create_transport_from_config({
        "type": "uart",
        "device": "/dev/serial0",
        "baud_rate": 115200
    })

    # List available transports
    transports = list_available_transports()
"""

import logging
from typing import Dict, Any, List, Optional

from .adapter import TransportAdapter, TransportConfig
from .uart import UartTransport, UartConfig
from .usb_serial import UsbSerialTransport, UsbSerialConfig, UsbSerialDevice
from .wifi import WifiTransport, WifiConfig

logger = logging.getLogger(__name__)


def create_transport(
    transport_type: str,
    config: Optional[TransportConfig] = None,
    **kwargs
) -> TransportAdapter:
    """Create a transport adapter by type name.

    Args:
        transport_type: Transport type ("uart", "usb-serial", "wifi")
        config: Transport configuration object (optional)
        **kwargs: Configuration parameters if config not provided

    Returns:
        Transport adapter instance

    Raises:
        ValueError: If transport type is unknown
        TypeError: If configuration is invalid

    Examples:
        # With config object
        config = UartConfig(device="/dev/serial0")
        transport = create_transport("uart", config)

        # With kwargs
        transport = create_transport("uart", device="/dev/serial0", baud_rate=115200)

        # USB-Serial by VID:PID
        transport = create_transport("usb-serial", vendor_id=0x0403, product_id=0x6011)

        # WiFi
        transport = create_transport("wifi", host="pi0-hid.local", port=9876)
    """
    transport_type = transport_type.lower()

    # UART transport
    if transport_type in ("uart", "serial"):
        if config is None:
            config = UartConfig(**kwargs)
        elif not isinstance(config, UartConfig):
            raise TypeError(f"Expected UartConfig, got {type(config).__name__}")
        return UartTransport(config)

    # USB-Serial transport
    elif transport_type in ("usb-serial", "usb_serial", "usb"):
        if config is None:
            config = UsbSerialConfig(**kwargs)
        elif not isinstance(config, UsbSerialConfig):
            raise TypeError(f"Expected UsbSerialConfig, got {type(config).__name__}")
        return UsbSerialTransport(config)

    # WiFi transport
    elif transport_type in ("wifi", "tcp", "network"):
        if config is None:
            config = WifiConfig(**kwargs)
        elif not isinstance(config, WifiConfig):
            raise TypeError(f"Expected WifiConfig, got {type(config).__name__}")
        return WifiTransport(config)

    else:
        available = list_available_transports()
        raise ValueError(
            f"Unknown transport type: '{transport_type}'. "
            f"Available: {', '.join(available)}"
        )


def create_transport_from_config(config_dict: Dict[str, Any]) -> TransportAdapter:
    """Create a transport adapter from a configuration dictionary.

    Args:
        config_dict: Configuration dictionary with 'type' key and transport-specific parameters

    Returns:
        Transport adapter instance

    Raises:
        ValueError: If 'type' key missing or transport type unknown
        TypeError: If configuration parameters are invalid

    Examples:
        # UART
        transport = create_transport_from_config({
            "type": "uart",
            "device": "/dev/serial0",
            "baud_rate": 115200
        })

        # USB-Serial
        transport = create_transport_from_config({
            "type": "usb-serial",
            "vendor_id": "0x0403",  # Hex string or int
            "product_id": "0x6011",
            "channel": 0
        })

        # WiFi
        transport = create_transport_from_config({
            "type": "wifi",
            "host": "192.168.1.100",
            "port": 9876,
            "connect_timeout": 5.0
        })
    """
    if "type" not in config_dict:
        raise ValueError("Configuration dictionary must contain 'type' key")

    transport_type = config_dict["type"]
    config_params = {k: v for k, v in config_dict.items() if k != "type"}

    # Handle hex strings for USB vendor/product IDs
    if transport_type in ("usb-serial", "usb_serial", "usb"):
        if "vendor_id" in config_params and isinstance(config_params["vendor_id"], str):
            config_params["vendor_id"] = int(config_params["vendor_id"], 0)  # Auto-detect hex/dec
        if "product_id" in config_params and isinstance(config_params["product_id"], str):
            config_params["product_id"] = int(config_params["product_id"], 0)

    return create_transport(transport_type, **config_params)


def list_available_transports() -> List[str]:
    """List available transport types.

    Returns:
        List of transport type names
    """
    return ["uart", "usb-serial", "wifi"]


def get_transport_info(transport_type: str) -> Dict[str, Any]:
    """Get information about a transport type.

    Args:
        transport_type: Transport type name

    Returns:
        Dictionary with transport information

    Raises:
        ValueError: If transport type is unknown

    Examples:
        info = get_transport_info("uart")
        # Returns: {
        #     "name": "uart",
        #     "description": "UART serial port communication",
        #     "config_class": "UartConfig",
        #     "adapter_class": "UartTransport"
        # }
    """
    transport_type = transport_type.lower()

    transport_info = {
        "uart": {
            "name": "uart",
            "aliases": ["serial"],
            "description": "UART serial port communication (GPIO pins)",
            "config_class": "UartConfig",
            "adapter_class": "UartTransport",
            "typical_use": "Direct GPIO connection between devices",
        },
        "usb-serial": {
            "name": "usb-serial",
            "aliases": ["usb_serial", "usb"],
            "description": "USB-to-serial adapters (FTDI, CH340, CP2102)",
            "config_class": "UsbSerialConfig",
            "adapter_class": "UsbSerialTransport",
            "typical_use": "USB TTL cables, development setups",
        },
        "wifi": {
            "name": "wifi",
            "aliases": ["tcp", "network"],
            "description": "WiFi/TCP socket communication",
            "config_class": "WifiConfig",
            "adapter_class": "WifiTransport",
            "typical_use": "Wireless HID devices, remote connections",
        },
    }

    # Handle aliases
    for name, info in transport_info.items():
        if transport_type == name or transport_type in info.get("aliases", []):
            return info

    raise ValueError(
        f"Unknown transport type: '{transport_type}'. "
        f"Available: {', '.join(transport_info.keys())}"
    )


def list_usb_serial_devices() -> List[UsbSerialDevice]:
    """List all detected USB-serial devices.

    Convenience function for discovering available USB-serial adapters.

    Returns:
        List of detected USB-serial devices

    Examples:
        devices = list_usb_serial_devices()
        for device in devices:
            print(f"{device.port}: {device.description}")
    """
    return UsbSerialTransport.list_devices()


def detect_available_transports() -> Dict[str, List[str]]:
    """Detect which transports are available on the system.

    Returns:
        Dictionary mapping transport types to lists of available connections

    Examples:
        available = detect_available_transports()
        # Returns: {
        #     "uart": ["/dev/serial0"],
        #     "usb-serial": ["/dev/ttyUSB0 (FTDI FT4232H)", "/dev/ttyUSB1"],
        #     "wifi": []  # Cannot auto-detect without mDNS
        # }
    """
    available = {
        "uart": [],
        "usb-serial": [],
        "wifi": [],
    }

    # Check for UART devices
    import os
    common_uart_devices = ["/dev/serial0", "/dev/ttyAMA0", "/dev/ttyS0"]
    for device in common_uart_devices:
        if os.path.exists(device):
            available["uart"].append(device)

    # Check for USB-serial devices
    usb_devices = list_usb_serial_devices()
    available["usb-serial"] = [str(device) for device in usb_devices]

    # WiFi devices cannot be auto-detected without mDNS discovery
    # (Would need to be in Phase 7: Service Discovery)
    available["wifi"] = []

    return available
