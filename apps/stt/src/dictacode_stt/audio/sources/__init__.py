"""Audio source factory and exports (v0.2.11 Phase 1-3)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from dictacode_stt.audio.source import (
    AudioSource,
    AudioSourceConfig,
    PlaybackMode,
    SourceType,
)
from dictacode_stt.audio.sources.file import FileSource
from dictacode_stt.audio.sources.synthetic import SyntheticSource


if TYPE_CHECKING:
    from dictacode_stt.audio.manager import AudioPortManager

__all__ = [
    "AudioSource",
    "AudioSourceConfig",
    "FileSource",
    "PlaybackMode",
    "SourceType",
    "SyntheticSource",
    "create_audio_source",
]


def create_audio_source(
    source_spec: str,
    port_manager: Optional[AudioPortManager] = None,
    **kwargs,
) -> AudioSource:
    """Create audio source from specification string.

    Args:
        source_spec: Source specification:
            - "mic" or "microphone" - Live microphone
            - "mic:PORT_ID" - Specific microphone
            - "file:path/to/audio.wav" - File playback
            - "file:path.wav:fast" - File playback, fast mode
            - "file:path.wav:realtime" - File playback, realtime mode
            - "synthetic:silence" - Synthetic silence
            - "synthetic:tone:440" - Synthetic 440Hz tone
            - "synthetic:noise:5000" - 5 second noise
        port_manager: Required for microphone sources
        **kwargs: Additional config overrides

    Returns:
        Configured AudioSource

    Examples:
        >>> # File source for testing
        >>> source = create_audio_source("file:test.wav:fast")
        >>> source.open()
        >>> source.start(callback=lambda d, f: print(f"Got {f} frames"))

        >>> # Synthetic tone
        >>> source = create_audio_source("synthetic:tone:440:2000")  # 2s of 440Hz

        >>> # Synthetic silence
        >>> source = create_audio_source("synthetic:silence:1000")  # 1s silence
    """
    parts = source_spec.split(":")

    if parts[0] in ("mic", "microphone"):
        # Microphone source - would need MicrophoneSource implementation
        raise NotImplementedError(
            "Microphone source not yet implemented. "
            "Use file or synthetic sources for testing."
        )

    elif parts[0] == "file":
        if len(parts) < 2:
            raise ValueError("File path required: file:path/to/audio.wav")

        file_path = Path(parts[1])
        playback_mode = PlaybackMode.REALTIME
        if len(parts) > 2:
            try:
                playback_mode = PlaybackMode[parts[2].upper()]
            except KeyError:
                raise ValueError(
                    f"Invalid playback mode: {parts[2]}. "
                    f"Use: realtime, fast, or controlled"
                )

        config = AudioSourceConfig(
            source_type=SourceType.FILE,
            file_path=file_path,
            playback_mode=playback_mode,
            **kwargs,
        )
        return FileSource(config)

    elif parts[0] == "synthetic":
        pattern = parts[1] if len(parts) > 1 else "silence"
        duration_ms = int(parts[2]) if len(parts) > 2 else None
        frequency_hz = float(parts[3]) if len(parts) > 3 else 440.0

        config = AudioSourceConfig(
            source_type=SourceType.SYNTHETIC,
            pattern=pattern,
            duration_ms=duration_ms,
            frequency_hz=frequency_hz,
            playback_mode=kwargs.get("playback_mode", PlaybackMode.REALTIME),
            **kwargs,
        )
        return SyntheticSource(config)

    else:
        raise ValueError(
            f"Unknown source type: {parts[0]}. " f"Use: mic, file, or synthetic"
        )
