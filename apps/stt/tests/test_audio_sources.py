"""Tests for audio source abstraction (v0.2.11)."""

import time
from pathlib import Path

import pytest

from dictacode_stt.audio.sources import (
    FileSource,
    PlaybackMode,
    SyntheticSource,
    create_audio_source,
)


class TestAudioSourceFactory:
    """Test the create_audio_source factory function."""

    def test_create_synthetic_silence(self):
        """Test creating synthetic silence source."""
        source = create_audio_source("synthetic:silence:1000")
        assert isinstance(source, SyntheticSource)
        assert source.config.pattern == "silence"
        assert source.config.duration_ms == 1000

    def test_create_synthetic_silence_default_duration(self):
        """Test synthetic silence with no duration (infinite)."""
        source = create_audio_source("synthetic:silence")
        assert isinstance(source, SyntheticSource)
        assert source.config.duration_ms is None

    def test_create_file_source_fast_mode(self, tmp_path):
        """Test creating file source in fast mode."""
        # Create dummy WAV file
        wav_path = tmp_path / "test.wav"
        self._create_dummy_wav(wav_path, duration_seconds=1)

        source = create_audio_source(f"file:{wav_path}:fast")
        assert isinstance(source, FileSource)
        assert source.config.playback_mode == PlaybackMode.FAST
        assert source.config.file_path == wav_path

    def test_create_file_source_realtime_mode(self, tmp_path):
        """Test creating file source in realtime mode."""
        wav_path = tmp_path / "test.wav"
        self._create_dummy_wav(wav_path, duration_seconds=1)

        source = create_audio_source(f"file:{wav_path}:realtime")
        assert isinstance(source, FileSource)
        assert source.config.playback_mode == PlaybackMode.REALTIME

    def test_create_mic_source_not_implemented(self):
        """Test that microphone source raises NotImplementedError."""
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            create_audio_source("mic")

    def test_invalid_source_type(self):
        """Test invalid source type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown source type"):
            create_audio_source("invalid:foo")

    def test_invalid_playback_mode(self, tmp_path):
        """Test invalid playback mode raises ValueError."""
        wav_path = tmp_path / "test.wav"
        self._create_dummy_wav(wav_path, duration_seconds=1)

        with pytest.raises(ValueError, match="Invalid playback mode"):
            create_audio_source(f"file:{wav_path}:invalid")

    @staticmethod
    def _create_dummy_wav(path: Path, duration_seconds: float = 1.0):
        """Create a minimal valid WAV file."""
        import wave

        import numpy as np

        sample_rate = 16000
        frames = int(sample_rate * duration_seconds)
        audio = np.zeros(frames, dtype=np.int16)

        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())


class TestSyntheticSource:
    """Test synthetic audio source."""

    def test_silence_generation(self):
        """Test that silence source generates zero samples."""
        source = create_audio_source("synthetic:silence:500")  # 0.5 seconds

        chunks = []
        total_frames = 0

        def on_audio(data: bytes, frames: int):
            chunks.append(data)
            nonlocal total_frames
            total_frames += frames

        finished = False

        def on_end():
            nonlocal finished
            finished = True

        source.open()
        source.start(callback=on_audio, on_end=on_end)

        # Wait for completion
        timeout = time.time() + 2.0
        while source.is_active() and time.time() < timeout:
            time.sleep(0.01)

        source.close()

        # Verify silence
        assert finished, "Source should have finished"
        assert total_frames > 0, "Should have generated frames"
        assert len(chunks) > 0, "Should have generated chunks"

        # Verify all samples are zero
        import numpy as np

        all_audio = b"".join(chunks)
        samples = np.frombuffer(all_audio, dtype=np.int16)
        assert np.all(samples == 0), "All samples should be zero (silence)"

    def test_silence_duration(self):
        """Test that silence source respects duration."""
        duration_ms = 500  # 0.5 seconds
        source = create_audio_source(f"synthetic:silence:{duration_ms}")

        total_frames = 0

        def on_audio(data: bytes, frames: int):
            nonlocal total_frames
            total_frames += frames

        source.open()
        source.start(callback=on_audio, on_end=lambda: None)

        # Wait for completion
        timeout = time.time() + 2.0
        while source.is_active() and time.time() < timeout:
            time.sleep(0.01)

        source.close()

        # Check total frames (should be ~8000 for 0.5s at 16kHz)
        expected_frames = int(16000 * (duration_ms / 1000))
        # Allow 10% tolerance for chunk boundaries
        assert abs(total_frames - expected_frames) / expected_frames < 0.1


class TestFileSource:
    """Test file-based audio source."""

    def test_file_playback_fast_mode(self, tmp_path):
        """Test file playback in fast mode."""
        # Create test WAV
        wav_path = tmp_path / "test.wav"
        self._create_test_wav(wav_path, duration_seconds=1.0)

        source = create_audio_source(f"file:{wav_path}:fast")

        chunks = []

        def on_audio(data: bytes, frames: int):
            chunks.append(data)

        finished = False

        def on_end():
            nonlocal finished
            finished = True

        start_time = time.time()
        source.open()
        source.start(callback=on_audio, on_end=on_end)

        # Wait for completion
        timeout = time.time() + 5.0
        while source.is_active() and time.time() < timeout:
            time.sleep(0.01)

        elapsed = time.time() - start_time
        source.close()

        # Fast mode should complete quickly (much faster than 1s)
        assert elapsed < 0.5, f"Fast mode took {elapsed}s, should be < 0.5s"
        assert finished, "File should have finished"
        assert len(chunks) > 0, "Should have received audio chunks"

    def test_file_playback_realtime_mode(self, tmp_path):
        """Test file playback in realtime mode."""
        # Create test WAV
        duration = 0.5  # Short to keep test fast
        wav_path = tmp_path / "test.wav"
        self._create_test_wav(wav_path, duration_seconds=duration)

        source = create_audio_source(f"file:{wav_path}:realtime")

        chunks = []

        def on_audio(data: bytes, frames: int):
            chunks.append(data)

        start_time = time.time()
        source.open()
        source.start(callback=on_audio, on_end=lambda: None)

        # Wait for completion
        timeout = time.time() + 5.0
        while source.is_active() and time.time() < timeout:
            time.sleep(0.01)

        elapsed = time.time() - start_time
        source.close()

        # Realtime mode should take approximately the audio duration
        # Allow some tolerance for overhead
        assert (
            elapsed >= duration * 0.8
        ), f"Realtime should take ~{duration}s, got {elapsed}s"
        assert len(chunks) > 0, "Should have received audio chunks"

    def test_file_not_found(self):
        """Test that missing file raises error."""
        source = create_audio_source("file:/nonexistent/file.wav:fast")

        with pytest.raises(FileNotFoundError):
            source.open()

    @staticmethod
    def _create_test_wav(
        path: Path, duration_seconds: float = 1.0, frequency: float = 440.0
    ):
        """Create a test WAV file with a tone."""
        import wave

        import numpy as np

        sample_rate = 16000
        frames = int(sample_rate * duration_seconds)

        # Generate tone
        t = np.linspace(0, duration_seconds, frames)
        audio = (np.sin(2 * np.pi * frequency * t) * 16384).astype(np.int16)

        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio.tobytes())


class TestAudioSourceLifecycle:
    """Test audio source lifecycle (open/start/stop/close)."""

    def test_source_lifecycle(self):
        """Test proper lifecycle: open -> start -> stop -> close."""
        source = create_audio_source("synthetic:silence:100")

        # Initial state
        assert not source.is_active()

        # Open
        source.open()
        assert not source.is_active()  # Not active until started

        # Start
        source.start(callback=lambda d, f: None, on_end=lambda: None)
        # May become active or finish immediately depending on timing
        # Just check it doesn't crash

        # Close
        source.close()
        assert not source.is_active()

    def test_double_close_safe(self):
        """Test that closing twice doesn't raise error."""
        source = create_audio_source("synthetic:silence:100")
        source.open()
        source.close()
        source.close()  # Should not raise
