"""
service.py - Layer 4: STT service orchestrating audio, transcription, and UART.

Coordinates the full pipeline: mic → recording → transcription → protocol → UART transport.

Usage:
    service = SttService(
        uart_device="/dev/serial0",
        protocol="json",
    )
    service.run_continuous()  # Runs until interrupted
"""

import logging
import subprocess
import sys
import tempfile
import time
import wave
import asyncio
from pathlib import Path
from typing import Optional, Dict

try:
    from systemd import daemon as sd_daemon
    HAS_SYSTEMD = True
except ImportError:
    HAS_SYSTEMD = False

from dictacode_stt import __version__
from dictacode_stt.protocol import (
    ProtocolAdapter,
    get_protocol,
    TextMessage,
    CommandMessage,
    ProbeMessage,
    ProbeAckMessage,
)
from dictacode_stt.compatibility import CompatibilityChecker
from dictacode_stt.state import SolutionState, SttState
from dictacode_stt.transport import (
    TransportAdapter,
    TransportError,
    UartTransport,
    create_transport,
)
from dictacode_stt.supervisor import LinkSupervisor, SupervisorConfig
from dictacode_stt.hid import HidDeviceRegistry, HidDevice
from dictacode_stt.audio import (
    AudioPortManager,
    AudioPort,
    AudioRingBuffer,
    Resampler,
)
from dictacode_stt.audio.source import AudioSource
from dictacode_stt.transcription import (
    TranscriptionAdapter,
    get_transcriber,
    PartialResult,
    FinalResult,
)

logger = logging.getLogger(__name__)


class SttService:
    """
    STT service - Layer 4: Application logic.

    Responsibilities:
    - Record audio from microphone
    - Transcode audio for Whisper
    - Invoke transcription
    - Send transcribed text over UART
    - Manage state and modes
    """

    def __init__(
        self,
        uart_device: str = "/dev/serial0",
        baud_rate: int = 115200,
        protocol_name: str = "json",
        transcriber: Optional[TranscriptionAdapter] = None,
        transcriber_name: str = "whisper",
        whisper_binary: Optional[Path] = None,
        whisper_model: Optional[Path] = None,
        device_index: int = 0,
        native_sample_rate: int = 48000,
        native_channels: int = 2,
        whisper_sample_rate: int = 16000,
        recording_duration: float = 5.0,
        language: str = "en",
        streaming: bool = False,
        dry_run: bool = False,
        supervisor_timeout: float = 30.0,
        supervisor_ping_interval: float = 5.0,
        supervisor_enabled: bool = True,
        prerequisite_poll_interval: float = 30.0,
        link_poll_interval: float = 5.0,
        handshake_timeout: float = 10.0,
        transport_type: Optional[str] = None,
        hid_device_id: Optional[str] = None,
        hid_registry: Optional[HidDeviceRegistry] = None,
        audio_source: Optional[AudioSource] = None,
        websocket_manager: Optional[any] = None,
    ):
        """
        Initialize STT service.

        Args:
            uart_device: UART device path (legacy, used if transport_type=None)
            baud_rate: UART baud rate (legacy)
            protocol_name: Protocol to use (json or msgpack)
            transcriber: Transcription adapter instance (v0.2.6, default: None = auto-create)
            transcriber_name: Transcriber name for factory (default: "whisper")
            whisper_binary: Path to whisper-cli (for backward compatibility, used if transcriber=None)
            whisper_model: Path to whisper model (for backward compatibility, used if transcriber=None)
            device_index: Audio device index
            native_sample_rate: Microphone native sample rate
            native_channels: Microphone channels
            whisper_sample_rate: Whisper required sample rate (16000)
            recording_duration: Recording duration in seconds
            language: Transcription language
            streaming: Enable streaming transcription (v0.2.7, default: False)
            dry_run: If True, don't send to transport (for testing)
            supervisor_timeout: Link timeout in seconds (default: 30)
            supervisor_ping_interval: Ping interval in seconds (default: 5)
            supervisor_enabled: Enable supervisor (default: True)
            prerequisite_poll_interval: Poll interval for prerequisites (default: 30)
            link_poll_interval: Poll interval for transport link (default: 5)
            handshake_timeout: Handshake timeout in seconds (default: 10)
            transport_type: Transport type (v0.2.8: "uart", "usb-serial", "wifi", default: None = auto from registry)
            hid_device_id: HID device ID to use (v0.2.8, default: None = auto-select)
            hid_registry: HID device registry (v0.2.8, default: None = create new)
            audio_source: Audio source for testing (v0.2.11, default: None = use microphone)
            websocket_manager: WebSocket manager for broadcasting updates (v0.3.0, default: None = no broadcast)
        """
        # v0.2.8: HID device registry and selection
        self.hid_registry = hid_registry or HidDeviceRegistry()
        self.hid_device_id = hid_device_id
        self.transport_type = transport_type

        # Legacy parameters (for backward compatibility)
        self.uart_device = uart_device
        self.baud_rate = baud_rate
        self.protocol_name = protocol_name
        self.device_index = device_index
        self.native_sample_rate = native_sample_rate
        self.native_channels = native_channels
        self.whisper_sample_rate = whisper_sample_rate
        self.recording_duration = recording_duration
        self.language = language
        self.dry_run = dry_run
        self.supervisor_enabled = supervisor_enabled
        self.prerequisite_poll_interval = prerequisite_poll_interval
        self.link_poll_interval = link_poll_interval
        self.handshake_timeout = handshake_timeout
        self._shutdown = False

        # Whisper paths (kept for backward compatibility)
        if whisper_binary is None:
            whisper_binary = Path.home() / "whisper.cpp/build/bin/whisper-cli"
        if whisper_model is None:
            whisper_model = Path.home() / "whisper.cpp/models/ggml-tiny.bin"

        self.whisper_binary = whisper_binary
        self.whisper_model = whisper_model

        # v0.2.6: Transcription adapter (strategy pattern)
        if transcriber is None:
            # Auto-create transcriber using factory
            transcriber = get_transcriber(
                transcriber_name,
                binary_path=whisper_binary,
                model_path=whisper_model,
            )
        self.transcriber = transcriber

        # Get audio requirements from transcriber
        audio_reqs = self.transcriber.get_audio_requirements()
        # Override whisper_sample_rate with transcriber requirements
        self.whisper_sample_rate = audio_reqs.sample_rate
        logger.info(
            f"Using transcriber: {self.transcriber.get_name()} "
            f"(requires {audio_reqs.sample_rate}Hz, {audio_reqs.channels}ch)"
        )

        # v0.2.7: Streaming transcription mode
        # Only enable if both requested AND adapter supports it
        self.streaming_mode = streaming and self.transcriber.supports_streaming()
        if streaming and not self.transcriber.supports_streaming():
            logger.warning(
                f"{self.transcriber.get_name()} doesn't support streaming, "
                f"falling back to batch mode"
            )
        if self.streaming_mode:
            logger.info("Streaming transcription mode enabled")

        # Initialize layers
        self.protocol: ProtocolAdapter = get_protocol(protocol_name)
        self.state: SttState = SttState()  # Starts in UNCONFIGURED
        self.transport: Optional[TransportAdapter] = None  # v0.2.8: Generic transport

        # v0.2.8: Selected HID device (resolved during start())
        self.active_hid_device: Optional[HidDevice] = None

        # Initialize supervisor (Layer 5) with config
        supervisor_config = SupervisorConfig(
            whisper_binary=whisper_binary,
            whisper_model=whisper_model,
            uart_device=uart_device,
            timeout=supervisor_timeout,
            ping_interval=supervisor_ping_interval,
        )
        self.supervisor: LinkSupervisor = LinkSupervisor(
            state=self.state,
            config=supervisor_config,
        )

        # v0.2.11: Audio source injection (for testing)
        self.audio_source: Optional[AudioSource] = audio_source
        self._source_mode = audio_source is not None

        # v0.3.0: WebSocket manager for broadcasting updates
        self.websocket_manager = websocket_manager

        # v0.2.4: Audio Port Abstraction (only used when audio_source=None)
        self.audio_manager = AudioPortManager()
        self.audio_port: Optional[AudioPort] = None
        self.audio_buffer: Optional[AudioRingBuffer] = None
        self.resampler: Optional[Resampler] = None
        self._audio_stream_active = False
        self._last_transcription: str = ""  # For overlap deduplication

        # Initialize audio port from device index (skip if using audio source)
        if not self._source_mode:
            try:
                ports = self.audio_manager.list_ports()
                # Find port matching device_index
                for port in ports:
                    if port.device_index == device_index:
                        self.audio_port = port
                        logger.info(
                            f"Audio port selected: {port.port_id} ({port.name}), "
                            f"native_rate={port.capabilities.native_rate}Hz"
                        )

                        # Initialize ring buffer (5 seconds max, 0.5s overlap)
                        self.audio_buffer = AudioRingBuffer(
                            max_seconds=5.0,
                            sample_rate=whisper_sample_rate,
                            overlap_seconds=0.5,
                            dtype="int16",
                        )

                        # Initialize resampler for native → whisper rate
                        self.resampler = Resampler(
                            target_rate=whisper_sample_rate,
                            dtype="int16",
                        )
                        break

                if not self.audio_port:
                    logger.warning(
                        f"Audio port for device {device_index} not found in port manager. "
                        f"Falling back to direct sounddevice access (legacy mode)."
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to initialize audio port abstraction: {e}. "
                    f"Falling back to legacy mode."
                )
        else:
            logger.info(f"Using audio source: {type(audio_source).__name__}")

        logger.info(
            f"STT service initialized: protocol={protocol_name}, "
            f"state={self.state.state.value}, language={language}, duration={recording_duration}s"
        )
        if supervisor_enabled:
            logger.info(
                f"Supervisor enabled: timeout={supervisor_timeout}s, "
                f"ping_interval={supervisor_ping_interval}s"
            )

    def _resolve_hid_device(self) -> Optional[HidDevice]:
        """
        Resolve HID device from registry (v0.2.8).

        Selection logic:
        1. If hid_device_id specified: use that device
        2. Otherwise: use best available device from registry
        3. Fallback: create legacy UART device from uart_device parameter

        Returns:
            HidDevice if found/created, None otherwise
        """
        # Load devices from config
        try:
            self.hid_registry.load_devices()
        except Exception as e:
            logger.warning(f"Failed to load HID device registry: {e}")

        # If specific device requested
        if self.hid_device_id:
            device = self.hid_registry.get_device(self.hid_device_id)
            if device:
                logger.info(f"Selected HID device: {device.device_id} ({device.name})")
                return device
            else:
                logger.error(f"Requested HID device not found: {self.hid_device_id}")
                return None

        # If transport type specified, filter by transport
        if self.transport_type:
            devices = [
                d for d in self.hid_registry.list_devices()
                if d.transport == self.transport_type
            ]
            if devices:
                # Use highest priority device of specified transport type
                device = min(devices, key=lambda d: d.priority)
                logger.info(
                    f"Selected {self.transport_type} device: "
                    f"{device.device_id} ({device.name})"
                )
                return device
            else:
                logger.warning(
                    f"No {self.transport_type} devices found in registry"
                )

        # Auto-select best available device
        if self.hid_registry.has_devices():
            device = self.hid_registry.find_best_available_device()
            if device:
                logger.info(
                    f"Auto-selected HID device: {device.device_id} ({device.name})"
                )
                return device
            else:
                logger.warning("No available devices in registry")

        # Fallback: Create legacy UART device from parameters
        logger.info(
            f"No devices in registry, using legacy UART config: {self.uart_device}"
        )
        from dictacode_stt.hid import HidDevice, HidDeviceStatus

        return HidDevice(
            device_id="legacy-uart",
            name=f"Legacy UART ({self.uart_device})",
            transport="uart",
            address=self.uart_device,
            priority=100,
            status=HidDeviceStatus.UNKNOWN,
            metadata={"baud_rate": self.baud_rate},
        )

    def _create_transport(self, device: HidDevice) -> TransportAdapter:
        """
        Create transport adapter from HID device config (v0.2.8).

        Args:
            device: HID device configuration

        Returns:
            TransportAdapter instance

        Raises:
            TransportError: If transport creation fails
        """
        # Get transport kwargs from device
        transport_kwargs = device.get_transport_kwargs()

        # Add baud_rate for UART if not in kwargs
        if device.transport == "uart" and "baud_rate" not in transport_kwargs:
            transport_kwargs["baud_rate"] = device.metadata.get(
                "baud_rate", self.baud_rate
            )

        logger.info(
            f"Creating {device.transport} transport: {device.address}"
        )
        logger.debug(f"Transport kwargs: {transport_kwargs}")

        try:
            transport = create_transport(device.transport, **transport_kwargs)
            logger.info(f"Transport created: {transport.get_name()}")
            return transport
        except Exception as e:
            raise TransportError(f"Failed to create {device.transport} transport: {e}")

    def _on_audio_data(self, audio_data: bytes) -> None:
        """
        Audio streaming callback - called when new audio data is available.

        Args:
            audio_data: Raw audio bytes from device
        """
        if not self.audio_buffer or not self.resampler or not self.audio_port:
            logger.warning("Audio buffer/resampler not initialized, dropping audio data")
            return

        try:
            # Resample from native rate to target rate (16kHz)
            resampled = self.resampler.process(
                audio_data,
                source_rate=self.audio_port.capabilities.native_rate
            )

            # v0.2.7: Feed directly to streaming transcriber if enabled
            if self.streaming_mode:
                self.transcriber.feed_audio(resampled)
            else:
                # Batch mode: Write to ring buffer for later transcription
                self.audio_buffer.write(resampled)

                # Log buffer status occasionally
                duration = self.audio_buffer.get_duration_seconds()
                if int(duration) % 5 == 0 and duration > 0:
                    unread = self.audio_buffer.get_unread_duration_seconds()
                    logger.debug(f"Audio buffer: {duration:.1f}s total, {unread:.1f}s unread")

        except Exception as e:
            logger.error(f"Error processing audio data: {e}", exc_info=True)

    def _on_audio_error(self, error: Exception) -> None:
        """
        Audio streaming error callback.

        Args:
            error: The error that occurred
        """
        logger.error(f"Audio stream error: {error}")
        self._audio_stream_active = False

    def _on_partial_result(self, result: PartialResult) -> None:
        """
        Handle partial transcription result (v0.2.7 streaming).

        Partial results are displayed but not sent to HID.

        Args:
            result: Partial transcription result
        """
        logger.debug(f"Partial: {result.text}")
        # v0.3.0: Broadcast partial results to WebSocket clients
        self._broadcast_websocket({
            "type": "transcription",
            "data": {"text": result.text, "final": False}
        })

    def _on_final_result(self, result: FinalResult) -> None:
        """
        Handle final transcription result (v0.2.7 streaming).

        Final results are sent to HID immediately.

        Args:
            result: Final transcription result
        """
        if result.text:
            logger.info(f"Final: {result.text}")
            self.send_text(result.text)

    def _on_transcription_error(self, error: Exception) -> None:
        """
        Handle transcription error (v0.2.7 streaming).

        Args:
            error: The error that occurred
        """
        logger.error(f"Transcription error: {error}")

    def start_audio_stream(self) -> bool:
        """
        Start continuous audio streaming (v0.2.4 streaming mode).

        Returns:
            True if stream started successfully, False otherwise
        """
        if not self.audio_port or not self.audio_buffer or not self.resampler:
            logger.warning("Audio port abstraction not available, cannot start streaming")
            return False

        if self._audio_stream_active:
            logger.warning("Audio stream already active")
            return True

        try:
            self.audio_port.start_stream(
                on_data=self._on_audio_data,
                on_error=self._on_audio_error,
                sample_rate=self.audio_port.capabilities.native_rate,
                channels=1,  # Mono
                chunk_size=1024,
            )
            self._audio_stream_active = True
            logger.info(
                f"Audio stream started: {self.audio_port.port_id} "
                f"@ {self.audio_port.capabilities.native_rate}Hz"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}", exc_info=True)
            return False

    def stop_audio_stream(self) -> None:
        """Stop continuous audio streaming."""
        if not self.audio_port or not self._audio_stream_active:
            return

        try:
            self.audio_port.stop_stream()
            self._audio_stream_active = False
            logger.info("Audio stream stopped")
        except Exception as e:
            logger.error(f"Error stopping audio stream: {e}", exc_info=True)

    def start(self) -> None:
        """
        Open transport and start streaming transcription if enabled.

        v0.2.8: Uses HID device registry and transport factory.
        """
        if not self.dry_run:
            # v0.2.8: Resolve HID device from registry or parameters
            self.active_hid_device = self._resolve_hid_device()
            if not self.active_hid_device:
                raise TransportError("No HID device available")

            # Create transport from device config
            self.transport = self._create_transport(self.active_hid_device)

            # Connect transport
            if not self.transport.connect():
                raise TransportError(
                    f"Failed to connect {self.active_hid_device.device_id}"
                )

            logger.info(
                f"Transport connected: {self.active_hid_device.device_id} "
                f"({self.active_hid_device.transport}://{self.active_hid_device.address})"
            )

            # Update registry status
            if self.hid_device_id or self.hid_registry.has_devices():
                from dictacode_stt.hid import HidDeviceStatus

                self.hid_registry.update_device_status(
                    self.active_hid_device.device_id, HidDeviceStatus.ACTIVE
                )
        else:
            logger.info("DRY RUN mode - Transport not opened")

        # v0.2.7: Start streaming transcription if enabled
        if self.streaming_mode:
            self.transcriber.start_streaming(
                language=self.language,
                on_partial=self._on_partial_result,
                on_final=self._on_final_result,
                on_error=self._on_transcription_error,
            )
            logger.info("Streaming transcription started")

    def stop(self) -> None:
        """Close transport, stop audio stream, and stop streaming transcription."""
        # v0.2.11: Stop audio source if active
        if self._source_mode and self.audio_source:
            try:
                if self.audio_source.is_active():
                    self.audio_source.stop()
                self.audio_source.close()
                logger.info("Audio source closed")
            except Exception as e:
                logger.error(f"Error closing audio source: {e}")

        # Stop audio stream first
        self.stop_audio_stream()

        # v0.2.7: Stop streaming transcription if enabled
        if self.streaming_mode and self.transcriber.is_streaming():
            try:
                final = self.transcriber.stop_streaming()
                if final and final.text:
                    logger.info(f"Final transcription on stop: {final.text}")
                    self.send_text(final.text)
                logger.info("Streaming transcription stopped")
            except Exception as e:
                logger.error(f"Error stopping streaming transcription: {e}")

        # Close transport
        if self.transport:
            self.transport.disconnect()
            logger.info("Transport closed")

            # Update registry status
            if self.active_hid_device and self.hid_registry.has_devices():
                from dictacode_stt.hid import HidDeviceStatus

                self.hid_registry.update_device_status(
                    self.active_hid_device.device_id, HidDeviceStatus.OFFLINE
                )

    def _sd_notify(self, message: str) -> None:
        """Send notification to systemd."""
        try:
            from systemd.daemon import notify
            notify(message)
        except ImportError:
            pass

    def _perform_handshake(self) -> bool:
        """
        Perform handshake with HID peer with version compatibility checking.

        Returns:
            True if handshake successful, False on timeout or incompatible version
        """
        if not self.transport:
            return False

        # Initialize compatibility checker
        try:
            checker = CompatibilityChecker()
        except FileNotFoundError as e:
            logger.error(f"Compatibility matrix not found: {e}")
            logger.error("Cannot perform version validation - handshake failed")
            return False

        # Send probe message with version info
        probe = ProbeMessage(
            timestamp=time.time(),
            protocol_version=checker.matrix.protocol_version,
            component="stt",
            component_version=__version__,
        )
        encoded = self.protocol.encode(probe)

        try:
            self.transport.send(encoded)
            logger.info(f"Sent probe message (STT v{__version__}, protocol v{checker.matrix.protocol_version})")
        except TransportError as e:
            logger.error(f"Failed to send probe: {e}")
            return False

        # Wait for ProbeAck
        logger.info("Waiting for probe_ack from HID...")
        start = time.time()
        read_attempts = 0
        while time.time() - start < self.handshake_timeout:
            try:
                # Try to read response
                read_attempts += 1
                # Read line-delimited response (most transports support readline)
                if hasattr(self.transport, 'readline'):
                    data = self.transport.readline()
                else:
                    # Fallback: read fixed amount
                    data = self.transport.receive(1024)

                if data:
                    logger.info(f"Received {len(data)} bytes, decoding...")
                    msg = self.protocol.decode(data)
                    if isinstance(msg, ProbeAckMessage):
                        logger.info(
                            f"Received probe_ack from {msg.component} v{msg.component_version} "
                            f"(protocol v{msg.protocol_version})"
                        )

                        # Validate protocol version first (REQUIRED)
                        if msg.protocol_version != checker.matrix.protocol_version:
                            error_msg = (
                                f"PROTOCOL MISMATCH: Expected protocol {checker.matrix.protocol_version}, "
                                f"peer reported {msg.protocol_version}. "
                                "Both sides must use the same protocol version."
                            )
                            logger.error(error_msg)
                            return False

                        # Validate component version compatibility
                        is_compatible, error_msg = checker.validate_compatibility(
                            __version__, msg.component_version
                        )

                        if not is_compatible:
                            logger.error(f"Version incompatibility: {error_msg}")
                            return False

                        logger.info(f"Handshake complete - protocol and versions compatible")
                        return True
                    else:
                        logger.info(f"Received unexpected message type: {type(msg).__name__}")
            except Exception as e:
                # Continue waiting on decode errors
                logger.info(f"Handshake read attempt {read_attempts} error: {e}")
                time.sleep(0.1)

        logger.warning(f"Handshake timeout after {self.handshake_timeout}s ({read_attempts} read attempts)")
        return False

    def record_audio_from_source(self) -> Optional[bytes]:
        """
        Record audio from injected source (v0.2.11).

        Returns:
            16kHz mono audio bytes (suitable for Whisper), or None if source finished

        Raises:
            RuntimeError: If source mode not active
        """
        if not self._source_mode or not self.audio_source:
            raise RuntimeError("record_audio_from_source called without audio source")

        # Collect audio chunks from source
        chunks = []
        total_frames = 0
        target_frames = int(self.whisper_sample_rate * self.recording_duration)

        def on_audio(data: bytes, frames: int) -> None:
            """Collect audio chunks."""
            nonlocal total_frames
            chunks.append(data)
            total_frames += frames

        def on_end() -> None:
            """Source finished - stop collecting."""
            pass

        # Start source if not active
        if not self.audio_source.is_active():
            self.audio_source.open()
            self.audio_source.start(callback=on_audio, on_end=on_end)

        logger.info(f"Reading {self.recording_duration}s from audio source...")
        start = time.perf_counter()

        # Collect chunks until we have enough or source finishes
        while total_frames < target_frames and self.audio_source.is_active():
            time.sleep(0.01)  # Brief sleep to avoid busy waiting

        elapsed = time.perf_counter() - start

        if not chunks:
            logger.warning("No audio data from source")
            return None

        # Concatenate chunks
        audio_bytes = b"".join(chunks)
        duration = total_frames / self.whisper_sample_rate
        logger.info(f"Got {duration:.1f}s from source in {elapsed:.2f}s ({len(audio_bytes)} bytes)")

        return audio_bytes

    def record_audio(self) -> bytes:
        """
        Record audio from microphone.

        Returns:
            16kHz mono audio bytes (suitable for Whisper)

        Raises:
            ImportError: If sounddevice/numpy not installed
            Exception: If recording fails
        """
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            raise ImportError("sounddevice/numpy not installed")

        total_frames = int(self.native_sample_rate * self.recording_duration)

        logger.info(
            f"Recording {self.recording_duration}s at {self.native_sample_rate}Hz "
            f"({self.native_channels} channels)..."
        )
        start = time.perf_counter()

        audio_data = sd.rec(
            total_frames,
            samplerate=self.native_sample_rate,
            channels=self.native_channels,
            dtype="int16",
            device=self.device_index,
        )
        sd.wait()

        elapsed = time.perf_counter() - start
        logger.info(f"Recorded in {elapsed:.2f}s")

        # Convert stereo to mono and downsample
        if self.native_channels > 1:
            mono = audio_data.mean(axis=1).astype(np.int16)
        else:
            mono = audio_data.flatten().astype(np.int16)

        # Downsample (simple decimation)
        downsample_factor = self.native_sample_rate // self.whisper_sample_rate
        resampled = mono[::downsample_factor]

        logger.debug(
            f"Resampled to {self.whisper_sample_rate}Hz mono: {len(resampled)} frames"
        )

        return resampled.tobytes()

    def read_audio_from_buffer(self, min_duration: float = 3.0) -> Optional[bytes]:
        """
        Read audio from ring buffer (v0.2.4 streaming mode).

        Waits for at least min_duration seconds of unread audio, then reads
        with overlap to prevent word cutoff.

        Args:
            min_duration: Minimum duration in seconds to wait for

        Returns:
            16kHz mono audio bytes with overlap, or None if buffer not available
        """
        if not self.audio_buffer:
            logger.warning("Audio buffer not available, falling back to record_audio()")
            return None

        # Wait for enough unread audio
        logger.info(f"Waiting for {min_duration}s of audio in buffer...")
        start_wait = time.perf_counter()
        timeout = min_duration + 10.0  # Add timeout buffer

        while time.perf_counter() - start_wait < timeout:
            unread = self.audio_buffer.get_unread_duration_seconds()
            if unread >= min_duration:
                # Read audio with overlap
                audio_bytes = self.audio_buffer.read_for_transcription()
                if audio_bytes:
                    duration = len(audio_bytes) // 2 // self.whisper_sample_rate
                    logger.info(f"Read {duration:.1f}s from buffer ({len(audio_bytes)} bytes)")
                    return audio_bytes
                else:
                    logger.warning("Buffer returned None despite having unread data")
                    return None

            # Brief sleep to avoid busy waiting
            time.sleep(0.1)

        # Timeout - return what we have
        unread = self.audio_buffer.get_unread_duration_seconds()
        logger.warning(
            f"Buffer timeout after {timeout:.1f}s, only {unread:.1f}s available. "
            f"Reading anyway..."
        )
        return self.audio_buffer.read_for_transcription()

    def _deduplicate_transcription(self, new_text: str) -> str:
        """
        Remove overlapping text from new transcription (v0.2.4 deduplication).

        With overlapping audio segments, transcriptions may contain duplicate text.
        This method detects and removes the overlap.

        Args:
            new_text: New transcription text

        Returns:
            Deduplicated text (overlap removed)
        """
        if not self._last_transcription or not new_text:
            return new_text

        # Normalize whitespace for comparison
        last_words = self._last_transcription.strip().split()
        new_words = new_text.strip().split()

        if not last_words or not new_words:
            return new_text

        # Find longest overlap at end of last_words and start of new_words
        # Try matching from 5 words down to 2 words
        max_overlap = min(len(last_words), len(new_words), 10)  # Cap at 10 words

        for overlap_len in range(max_overlap, 1, -1):
            last_suffix = " ".join(last_words[-overlap_len:])
            new_prefix = " ".join(new_words[:overlap_len])

            if last_suffix.lower() == new_prefix.lower():
                # Found overlap - remove it from new text
                deduplicated_words = new_words[overlap_len:]
                deduplicated = " ".join(deduplicated_words)
                logger.info(
                    f"Deduplication: removed {overlap_len} overlapping words "
                    f"('{new_prefix}')"
                )
                return deduplicated

        # No overlap found
        return new_text

    def save_wav(self, audio_bytes: bytes, path: str) -> None:
        """Save 16kHz mono audio bytes to WAV file."""
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)  # mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.whisper_sample_rate)
            wf.writeframes(audio_bytes)

    def transcribe(self, wav_path: str) -> str:
        """
        Transcribe WAV file using configured transcription adapter.

        Args:
            wav_path: Path to WAV file

        Returns:
            Transcribed text (empty string on failure)
        """
        logger.info("Transcribing...")
        start = time.perf_counter()

        # Use transcription adapter (v0.2.6)
        result = self.transcriber.transcribe(Path(wav_path), language=self.language)

        elapsed = time.perf_counter() - start
        logger.info(f"Transcribed in {elapsed:.2f}s")

        if not result.success:
            logger.error(f"Transcription failed: {result.error}")
            return ""

        return result.text

    def _broadcast_websocket(self, message: dict) -> None:
        """
        Broadcast message to WebSocket clients (v0.3.0).

        Args:
            message: Message dict to broadcast
        """
        if not self.websocket_manager:
            return

        try:
            # Run broadcast in asyncio event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If event loop is running, create task
                asyncio.create_task(self.websocket_manager.broadcast(message))
            else:
                # If no event loop, run synchronously
                loop.run_until_complete(self.websocket_manager.broadcast(message))
        except Exception as e:
            logger.error(f"WebSocket broadcast failed: {e}")

    def send_text(self, text: str) -> bool:
        """
        Send text over transport.

        Args:
            text: Text to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not text:
            logger.warning("Empty text, not sending")
            return False

        msg = TextMessage(payload=text)
        encoded = self.protocol.encode(msg)

        if self.dry_run:
            logger.info(f"Would send {len(encoded)} bytes: {text}")
            if self.supervisor_enabled:
                self.supervisor.mark_activity()
            # v0.3.0: Broadcast transcription to WebSocket clients
            self._broadcast_websocket({
                "type": "transcription",
                "data": {"text": text, "final": True}
            })
            return True

        try:
            self.transport.send(encoded)
            logger.info(f"Sent {len(encoded)} bytes: {text}")
            # Supervisor: mark activity on successful send
            if self.supervisor_enabled:
                self.supervisor.mark_activity()
            # v0.3.0: Broadcast transcription to WebSocket clients
            self._broadcast_websocket({
                "type": "transcription",
                "data": {"text": text, "final": True}
            })
            return True
        except TransportError as e:
            logger.error(f"Transport send failed: {e}")
            if self.supervisor_enabled:
                self.supervisor._mark_unhealthy()
            return False

    def send_command(self, cmd: str, arg: Optional[str] = None) -> bool:
        """
        Send command over transport.

        Args:
            cmd: Command name
            arg: Command argument (optional)

        Returns:
            True if sent successfully, False otherwise
        """
        msg = CommandMessage(command=cmd, argument=arg)
        encoded = self.protocol.encode(msg)

        if self.dry_run:
            logger.info(f"Would send command: {cmd}" + (f" {arg}" if arg else ""))
            if self.supervisor_enabled:
                self.supervisor.mark_activity()
            return True

        try:
            self.transport.send(encoded)
            arg_str = f" {arg}" if arg else ""
            logger.info(f"Sent command: {cmd}{arg_str}")
            # Supervisor: mark activity on successful send
            if self.supervisor_enabled:
                self.supervisor.mark_activity()
            return True
        except TransportError as e:
            logger.error(f"Transport send failed: {e}")
            if self.supervisor_enabled:
                self.supervisor._mark_unhealthy()
            return False

    def pause(self) -> bool:
        """Pause transcription (LISTENING → PAUSED).

        v0.3.0 Phase 3.4: User-initiated pause via API.
        Audio recording continues but transcription is paused.

        Returns:
            True if successfully paused, False if not in LISTENING state
        """
        if self.state.state != SolutionState.LISTENING:
            logger.warning(f"Cannot pause from state {self.state.state.value}")
            return False

        logger.info("Pausing service (user requested)")
        self.state.transition_to(SolutionState.PAUSED)

        # Broadcast state change to WebSocket clients
        from datetime import datetime
        self._broadcast_websocket({
            "type": "state_change",
            "data": {
                "new_state": "paused",
                "old_state": "listening",
                "timestamp": datetime.utcnow().isoformat()
            }
        })

        return True

    def resume(self) -> bool:
        """Resume transcription (PAUSED → LISTENING).

        v0.3.0 Phase 3.4: User-initiated resume via API.
        Resumes normal transcription operation.

        Returns:
            True if successfully resumed, False if not in PAUSED state
        """
        if self.state.state != SolutionState.PAUSED:
            logger.warning(f"Cannot resume from state {self.state.state.value}")
            return False

        logger.info("Resuming service (user requested)")
        self.state.transition_to(SolutionState.LISTENING)

        # Broadcast state change to WebSocket clients
        from datetime import datetime
        self._broadcast_websocket({
            "type": "state_change",
            "data": {
                "new_state": "listening",
                "old_state": "paused",
                "timestamp": datetime.utcnow().isoformat()
            }
        })

        return True

    def get_state(self) -> str:
        """Get current service state as string.

        v0.3.0 Phase 3.4: For API state queries.

        Returns:
            Current state value (e.g., 'listening', 'paused', 'degraded')
        """
        return self.state.state.value

    def _reconnect(self) -> bool:
        """
        Attempt to reconnect transport.

        Returns:
            True if reconnection successful, False otherwise
        """
        self.supervisor.on_reconnect_attempt()

        try:
            # Close existing transport
            if self.transport:
                try:
                    self.transport.disconnect()
                except Exception:
                    pass  # Ignore close errors

            # Recreate transport (uses same device as before)
            if not self.active_hid_device:
                logger.error("No active HID device to reconnect to")
                return False

            self.transport = self._create_transport(self.active_hid_device)

            # Reconnect
            if not self.transport.connect():
                raise TransportError("Failed to connect")

            # Success
            self.supervisor.on_reconnect_success()
            logger.info(
                f"Transport reconnected: {self.active_hid_device.device_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False

    def run_once(self) -> Dict[str, any]:
        """
        Run single pipeline iteration.

        v0.2.4: Uses streaming + ring buffer when available, falls back to blocking record.
        v0.2.11: Supports audio source injection for testing.

        Returns:
            Dictionary with timing stats and results
        """
        stats = {}
        total_start = time.perf_counter()

        # Record audio - prefer audio source, then streaming buffer, then blocking
        try:
            record_start = time.perf_counter()

            if self._source_mode:
                # v0.2.11: Read from injected audio source
                audio_bytes = self.record_audio_from_source()
                stats["mode"] = "source"
            elif self._audio_stream_active and self.audio_buffer:
                # v0.2.4: Read from ring buffer (streaming mode)
                audio_bytes = self.read_audio_from_buffer(min_duration=self.recording_duration)
                stats["mode"] = "streaming"
            else:
                # Legacy: Blocking record
                audio_bytes = self.record_audio()
                stats["mode"] = "blocking"

            if not audio_bytes:
                logger.warning("No audio data received")
                return {"error": "No audio data"}

            stats["record_sec"] = time.perf_counter() - record_start
        except Exception as e:
            logger.error(f"Recording failed: {e}")
            return {"error": str(e)}

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        self.save_wav(audio_bytes, wav_path)

        # Transcribe
        try:
            transcribe_start = time.perf_counter()
            text = self.transcribe(wav_path)
            stats["transcribe_sec"] = time.perf_counter() - transcribe_start
        finally:
            # Clean up temp file
            Path(wav_path).unlink(missing_ok=True)

        # v0.2.4: Deduplicate overlapping transcriptions
        if self._audio_stream_active and text:
            text_before_dedup = text
            text = self._deduplicate_transcription(text)
            if text != text_before_dedup:
                stats["deduplicated"] = True
            self._last_transcription = text_before_dedup  # Store original for next comparison

        stats["text"] = text
        stats["text_len"] = len(text)

        logger.info(f"=== RESULT === {text}")

        # Send over UART
        if text:
            send_start = time.perf_counter()
            self.send_text(text)
            stats["send_sec"] = time.perf_counter() - send_start
        else:
            logger.info("No text to send (empty transcription)")
            stats["send_sec"] = 0

        stats["total_sec"] = time.perf_counter() - total_start

        return stats

    def run_continuous(self) -> None:
        """
        Run continuous state-driven main loop.

        v0.2.3: State machine drives behavior.
        Blocks until KeyboardInterrupt.
        """
        logger.info(f"Starting service in state: {self.state.state.value}")
        self._sd_notify("READY=1")  # Service is UP regardless of state

        iteration = 0
        try:
            while not self._shutdown:
                # Notify systemd of current state
                self._sd_notify(f"STATUS=state={self.state.state.value}")
                self.supervisor.notify_watchdog()

                # State-driven behavior
                if self.state.should_poll_prerequisites():
                    # UNCONFIGURED state: poll for prerequisites
                    if self.supervisor.check_prerequisites():
                        logger.info("Prerequisites detected, transitioning...")
                        self.supervisor.signal_prerequisites_ready()
                    else:
                        logger.debug(
                            f"Prerequisites missing, polling in {self.prerequisite_poll_interval}s"
                        )
                        time.sleep(self.prerequisite_poll_interval)
                    continue

                if self.state.should_poll_link():
                    # LINK_PENDING state: poll for UART
                    if self.supervisor.check_link_available():
                        logger.info("UART device detected, transitioning...")
                        self.supervisor.signal_link_available()
                        # Open UART now
                        if not self.dry_run:
                            try:
                                self.start()
                            except Exception as e:
                                logger.error(f"Failed to open UART: {e}")
                                time.sleep(self.link_poll_interval)
                                continue
                    else:
                        logger.debug(
                            f"UART not available, polling in {self.link_poll_interval}s"
                        )
                        time.sleep(self.link_poll_interval)
                    continue

                if self.state.should_handshake():
                    # HANDSHAKE_INIT state: attempt handshake
                    if self._perform_handshake():
                        logger.info("Handshake successful")
                        self.supervisor.signal_handshake_complete()

                        # v0.2.4: Start audio streaming
                        if self.audio_port and self.audio_buffer:
                            if self.start_audio_stream():
                                logger.info("Audio streaming started")
                            else:
                                logger.warning("Failed to start audio stream, will use blocking mode")

                        # Notify systemd that we're ready
                        if HAS_SYSTEMD:
                            sd_daemon.notify("READY=1")
                            sd_daemon.notify("STATUS=Listening for audio input")
                            logger.info("Notified systemd: READY=1")
                    else:
                        # Timeout - back to link pending
                        logger.warning("Handshake failed, back to LINK_PENDING")
                        self.state.transition_to(SolutionState.LINK_PENDING)
                        self.stop()  # Close UART
                    continue

                # Operational states (LISTENING, MAINTENANCE, DEGRADED)
                if self.state.should_transcribe():
                    iteration += 1
                    logger.info(f"=== ITERATION {iteration} ===")
                    stats = self.run_once()

                    if "error" not in stats:
                        logger.info(
                            f"Timing: record={stats['record_sec']:.2f}s, "
                            f"transcribe={stats['transcribe_sec']:.2f}s, "
                            f"send={stats['send_sec']*1000:.2f}ms, "
                            f"total={stats['total_sec']:.2f}s, "
                            f"len={stats['text_len']}"
                        )

                # Health monitoring in operational states
                if self.state.is_operational() and self.supervisor_enabled:
                    if not self.supervisor.check_health():
                        logger.warning("Link unhealthy, attempting reconnection...")
                        self.supervisor.signal_link_degraded()
                        if not self._reconnect():
                            # Reconnection failed
                            delay = self.supervisor.reconnect_delay()
                            logger.error(f"Reconnection failed, waiting {delay:.1f}s...")
                            time.sleep(delay)
                            self.supervisor.signal_link_lost()
                        else:
                            # Reconnection succeeded - transition back to LISTENING
                            logger.info("Reconnection successful, resuming transcription")
                            self.state.transition_to(SolutionState.LISTENING)

                time.sleep(0.5)  # Brief pause between iterations

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            self._shutdown = True

    def run_diagnostic(self, scope: str = "all") -> None:
        """Run diagnostic checks and log results.

        Only runs in MAINTENANCE state.

        Args:
            scope: "audio", "whisper", "uart", or "all"
        """
        if self.state.state != SolutionState.MAINTENANCE:
            logger.warning("diagnose ignored - not in MAINTENANCE state")
            return

        from dictacode_stt.diagnostics import run_all_checks

        logger.info(f"Running diagnostic: {scope}")
        result = run_all_checks(
            device_index=self.device_index,
            uart_device=self.uart_device,
            whisper_binary=self.whisper_binary,
            whisper_model=self.whisper_model,
        )

        # Log results to journal
        for check in result.checks:
            if check.status.value == "ok":
                logger.info(f"[DIAG OK] {check.name}: {check.message}")
            elif check.status.value == "warn":
                logger.warning(f"[DIAG WARN] {check.name}: {check.message}")
            else:
                logger.error(f"[DIAG FAIL] {check.name}: {check.message}")

        logger.info(
            f"Diagnostic complete: {result.passed} passed, "
            f"{result.failures} failed, {result.warnings} warnings"
        )
