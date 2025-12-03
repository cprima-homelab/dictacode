"""Microphone audio source for live capture (v0.3.10)."""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Optional

import numpy as np
import sounddevice as sd

from dictacode_stt.audio.source import (
    AudioChunkCallback,
    AudioSource,
    AudioSourceConfig,
    SourceEndCallback,
    SourceType,
)

if TYPE_CHECKING:
    from dictacode_stt.audio.manager import AudioPortManager
    from dictacode_stt.audio.port import AudioPort


logger = logging.getLogger(__name__)


class MicrophoneSource(AudioSource):
    """Live microphone capture source."""

    def __init__(
        self,
        config: AudioSourceConfig,
        port_manager: Optional[AudioPortManager] = None,
        port_id: str = "auto",
    ):
        """Initialize microphone source.

        Args:
            config: Source configuration
            port_manager: AudioPortManager for device selection
            port_id: Port ID or "auto" for default device
        """
        self.config = config
        self._port_manager = port_manager
        self._port_id = port_id
        self._port: Optional[AudioPort] = None
        self._stream: Optional[sd.InputStream] = None
        self._active = False
        self._callback: Optional[AudioChunkCallback] = None
        self._on_end: Optional[SourceEndCallback] = None
        self._device_index: Optional[int] = None

    def get_type(self) -> SourceType:
        """Return source type."""
        return SourceType.MICROPHONE

    def get_config(self) -> AudioSourceConfig:
        """Return source configuration."""
        return self.config

    def open(self) -> None:
        """Open microphone device."""
        # Resolve device
        if self._port_manager:
            if self._port_id == "auto":
                self._port = self._port_manager.get_default_port()
            else:
                self._port = self._port_manager.get_port(self._port_id)

            if self._port:
                self._device_index = self._port.device_index
                logger.info(
                    f"Opened microphone: {self._port.port_id} "
                    f"(device {self._device_index})"
                )
            else:
                logger.warning(f"Port not found: {self._port_id}, using default")
                self._device_index = None
        else:
            # No port manager - use default device
            self._device_index = None
            logger.info("Using default microphone (no port manager)")

    def close(self) -> None:
        """Close microphone device."""
        self.stop()
        self._port = None
        self._device_index = None

    def start(
        self,
        callback: AudioChunkCallback,
        on_end: Optional[SourceEndCallback] = None,
    ) -> None:
        """Start streaming audio from microphone.

        Args:
            callback: Called with each audio chunk
            on_end: Not used for microphone (never ends)
        """
        if self._active:
            logger.warning("Microphone already active")
            return

        self._callback = callback
        self._on_end = on_end
        self._active = True

        # Create sounddevice InputStream
        try:
            self._stream = sd.InputStream(
                device=self._device_index,
                channels=self.config.channels,
                samplerate=self.config.sample_rate,
                blocksize=self.config.chunk_size,
                dtype=np.int16,
                callback=self._audio_callback,
            )
            self._stream.start()
            logger.info(
                f"Started microphone capture: {self.config.sample_rate}Hz, "
                f"{self.config.channels}ch, {self.config.chunk_size} samples/chunk"
            )
        except Exception as e:
            self._active = False
            logger.error(f"Failed to start microphone: {e}")
            raise

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Sounddevice callback - delivers audio chunks."""
        if status:
            logger.warning(f"Audio callback status: {status}")

        if self._callback and self._active:
            # Convert to bytes for consistency with other sources
            data = indata.tobytes()
            self._callback(data, frames)

    def stop(self) -> None:
        """Stop streaming."""
        self._active = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"Error stopping stream: {e}")
            self._stream = None
        logger.info("Stopped microphone capture")

    def is_active(self) -> bool:
        """Return True if streaming."""
        return self._active

    def is_finite(self) -> bool:
        """Microphone never ends (continuous source)."""
        return False
