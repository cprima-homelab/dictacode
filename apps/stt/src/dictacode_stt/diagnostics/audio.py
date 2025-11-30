"""Audio device diagnostic checks for STT.

Checks microphone detection and recording capability.
"""

from __future__ import annotations

from typing import List, Optional

from .base import DiagnosticResult


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
        import sounddevice as sd
        import numpy as np

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

    return result
