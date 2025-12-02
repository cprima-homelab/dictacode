"""Audio port abstraction - hardware interface layer."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional

import sounddevice as sd


logger = logging.getLogger(__name__)

# Callback type aliases
AudioDataCallback = Callable[[bytes], None]  # on_data(chunk)
AudioErrorCallback = Callable[[Exception], None]  # on_error(err)


@dataclass
class AudioPortCapabilities:
    """Hardware capabilities of an audio port."""

    sample_rates: List[int]  # [44100, 48000, 96000]
    channels: int  # max input channels
    formats: List[str]  # ["int16", "float32"]
    native_rate: int  # default/optimal rate

    @classmethod
    def from_device_info(cls, device_info: dict) -> "AudioPortCapabilities":
        """Create capabilities from sounddevice device info."""
        # sounddevice provides default sample rate
        native_rate = int(device_info.get("default_samplerate", 48000))

        # Common sample rates to test
        test_rates = [16000, 22050, 44100, 48000, 96000]
        supported_rates = []

        for rate in test_rates:
            try:
                sd.check_input_settings(
                    device=device_info["index"],
                    channels=1,
                    samplerate=rate,
                )
                supported_rates.append(rate)
            except Exception:
                pass

        # If no rates found, use native rate as fallback
        if not supported_rates:
            supported_rates = [native_rate]

        return cls(
            sample_rates=supported_rates,
            channels=device_info.get("max_input_channels", 1),
            formats=["int16", "float32"],  # sounddevice supports both
            native_rate=native_rate,
        )


class PortStatus(Enum):
    """Status of an audio port."""

    AVAILABLE = "available"
    IN_USE = "in_use"
    ERROR = "error"
    DISCONNECTED = "disconnected"


@dataclass
class AudioPort:
    """Abstraction of a physical audio input port.

    Provides driver-like interface for audio hardware.
    """

    port_id: str  # Stable identifier (serial/name preferred)
    port_type: str  # "usb" | "jack" | "alsa"
    name: str  # Human-readable name
    capabilities: AudioPortCapabilities
    status: PortStatus
    device_index: int  # sounddevice device index

    # Internal state
    _stream: Optional[sd.InputStream] = None
    _on_data_callback: Optional[AudioDataCallback] = None
    _on_error_callback: Optional[AudioErrorCallback] = None

    def open(self) -> None:
        """Open the audio port for use."""
        if self.status == PortStatus.IN_USE:
            logger.warning(f"Port {self.port_id} already open")
            return

        self.status = PortStatus.IN_USE
        logger.info(f"Opened port {self.port_id}")

    def close(self) -> None:
        """Close the audio port."""
        if self._stream is not None:
            self.stop_stream()

        self.status = PortStatus.AVAILABLE
        logger.info(f"Closed port {self.port_id}")

    def configure(self, sample_rate: int, channels: int) -> None:
        """Configure audio capture parameters.

        Args:
            sample_rate: Desired sample rate (must be in capabilities.sample_rates)
            channels: Number of channels (1 for mono, 2 for stereo)

        Raises:
            ValueError: If sample rate not supported
        """
        if sample_rate not in self.capabilities.sample_rates:
            raise ValueError(
                f"Sample rate {sample_rate} not supported. "
                f"Available: {self.capabilities.sample_rates}"
            )

        if channels > self.capabilities.channels:
            raise ValueError(
                f"Requested {channels} channels, but port only supports "
                f"{self.capabilities.channels}"
            )

        logger.info(f"Configured port {self.port_id}: {sample_rate}Hz, {channels}ch")

    def start_stream(
        self,
        on_data: AudioDataCallback,
        on_error: AudioErrorCallback,
        sample_rate: int = None,
        channels: int = 1,
        chunk_size: int = 1024,
    ) -> None:
        """Start continuous audio capture with callbacks.

        Args:
            on_data: Callback for audio data chunks
            on_error: Callback for errors
            sample_rate: Sample rate (defaults to native_rate)
            channels: Number of channels (default: 1 for mono)
            chunk_size: Frames per buffer

        """
        if self._stream is not None and self._stream.active:
            logger.warning(f"Stream already active on port {self.port_id}")
            return

        if sample_rate is None:
            sample_rate = self.capabilities.native_rate

        self._on_data_callback = on_data
        self._on_error_callback = on_error

        def _audio_callback(indata, frames, time, status):
            """Internal callback for sounddevice stream."""
            if status:
                if self._on_error_callback:
                    self._on_error_callback(Exception(f"Stream status: {status}"))

            if self._on_data_callback:
                # Convert numpy array to bytes
                audio_bytes = indata.tobytes()
                self._on_data_callback(audio_bytes)

        try:
            self._stream = sd.InputStream(
                device=self.device_index,
                channels=channels,
                samplerate=sample_rate,
                blocksize=chunk_size,
                callback=_audio_callback,
                dtype="int16",
            )
            self._stream.start()
            logger.info(
                f"Started stream on port {self.port_id}: {sample_rate}Hz, {channels}ch"
            )

        except Exception as e:
            logger.error(f"Failed to start stream on port {self.port_id}: {e}")
            if self._on_error_callback:
                self._on_error_callback(e)
            raise

    def stop_stream(self) -> None:
        """Stop audio capture."""
        if self._stream is None:
            return

        try:
            self._stream.stop()
            self._stream.close()
            logger.info(f"Stopped stream on port {self.port_id}")

        except Exception as e:
            logger.error(f"Error stopping stream on port {self.port_id}: {e}")
            if self._on_error_callback:
                self._on_error_callback(e)

        finally:
            self._stream = None
            self._on_data_callback = None
            self._on_error_callback = None

    def is_streaming(self) -> bool:
        """Check if port is actively streaming."""
        return self._stream is not None and self._stream.active

    def is_healthy(self) -> bool:
        """Check if port is in a healthy state."""
        return self.status in (PortStatus.AVAILABLE, PortStatus.IN_USE)
