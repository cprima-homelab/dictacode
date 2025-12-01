"""Audio port manager - device discovery and lifecycle management."""

import logging
from typing import List, Optional, Callable
import sounddevice as sd

from .port import AudioPort, AudioPortCapabilities, PortStatus
from .device_id import generate_port_id

logger = logging.getLogger(__name__)


class AudioPortManager:
    """Manages audio port discovery and lifecycle.

    Provides backend data for CLI and web frontend.
    """

    def __init__(self):
        """Initialize the audio port manager."""
        self._ports_cache: Optional[List[AudioPort]] = None
        self._on_port_changed_callback: Optional[Callable] = None

    def list_ports(self, force_refresh: bool = False) -> List[AudioPort]:
        """Enumerate all available audio input ports.

        Args:
            force_refresh: If True, bypass cache and re-enumerate devices

        Returns:
            List of AudioPort objects, sorted by port_id
        """
        if self._ports_cache is not None and not force_refresh:
            logger.debug(f"Returning cached ports ({len(self._ports_cache)} ports)")
            return self._ports_cache

        logger.info("Enumerating audio input ports...")
        ports = []

        try:
            # Get all devices from sounddevice
            devices = sd.query_devices()

            for idx, device_info in enumerate(devices):
                # Skip output-only devices
                if device_info.get("max_input_channels", 0) <= 0:
                    continue

                # Generate stable port ID
                port_id, port_type = generate_port_id(device_info)

                # Get device capabilities
                try:
                    capabilities = AudioPortCapabilities.from_device_info(device_info)
                except Exception as e:
                    logger.warning(
                        f"Could not determine capabilities for device {idx}: {e}"
                    )
                    continue

                # Create AudioPort instance
                port = AudioPort(
                    port_id=port_id,
                    port_type=port_type,
                    name=device_info.get("name", f"Unknown Device {idx}"),
                    capabilities=capabilities,
                    status=PortStatus.AVAILABLE,
                    device_index=idx,
                )

                ports.append(port)
                logger.debug(
                    f"Discovered port: {port_id} ({port.name}) "
                    f"[{port.capabilities.native_rate}Hz]"
                )

        except Exception as e:
            logger.error(f"Failed to enumerate audio ports: {e}")
            raise

        # Sort by port_id for consistent ordering
        ports.sort(key=lambda p: p.port_id)

        logger.info(f"Found {len(ports)} audio input port(s)")
        self._ports_cache = ports
        return ports

    def get_port(self, port_id: str) -> Optional[AudioPort]:
        """Get specific port by stable ID.

        Args:
            port_id: Stable port identifier (e.g., "rode-videomic-ntg", "usb:1-1.3")

        Returns:
            AudioPort instance or None if not found
        """
        ports = self.list_ports()

        for port in ports:
            if port.port_id == port_id:
                logger.debug(f"Found port: {port_id}")
                return port

        logger.warning(f"Port not found: {port_id}")
        return None

    def get_default_port(self) -> Optional[AudioPort]:
        """Get system default audio input.

        Returns:
            AudioPort for default input device, or None if not available
        """
        try:
            default_device = sd.query_devices(kind="input")
            default_index = default_device["index"]

            ports = self.list_ports()
            for port in ports:
                if port.device_index == default_index:
                    logger.info(f"Default input port: {port.port_id}")
                    return port

        except Exception as e:
            logger.error(f"Could not determine default input port: {e}")

        # Fallback: return first available port
        ports = self.list_ports()
        if ports:
            logger.info(f"Fallback to first port: {ports[0].port_id}")
            return ports[0]

        logger.warning("No audio input ports available")
        return None

    def get_active_port(self) -> Optional[AudioPort]:
        """Get currently streaming port (if any).

        Returns:
            AudioPort that is currently streaming, or None
        """
        ports = self.list_ports()

        for port in ports:
            if port.is_streaming():
                logger.debug(f"Active port: {port.port_id}")
                return port

        logger.debug("No active streaming port")
        return None

    def register_callback(self, on_port_changed: Callable) -> None:
        """Register callback for port changes (hot-plug support).

        Args:
            on_port_changed: Callback function called when ports change

        Note:
            Hot-plug detection is not implemented in v0.2.4.
            This is a placeholder for future implementation.
        """
        self._on_port_changed_callback = on_port_changed
        logger.info("Registered port change callback (hot-plug not yet implemented)")

    def refresh_ports(self) -> List[AudioPort]:
        """Force refresh of port list (useful for detecting hot-plugged devices).

        Returns:
            Updated list of AudioPort objects
        """
        logger.info("Refreshing port list...")
        return self.list_ports(force_refresh=True)
