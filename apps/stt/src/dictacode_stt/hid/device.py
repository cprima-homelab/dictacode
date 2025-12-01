"""
device.py - HID Device Model (v0.2.8 Phase 5)

Data models for HID devices in the multi-device registry.

Represents a configured HID device (Pi Zero running dictacode-hid) that
can receive transcribed text from the STT service.

Usage:
    device = HidDevice(
        device_id="pi0-desk",
        name="Desk Pi Zero (UART)",
        transport="uart",
        address="/dev/serial0",
        priority=10
    )

    # Get transport kwargs for factory
    transport_kwargs = device.get_transport_kwargs()
    transport = create_transport(device.transport, **transport_kwargs)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any


class HidDeviceStatus(Enum):
    """HID device connection status."""
    UNKNOWN = "unknown"      # Status not yet determined
    ONLINE = "online"        # Device reachable but not active
    OFFLINE = "offline"      # Device unreachable
    ACTIVE = "active"        # Currently selected and in use
    ERROR = "error"          # Device has errors


@dataclass
class HidDevice:
    """Represents a configured HID device.

    A HID device is a Pi Zero (or similar) running dictacode-hid that
    can receive transcribed text and type it as keyboard input.

    Attributes:
        device_id: Unique identifier (e.g., "pi0-desk", "pi0-laptop")
        name: Human-readable name
        transport: Transport type ("uart", "usb-serial", "wifi")
        address: Connection address (port path or IP address)
        port: TCP port for WiFi transport (default: 9876)
        priority: Priority for device selection (lower = higher priority)
        status: Current device status
        metadata: Additional device-specific configuration
    """
    device_id: str
    name: str
    transport: str
    address: str
    port: Optional[int] = None
    priority: int = 100
    status: HidDeviceStatus = HidDeviceStatus.UNKNOWN
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_transport_kwargs(self) -> Dict[str, Any]:
        """Get transport factory kwargs for this device.

        Returns:
            Dictionary of kwargs for create_transport()

        Examples:
            # UART device
            device = HidDevice(transport="uart", address="/dev/serial0")
            kwargs = device.get_transport_kwargs()
            # Returns: {"device": "/dev/serial0"}

            # WiFi device
            device = HidDevice(transport="wifi", address="192.168.1.100", port=9876)
            kwargs = device.get_transport_kwargs()
            # Returns: {"host": "192.168.1.100", "port": 9876}

            # USB-Serial device
            device = HidDevice(
                transport="usb-serial",
                address="0403:6011",
                metadata={"channel": 0}
            )
            kwargs = device.get_transport_kwargs()
            # Returns: {"vendor_id": 0x0403, "product_id": 0x6011, "channel": 0}
        """
        kwargs = {}

        if self.transport == "uart":
            kwargs["device"] = self.address

        elif self.transport in ("usb-serial", "usb_serial", "usb"):
            # Parse vendor:product ID from address
            if ":" in self.address:
                try:
                    vid_str, pid_str = self.address.split(":", 1)
                    kwargs["vendor_id"] = int(vid_str, 16)
                    kwargs["product_id"] = int(pid_str, 16)
                except ValueError:
                    # Fallback: treat as port path
                    kwargs["port"] = self.address
            else:
                # Direct port specification
                kwargs["port"] = self.address

            # Add channel if specified
            if "channel" in self.metadata:
                kwargs["channel"] = self.metadata["channel"]

            # Add serial number if specified
            if "serial_number" in self.metadata:
                kwargs["serial_number"] = self.metadata["serial_number"]

        elif self.transport in ("wifi", "tcp", "network"):
            kwargs["host"] = self.address
            kwargs["port"] = self.port or 9876

        # Add any additional metadata as kwargs
        for key, value in self.metadata.items():
            if key not in kwargs:  # Don't override existing kwargs
                kwargs[key] = value

        return kwargs

    def is_available(self) -> bool:
        """Check if device is available for connection.

        Returns:
            True if device status indicates it's available
        """
        return self.status in (HidDeviceStatus.ONLINE, HidDeviceStatus.ACTIVE)

    def is_active(self) -> bool:
        """Check if device is currently active.

        Returns:
            True if device is the active device
        """
        return self.status == HidDeviceStatus.ACTIVE

    def __str__(self) -> str:
        """Human-readable device description."""
        parts = [f"{self.device_id} ({self.name})"]
        parts.append(f"{self.transport}://{self.address}")
        if self.port:
            parts.append(f":{self.port}")
        parts.append(f"[{self.status.value}]")
        return " ".join(parts)

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"HidDevice(device_id={self.device_id!r}, "
            f"name={self.name!r}, "
            f"transport={self.transport!r}, "
            f"address={self.address!r}, "
            f"status={self.status})"
        )
