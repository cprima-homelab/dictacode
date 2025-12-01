"""Whisper.cpp transcription adapter (v0.2.6 Phase 2)."""

import logging
import subprocess
import time
from pathlib import Path
from typing import Optional

from .adapter import TranscriptionAdapter, TranscriptionResult, AudioRequirements

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
        """Whisper.cpp doesn't support streaming in batch mode."""
        return False
