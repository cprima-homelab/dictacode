"""Transcription adapter abstract base class (v0.2.6 Phase 1)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""

    text: str
    confidence: Optional[float] = None
    language: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Return True if transcription succeeded."""
        return self.error is None and len(self.text) > 0


@dataclass
class AudioRequirements:
    """Audio format requirements for a transcription engine."""

    sample_rate: int  # e.g., 16000
    channels: int  # e.g., 1 (mono)
    bit_depth: int  # e.g., 16
    formats: List[str]  # e.g., ["wav", "mp3", "ogg"]


class TranscriptionAdapter(ABC):
    """Abstract speech-to-text transcription engine.

    Follows the Adapter pattern like ProtocolAdapter in protocol.py.
    Allows swapping between Whisper, Vosk, and online providers.
    """

    @abstractmethod
    def get_name(self) -> str:
        """Return engine name (e.g., 'whisper', 'vosk', 'google')."""
        pass

    @abstractmethod
    def get_audio_requirements(self) -> AudioRequirements:
        """Return audio format requirements for this engine."""
        pass

    @abstractmethod
    def transcribe(self, audio_path: Path, language: str = "en") -> TranscriptionResult:
        """Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., "en", "de")

        Returns:
            TranscriptionResult with text or error
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is available (binary exists, API key set, etc.)."""
        pass

    def supports_streaming(self) -> bool:
        """Return True if engine supports streaming transcription."""
        return False  # Default: no streaming

    # v0.3.13: Live status for DiagnosticsAggregator
    def status(self) -> dict:
        """Return live status for diagnostics aggregator.

        Subclasses may override to add backend-specific fields.
        Timestamps/counters are set externally by service.py.

        Returns:
            Dict with backend, available, last_asr_ts, and counters.
        """
        return {
            "backend": self.get_name(),
            "available": self.is_available() if hasattr(self, "is_available") else True,
            "last_asr_ts": getattr(self, "_last_asr_ts", None),
            "asr_success_total": getattr(self, "_asr_success_total", 0),
            "asr_error_total": getattr(self, "_asr_error_total", 0),
        }
