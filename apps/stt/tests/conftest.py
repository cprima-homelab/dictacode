"""Pytest configuration and fixtures for dictacode STT tests."""

from pathlib import Path

import pytest

from dictacode_stt.audio.sources import (
    AudioSource,
    AudioSourceConfig,
    PlaybackMode,
    SourceType,
    create_audio_source,
)


# Fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "audio"


@pytest.fixture
def fixtures_dir() -> Path:
    """Return path to audio fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def hello_world_source() -> AudioSource:
    """Audio source for 'hello world' test audio."""
    fixture_path = FIXTURES_DIR / "hello_world.wav"
    if not fixture_path.exists():
        pytest.skip(f"Test fixture missing: {fixture_path}")
    return create_audio_source(f"file:{fixture_path}:fast")


@pytest.fixture
def numbers_source() -> AudioSource:
    """Audio source for '1-5' counting test audio."""
    fixture_path = FIXTURES_DIR / "numbers_1_to_5.wav"
    if not fixture_path.exists():
        pytest.skip(f"Test fixture missing: {fixture_path}")
    return create_audio_source(f"file:{fixture_path}:fast")


@pytest.fixture
def silence_source() -> AudioSource:
    """Audio source for 1 second of silence."""
    fixture_path = FIXTURES_DIR / "silence_1s.wav"
    if not fixture_path.exists():
        # Fallback to synthetic if file doesn't exist
        return create_audio_source("synthetic:silence:1000")
    return create_audio_source(f"file:{fixture_path}:fast")


@pytest.fixture
def short_phrase_source() -> AudioSource:
    """Audio source for short test phrase."""
    fixture_path = FIXTURES_DIR / "short_phrase.wav"
    if not fixture_path.exists():
        pytest.skip(f"Test fixture missing: {fixture_path}")
    return create_audio_source(f"file:{fixture_path}:fast")


@pytest.fixture
def synthetic_silence_source() -> AudioSource:
    """Synthetic silence source (always available, no files needed)."""
    return create_audio_source("synthetic:silence:1000")


def create_file_source(
    fixture_name: str,
    playback_mode: PlaybackMode = PlaybackMode.FAST,
    loop: bool = False,
) -> AudioSource:
    """
    Helper to create audio source from fixture file.

    Args:
        fixture_name: Name of fixture file (e.g., "hello_world.wav")
        playback_mode: Playback mode (default: FAST)
        loop: Whether to loop (default: False)

    Returns:
        AudioSource instance

    Raises:
        FileNotFoundError: If fixture doesn't exist
    """
    fixture_path = FIXTURES_DIR / fixture_name
    if not fixture_path.exists():
        raise FileNotFoundError(f"Test fixture not found: {fixture_path}")

    # Use string spec for simple cases
    if playback_mode == PlaybackMode.FAST and not loop:
        return create_audio_source(f"file:{fixture_path}:fast")

    # Use config for advanced options
    from dictacode_stt.audio.sources import FileSource

    config = AudioSourceConfig(
        source_type=SourceType.FILE,
        file_path=fixture_path,
        playback_mode=playback_mode,
        loop=loop,
    )
    return FileSource(config)


def collect_audio_from_source(source: AudioSource, max_duration: float = 10.0) -> bytes:
    """
    Collect all audio from a source.

    Args:
        source: Audio source to read from
        max_duration: Maximum duration in seconds (safety limit)

    Returns:
        Combined audio bytes
    """
    chunks = []
    total_frames = 0
    max_frames = int(16000 * max_duration)  # Assume 16kHz

    def on_audio(data: bytes, frames: int) -> None:
        nonlocal total_frames
        if total_frames < max_frames:
            chunks.append(data)
            total_frames += frames

    def on_end() -> None:
        pass

    source.open()
    source.start(callback=on_audio, on_end=on_end)

    import time

    while source.is_active() and total_frames < max_frames:
        time.sleep(0.01)

    source.close()

    return b"".join(chunks)
