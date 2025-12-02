"""Audio port abstraction layer for dictacode STT.

Provides driver-like interface for audio hardware:
- Port discovery and enumeration
- Stable port identification
- Streaming audio capture with callbacks
- Ring buffer with overlap (fixes word cutoff)
- Sample rate conversion (resampling)
- Configuration profiles for known devices
"""

from .buffer import AudioRingBuffer
from .config import AudioConfig, AudioProfile
from .manager import AudioPortManager
from .port import AudioPort, AudioPortCapabilities, PortStatus
from .resampler import Resampler, ResamplerScipy


__all__ = [
    "AudioConfig",
    "AudioPort",
    "AudioPortCapabilities",
    "AudioPortManager",
    "AudioProfile",
    "AudioRingBuffer",
    "PortStatus",
    "Resampler",
    "ResamplerScipy",
]
