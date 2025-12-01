"""Audio backend abstraction for cross-platform audio support (v0.2.10 Phase 1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Callable


class BackendType(Enum):
    """Audio backend types."""

    ALSA = "alsa"  # Linux native
    PULSEAUDIO = "pulseaudio"  # Linux with PulseAudio
    PORTAUDIO = "portaudio"  # Cross-platform via PortAudio
    COREAUDIO = "coreaudio"  # macOS native
    WASAPI = "wasapi"  # Windows native
    AAUDIO = "aaudio"  # Android native


@dataclass
class BackendCapabilities:
    """Capabilities of an audio backend."""

    name: str
    platform: str  # "linux", "darwin", "win32", "android"
    supports_exclusive: bool  # Exclusive device access
    supports_loopback: bool  # System audio capture
    supports_hot_plug: bool  # Device change notifications
    min_latency_ms: int
    max_channels: int


@dataclass
class BackendDeviceInfo:
    """Platform-agnostic device information."""

    device_id: str  # Backend-specific ID
    name: str  # Human-readable name
    is_input: bool
    is_output: bool
    is_default: bool
    sample_rates: List[int]
    channels: int
    backend_type: BackendType

    # Platform-specific metadata (optional)
    alsa_card: Optional[int] = None
    alsa_device: Optional[int] = None
    usb_vendor_id: Optional[str] = None
    usb_product_id: Optional[str] = None


# Callback types
AudioDataCallback = Callable[[bytes, int], None]  # (data, frames)
DeviceChangeCallback = Callable[[List[BackendDeviceInfo]], None]


class AudioBackend(ABC):
    """Abstract audio backend for platform-specific audio APIs."""

    @abstractmethod
    def get_type(self) -> BackendType:
        """Return backend type."""
        pass

    @abstractmethod
    def get_capabilities(self) -> BackendCapabilities:
        """Return backend capabilities."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available on this system."""
        pass

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the audio backend."""
        pass

    @abstractmethod
    def terminate(self) -> None:
        """Cleanup backend resources."""
        pass

    @abstractmethod
    def list_devices(self) -> List[BackendDeviceInfo]:
        """Enumerate available audio devices."""
        pass

    @abstractmethod
    def get_default_input_device(self) -> Optional[BackendDeviceInfo]:
        """Get system default input device."""
        pass

    @abstractmethod
    def open_input_stream(
        self,
        device_id: str,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
        buffer_frames: int = 1024,
    ) -> "AudioInputStream":
        """Open an input stream on the specified device."""
        pass

    def register_device_change_callback(
        self,
        callback: DeviceChangeCallback,
    ) -> None:
        """Register callback for device changes (if supported)."""
        pass  # Optional, default no-op


class AudioInputStream(ABC):
    """Abstract audio input stream."""

    @abstractmethod
    def start(self) -> None:
        """Start capturing audio."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop capturing audio."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close and release stream resources."""
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """Return True if stream is capturing."""
        pass

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Actual sample rate of stream."""
        pass

    @property
    @abstractmethod
    def channels(self) -> int:
        """Number of channels."""
        pass

    @property
    @abstractmethod
    def latency_ms(self) -> float:
        """Current stream latency."""
        pass
