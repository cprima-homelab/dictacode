"""Whisper.cpp transcription adapter (v0.2.6 Phase 2, v0.2.7 Phase 3).

v0.2.6: Batch transcription via whisper-cli subprocess
v0.2.7: Pseudo-streaming via chunked batch transcription

Note: Whisper.cpp doesn't support true streaming. This implementation
accumulates audio chunks and transcribes them in batches, providing
delayed "final" results to maintain API compatibility with streaming.
"""

import logging
import struct
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

from .adapter import TranscriptionAdapter, TranscriptionResult, AudioRequirements
from .streaming import (
    FinalResult,
    PartialCallback,
    FinalCallback,
    ErrorCallback,
)

logger = logging.getLogger(__name__)


class WhisperAdapter(TranscriptionAdapter):
    """Whisper.cpp transcription via subprocess.

    Extracted from service.py transcribe() method to follow adapter pattern.
    """

    def __init__(
        self,
        binary_path: Optional[Path] = None,
        model_path: Optional[Path] = None,
        timeout: float = 60.0,
    ):
        """Initialize Whisper adapter.

        Args:
            binary_path: Path to whisper-cli binary (default: auto-detect)
            model_path: Path to whisper model (default: auto-detect)
            timeout: Subprocess timeout in seconds
        """
        self.binary = binary_path or self._find_binary()
        self.model = model_path or self._find_model()
        self.timeout = timeout

        # Streaming state (v0.2.7 - pseudo-streaming via chunked batch)
        self._chunk_buffer = bytearray()
        self._chunk_threshold = 16000 * 2 * 3  # 3 seconds of audio (16kHz, 16-bit)
        self._streaming = False
        self._language = "en"
        self._callbacks: dict = {}

    def _find_binary(self) -> Path:
        """Find whisper-cli binary in common locations."""
        common_paths = [
            Path.home() / "whisper.cpp/build/bin/whisper-cli",
            Path.home() / "whisper.cpp/main",
            Path("/usr/local/bin/whisper-cli"),
            Path("/usr/bin/whisper-cli"),
        ]
        for path in common_paths:
            if path.exists():
                return path
        # Return default even if not found (will fail in is_available())
        return Path.home() / "whisper.cpp/build/bin/whisper-cli"

    def _find_model(self) -> Path:
        """Find whisper model in common locations."""
        common_paths = [
            Path.home() / "whisper.cpp/models/ggml-tiny.bin",
            Path.home() / "whisper.cpp/models/ggml-tiny.en.bin",
            Path.home() / "whisper.cpp/models/ggml-base.en.bin",
            Path("/usr/share/whisper/models/ggml-tiny.en.bin"),
        ]
        for path in common_paths:
            if path.exists():
                return path
        # Return default even if not found (will fail in is_available())
        return Path.home() / "whisper.cpp/models/ggml-tiny.bin"

    def get_name(self) -> str:
        """Return engine name."""
        return "whisper"

    def get_audio_requirements(self) -> AudioRequirements:
        """Return Whisper audio format requirements."""
        return AudioRequirements(
            sample_rate=16000,
            channels=1,
            bit_depth=16,
            formats=["wav"],
        )

    def transcribe(
        self, audio_path: Path, language: str = "en"
    ) -> TranscriptionResult:
        """Transcribe audio file using whisper-cli subprocess.

        Args:
            audio_path: Path to WAV file
            language: Language code (e.g., "en", "de")

        Returns:
            TranscriptionResult with text or error
        """
        cmd = [
            str(self.binary),
            "-m",
            str(self.model),
            "-f",
            str(audio_path),
            "--language",
            language,
            "--no-timestamps",
        ]

        start = time.perf_counter()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired:
            return TranscriptionResult(
                text="", error=f"Timeout after {self.timeout}s", language=language
            )
        except Exception as e:
            return TranscriptionResult(text="", error=str(e), language=language)

        duration_ms = int((time.perf_counter() - start) * 1000)

        if result.returncode != 0:
            return TranscriptionResult(
                text="",
                error=f"Whisper failed: {result.stderr}",
                language=language,
                duration_ms=duration_ms,
            )

        # Parse output (same logic as service.py)
        text = self._parse_output(result.stdout)

        return TranscriptionResult(
            text=text,
            language=language,
            duration_ms=duration_ms,
            confidence=None,  # Whisper.cpp doesn't provide confidence scores
        )

    def _parse_output(self, stdout: str) -> str:
        """Parse whisper-cli output to extract transcribed text.

        Removes timestamp brackets and joins lines.
        """
        lines = stdout.strip().split("\n")
        text_parts = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove timestamp brackets if present (e.g., "[00:00.000 --> 00:05.000]")
            if line.startswith("["):
                bracket_end = line.find("]")
                if bracket_end != -1:
                    text = line[bracket_end + 1 :].strip()
                    if text:
                        text_parts.append(text)
            else:
                text_parts.append(line)

        return " ".join(text_parts)

    def is_available(self) -> bool:
        """Check if whisper binary and model exist."""
        return self.binary.exists() and self.model.exists()

    def supports_streaming(self) -> bool:
        """Whisper.cpp doesn't support true streaming.

        Returns False to indicate no native streaming support.
        However, pseudo-streaming is available via chunked batch.
        """
        return False

    # Streaming methods (v0.2.7 - pseudo-streaming via chunked batch)

    def start_streaming(
        self,
        language: str = "en",
        on_partial: Optional[PartialCallback] = None,
        on_final: Optional[FinalCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        """Start pseudo-streaming via chunked batch.

        Note: Whisper doesn't support true streaming. This accumulates
        audio and transcribes in chunks, providing delayed "final" results.

        Args:
            language: Language code (e.g., "en", "de", "fr")
            on_partial: Callback for intermediate results (unused - no partials)
            on_final: Callback when chunk is transcribed
            on_error: Callback for transcription errors

        Raises:
            RuntimeError: If streaming is already active
        """
        if self._streaming:
            raise RuntimeError("Streaming already active")

        self._language = language
        self._callbacks = {
            "on_partial": on_partial,
            "on_final": on_final,
            "on_error": on_error,
        }
        self._chunk_buffer = bytearray()
        self._streaming = True

        logger.info(
            "Whisper pseudo-streaming started (chunked batch mode, "
            f"chunk threshold: {self._chunk_threshold / (16000 * 2):.1f}s)"
        )

    def feed_audio(self, chunk: bytes) -> None:
        """Accumulate audio and transcribe when threshold reached.

        Args:
            chunk: Raw audio bytes (16kHz, 16-bit, mono)

        Note:
            Unlike true streaming (Vosk), this accumulates audio and
            transcribes in batches. No partial results are emitted.
        """
        if not self._streaming:
            return

        self._chunk_buffer.extend(chunk)

        # Transcribe when we have enough audio
        if len(self._chunk_buffer) >= self._chunk_threshold:
            self._transcribe_buffer()

    def _transcribe_buffer(self) -> None:
        """Transcribe accumulated buffer via batch method."""
        if not self._chunk_buffer:
            return

        logger.debug(
            f"Transcribing buffer ({len(self._chunk_buffer)} bytes, "
            f"{len(self._chunk_buffer) / (16000 * 2):.1f}s)"
        )

        temp_path = None
        try:
            # Write buffer to temp WAV file
            with tempfile.NamedTemporaryFile(
                suffix=".wav", delete=False
            ) as f:
                self._write_wav(f, bytes(self._chunk_buffer))
                temp_path = Path(f.name)

            # Use batch transcription
            result = self.transcribe(temp_path, self._language)

            if result.success and self._callbacks.get("on_final"):
                self._callbacks["on_final"](
                    FinalResult(
                        text=result.text,
                        confidence=result.confidence,
                        duration_ms=result.duration_ms,
                    )
                )
            elif not result.success:
                logger.error(f"Chunk transcription failed: {result.error}")
                if self._callbacks.get("on_error"):
                    self._callbacks["on_error"](
                        RuntimeError(result.error)
                    )

            # Clear buffer
            self._chunk_buffer = bytearray()

        except Exception as e:
            logger.error(f"Error transcribing buffer: {e}")
            if self._callbacks.get("on_error"):
                self._callbacks["on_error"](e)

        finally:
            # Clean up temp file
            if temp_path and temp_path.exists():
                temp_path.unlink()

    def _write_wav(self, file_obj, audio_data: bytes) -> None:
        """Write raw audio bytes to WAV file.

        Args:
            file_obj: File object to write to
            audio_data: Raw audio bytes (16kHz, 16-bit, mono)
        """
        with wave.open(file_obj.name, "wb") as wf:
            wf.setnchannels(1)  # Mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(16000)  # 16kHz
            wf.writeframes(audio_data)

    def stop_streaming(self) -> Optional[FinalResult]:
        """Transcribe remaining buffer.

        Returns:
            Final result for remaining audio, or None

        Raises:
            RuntimeError: If streaming is not active
        """
        if not self._streaming:
            raise RuntimeError("Streaming not active")

        logger.info("Whisper pseudo-streaming stopped")

        # Transcribe any remaining audio
        if self._chunk_buffer:
            self._transcribe_buffer()

        self._streaming = False
        self._callbacks = {}
        return None

    def is_streaming(self) -> bool:
        """Return True if currently in streaming session."""
        return self._streaming
