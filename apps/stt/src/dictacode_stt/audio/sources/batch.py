"""Batch file audio source for processing multiple files (v0.3.10)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Union

from dictacode_stt.audio.source import (
    AudioChunkCallback,
    AudioSource,
    AudioSourceConfig,
    PlaybackMode,
    SourceEndCallback,
    SourceType,
)
from dictacode_stt.audio.sources.file import FileSource


logger = logging.getLogger(__name__)


class BatchFileSource(AudioSource):
    """Process multiple audio files sequentially.

    Iterates through a list of file paths, streaming each one through
    the callback. Calls on_end when all files are processed.
    """

    def __init__(
        self,
        file_paths: List[Path],
        config: AudioSourceConfig,
        playback_mode: PlaybackMode = PlaybackMode.FAST,
    ):
        """Initialize batch file source.

        Args:
            file_paths: List of audio file paths to process
            config: Base configuration (applied to each file)
            playback_mode: FAST for testing, REALTIME for simulation
        """
        if not file_paths:
            raise ValueError("At least one file path required for BatchFileSource")

        self._file_paths = [Path(p) for p in file_paths]
        self._base_config = config
        self._playback_mode = playback_mode
        self._current_source: Optional[FileSource] = None
        self._current_index = 0
        self._active = False
        self._callback: Optional[AudioChunkCallback] = None
        self._on_end: Optional[SourceEndCallback] = None
        self._files_processed = 0

    @classmethod
    def from_paths(
        cls,
        paths: Union[List[str], List[Path]],
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        playback_mode: PlaybackMode = PlaybackMode.FAST,
    ) -> "BatchFileSource":
        """Create BatchFileSource from list of path strings.

        Args:
            paths: List of file paths (strings or Path objects)
            sample_rate: Target sample rate
            channels: Target channel count
            chunk_size: Samples per chunk
            playback_mode: Playback mode

        Returns:
            Configured BatchFileSource
        """
        config = AudioSourceConfig(
            source_type=SourceType.FILE,
            sample_rate=sample_rate,
            channels=channels,
            chunk_size=chunk_size,
            playback_mode=playback_mode,
        )
        return cls(
            file_paths=[Path(p) for p in paths],
            config=config,
            playback_mode=playback_mode,
        )

    def get_type(self) -> SourceType:
        """Return source type."""
        return SourceType.FILE

    def get_config(self) -> AudioSourceConfig:
        """Return source configuration."""
        return self._base_config

    def get_file_count(self) -> int:
        """Return total number of files to process."""
        return len(self._file_paths)

    def get_files_processed(self) -> int:
        """Return number of files processed so far."""
        return self._files_processed

    def get_current_file(self) -> Optional[Path]:
        """Return path of file currently being processed."""
        if 0 <= self._current_index < len(self._file_paths):
            return self._file_paths[self._current_index]
        return None

    def open(self) -> None:
        """Validate all files exist."""
        missing = [p for p in self._file_paths if not p.exists()]
        if missing:
            raise FileNotFoundError(
                f"Batch source missing files: {[str(p) for p in missing[:5]]}"
                + (f" and {len(missing) - 5} more" if len(missing) > 5 else "")
            )
        logger.info(f"Opened batch source with {len(self._file_paths)} files")

    def close(self) -> None:
        """Close current file source."""
        if self._current_source:
            self._current_source.close()
            self._current_source = None

    def _open_next_file(self) -> bool:
        """Open the next file in the batch.

        Returns:
            True if a file was opened, False if batch exhausted
        """
        if self._current_index >= len(self._file_paths):
            return False

        path = self._file_paths[self._current_index]
        logger.info(
            f"Opening file {self._current_index + 1}/{len(self._file_paths)}: {path}"
        )

        # Create config for this specific file
        config = AudioSourceConfig(
            source_type=SourceType.FILE,
            sample_rate=self._base_config.sample_rate,
            channels=self._base_config.channels,
            chunk_size=self._base_config.chunk_size,
            playback_mode=self._playback_mode,
            file_path=path,
            loop=False,
        )

        self._current_source = FileSource(config)
        self._current_source.open()
        return True

    def start(
        self,
        callback: AudioChunkCallback,
        on_end: Optional[SourceEndCallback] = None,
    ) -> None:
        """Start streaming audio from batch.

        Args:
            callback: Called with each audio chunk
            on_end: Called when all files processed
        """
        self._callback = callback
        self._on_end = on_end
        self._active = True
        self._current_index = 0
        self._files_processed = 0

        # Start first file
        if self._open_next_file():
            self._current_source.start(
                callback=self._on_chunk,
                on_end=self._on_file_end,
            )
        else:
            # Empty batch (shouldn't happen with validation)
            self._active = False
            if self._on_end:
                self._on_end()

    def _on_chunk(self, data: bytes, frame_count: int) -> None:
        """Forward chunk to user callback."""
        if self._callback and self._active:
            self._callback(data, frame_count)

    def _on_file_end(self) -> None:
        """Handle end of current file."""
        if not self._active:
            return

        self._files_processed += 1
        logger.info(
            f"Completed file {self._files_processed}/{len(self._file_paths)}"
        )

        # Close current source
        if self._current_source:
            self._current_source.close()
            self._current_source = None

        # Move to next file
        self._current_index += 1

        if self._open_next_file():
            # Start next file
            self._current_source.start(
                callback=self._on_chunk,
                on_end=self._on_file_end,
            )
        else:
            # All files processed
            logger.info(
                f"Batch complete: processed {self._files_processed} files"
            )
            self._active = False
            if self._on_end:
                self._on_end()

    def stop(self) -> None:
        """Stop streaming."""
        self._active = False
        if self._current_source:
            self._current_source.stop()

    def is_active(self) -> bool:
        """Return True if streaming."""
        return self._active

    def is_finite(self) -> bool:
        """Batch source is finite."""
        return True
