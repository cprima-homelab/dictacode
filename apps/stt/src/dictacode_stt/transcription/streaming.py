"""Streaming transcription support (v0.2.7 Phase 1).

This module defines the streaming interface for real-time transcription:
- PartialResult: Intermediate transcription results (may change)
- FinalResult: Confirmed transcription results (speech segment complete)
- StreamingTranscriptionAdapter: Protocol for streaming-capable adapters
"""

from dataclasses import dataclass
from typing import Callable, Optional, Protocol


@dataclass
class PartialResult:
    """Intermediate transcription result (may change).

    Partial results are emitted continuously as the user speaks.
    They represent the transcriber's current best guess and may
    change as more audio is processed.

    Attributes:
        text: Current transcription text
        is_final: Whether this partial result is finalized
        confidence: Optional confidence score (0.0-1.0)
    """

    text: str
    is_final: bool = False
    confidence: Optional[float] = None


@dataclass
class FinalResult:
    """Confirmed transcription result (speech segment complete).

    Final results are emitted when a speech segment ends (detected
    via voice activity detection or silence). They represent the
    transcriber's final decision and should not change.

    Attributes:
        text: Final transcription text
        confidence: Optional confidence score (0.0-1.0)
        duration_ms: Optional duration of speech segment in milliseconds
    """

    text: str
    confidence: Optional[float] = None
    duration_ms: Optional[int] = None


# Callback types for streaming transcription
PartialCallback = Callable[[PartialResult], None]
FinalCallback = Callable[[FinalResult], None]
ErrorCallback = Callable[[Exception], None]


class StreamingTranscriptionAdapter(Protocol):
    """Protocol for streaming-capable transcription adapters.

    Adapters implementing this protocol can process audio in real-time,
    emitting partial results as the user speaks and final results when
    speech segments complete.

    Usage:
        adapter = VoskAdapter()
        adapter.start_streaming(
            language="en",
            on_partial=lambda r: print(f"Partial: {r.text}"),
            on_final=lambda r: print(f"Final: {r.text}"),
        )

        # Feed audio chunks continuously
        for chunk in audio_stream:
            adapter.feed_audio(chunk)

        # Stop streaming when done
        final = adapter.stop_streaming()
    """

    def supports_streaming(self) -> bool:
        """Return True if adapter supports streaming.

        Returns:
            True if adapter can stream, False otherwise
        """
        ...

    def start_streaming(
        self,
        language: str = "en",
        on_partial: Optional[PartialCallback] = None,
        on_final: Optional[FinalCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        """Start streaming transcription session.

        Args:
            language: Language code (e.g., "en", "de", "fr")
            on_partial: Callback for intermediate results
            on_final: Callback when speech segment completes
            on_error: Callback for transcription errors

        Raises:
            RuntimeError: If streaming is already active
            ValueError: If language is not supported
        """
        ...

    def feed_audio(self, chunk: bytes) -> None:
        """Feed audio chunk to transcriber.

        Audio chunks are processed continuously. Callbacks (on_partial,
        on_final) are invoked as results become available.

        Args:
            chunk: Raw audio bytes (format depends on adapter requirements)

        Note:
            Check adapter.get_audio_requirements() for expected format.
            Common format: 16kHz, 16-bit, mono PCM.
        """
        ...

    def stop_streaming(self) -> Optional[FinalResult]:
        """Stop streaming and get final result.

        Processes any remaining audio and returns the final transcription.

        Returns:
            Final result for remaining audio, or None if no audio left

        Raises:
            RuntimeError: If streaming is not active
        """
        ...

    def is_streaming(self) -> bool:
        """Return True if currently in streaming session.

        Returns:
            True if streaming is active, False otherwise
        """
        ...
