"""File-based audio source for testing (v0.2.11 Phase 2)."""

from __future__ import annotations

import logging
import threading
import time
import wave
from pathlib import Path
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


class FileSource(AudioSource):
    """Audio file playback source for testing."""

    def __init__(self, config: AudioSourceConfig):
        """Initialize file source.

        Args:
            config: Source configuration with file_path set
        """
        if not config.file_path:
            raise ValueError("file_path required for FileSource")

        self.config = config
        self._wav: Optional[wave.Wave_read] = None
        self._thread: Optional[threading.Thread] = None
        self._active = False
        self._callback: Optional[AudioChunkCallback] = None
        self._on_end: Optional[SourceEndCallback] = None

    def get_type(self) -> SourceType:
        """Return source type."""
        return SourceType.FILE

    def get_config(self) -> AudioSourceConfig:
        """Return source configuration."""
        return self.config

    def open(self) -> None:
        """Open WAV file and validate format."""
        self._wav = wave.open(str(self.config.file_path), "rb")

        # Validate format
        if self._wav.getsampwidth() != 2:  # 16-bit
            raise ValueError("Only 16-bit WAV files supported")

        # Seek to start offset if specified
        if self.config.start_offset_ms > 0:
            start_frame = int(
                self.config.start_offset_ms * self._wav.getframerate() / 1000
            )
            self._wav.setpos(start_frame)

        logger.info(
            f"Opened file source: {self.config.file_path} "
            f"({self._wav.getframerate()}Hz, {self._wav.getnchannels()}ch)"
        )

    def close(self) -> None:
        """Close WAV file."""
        if self._wav:
            self._wav.close()
            self._wav = None

    def start(
        self,
        callback: AudioChunkCallback,
        on_end: Optional[SourceEndCallback] = None,
    ) -> None:
        """Start streaming audio from file.

        Args:
            callback: Called with each audio chunk
            on_end: Called when file ends (unless looping)
        """
        self._callback = callback
        self._on_end = on_end
        self._active = True

        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def _playback_loop(self) -> None:
        """Stream audio chunks from file with pacing."""
        if not self._wav:
            logger.error("WAV file not opened")
            return

        file_rate = self._wav.getframerate()
        file_channels = self._wav.getnchannels()
        target_rate = self.config.sample_rate
        chunk_frames = self.config.chunk_size

        # Calculate timing for real-time playback
        chunk_duration = chunk_frames / target_rate

        # Calculate end position
        end_frame = None
        if self.config.end_offset_ms:
            end_frame = int(self.config.end_offset_ms * file_rate / 1000)

        logger.debug(
            f"Starting playback loop: mode={self.config.playback_mode.value}, "
            f"chunk_duration={chunk_duration:.3f}s"
        )

        while self._active:
            start_time = time.monotonic()

            # Read chunk from file
            frames_to_read = int(chunk_frames * file_rate / target_rate)
            data = self._wav.readframes(frames_to_read)

            if not data:
                if self.config.loop:
                    # Restart from beginning
                    start_frame = int(
                        self.config.start_offset_ms * file_rate / 1000
                    )
                    self._wav.setpos(start_frame)
                    logger.debug("Looping back to start")
                    continue
                else:
                    # End of file
                    logger.debug("Reached end of file")
                    break

            # Check end position
            if end_frame and self._wav.tell() >= end_frame:
                if self.config.loop:
                    start_frame = int(
                        self.config.start_offset_ms * file_rate / 1000
                    )
                    self._wav.setpos(start_frame)
                    logger.debug("Reached end offset, looping")
                    continue
                else:
                    logger.debug("Reached end offset, stopping")
                    break

            # Resample if needed
            if file_rate != target_rate or file_channels != self.config.channels:
                data = self._resample(data, file_rate, file_channels)

            # Deliver chunk
            if self._callback:
                frame_count = len(data) // (2 * self.config.channels)
                self._callback(data, frame_count)

            # Pace delivery based on playback mode
            if self.config.playback_mode == PlaybackMode.REALTIME:
                elapsed = time.monotonic() - start_time
                sleep_time = chunk_duration - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            elif self.config.playback_mode == PlaybackMode.FAST:
                pass  # No delay, maximum speed

        self._active = False
        logger.info("Playback loop ended")
        if self._on_end:
            self._on_end()

    def _resample(
        self,
        data: bytes,
        source_rate: int,
        source_channels: int,
    ) -> bytes:
        """Resample audio to target format.

        Args:
            data: Input audio data
            source_rate: Source sample rate
            source_channels: Source channel count

        Returns:
            Resampled audio data
        """
        # Convert to numpy array
        samples = np.frombuffer(data, dtype=np.int16)

        # Convert channels if needed
        if source_channels > self.config.channels:
            # Stereo to mono: average channels
            samples = samples.reshape(-1, source_channels)
            samples = samples.mean(axis=1).astype(np.int16)
        elif source_channels < self.config.channels:
            # Mono to stereo: duplicate
            samples = np.column_stack([samples] * self.config.channels)
            samples = samples.flatten()

        # Resample if needed
        if source_rate != self.config.sample_rate:
            try:
                from scipy import signal

                num_samples = int(len(samples) * self.config.sample_rate / source_rate)
                samples = signal.resample(samples, num_samples).astype(np.int16)
            except ImportError:
                logger.warning(
                    f"scipy not available, cannot resample {source_rate}Hz to {self.config.sample_rate}Hz"
                )
                # Fall back to simple decimation/interpolation
                if source_rate > self.config.sample_rate:
                    # Decimate
                    step = source_rate // self.config.sample_rate
                    samples = samples[::step]
                # Note: interpolation would require scipy

        return samples.tobytes()

    def stop(self) -> None:
        """Stop streaming."""
        self._active = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def is_active(self) -> bool:
        """Return True if streaming."""
        return self._active

    def supports_seeking(self) -> bool:
        """File source supports seeking."""
        return True

    def seek(self, position_ms: int) -> None:
        """Seek to position in file.

        Args:
            position_ms: Position in milliseconds
        """
        if self._wav:
            frame = int(position_ms * self._wav.getframerate() / 1000)
            self._wav.setpos(frame)
            logger.debug(f"Seeked to {position_ms}ms (frame {frame})")
