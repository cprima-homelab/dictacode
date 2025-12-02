"""Pytest configuration and fixtures for dictacode STT tests."""

import os
from pathlib import Path
from typing import Callable

import pytest

from dictacode_stt.audio.sources import (
    AudioSource,
    AudioSourceConfig,
    PlaybackMode,
    SourceType,
    create_audio_source,
)


# Custom pytest markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "device_only: mark test to run only on actual devices (Raspberry Pi)",
    )
    config.addinivalue_line(
        "markers",
        "laptop: mark test to run on developer laptop (default)",
    )


def pytest_collection_modifyitems(config, items):
    """
    Automatically skip tests based on environment.

    - On device: skip laptop-only tests (if explicitly marked)
    - On laptop: skip device_only tests
    """
    # Detect if running on device (Raspberry Pi)
    is_device = os.path.exists("/dev/hidg0") or os.path.exists("/dev/serial0")

    skip_device = pytest.mark.skip(reason="requires actual device hardware")
    skip_laptop = pytest.mark.skip(reason="requires laptop environment")

    for item in items:
        if "device_only" in item.keywords:
            if not is_device:
                item.add_marker(skip_device)
        # No explicit laptop marker needed - tests without device_only run on laptop by default


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


# === Canonical Templates Fixtures ===

def _get_repo_root() -> Path:
    """Find repository root by walking up from this file."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "compatibility.json").exists() or (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repository root")


CANONICAL_TEMPLATES_DIR = _get_repo_root() / "ops" / "packaging" / "templates"


@pytest.fixture
def canonical_templates_dir() -> Path:
    """Return path to canonical templates directory."""
    if not CANONICAL_TEMPLATES_DIR.exists():
        pytest.skip(f"Canonical templates directory not found: {CANONICAL_TEMPLATES_DIR}")
    return CANONICAL_TEMPLATES_DIR


@pytest.fixture
def canonical_stt_conf() -> Path:
    """Return path to canonical stt.conf template."""
    conf_path = CANONICAL_TEMPLATES_DIR / "stt.conf"
    if not conf_path.exists():
        pytest.skip(f"Canonical stt.conf not found: {conf_path}")
    return conf_path


@pytest.fixture
def get_canonical_template() -> Callable[[str], Path]:
    """Return function to get path to any canonical template.

    Usage:
        def test_something(get_canonical_template):
            stt_conf = get_canonical_template("stt.conf")
            hid_conf = get_canonical_template("hid.conf")
    """
    def _get(template_name: str) -> Path:
        path = CANONICAL_TEMPLATES_DIR / template_name
        if not path.exists():
            pytest.skip(f"Canonical template not found: {path}")
        return path
    return _get
