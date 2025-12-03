"""Audio device diagnostic checks for STT.

Checks microphone detection, recording capability, and ALSA mixer levels.

v0.3.15: Added mixer level and ALSA state persistence checks.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from .base import DiagnosticResult


# ALSA state file location (where alsactl store saves mixer settings)
ALSA_STATE_FILE = Path("/var/lib/alsa/asound.state")


def get_audio_devices() -> List[dict]:
    """Get list of available audio input devices."""
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        input_devices = []
        for i, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                input_devices.append(
                    {
                        "index": i,
                        "name": dev["name"],
                        "channels": dev["max_input_channels"],
                        "sample_rate": dev["default_samplerate"],
                    }
                )
        return input_devices
    except Exception:
        return []


def check_device_exists(device_index: int) -> bool:
    """Check if audio device exists."""
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        if 0 <= device_index < len(devices):
            return devices[device_index]["max_input_channels"] > 0
        return False
    except Exception:
        return False


def test_audio_recording(device_index: int, duration: float = 1.0) -> bool:
    """Test if audio recording works (1 second test capture)."""
    try:
        import numpy as np
        import sounddevice as sd

        # Record a short sample
        sample_rate = 16000
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            device=device_index,
            dtype=np.float32,
        )
        sd.wait()

        # Check if we got audio data
        if recording is None or len(recording) == 0:
            return False

        # Check if there's any signal (not just silence/noise floor)
        # Very basic check - just ensure we got data
        return True
    except Exception:
        return False


def get_mixer_capture_level(card: int = 0) -> Optional[Tuple[int, int]]:
    """Get ALSA mixer capture level for Mic control.

    Args:
        card: ALSA card number

    Returns:
        Tuple of (current_value, max_value) or None if not available
    """
    try:
        result = subprocess.run(
            ["amixer", "-c", str(card), "sget", "Mic"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None

        # Parse output like: "Mono: Playback [on] Capture 20 [83%] [20.00dB]"
        # Look for "Capture N [X%]"
        match = re.search(r"Capture\s+(\d+)\s+\[(\d+)%\]", result.stdout)
        if match:
            value = int(match.group(1))
            percent = int(match.group(2))
            return (percent, 100)

        return None
    except Exception:
        return None


def check_alsa_state_persisted() -> bool:
    """Check if ALSA state file exists (settings will persist across reboots)."""
    return ALSA_STATE_FILE.exists()


def run_mixer_checks(card: int = 0) -> DiagnosticResult:
    """Run ALSA mixer diagnostic checks.

    v0.3.15: Check mixer capture levels and state persistence.

    Args:
        card: ALSA card number to check
    """
    result = DiagnosticResult(component="stt")

    # Check if amixer is available
    try:
        subprocess.run(
            ["amixer", "--version"],
            capture_output=True,
            timeout=5,
        )
        result.ok("alsa_tools", "amixer available")
    except FileNotFoundError:
        result.warn(
            "alsa_tools",
            "amixer not found",
            "Install alsa-utils: apt install alsa-utils",
        )
        return result
    except Exception as e:
        result.warn("alsa_tools", f"amixer check failed: {e}")
        return result

    # Check mixer capture level
    level = get_mixer_capture_level(card)
    if level is not None:
        percent, _ = level
        if percent == 0:
            result.fail(
                "mixer_capture_level",
                f"Mic capture level is 0% (muted) on card {card}",
                f"Run: amixer -c {card} sset 'Mic' 80%",
            )
        elif percent < 50:
            result.warn(
                "mixer_capture_level",
                f"Mic capture level is low ({percent}%) on card {card}",
                f"Consider: amixer -c {card} sset 'Mic' 80%",
            )
        else:
            result.ok("mixer_capture_level", f"Mic capture level: {percent}%")
    else:
        result.warn(
            "mixer_capture_level",
            f"Could not read Mic capture level on card {card}",
            "Check if audio device has 'Mic' control",
        )

    # Check ALSA state persistence
    if check_alsa_state_persisted():
        result.ok("alsa_state", "ALSA state file exists (settings will persist)")
    else:
        result.warn(
            "alsa_state",
            "ALSA state file not found - mixer settings may reset on reboot",
            "Run: alsactl store",
        )

    return result


def run_audio_checks(device_index: int = 0) -> DiagnosticResult:
    """Run all audio diagnostic checks.

    Args:
        device_index: Audio device index to check.
    """
    result = DiagnosticResult(component="stt")

    # Check sounddevice import
    try:
        import sounddevice as sd

        result.ok("audio_library", "sounddevice library available")
    except ImportError:
        result.fail(
            "audio_library",
            "sounddevice library not installed",
            "Run: pip install sounddevice",
        )
        return result

    # Check for audio devices
    devices = get_audio_devices()
    if devices:
        result.ok("audio_devices", f"Found {len(devices)} input device(s)")

        # List devices in verbose mode
        for dev in devices[:3]:  # Show up to 3
            result.ok(
                f"audio_device_{dev['index']}",
                f"Device {dev['index']}: {dev['name']} ({dev['channels']}ch)",
            )
    else:
        result.fail(
            "audio_devices",
            "No audio input devices found",
            "Connect a microphone and check audio configuration",
        )
        return result

    # Check specific device
    if check_device_exists(device_index):
        result.ok("audio_target_device", f"Target device {device_index} exists")
    else:
        result.fail(
            "audio_target_device",
            f"Target device {device_index} not found",
            f"Check device index (found: {[d['index'] for d in devices]})",
        )
        return result

    # Test recording (only if device exists)
    try:
        if test_audio_recording(device_index, duration=0.5):
            result.ok("audio_recording", "Audio recording test passed")
        else:
            result.warn(
                "audio_recording",
                "Audio recording test returned no data",
                "Check microphone connection and permissions",
            )
    except Exception as e:
        result.fail(
            "audio_recording",
            f"Audio recording test failed: {e}",
            "Check microphone permissions and ALSA configuration",
        )

    # v0.3.15: Include mixer checks
    mixer_result = run_mixer_checks(card=0)
    for check in mixer_result.checks:
        result.add(check)

    return result
