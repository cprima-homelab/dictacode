"""
hid package - HID Device Management (v0.2.8 Phase 5)

Multi-device registry for managing HID devices (Pi Zeros running dictacode-hid).

Provides:
- HidDevice: Data model for HID device configuration
- HidDeviceStatus: Enum for device status
- HidDeviceRegistry: Registry for managing multiple devices

Usage:
    from dictacode_stt.hid import HidDeviceRegistry, HidDevice, HidDeviceStatus

    # Load devices from config
    registry = HidDeviceRegistry()
    registry.load_devices()

    # Get active device
    device = registry.get_active_device()
    if not device:
        device = registry.get_default_device()

    # Create transport for device
    transport_kwargs = device.get_transport_kwargs()
    transport = create_transport(device.transport, **transport_kwargs)
"""

from .device import HidDevice, HidDeviceStatus
from .registry import HidDeviceRegistry


__all__ = [
    "HidDevice",
    "HidDeviceRegistry",
    "HidDeviceStatus",
]
