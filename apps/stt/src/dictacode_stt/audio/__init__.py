"""Audio port abstraction layer for dictacode STT.

Provides driver-like interface for audio hardware:
- Port discovery and enumeration
- Stable port identification
- Streaming audio capture with callbacks
- Ring buffer with overlap (fixes word cutoff)
- Sample rate conversion (resampling)
- Configuration profiles for known devices
"""

from .port import AudioPort, AudioPortCapabilities, PortStatus
from .manager import AudioPortManager
from .buffer import AudioRingBuffer
from .resampler import Resampler, ResamplerScipy
from .config import AudioConfig, AudioProfile

__all__ = [
    "AudioPort",
    "AudioPortCapabilities",
    "PortStatus",
    "AudioPortManager",
    "AudioRingBuffer",
    "Resampler",
    "ResamplerScipy",
    "AudioConfig",
    "AudioProfile",
]
