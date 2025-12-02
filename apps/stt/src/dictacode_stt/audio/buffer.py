"""Audio ring buffer with overlap for continuous capture.

Fixes word cutoff bug by including overlap from previous segments.
"""

import logging
from collections import deque
from typing import Optional

import numpy as np


logger = logging.getLogger(__name__)


class AudioRingBuffer:
    """Circular buffer with overlap for continuous audio capture.

    Prevents word cutoff at segment boundaries by including overlap
    samples in each read. This ensures words spanning boundaries are
    captured in both segments for transcription.

    Example:
        Current (broken):
          [record 3s]───[transcribe]───[record 3s]───[transcribe]
                             ↑ gap here - words lost

        New (ring buffer):
          ════════════════════════════════════════════  ← continuous stream
                ↓ read pointer with overlap
          [───────transcribe───────]
                    [───────transcribe───────]
                          [───────transcribe───────]
    """

    def __init__(
        self,
        max_seconds: float,
        sample_rate: int = 16000,
        overlap_seconds: float = 0.5,
        dtype: str = "int16",
    ):
        """Initialize ring buffer.

        Args:
            max_seconds: Maximum buffer duration in seconds
            sample_rate: Audio sample rate (samples per second)
            overlap_seconds: Overlap duration for word cutoff prevention
            dtype: Audio data type ("int16" or "float32")
        """
        self.sample_rate = sample_rate
        self.overlap_seconds = overlap_seconds
        self.dtype = dtype

        # Calculate buffer sizes in samples
        self.max_samples = int(max_seconds * sample_rate)
        self.overlap_samples = int(overlap_seconds * sample_rate)

        # Circular buffer (stores raw audio samples as numpy array)
        self._buffer: deque = deque(maxlen=None)  # No automatic eviction
        self._total_samples = 0  # Total samples written
        self._read_pos = 0  # Last read position

        logger.info(
            f"AudioRingBuffer initialized: {max_seconds}s max, "
            f"{overlap_seconds}s overlap, {sample_rate}Hz, {dtype}"
        )

    def write(self, chunk: bytes) -> None:
        """Write audio chunk to buffer.

        Args:
            chunk: Audio data as bytes (will be converted to numpy array)
        """
        # Convert bytes to numpy array
        if self.dtype == "int16":
            samples = np.frombuffer(chunk, dtype=np.int16)
        elif self.dtype == "float32":
            samples = np.frombuffer(chunk, dtype=np.float32)
        else:
            raise ValueError(f"Unsupported dtype: {self.dtype}")

        # Add to buffer
        self._buffer.append(samples)
        self._total_samples += len(samples)

        # Evict old samples if buffer exceeds max size
        while self._get_buffer_size() > self.max_samples:
            removed = self._buffer.popleft()
            self._total_samples -= len(removed)
            # Adjust read position
            if self._read_pos > 0:
                self._read_pos = max(0, self._read_pos - len(removed))

        logger.debug(
            f"Wrote {len(samples)} samples to buffer "
            f"(total: {self._total_samples} samples)"
        )

    def read_for_transcription(self) -> Optional[bytes]:
        """Read audio with overlap to prevent word cutoff.

        Returns audio from last read position with overlap from previous segment.

        Returns:
            Audio data as bytes, or None if insufficient data available
        """
        current_size = self._get_buffer_size()

        if current_size == 0:
            logger.debug("Buffer empty, no data to read")
            return None

        # Calculate start position with overlap
        # Include overlap_samples from before the last read position
        start_pos = max(0, self._read_pos - self.overlap_samples)

        # Get all samples from start_pos to end of buffer
        audio_samples = self._get_samples_from_buffer(start_pos, current_size)

        if len(audio_samples) == 0:
            logger.debug("No new samples available for transcription")
            return None

        # Update read position to current end
        self._read_pos = current_size

        logger.debug(
            f"Read {len(audio_samples)} samples for transcription "
            f"(includes {min(self.overlap_samples, start_pos)} overlap samples)"
        )

        # Convert back to bytes
        return audio_samples.tobytes()

    def peek(self, num_samples: int = None) -> Optional[bytes]:
        """Peek at buffer contents without advancing read position.

        Args:
            num_samples: Number of samples to peek (None = all available)

        Returns:
            Audio data as bytes, or None if buffer empty
        """
        current_size = self._get_buffer_size()

        if current_size == 0:
            return None

        if num_samples is None:
            num_samples = current_size

        samples = self._get_samples_from_buffer(0, min(num_samples, current_size))
        return samples.tobytes() if len(samples) > 0 else None

    def clear(self) -> None:
        """Clear the buffer and reset read position."""
        self._buffer.clear()
        self._total_samples = 0
        self._read_pos = 0
        logger.info("Buffer cleared")

    def get_duration_seconds(self) -> float:
        """Get current buffer duration in seconds.

        Returns:
            Duration in seconds
        """
        return self._get_buffer_size() / self.sample_rate

    def get_unread_duration_seconds(self) -> float:
        """Get duration of unread audio in seconds.

        Returns:
            Duration of unread audio in seconds
        """
        unread_samples = self._get_buffer_size() - self._read_pos
        return max(0, unread_samples / self.sample_rate)

    def is_empty(self) -> bool:
        """Check if buffer is empty.

        Returns:
            True if buffer contains no data
        """
        return self._get_buffer_size() == 0

    def has_unread_data(self) -> bool:
        """Check if buffer has unread data.

        Returns:
            True if there is unread audio data
        """
        return self._get_buffer_size() > self._read_pos

    def _get_buffer_size(self) -> int:
        """Get total number of samples in buffer.

        Returns:
            Number of samples
        """
        return sum(len(chunk) for chunk in self._buffer)

    def _get_samples_from_buffer(self, start: int, end: int) -> np.ndarray:
        """Extract samples from buffer between start and end positions.

        Args:
            start: Start sample index (inclusive)
            end: End sample index (exclusive)

        Returns:
            Numpy array of samples
        """
        if start >= end:
            return np.array([], dtype=self.dtype)

        # Concatenate all chunks and extract slice
        all_samples = np.concatenate(list(self._buffer))
        return all_samples[start:end]

    def __repr__(self) -> str:
        """String representation of buffer state."""
        return (
            f"AudioRingBuffer(size={self._get_buffer_size()} samples, "
            f"duration={self.get_duration_seconds():.2f}s, "
            f"unread={self.get_unread_duration_seconds():.2f}s, "
            f"overlap={self.overlap_seconds}s)"
        )
