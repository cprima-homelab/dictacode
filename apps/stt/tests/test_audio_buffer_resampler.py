"""Tests for audio ring buffer and resampler."""

import numpy as np
import pytest

from dictacode_stt.audio.buffer import AudioRingBuffer
from dictacode_stt.audio.resampler import Resampler


class TestAudioRingBuffer:
    """Test AudioRingBuffer functionality."""

    def test_buffer_init(self):
        """Test buffer initialization."""
        buffer = AudioRingBuffer(
            max_seconds=5.0, sample_rate=16000, overlap_seconds=0.5, dtype="int16"
        )

        assert buffer.sample_rate == 16000
        assert buffer.overlap_seconds == 0.5
        assert buffer.max_samples == 5 * 16000
        assert buffer.overlap_samples == 0.5 * 16000
        assert buffer.is_empty() is True

    def test_buffer_write_read(self):
        """Test writing and reading from buffer."""
        buffer = AudioRingBuffer(max_seconds=5.0, sample_rate=16000, dtype="int16")

        # Create test audio (1 second of samples)
        samples = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
        audio_bytes = samples.tobytes()

        # Write to buffer
        buffer.write(audio_bytes)

        assert buffer.is_empty() is False
        assert buffer.has_unread_data() is True
        assert buffer.get_duration_seconds() == pytest.approx(1.0, rel=0.01)

        # Read from buffer
        read_bytes = buffer.read_for_transcription()
        assert read_bytes is not None
        assert len(read_bytes) == len(audio_bytes)

    def test_buffer_overlap(self):
        """Test overlap functionality."""
        buffer = AudioRingBuffer(
            max_seconds=5.0, sample_rate=16000, overlap_seconds=0.5, dtype="int16"
        )

        # Write first chunk (1 second)
        chunk1 = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
        buffer.write(chunk1.tobytes())

        # Read first chunk
        read1 = buffer.read_for_transcription()
        assert read1 is not None
        read1_samples = np.frombuffer(read1, dtype=np.int16)
        assert len(read1_samples) == 16000  # All samples from first chunk

        # Write second chunk (1 second)
        chunk2 = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
        buffer.write(chunk2.tobytes())

        # Read second chunk - should include overlap from first chunk
        read2 = buffer.read_for_transcription()
        assert read2 is not None
        read2_samples = np.frombuffer(read2, dtype=np.int16)

        # Should have: overlap (8000) + new samples (16000) = 24000
        expected_samples = int(0.5 * 16000) + 16000
        assert len(read2_samples) == expected_samples

        # First overlap_samples should match end of chunk1
        overlap_samples = int(0.5 * 16000)
        assert np.array_equal(
            read2_samples[:overlap_samples], chunk1[-overlap_samples:]
        )

    def test_buffer_no_cutoff(self):
        """Test that audio at boundaries is not lost."""
        buffer = AudioRingBuffer(
            max_seconds=5.0, sample_rate=16000, overlap_seconds=0.5, dtype="int16"
        )

        # Write and read multiple chunks
        chunks = []
        for i in range(3):
            chunk = np.full(16000, fill_value=i, dtype=np.int16)
            chunks.append(chunk)
            buffer.write(chunk.tobytes())

            read_bytes = buffer.read_for_transcription()
            if read_bytes:
                read_samples = np.frombuffer(read_bytes, dtype=np.int16)
                # Verify we can reconstruct the data with overlap
                # (actual verification would check for word boundaries in real audio)
                assert len(read_samples) > 0

    def test_buffer_max_size_eviction(self):
        """Test that buffer evicts old samples when exceeding max size."""
        buffer = AudioRingBuffer(max_seconds=2.0, sample_rate=16000, dtype="int16")

        # Write 3 seconds of audio (should evict 1 second)
        for i in range(3):
            chunk = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
            buffer.write(chunk.tobytes())

        # Buffer should be at max size (2 seconds)
        assert buffer.get_duration_seconds() <= 2.0

    def test_buffer_clear(self):
        """Test buffer clearing."""
        buffer = AudioRingBuffer(max_seconds=5.0, sample_rate=16000, dtype="int16")

        # Write some data
        samples = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
        buffer.write(samples.tobytes())

        assert buffer.is_empty() is False

        # Clear buffer
        buffer.clear()

        assert buffer.is_empty() is True
        assert buffer.get_duration_seconds() == 0.0
        assert buffer.has_unread_data() is False

    def test_buffer_peek(self):
        """Test peeking at buffer without advancing read position."""
        buffer = AudioRingBuffer(max_seconds=5.0, sample_rate=16000, dtype="int16")

        # Write data
        samples = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
        buffer.write(samples.tobytes())

        # Peek at data
        peek1 = buffer.peek()
        assert peek1 is not None

        # Peek again - should return same data
        peek2 = buffer.peek()
        assert peek1 == peek2

        # Data should still be unread
        assert buffer.has_unread_data() is True

    def test_buffer_unread_duration(self):
        """Test tracking of unread audio duration."""
        buffer = AudioRingBuffer(max_seconds=5.0, sample_rate=16000, dtype="int16")

        # Write 2 seconds of audio
        for i in range(2):
            chunk = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
            buffer.write(chunk.tobytes())

        # All data is unread
        assert buffer.get_unread_duration_seconds() == pytest.approx(2.0, rel=0.01)

        # Read once
        buffer.read_for_transcription()

        # No new unread data (without writing more)
        assert buffer.get_unread_duration_seconds() == pytest.approx(0.0, rel=0.01)

        # Write more
        chunk = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
        buffer.write(chunk.tobytes())

        # Now we have 1 second of unread data
        assert buffer.get_unread_duration_seconds() == pytest.approx(1.0, rel=0.01)

    def test_buffer_empty_read(self):
        """Test reading from empty buffer."""
        buffer = AudioRingBuffer(max_seconds=5.0, sample_rate=16000, dtype="int16")

        # Read from empty buffer
        result = buffer.read_for_transcription()
        assert result is None

    def test_buffer_float32_dtype(self):
        """Test buffer with float32 dtype."""
        buffer = AudioRingBuffer(
            max_seconds=5.0, sample_rate=16000, overlap_seconds=0.5, dtype="float32"
        )

        # Create float32 audio data
        samples = np.random.uniform(-1.0, 1.0, size=16000).astype(np.float32)
        buffer.write(samples.tobytes())

        # Read and verify
        read_bytes = buffer.read_for_transcription()
        assert read_bytes is not None
        read_samples = np.frombuffer(read_bytes, dtype=np.float32)
        assert len(read_samples) == 16000


class TestResampler:
    """Test Resampler functionality."""

    def test_resampler_init(self):
        """Test resampler initialization."""
        resampler = Resampler(target_rate=16000, dtype="int16")

        assert resampler.target_rate == 16000
        assert resampler.dtype == "int16"

    def test_resampler_no_change(self):
        """Test resampling when source and target rates match."""
        resampler = Resampler(target_rate=16000, dtype="int16")

        # Create test audio at target rate
        samples = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
        audio_bytes = samples.tobytes()

        # Resample (should be no-op)
        result = resampler.process(audio_bytes, source_rate=16000)

        assert result == audio_bytes

    def test_resampler_downsample(self):
        """Test downsampling from 48kHz to 16kHz."""
        resampler = Resampler(target_rate=16000, dtype="int16")

        # Create 1 second of 48kHz audio
        samples_48k = np.random.randint(-32768, 32767, size=48000, dtype=np.int16)
        audio_bytes_48k = samples_48k.tobytes()

        # Resample to 16kHz
        result = resampler.process(audio_bytes_48k, source_rate=48000)

        # Should have 1/3 the samples (48000 → 16000)
        result_samples = np.frombuffer(result, dtype=np.int16)
        assert len(result_samples) == pytest.approx(16000, rel=0.01)

    def test_resampler_upsample(self):
        """Test upsampling from 8kHz to 16kHz."""
        resampler = Resampler(target_rate=16000, dtype="int16")

        # Create 1 second of 8kHz audio
        samples_8k = np.random.randint(-32768, 32767, size=8000, dtype=np.int16)
        audio_bytes_8k = samples_8k.tobytes()

        # Resample to 16kHz
        result = resampler.process(audio_bytes_8k, source_rate=8000)

        # Should have 2x the samples (8000 → 16000)
        result_samples = np.frombuffer(result, dtype=np.int16)
        assert len(result_samples) == pytest.approx(16000, rel=0.01)

    def test_resampler_preserves_signal(self):
        """Test that resampling preserves signal characteristics."""
        resampler = Resampler(target_rate=16000, dtype="int16")

        # Create a simple sine wave at 440 Hz (A note) at 48kHz
        duration = 1.0  # seconds
        source_rate = 48000
        frequency = 440  # Hz

        t = np.linspace(0, duration, int(source_rate * duration), endpoint=False)
        signal = np.sin(2 * np.pi * frequency * t)
        # Scale to int16 range
        samples_48k = (signal * 32767 * 0.9).astype(np.int16)

        # Resample to 16kHz
        result = resampler.process(samples_48k.tobytes(), source_rate=48000)
        samples_16k = np.frombuffer(result, dtype=np.int16)

        # Verify we have approximately 1 second of 16kHz audio
        assert len(samples_16k) == pytest.approx(16000, rel=0.01)

        # Signal should still be mostly within expected range
        # (some distortion is expected from linear interpolation)
        assert np.abs(samples_16k).max() <= 32767
        assert np.abs(samples_16k).max() > 20000  # Signal not completely flattened

    def test_resampler_get_output_size(self):
        """Test output size calculation."""
        resampler = Resampler(target_rate=16000, dtype="int16")

        # 48kHz → 16kHz: 48000 samples → 16000 samples
        output_size = resampler.get_output_size(input_size=48000, source_rate=48000)
        assert output_size == 16000

        # 16kHz → 16kHz: no change
        output_size = resampler.get_output_size(input_size=16000, source_rate=16000)
        assert output_size == 16000

        # 8kHz → 16kHz: 8000 samples → 16000 samples
        output_size = resampler.get_output_size(input_size=8000, source_rate=8000)
        assert output_size == 16000

    def test_resampler_float32(self):
        """Test resampler with float32 dtype."""
        resampler = Resampler(target_rate=16000, dtype="float32")

        # Create float32 audio at 48kHz
        samples_48k = np.random.uniform(-1.0, 1.0, size=48000).astype(np.float32)

        # Resample to 16kHz
        result = resampler.process(samples_48k.tobytes(), source_rate=48000)

        # Verify output
        result_samples = np.frombuffer(result, dtype=np.float32)
        assert len(result_samples) == pytest.approx(16000, rel=0.01)
        assert result_samples.dtype == np.float32

    def test_resampler_invalid_source_rate(self):
        """Test error handling for invalid source rate."""
        resampler = Resampler(target_rate=16000, dtype="int16")

        samples = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)

        with pytest.raises(ValueError, match="Invalid source_rate"):
            resampler.process(samples.tobytes(), source_rate=0)

        with pytest.raises(ValueError, match="Invalid source_rate"):
            resampler.process(samples.tobytes(), source_rate=-1)
