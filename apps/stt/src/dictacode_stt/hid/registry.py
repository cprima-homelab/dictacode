"""
registry.py - HID Device Registry (v0.2.8 Phase 5)

Registry for managing multiple configured HID devices.

Loads device configurations from /etc/dictacode/hid/devices.d/*.conf
and provides device selection, health checking, and status management.

Usage:
    # Load devices from config
    registry = HidDeviceRegistry()
    registry.load_devices()

    # List all devices
    for device in registry.list_devices():
        print(f"{device.device_id}: {device.status}")

    # Get active device
    active = registry.get_active_device()
    if not active:
        active = registry.get_default_device()

    # Set active device
    registry.set_active_device("pi0-desk")
"""

import configparser
import logging
from pathlib import Path
from typing import List, Optional, Dict

from .device import HidDevice, HidDeviceStatus

logger = logging.getLogger(__name__)


class HidDeviceRegistry:
    """Registry of configured HID devices.

    Manages multiple HID devices, loads configurations from files,
    and handles device selection and status tracking.

    Configuration files are loaded from /etc/dictacode/hid/devices.d/*.conf
    Each file represents one HID device configuration.
    """

    DEFAULT_CONFIG_DIR = Path("/etc/dictacode/hid/devices.d")

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize HID device registry.

        Args:
            config_dir: Configuration directory (default: /etc/dictacode/hid/devices.d)
        """
        self.config_dir = config_dir or self.DEFAULT_CONFIG_DIR
        self._devices: Dict[str, HidDevice] = {}
        self._active_device_id: Optional[str] = None

    def load_devices(self) -> None:
        """Load device configurations from config directory.

        Reads all *.conf files from config_dir and parses them as device configurations.
        Clears existing devices before loading.

        Config file format:
            [device]
            id = pi0-desk
            name = Desk Pi Zero (UART)
            transport = uart
            address = /dev/serial0
            priority = 10

            [metadata]
            # Optional device-specific metadata
            channel = 0
            serial_number = FT1234AB
        """
        self._devices.clear()

        if not self.config_dir.exists():
            logger.warning(
                f"HID device config directory not found: {self.config_dir}"
            )
            return

        if not self.config_dir.is_dir():
            logger.error(
                f"HID device config path is not a directory: {self.config_dir}"
            )
            return

        # Load all .conf files
        conf_files = list(self.config_dir.glob("*.conf"))
        if not conf_files:
            logger.warning(
                f"No device configuration files found in {self.config_dir}"
            )
            return

        logger.info(f"Loading HID device configurations from {self.config_dir}")

        for conf_file in conf_files:
            try:
                device = self._parse_device_config(conf_file)
                if device:
                    self._devices[device.device_id] = device
                    logger.debug(f"Loaded device: {device.device_id} from {conf_file.name}")
            except Exception as e:
                logger.error(f"Failed to parse {conf_file}: {e}")

        logger.info(f"Loaded {len(self._devices)} HID device(s)")

    def _parse_device_config(self, path: Path) -> Optional[HidDevice]:
        """Parse a device configuration file.

        Args:
            path: Path to configuration file

        Returns:
            HidDevice if parsing successful, None otherwise

        Config file example:
            [device]
            id = pi0-desk
            name = Desk Pi Zero (UART)
            transport = uart
            address = /dev/serial0
            priority = 10

            [metadata]
            channel = 0
        """
        config = configparser.ConfigParser()
        config.read(path)

        if "device" not in config:
            logger.warning(f"{path}: Missing [device] section")
            return None

        device_section = config["device"]

        # Required fields
        device_id = device_section.get("id", path.stem)
        if not device_id:
            logger.warning(f"{path}: Missing device 'id'")
            return None

        transport = device_section.get("transport", "uart")
        address = device_section.get("address")
        if not address:
            logger.warning(f"{path}: Missing device 'address'")
            return None

        # Optional fields
        name = device_section.get("name", device_id)
        port = device_section.getint("port", fallback=None)
        priority = device_section.getint("priority", fallback=100)

        # Parse metadata section if present
        metadata = {}
        if "metadata" in config:
            metadata = dict(config["metadata"])

            # Convert numeric metadata values
            for key, value in metadata.items():
                try:
                    # Try int first
                    metadata[key] = int(value)
                except ValueError:
                    try:
                        # Try float
                        metadata[key] = float(value)
                    except ValueError:
                        # Keep as string
                        pass

        return HidDevice(
            device_id=device_id,
            name=name,
            transport=transport,
            address=address,
            port=port,
            priority=priority,
            status=HidDeviceStatus.UNKNOWN,
            metadata=metadata,
        )

    def list_devices(self, status_filter: Optional[HidDeviceStatus] = None) -> List[HidDevice]:
        """List all configured devices.

        Args:
            status_filter: Optional status filter

        Returns:
            List of HID devices, sorted by priority

        Examples:
            # All devices
            devices = registry.list_devices()

            # Only online devices
            online = registry.list_devices(status_filter=HidDeviceStatus.ONLINE)
        """
        devices = list(self._devices.values())

        if status_filter:
            devices = [d for d in devices if d.status == status_filter]

        # Sort by priority (lower number = higher priority)
        devices.sort(key=lambda d: d.priority)

        return devices

    def get_device(self, device_id: str) -> Optional[HidDevice]:
        """Get device by ID.

        Args:
            device_id: Device identifier

        Returns:
            HidDevice if found, None otherwise
        """
        return self._devices.get(device_id)

    def get_active_device(self) -> Optional[HidDevice]:
        """Get currently active device.

        Returns:
            Active HID device if set, None otherwise
        """
        if self._active_device_id:
            return self._devices.get(self._active_device_id)
        return None

    def set_active_device(self, device_id: str) -> bool:
        """Set the active device.

        Args:
            device_id: Device identifier to activate

        Returns:
            True if device was set as active, False if device not found

        Side effects:
            - Sets previous active device status to ONLINE (if available)
            - Sets new active device status to ACTIVE
        """
        if device_id not in self._devices:
            logger.error(f"Device not found: {device_id}")
            return False

        # Deactivate previous active device
        if self._active_device_id and self._active_device_id in self._devices:
            prev_device = self._devices[self._active_device_id]
            if prev_device.status == HidDeviceStatus.ACTIVE:
                prev_device.status = HidDeviceStatus.ONLINE

        # Activate new device
        self._active_device_id = device_id
        self._devices[device_id].status = HidDeviceStatus.ACTIVE

        logger.info(f"Active device set to: {device_id}")
        return True

    def get_default_device(self) -> Optional[HidDevice]:
        """Get device with highest priority (lowest number).

        Returns:
            HID device with highest priority, or None if no devices configured

        Examples:
            # Get default device and activate it
            default = registry.get_default_device()
            if default:
                registry.set_active_device(default.device_id)
        """
        if not self._devices:
            return None

        # Return device with lowest priority number (highest priority)
        return min(self._devices.values(), key=lambda d: d.priority)

    def update_device_status(self, device_id: str, status: HidDeviceStatus) -> None:
        """Update device status.

        Args:
            device_id: Device identifier
            status: New status

        Used by health checks and connection monitoring to update device status.
        """
        if device_id in self._devices:
            self._devices[device_id].status = status
            logger.debug(f"Device {device_id} status: {status.value}")
        else:
            logger.warning(f"Cannot update status for unknown device: {device_id}")

    def get_available_devices(self) -> List[HidDevice]:
        """Get devices that are available for connection.

        Returns:
            List of devices with status ONLINE or ACTIVE, sorted by priority
        """
        available = [
            d for d in self._devices.values()
            if d.status in (HidDeviceStatus.ONLINE, HidDeviceStatus.ACTIVE)
        ]
        available.sort(key=lambda d: d.priority)
        return available

    def find_best_available_device(self) -> Optional[HidDevice]:
        """Find the best available device based on priority.

        Returns:
            Device with highest priority that's available, or None

        Priority selection:
        1. Current active device (if available)
        2. Highest priority online device
        3. Highest priority unknown device (not yet checked)
        """
        # Current active device
        active = self.get_active_device()
        if active and active.is_available():
            return active

        # Highest priority online device
        available = self.get_available_devices()
        if available:
            return available[0]  # Already sorted by priority

        # Highest priority unknown device (not yet health-checked)
        unknown = [
            d for d in self._devices.values()
            if d.status == HidDeviceStatus.UNKNOWN
        ]
        if unknown:
            unknown.sort(key=lambda d: d.priority)
            return unknown[0]

        return None

    def count_devices(self, status: Optional[HidDeviceStatus] = None) -> int:
        """Count devices by status.

        Args:
            status: Optional status filter

        Returns:
            Number of devices matching criteria

        Examples:
            total = registry.count_devices()
            online = registry.count_devices(HidDeviceStatus.ONLINE)
            offline = registry.count_devices(HidDeviceStatus.OFFLINE)
        """
        if status is None:
            return len(self._devices)

        return sum(1 for d in self._devices.values() if d.status == status)

    def has_devices(self) -> bool:
        """Check if any devices are configured.

        Returns:
            True if at least one device is configured
        """
        return len(self._devices) > 0

    def clear(self) -> None:
        """Clear all devices from registry.

        Used for testing or reloading configurations.
        """
        self._devices.clear()
        self._active_device_id = None
        logger.debug("Device registry cleared")
