"""Audio source factory and exports (v0.3.10)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Union

from dictacode_stt.audio.source import (
    AudioSource,
    AudioSourceConfig,
    PlaybackMode,
    SourceType,
)
from dictacode_stt.audio.sources.batch import BatchFileSource
from dictacode_stt.audio.sources.directory import DirectorySource
from dictacode_stt.audio.sources.file import FileSource
from dictacode_stt.audio.sources.microphone import MicrophoneSource
from dictacode_stt.audio.sources.synthetic import SyntheticSource


if TYPE_CHECKING:
    from dictacode_stt.audio.manager import AudioPortManager
    from dictacode_stt.stt_config import AudioConfig

__all__ = [
    "AudioSource",
    "AudioSourceConfig",
    "BatchFileSource",
    "DirectorySource",
    "FileSource",
    "MicrophoneSource",
    "PlaybackMode",
    "SourceType",
    "SyntheticSource",
    "create_audio_source",
    "create_source_from_profile",
]


def create_audio_source(
    source_spec: str,
    port_manager: Optional[AudioPortManager] = None,
    **kwargs,
) -> AudioSource:
    """Create audio source from specification string.

    Args:
        source_spec: Source specification:
            - "mic" or "microphone" - Live microphone (default device)
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
        >>> # Microphone source
        >>> source = create_audio_source("mic", port_manager=pm)
        >>> source.open()
        >>> source.start(callback=lambda d, f: process(d))

        >>> # File source for testing
        >>> source = create_audio_source("file:test.wav:fast")
        >>> source.open()
        >>> source.start(callback=lambda d, f: print(f"Got {f} frames"))

        >>> # Synthetic tone
        >>> source = create_audio_source("synthetic:tone:440:2000")  # 2s of 440Hz
    """
    parts = source_spec.split(":")

    if parts[0] in ("mic", "microphone"):
        # Microphone source
        port_id = parts[1] if len(parts) > 1 else "auto"
        config = AudioSourceConfig(
            source_type=SourceType.MICROPHONE,
            sample_rate=kwargs.get("sample_rate", 16000),
            channels=kwargs.get("channels", 1),
            chunk_size=kwargs.get("chunk_size", 1024),
        )
        return MicrophoneSource(
            config=config,
            port_manager=port_manager,
            port_id=port_id,
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


def create_source_from_profile(
    audio_config: "AudioConfig",
    port_manager: Optional[AudioPortManager] = None,
    sample_rate: int = 16000,
    channels: int = 1,
    chunk_size: int = 1024,
    playback_mode: PlaybackMode = PlaybackMode.FAST,
) -> AudioSource:
    """Create audio source from profile AudioConfig.

    Args:
        audio_config: AudioConfig from PipelineProfile
        port_manager: Required for microphone sources
        sample_rate: Target sample rate (may be overridden by profile)
        channels: Target channel count
        chunk_size: Samples per chunk
        playback_mode: Playback mode for file sources

    Returns:
        Configured AudioSource

    Raises:
        ValueError: Invalid source type or missing required fields
        FileNotFoundError: File/directory path not found

    Examples:
        >>> from dictacode_stt.stt_config import AudioConfig
        >>> config = AudioConfig(source="mic", port="auto")
        >>> source = create_source_from_profile(config, port_manager=pm)

        >>> config = AudioConfig(source="file", path=["/path/to/audio.wav"])
        >>> source = create_source_from_profile(config)
    """
    source_type = audio_config.source.lower()

    base_config = AudioSourceConfig(
        source_type=SourceType.MICROPHONE if source_type == "mic" else SourceType.FILE,
        sample_rate=sample_rate,
        channels=channels,
        chunk_size=chunk_size,
        playback_mode=playback_mode,
    )

    if source_type == "mic":
        return MicrophoneSource(
            config=base_config,
            port_manager=port_manager,
            port_id=audio_config.port,
        )

    elif source_type == "file":
        if not audio_config.path:
            raise ValueError("File source requires 'path' field")

        # Handle list or single path
        paths: List[Path] = []
        if isinstance(audio_config.path, list):
            paths = [Path(p) for p in audio_config.path]
        else:
            paths = [Path(audio_config.path)]

        if len(paths) == 1:
            # Single file - use FileSource directly
            file_config = AudioSourceConfig(
                source_type=SourceType.FILE,
                sample_rate=sample_rate,
                channels=channels,
                chunk_size=chunk_size,
                playback_mode=playback_mode,
                file_path=paths[0],
            )
            return FileSource(file_config)
        else:
            # Multiple files - use BatchFileSource
            return BatchFileSource(
                file_paths=paths,
                config=base_config,
                playback_mode=playback_mode,
            )

    elif source_type == "directory":
        if not audio_config.path:
            raise ValueError("Directory source requires 'path' field")

        # path should be a single directory for directory source
        directory = audio_config.path
        if isinstance(directory, list):
            directory = directory[0]

        return DirectorySource(
            directory=Path(directory),
            pattern=audio_config.pattern,
            config=base_config,
            playback_mode=playback_mode,
        )

    else:
        raise ValueError(
            f"Unknown audio source type: {source_type}. "
            f"Use: mic, file, or directory"
        )
