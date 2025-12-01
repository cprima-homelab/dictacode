"""Vosk transcription adapter with native streaming support (v0.2.7 Phase 2).

Vosk is an offline speech recognition toolkit that supports:
- Batch transcription (v0.2.6 TranscriptionAdapter interface)
- Real-time streaming transcription (v0.2.7 StreamingTranscriptionAdapter)

Vosk provides low-latency streaming with partial and final results,
making it ideal for real-time dictation applications.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from .adapter import TranscriptionAdapter, TranscriptionResult, AudioRequirements
from .streaming import (
    PartialResult,
    FinalResult,
    PartialCallback,
    FinalCallback,
    ErrorCallback,
)

logger = logging.getLogger(__name__)


class VoskAdapter(TranscriptionAdapter):
    """Vosk transcription with native streaming support.

    Vosk provides both batch and streaming transcription:
    - Batch: transcribe() processes complete audio files
    - Streaming: start_streaming() + feed_audio() for real-time

    The streaming mode leverages Vosk's KaldiRecognizer to emit:
    - Partial results: Continuous updates as user speaks
    - Final results: Confirmed text when speech segment ends

    Example:
        # Batch transcription
        adapter = VoskAdapter()
        result = adapter.transcribe(Path("audio.wav"))

        # Streaming transcription
        adapter.start_streaming(
            on_partial=lambda r: print(f"Partial: {r.text}"),
            on_final=lambda r: print(f"Final: {r.text}"),
        )
        for chunk in audio_stream:
            adapter.feed_audio(chunk)
        adapter.stop_streaming()
    """

    def __init__(self, model_path: Optional[Path] = None):
        """Initialize Vosk adapter.

        Args:
            model_path: Path to Vosk model directory (default: auto-detect)
        """
        self.model_path = model_path or self._find_model()
        self._model = None  # Lazy load
        self._recognizer = None  # For streaming
        self._streaming = False
        self._callbacks: dict = {}

    def _find_model(self) -> Path:
        """Find Vosk model in common locations."""
        common_paths = [
            Path.home() / ".vosk/model",
            Path.home() / ".vosk/model-small-en-us-0.15",
            Path.home() / "vosk/model",
            Path("/usr/share/vosk/model"),
            Path("/opt/vosk/model"),
        ]
        for path in common_paths:
            if path.exists() and path.is_dir():
                return path
        # Return default even if not found (will fail in is_available())
        return Path.home() / ".vosk/model"

    def get_name(self) -> str:
        """Return engine name."""
        return "vosk"

    def get_audio_requirements(self) -> AudioRequirements:
        """Return Vosk audio format requirements."""
        return AudioRequirements(
            sample_rate=16000,
            channels=1,
            bit_depth=16,
            formats=["wav"],
        )

    def transcribe(
        self, audio_path: Path, language: str = "en"
    ) -> TranscriptionResult:
        """Transcribe audio file using Vosk (batch mode).

        Args:
            audio_path: Path to WAV file
            language: Language code (ignored - model determines language)

        Returns:
            TranscriptionResult with text or error
        """
        try:
            from vosk import Model, KaldiRecognizer
            import wave
        except ImportError:
            return TranscriptionResult(
                text="",
                error="Vosk not installed. Install with: pip install vosk",
                language=language,
            )

        start = time.perf_counter()

        try:
            # Lazy load model
            if self._model is None:
                self._model = Model(str(self.model_path))

            # Open WAV file
            with wave.open(str(audio_path), "rb") as wf:
                if wf.getnchannels() != 1:
                    return TranscriptionResult(
                        text="",
                        error="Audio must be mono (1 channel)",
                        language=language,
                    )

                # Create recognizer
                rec = KaldiRecognizer(self._model, wf.getframerate())
                rec.SetWords(True)

                # Process audio in chunks
                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    rec.AcceptWaveform(data)

                # Get final result
                result = json.loads(rec.FinalResult())
                text = result.get("text", "")

                duration_ms = int((time.perf_counter() - start) * 1000)

                return TranscriptionResult(
                    text=text,
                    language=language,
                    duration_ms=duration_ms,
                    confidence=result.get("confidence"),
                )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return TranscriptionResult(
                text="",
                error=str(e),
                language=language,
                duration_ms=duration_ms,
            )

    def is_available(self) -> bool:
        """Check if Vosk is installed and model exists."""
        try:
            import vosk  # noqa: F401

            return self.model_path.exists() and self.model_path.is_dir()
        except ImportError:
            return False

    # Streaming methods (v0.2.7)

    def supports_streaming(self) -> bool:
        """Vosk supports native streaming."""
        return True

    def start_streaming(
        self,
        language: str = "en",
        on_partial: Optional[PartialCallback] = None,
        on_final: Optional[FinalCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        """Start Vosk streaming session.

        Args:
            language: Language code (ignored - model determines language)
            on_partial: Callback for intermediate results
            on_final: Callback when speech segment completes
            on_error: Callback for transcription errors

        Raises:
            RuntimeError: If streaming is already active
            ImportError: If Vosk is not installed
        """
        if self._streaming:
            raise RuntimeError("Streaming already active")

        try:
            from vosk import Model, KaldiRecognizer
        except ImportError as e:
            if on_error:
                on_error(e)
            raise ImportError(
                "Vosk not installed. Install with: pip install vosk"
            ) from e

        try:
            # Lazy load model
            if self._model is None:
                logger.info(f"Loading Vosk model from {self.model_path}")
                self._model = Model(str(self.model_path))

            # Create recognizer for streaming (16kHz)
            self._recognizer = KaldiRecognizer(self._model, 16000)
            self._recognizer.SetWords(True)

            # Store callbacks
            self._callbacks = {
                "on_partial": on_partial,
                "on_final": on_final,
                "on_error": on_error,
            }
            self._streaming = True

            logger.info("Vosk streaming started")

        except Exception as e:
            logger.error(f"Failed to start Vosk streaming: {e}")
            if on_error:
                on_error(e)
            raise

    def feed_audio(self, chunk: bytes) -> None:
        """Feed audio chunk and emit results via callbacks.

        Args:
            chunk: Raw audio bytes (16kHz, 16-bit, mono)

        Note:
            This method processes audio and invokes callbacks:
            - on_partial: Called with intermediate results
            - on_final: Called when speech segment completes
        """
        if not self._streaming or not self._recognizer:
            return

        try:
            # AcceptWaveform returns True when utterance is complete
            if self._recognizer.AcceptWaveform(chunk):
                # Final result for this utterance
                result = json.loads(self._recognizer.Result())
                text = result.get("text", "")
                if text and self._callbacks.get("on_final"):
                    self._callbacks["on_final"](
                        FinalResult(
                            text=text,
                            confidence=result.get("confidence"),
                        )
                    )
            else:
                # Partial result (speech in progress)
                partial = json.loads(self._recognizer.PartialResult())
                text = partial.get("partial", "")
                if text and self._callbacks.get("on_partial"):
                    self._callbacks["on_partial"](
                        PartialResult(
                            text=text,
                            is_final=False,
                        )
                    )

        except Exception as e:
            logger.error(f"Error feeding audio to Vosk: {e}")
            if self._callbacks.get("on_error"):
                self._callbacks["on_error"](e)

    def stop_streaming(self) -> Optional[FinalResult]:
        """Stop streaming and return final result.

        Returns:
            Final result for any remaining audio, or None

        Raises:
            RuntimeError: If streaming is not active
        """
        if not self._streaming:
            raise RuntimeError("Streaming not active")

        if not self._recognizer:
            self._streaming = False
            return None

        try:
            # Get final result from recognizer
            result = json.loads(self._recognizer.FinalResult())
            text = result.get("text", "")

            logger.info("Vosk streaming stopped")

            return FinalResult(text=text) if text else None

        except Exception as e:
            logger.error(f"Error stopping Vosk streaming: {e}")
            if self._callbacks.get("on_error"):
                self._callbacks["on_error"](e)
            return None

        finally:
            # Clean up streaming state
            self._recognizer = None
            self._streaming = False
            self._callbacks = {}

    def is_streaming(self) -> bool:
        """Return True if currently in streaming session."""
        return self._streaming
