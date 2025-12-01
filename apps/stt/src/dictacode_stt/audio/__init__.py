"""Audio port abstraction layer for dictacode STT.

Provides driver-like interface for audio hardware:
- Port discovery and enumeration
- Stable port identification
- Streaming audio capture with callbacks
- Ring buffer with overlap (fixes word cutoff)
"""

from .port import AudioPort, AudioPortCapabilities, PortStatus
from .manager import AudioPortManager

__all__ = [
    "AudioPort",
    "AudioPortCapabilities",
    "PortStatus",
    "AudioPortManager",
]
