"""Integration tests for SttService with audio sources (v0.2.11)."""

from pathlib import Path

import pytest

from dictacode_stt.audio.sources import create_audio_source
from dictacode_stt.service import SttService
from dictacode_stt.transcription import TranscriptionAdapter, TranscriptionResult


class MockTranscriber(TranscriptionAdapter):
    """Mock transcriber for testing."""

    def __init__(self, transcription_text: str = "mock transcription"):
        self.transcription_text = transcription_text
        self.transcribe_calls = []

    def get_name(self) -> str:
        return "MockTranscriber"

    def transcribe(self, audio_path: Path, language: str = "en") -> TranscriptionResult:
        self.transcribe_calls.append((audio_path, language))
        return TranscriptionResult(
            success=True,
            text=self.transcription_text,
            language=language,
        )

    def get_audio_requirements(self):
        from dictacode_stt.transcription import AudioRequirements

        return AudioRequirements(sample_rate=16000, channels=1, format="wav")

    def supports_streaming(self) -> bool:
        return False


class TestSttServiceWithAudioSource:
    """Test SttService with injected audio sources."""

    def test_service_with_synthetic_silence(self):
        """Test service with synthetic silence source."""
        # Create service with synthetic silence
        source = create_audio_source("synthetic:silence:500")  # 0.5 seconds
        mock_transcriber = MockTranscriber(transcription_text="")

        service = SttService(
            audio_source=source,
            transcriber=mock_transcriber,
            dry_run=True,  # Don't need transport for this test
        )

        # Verify source mode is active
        assert service._source_mode
        assert service.audio_source is source

        # Run one iteration
        stats = service.run_once()

        # Verify audio was processed
        assert "mode" in stats
        assert stats["mode"] == "source"
        assert "error" not in stats

        # Verify transcriber was called
        assert len(mock_transcriber.transcribe_calls) == 1

    def test_service_with_file_source(self, tmp_path):
        """Test service with file-based audio source."""
        # Create test WAV file
        wav_path = tmp_path / "test.wav"
        self._create_test_wav(wav_path, duration_seconds=1.0)

        # Create service with file source
        source = create_audio_source(f"file:{wav_path}:fast")
        mock_transcriber = MockTranscriber(transcription_text="test audio")

        service = SttService(
            audio_source=source,
            transcriber=mock_transcriber,
            recording_duration=1.0,
            dry_run=True,
        )

        # Run one iteration
        stats = service.run_once()

        # Verify processing
        assert stats["mode"] == "source"
        assert "error" not in stats
        assert stats["text"] == "test audio"
        assert len(mock_transcriber.transcribe_calls) == 1

    def test_service_without_audio_source_uses_microphone(self):
        """Test that service without audio_source uses normal microphone path."""
        mock_transcriber = MockTranscriber(transcription_text="mic test")

        service = SttService(
            # No audio_source parameter
            transcriber=mock_transcriber,
            dry_run=True,
        )

        # Verify source mode is NOT active
        assert not service._source_mode
        assert service.audio_source is None

        # Service should use normal microphone code path
        # (we won't actually run it since it needs a real mic)

    def test_service_stops_audio_source_on_stop(self):
        """Test that service properly stops audio source."""
        source = create_audio_source("synthetic:silence:5000")  # 5 seconds
        mock_transcriber = MockTranscriber()

        service = SttService(
            audio_source=source,
            transcriber=mock_transcriber,
            dry_run=True,
        )

        # Start source
        service.run_once()  # This starts the source

        # Stop service
        service.stop()

        # Source should be stopped and closed
        assert not source.is_active()

    def test_multiple_iterations_with_looping_source(self, tmp_path):
        """Test multiple service iterations with looping audio source."""
        # Create short test file
        wav_path = tmp_path / "short.wav"
        self._create_test_wav(wav_path, duration_seconds=0.5)

        # Create looping source
        from dictacode_stt.audio.sources import (
            AudioSourceConfig,
            FileSource,
            PlaybackMode,
            SourceType,
        )

        config = AudioSourceConfig(
            source_type=SourceType.FILE,
            file_path=wav_path,
            playback_mode=PlaybackMode.FAST,
            loop=True,  # Loop indefinitely
        )
        source = FileSource(config)

        mock_transcriber = MockTranscriber(transcription_text="loop test")

        service = SttService(
            audio_source=source,
            transcriber=mock_transcriber,
            recording_duration=0.5,
            dry_run=True,
        )

        # Run multiple iterations
        for i in range(3):
            stats = service.run_once()
            assert stats["mode"] == "source"
            assert stats["text"] == "loop test"

        # Should have called transcriber 3 times
        assert len(mock_transcriber.transcribe_calls) == 3

        service.stop()

    @staticmethod
    def _create_test_wav(path: Path, duration_seconds: float = 1.0):
        """Create a minimal test WAV file."""
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


@pytest.mark.integration
class TestEndToEndWithFixtures:
    """End-to-end integration tests with audio fixtures."""

    def test_silence_produces_empty_transcription(self, synthetic_silence_source):
        """Test that silence produces empty transcription."""
        mock_transcriber = MockTranscriber(transcription_text="")

        service = SttService(
            audio_source=synthetic_silence_source,
            transcriber=mock_transcriber,
            recording_duration=1.0,
            dry_run=True,
        )

        stats = service.run_once()
        service.stop()

        # Empty transcription shouldn't be sent
        assert stats["text"] == ""
        assert "send_sec" not in stats or stats["send_sec"] == 0

    @pytest.mark.skip(reason="Requires actual audio fixture file")
    def test_hello_world_fixture(self, hello_world_source):
        """Test transcription with hello world fixture."""
        # This test requires:
        # 1. Real Whisper transcriber (not mock)
        # 2. Actual hello_world.wav fixture file
        # Skip for now, but shows pattern for real tests

        from dictacode_stt.transcription import get_transcriber

        transcriber = get_transcriber("whisper")
        service = SttService(
            audio_source=hello_world_source,
            transcriber=transcriber,
            recording_duration=2.0,
            dry_run=True,
        )

        stats = service.run_once()
        service.stop()

        # Check transcription contains expected words
        text_lower = stats["text"].lower()
        assert "hello" in text_lower
        assert "world" in text_lower
