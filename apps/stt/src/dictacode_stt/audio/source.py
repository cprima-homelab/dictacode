"""Audio source abstraction for testing and production (v0.2.11 Phase 1)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


class SourceType(Enum):
    """Audio source types."""

    MICROPHONE = "microphone"
    FILE = "file"
    SYNTHETIC = "synthetic"


class PlaybackMode(Enum):
    """Playback timing modes."""

    REALTIME = "realtime"  # Simulate real microphone timing
    FAST = "fast"  # As fast as possible (CI)
    CONTROLLED = "controlled"  # Manual advancement (unit tests)


@dataclass
class AudioSourceConfig:
    """Configuration for audio source."""

    source_type: SourceType
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024  # Samples per chunk
    playback_mode: PlaybackMode = PlaybackMode.REALTIME

    # File source options
    file_path: Optional[Path] = None
    loop: bool = False
    start_offset_ms: int = 0
    end_offset_ms: Optional[int] = None

    # Synthetic source options
    pattern: str = "silence"  # "silence", "tone", "noise", "click", "sweep"
    duration_ms: Optional[int] = None
    frequency_hz: float = 440.0  # For tone


# Callback types
AudioChunkCallback = Callable[[bytes, int], None]  # (data, frame_count)
SourceEndCallback = Callable[[], None]


class AudioSource(ABC):
    """Abstract audio source - microphone, file, or synthetic."""

    @abstractmethod
    def get_type(self) -> SourceType:
        """Return source type."""
        pass

    @abstractmethod
    def get_config(self) -> AudioSourceConfig:
        """Return source configuration."""
        pass

    @abstractmethod
    def open(self) -> None:
        """Open/initialize the source."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close and release resources."""
        pass

    @abstractmethod
    def start(
        self,
        callback: AudioChunkCallback,
        on_end: Optional[SourceEndCallback] = None,
    ) -> None:
        """Start streaming audio to callback.

        Args:
            callback: Called with each audio chunk
            on_end: Called when source exhausted (file/synthetic)
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop streaming."""
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """Return True if currently streaming."""
        pass

    def is_finite(self) -> bool:
        """Return True if source has finite duration (file, synthetic)."""
        return self.get_type() != SourceType.MICROPHONE

    def supports_seeking(self) -> bool:
        """Return True if source supports seek operations."""
        return False

    def seek(self, position_ms: int) -> None:
        """Seek to position (if supported)."""
        raise NotImplementedError("Source does not support seeking")
