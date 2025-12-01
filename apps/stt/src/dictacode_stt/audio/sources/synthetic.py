"""Synthetic audio source for testing (v0.2.11 Phase 3)."""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import numpy as np

from dictacode_stt.audio.source import (
    AudioSource,
    AudioSourceConfig,
    AudioChunkCallback,
    SourceEndCallback,
    SourceType,
    PlaybackMode,
)

logger = logging.getLogger(__name__)


class SyntheticSource(AudioSource):
    """Generated audio source for testing."""

    PATTERNS = {
        "silence": "_generate_silence",
        "tone": "_generate_tone",
        "noise": "_generate_noise",
        "click": "_generate_click",
        "sweep": "_generate_sweep",
    }

    def __init__(self, config: AudioSourceConfig):
        """Initialize synthetic source.

        Args:
            config: Source configuration with pattern specified
        """
        self.config = config
        self._thread: Optional[threading.Thread] = None
        self._active = False
        self._callback: Optional[AudioChunkCallback] = None
        self._on_end: Optional[SourceEndCallback] = None
        self._samples_delivered = 0

        # Validate pattern
        if self.config.pattern not in self.PATTERNS:
            raise ValueError(
                f"Unknown pattern: {self.config.pattern}. "
                f"Available: {list(self.PATTERNS.keys())}"
            )

    def get_type(self) -> SourceType:
        """Return source type."""
        return SourceType.SYNTHETIC

    def get_config(self) -> AudioSourceConfig:
        """Return source configuration."""
        return self.config

    def open(self) -> None:
        """Initialize source."""
        self._samples_delivered = 0
        logger.info(
            f"Opened synthetic source: pattern={self.config.pattern}, "
            f"duration={self.config.duration_ms}ms"
        )

    def close(self) -> None:
        """Cleanup resources."""
        pass

    def start(
        self,
        callback: AudioChunkCallback,
        on_end: Optional[SourceEndCallback] = None,
    ) -> None:
        """Start generating audio.

        Args:
            callback: Called with each generated chunk
            on_end: Called when duration reached (if finite)
        """
        self._callback = callback
        self._on_end = on_end
        self._active = True
        self._samples_delivered = 0

        self._thread = threading.Thread(target=self._generation_loop, daemon=True)
        self._thread.start()

    def _generation_loop(self) -> None:
        """Generate and deliver audio chunks."""
        chunk_frames = self.config.chunk_size
        chunk_duration = chunk_frames / self.config.sample_rate

        # Total samples if finite duration
        total_samples = None
        if self.config.duration_ms:
            total_samples = int(
                self.config.duration_ms * self.config.sample_rate / 1000
            )

        generator = getattr(
            self, self.PATTERNS.get(self.config.pattern, "_generate_silence")
        )

        logger.debug(
            f"Starting generation loop: pattern={self.config.pattern}, "
            f"mode={self.config.playback_mode.value}"
        )

        while self._active:
            start_time = time.monotonic()

            # Check if we've delivered enough
            if total_samples and self._samples_delivered >= total_samples:
                logger.debug(f"Reached duration limit: {self._samples_delivered} samples")
                break

            # Generate chunk
            remaining = None
            if total_samples:
                remaining = total_samples - self._samples_delivered
            frames = min(chunk_frames, remaining) if remaining else chunk_frames

            data = generator(frames)

            # Deliver
            if self._callback:
                self._callback(data, frames)

            self._samples_delivered += frames

            # Pace delivery
            if self.config.playback_mode == PlaybackMode.REALTIME:
                elapsed = time.monotonic() - start_time
                sleep_time = chunk_duration - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        self._active = False
        logger.info(f"Generation loop ended: {self._samples_delivered} samples delivered")
        if self._on_end:
            self._on_end()

    def _generate_silence(self, frames: int) -> bytes:
        """Generate silence.

        Args:
            frames: Number of frames to generate

        Returns:
            Audio data (all zeros)
        """
        samples = np.zeros(frames * self.config.channels, dtype=np.int16)
        return samples.tobytes()

    def _generate_tone(self, frames: int) -> bytes:
        """Generate sine wave tone.

        Args:
            frames: Number of frames to generate

        Returns:
            Audio data with sine wave
        """
        t = np.arange(frames) / self.config.sample_rate
        t += self._samples_delivered / self.config.sample_rate  # Phase continuity

        samples = np.sin(2 * np.pi * self.config.frequency_hz * t)
        samples = (samples * 16000).astype(np.int16)  # Scale to 16-bit

        if self.config.channels > 1:
            samples = np.column_stack([samples] * self.config.channels).flatten()

        return samples.tobytes()

    def _generate_noise(self, frames: int) -> bytes:
        """Generate white noise.

        Args:
            frames: Number of frames to generate

        Returns:
            Audio data with random noise
        """
        samples = np.random.randint(
            -8000,
            8000,
            size=frames * self.config.channels,
            dtype=np.int16,
        )
        return samples.tobytes()

    def _generate_click(self, frames: int) -> bytes:
        """Generate periodic clicks (useful for timing tests).

        Args:
            frames: Number of frames to generate

        Returns:
            Audio data with periodic clicks
        """
        samples = np.zeros(frames * self.config.channels, dtype=np.int16)
        # Click every 0.5 seconds
        click_interval = int(0.5 * self.config.sample_rate)
        for i in range(frames):
            global_pos = self._samples_delivered + i
            if global_pos % click_interval == 0:
                samples[i * self.config.channels] = 16000
        return samples.tobytes()

    def _generate_sweep(self, frames: int) -> bytes:
        """Generate frequency sweep.

        Args:
            frames: Number of frames to generate

        Returns:
            Audio data with frequency sweep
        """
        t = np.arange(frames) / self.config.sample_rate
        t += self._samples_delivered / self.config.sample_rate

        # Sweep from 100Hz to 4000Hz over 2 seconds
        freq = 100 + (4000 - 100) * (t % 2.0) / 2.0
        phase = 2 * np.pi * np.cumsum(freq) / self.config.sample_rate
        samples = np.sin(phase)
        samples = (samples * 16000).astype(np.int16)

        if self.config.channels > 1:
            samples = np.column_stack([samples] * self.config.channels).flatten()

        return samples.tobytes()

    def stop(self) -> None:
        """Stop generating audio."""
        self._active = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def is_active(self) -> bool:
        """Return True if generating."""
        return self._active
