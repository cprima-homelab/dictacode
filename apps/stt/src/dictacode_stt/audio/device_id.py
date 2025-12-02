"""Stable port ID generation for audio devices.

Port ID hierarchy (preference order):
1. Device serial/name - Follows device across USB ports (preferred)
2. USB bus path - Stable per physical port
3. ALSA card ID - Last resort for built-in devices
"""

import logging
import re
from typing import Optional


logger = logging.getLogger(__name__)


def generate_port_id(device_info: dict) -> tuple[str, str]:
    """Generate stable port ID and type for an audio device.

    Args:
        device_info: sounddevice device info dictionary

    Returns:
        Tuple of (port_id, port_type) where:
        - port_id: Stable identifier (serial/name, usb:path, or hw:card)
        - port_type: "usb", "jack", or "alsa"

    Examples:
        >>> generate_port_id(rode_mic_info)
        ("rode-ntg-12345", "usb")

        >>> generate_port_id(usb_no_serial_info)
        ("usb:1-1.3", "usb")

        >>> generate_port_id(builtin_audio_info)
        ("hw:0", "jack")
    """
    name = device_info.get("name", "")
    index = device_info.get("index", -1)

    # Priority 1: Extract device serial/unique name from device name
    port_id, port_type = _try_device_serial(name)
    if port_id:
        logger.debug(f"Generated port ID from serial/name: {port_id}")
        return port_id, port_type

    # Priority 2: Try USB path extraction
    port_id, port_type = _try_usb_path(name, index)
    if port_id:
        logger.debug(f"Generated port ID from USB path: {port_id}")
        return port_id, port_type

    # Priority 3: Fallback to ALSA card number
    port_id, port_type = _fallback_alsa_card(name, index)
    logger.debug(f"Generated port ID from ALSA card: {port_id}")
    return port_id, port_type


def _try_device_serial(name: str) -> tuple[Optional[str], Optional[str]]:
    """Try to extract device serial or unique identifier from name.

    Examples of device names with identifiers:
    - "RØDE VideoMic NTG: USB Audio (hw:2,0)"
    - "C920 HD Pro Webcam: USB Audio (hw:3,0)"
    - "Blue Snowball: USB Audio (hw:1,0)"

    Returns:
        (port_id, port_type) or (None, None) if not found
    """
    # Check for known device patterns
    known_devices = {
        r"RØDE\s+VideoMic\s+NTG": "rode-videomic-ntg",
        r"Blue\s+Snowball": "blue-snowball",
        r"C920\s+HD\s+Pro": "logitech-c920",
        r"Yeti\s+Stereo": "blue-yeti",
    }

    for pattern, device_id in known_devices.items():
        if re.search(pattern, name, re.IGNORECASE):
            return device_id, "usb"

    # Generic approach: use first part of name if it looks like a product name
    # (before colon, cleaned up)
    if ":" in name:
        product_name = name.split(":")[0].strip()
        # Clean up the name: lowercase, replace spaces/special chars with dash
        cleaned = re.sub(r"[^\w\s-]", "", product_name.lower())
        cleaned = re.sub(r"[-\s]+", "-", cleaned).strip("-")

        if cleaned and len(cleaned) > 3:  # Must be meaningful
            # Check if it's a USB device
            if "usb" in name.lower():
                return cleaned, "usb"

    return None, None


def _try_usb_path(name: str, index: int) -> tuple[Optional[str], Optional[str]]:
    """Try to extract USB bus path from device name or system info.

    USB paths look like: usb:1-1.3 (bus 1, port 1.3)

    Args:
        name: Device name string
        index: sounddevice device index

    Returns:
        (port_id, port_type) or (None, None) if not USB or path unavailable
    """
    # Check if this is a USB device
    if "usb" not in name.lower():
        return None, None

    # Try to extract hw card number from name (e.g., "hw:2,0")
    hw_match = re.search(r"hw:(\d+)", name)
    if hw_match:
        card_num = hw_match.group(1)

        # Try to read USB path from /proc/asound/card{N}/usbid or similar
        # This is Linux-specific
        try:
            with open(f"/proc/asound/card{card_num}/id") as f:
                card_id = f.read().strip()

            # Try to get USB bus info from /sys/class/sound/card{N}/device
            import os

            device_path = f"/sys/class/sound/card{card_num}/device"
            if os.path.islink(device_path):
                real_path = os.readlink(device_path)
                # Extract USB path like "1-1.3" from path
                usb_match = re.search(r"usb\d+/(\d+-[\d.]+)", real_path)
                if usb_match:
                    usb_path = usb_match.group(1)
                    return f"usb:{usb_path}", "usb"

        except (FileNotFoundError, PermissionError, OSError) as e:
            logger.debug(f"Could not read USB path for card {card_num}: {e}")

    return None, None


def _fallback_alsa_card(name: str, index: int) -> tuple[str, str]:
    """Fallback to ALSA card identifier.

    Args:
        name: Device name string
        index: sounddevice device index

    Returns:
        (port_id, port_type) - always succeeds with hw:N format
    """
    # Extract ALSA card number from name
    hw_match = re.search(r"hw:(\d+)", name)
    if hw_match:
        card_num = hw_match.group(1)
        port_id = f"hw:{card_num}"
    else:
        # Last resort: use device index
        port_id = f"hw:{index}"

    # Determine type based on name
    if "usb" in name.lower():
        port_type = "usb"
    elif any(x in name.lower() for x in ["headphone", "bcm2835", "jack", "audio"]):
        port_type = "jack"
    else:
        port_type = "alsa"

    return port_id, port_type


def sanitize_port_id(port_id: str) -> str:
    """Sanitize a port ID to ensure it's safe for use as a filename or config key.

    Args:
        port_id: Raw port ID

    Returns:
        Sanitized port ID (lowercase, alphanumeric + dash/colon/underscore only)
    """
    # Replace unsafe characters
    sanitized = re.sub(r"[^\w:-]", "-", port_id.lower())
    # Remove duplicate dashes
    sanitized = re.sub(r"-+", "-", sanitized)
    # Remove leading/trailing dashes
    sanitized = sanitized.strip("-")
    return sanitized
