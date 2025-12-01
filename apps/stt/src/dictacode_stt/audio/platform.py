"""Platform detection for audio backend selection (v0.2.10 Phase 1)."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass


@dataclass
class PlatformInfo:
    """Detected platform information."""

    system: str  # "Linux", "Darwin", "Windows"
    release: str  # Kernel/OS version
    machine: str  # "x86_64", "aarch64", "armv7l"
    is_raspberry_pi: bool
    is_android: bool
    recommended_backend: str


def detect_platform() -> PlatformInfo:
    """Detect current platform and recommend backend.

    Returns:
        PlatformInfo with system details and recommended backend
    """
    sys = platform.system()
    release = platform.release()
    machine = platform.machine()

    # Raspberry Pi detection
    is_rpi = False
    if sys == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                cpuinfo = f.read()
            is_rpi = "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo
        except Exception:
            pass

    # Android detection
    is_android = "ANDROID_ROOT" in os.environ or "android" in release.lower()

    # Recommend backend
    if is_android:
        recommended = "aaudio"
    elif sys == "Linux":
        recommended = "alsa"
    elif sys == "Darwin":
        recommended = "coreaudio"
    elif sys == "Windows":
        recommended = "wasapi"
    else:
        recommended = "portaudio"

    return PlatformInfo(
        system=sys,
        release=release,
        machine=machine,
        is_raspberry_pi=is_rpi,
        is_android=is_android,
        recommended_backend=recommended,
    )
