"""Directory audio source for batch processing with glob patterns (v0.3.10)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from dictacode_stt.audio.source import (
    AudioChunkCallback,
    AudioSource,
    AudioSourceConfig,
    PlaybackMode,
    SourceEndCallback,
    SourceType,
)
from dictacode_stt.audio.sources.batch import BatchFileSource


logger = logging.getLogger(__name__)


class DirectorySource(AudioSource):
    """Process audio files matching a glob pattern in a directory.

    Discovers files at open() time and delegates to BatchFileSource.
    """

    def __init__(
        self,
        directory: Path,
        pattern: str = "*.wav",
        config: AudioSourceConfig = None,
        playback_mode: PlaybackMode = PlaybackMode.FAST,
        recursive: bool = False,
    ):
        """Initialize directory source.

        Args:
            directory: Directory to search for audio files
            pattern: Glob pattern to match files (default: "*.wav")
            config: Base configuration (applied to each file)
            playback_mode: FAST for testing, REALTIME for simulation
            recursive: If True, search subdirectories (uses **/pattern)
        """
        self._directory = Path(directory)
        self._pattern = pattern
        self._recursive = recursive
        self._playback_mode = playback_mode
        self._base_config = config or AudioSourceConfig(
            source_type=SourceType.FILE,
            playback_mode=playback_mode,
        )
        self._batch_source: Optional[BatchFileSource] = None
        self._discovered_files: List[Path] = []

    @classmethod
    def from_path(
        cls,
        directory: str,
        pattern: str = "*.wav",
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        playback_mode: PlaybackMode = PlaybackMode.FAST,
        recursive: bool = False,
    ) -> "DirectorySource":
        """Create DirectorySource from path string.

        Args:
            directory: Directory path
            pattern: Glob pattern (default: "*.wav")
            sample_rate: Target sample rate
            channels: Target channel count
            chunk_size: Samples per chunk
            playback_mode: Playback mode
            recursive: Search subdirectories

        Returns:
            Configured DirectorySource
        """
        config = AudioSourceConfig(
            source_type=SourceType.FILE,
            sample_rate=sample_rate,
            channels=channels,
            chunk_size=chunk_size,
            playback_mode=playback_mode,
        )
        return cls(
            directory=Path(directory),
            pattern=pattern,
            config=config,
            playback_mode=playback_mode,
            recursive=recursive,
        )

    def get_type(self) -> SourceType:
        """Return source type."""
        return SourceType.FILE

    def get_config(self) -> AudioSourceConfig:
        """Return source configuration."""
        return self._base_config

    def get_discovered_files(self) -> List[Path]:
        """Return list of discovered files (after open())."""
        return self._discovered_files.copy()

    def get_file_count(self) -> int:
        """Return number of files discovered."""
        return len(self._discovered_files)

    def open(self) -> None:
        """Discover files and validate directory exists."""
        if not self._directory.exists():
            raise FileNotFoundError(f"Directory not found: {self._directory}")
        if not self._directory.is_dir():
            raise ValueError(f"Not a directory: {self._directory}")

        # Discover files
        if self._recursive:
            glob_pattern = f"**/{self._pattern}"
        else:
            glob_pattern = self._pattern

        self._discovered_files = sorted(self._directory.glob(glob_pattern))

        if not self._discovered_files:
            raise FileNotFoundError(
                f"No files matching '{self._pattern}' in {self._directory}"
            )

        logger.info(
            f"Discovered {len(self._discovered_files)} files "
            f"matching '{self._pattern}' in {self._directory}"
        )

        # Create batch source
        self._batch_source = BatchFileSource(
            file_paths=self._discovered_files,
            config=self._base_config,
            playback_mode=self._playback_mode,
        )
        self._batch_source.open()

    def close(self) -> None:
        """Close batch source."""
        if self._batch_source:
            self._batch_source.close()
            self._batch_source = None

    def start(
        self,
        callback: AudioChunkCallback,
        on_end: Optional[SourceEndCallback] = None,
    ) -> None:
        """Start streaming audio from discovered files.

        Args:
            callback: Called with each audio chunk
            on_end: Called when all files processed
        """
        if not self._batch_source:
            raise RuntimeError("DirectorySource not opened")
        self._batch_source.start(callback=callback, on_end=on_end)

    def stop(self) -> None:
        """Stop streaming."""
        if self._batch_source:
            self._batch_source.stop()

    def is_active(self) -> bool:
        """Return True if streaming."""
        return self._batch_source.is_active() if self._batch_source else False

    def is_finite(self) -> bool:
        """Directory source is finite."""
        return True

    def get_files_processed(self) -> int:
        """Return number of files processed so far."""
        return self._batch_source.get_files_processed() if self._batch_source else 0

    def get_current_file(self) -> Optional[Path]:
        """Return path of file currently being processed."""
        return self._batch_source.get_current_file() if self._batch_source else None
