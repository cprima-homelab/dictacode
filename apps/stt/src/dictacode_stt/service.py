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
from pathlib import Path
from typing import Optional, Dict

from dictacode_stt.protocol import (
    ProtocolAdapter,
    get_protocol,
    TextMessage,
    CommandMessage,
)
from dictacode_stt.state import DeviceMode, SttState
from dictacode_stt.transport import UartTransport, TransportError
from dictacode_stt.supervisor import LinkSupervisor

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
        whisper_binary: Optional[Path] = None,
        whisper_model: Optional[Path] = None,
        device_index: int = 0,
        native_sample_rate: int = 48000,
        native_channels: int = 2,
        whisper_sample_rate: int = 16000,
        recording_duration: float = 5.0,
        language: str = "en",
        initial_mode: DeviceMode = DeviceMode.LISTENING,
        dry_run: bool = False,
        supervisor_timeout: float = 30.0,
        supervisor_ping_interval: float = 5.0,
        supervisor_enabled: bool = True,
    ):
        """
        Initialize STT service.

        Args:
            uart_device: UART device path
            baud_rate: UART baud rate
            protocol_name: Protocol to use (json or msgpack)
            whisper_binary: Path to whisper-cli (default: ~/whisper.cpp/build/bin/whisper-cli)
            whisper_model: Path to whisper model (default: ~/whisper.cpp/models/ggml-tiny.bin)
            device_index: Audio device index
            native_sample_rate: Microphone native sample rate
            native_channels: Microphone channels
            whisper_sample_rate: Whisper required sample rate (16000)
            recording_duration: Recording duration in seconds
            language: Transcription language
            initial_mode: Initial device mode
            dry_run: If True, don't send to UART (for testing)
            supervisor_timeout: Link timeout in seconds (default: 30)
            supervisor_ping_interval: Ping interval in seconds (default: 5)
            supervisor_enabled: Enable supervisor (default: True)
        """
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

        # Whisper paths
        if whisper_binary is None:
            whisper_binary = Path.home() / "whisper.cpp/build/bin/whisper-cli"
        if whisper_model is None:
            whisper_model = Path.home() / "whisper.cpp/models/ggml-tiny.bin"

        self.whisper_binary = whisper_binary
        self.whisper_model = whisper_model

        # Initialize layers
        self.protocol: ProtocolAdapter = get_protocol(protocol_name)
        self.state: SttState = SttState(mode=initial_mode)
        self.uart: Optional[UartTransport] = None

        # Initialize supervisor (Layer 5)
        self.supervisor: LinkSupervisor = LinkSupervisor(
            timeout=supervisor_timeout,
            ping_interval=supervisor_ping_interval,
        )

        logger.info(
            f"STT service initialized: uart={uart_device}, protocol={protocol_name}, "
            f"mode={initial_mode.name}, language={language}, duration={recording_duration}s"
        )
        if supervisor_enabled:
            logger.info(
                f"Supervisor enabled: timeout={supervisor_timeout}s, "
                f"ping_interval={supervisor_ping_interval}s"
            )

    def start(self) -> None:
        """Open UART transport."""
        if not self.dry_run:
            self.uart = UartTransport(self.uart_device, self.baud_rate)
            self.uart.open()
            logger.info(f"UART opened: {self.uart_device}")
        else:
            logger.info("DRY RUN mode - UART not opened")

    def stop(self) -> None:
        """Close UART transport."""
        if self.uart:
            self.uart.close()
            logger.info("UART closed")

    def check_prerequisites(self) -> bool:
        """
        Check if Whisper binary and model exist.

        Returns:
            True if prerequisites are met, False otherwise
        """
        if not self.whisper_binary.exists():
            logger.error(f"Whisper binary not found: {self.whisper_binary}")
            return False

        if not self.whisper_model.exists():
            logger.error(f"Whisper model not found: {self.whisper_model}")
            return False

        return True

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

    def save_wav(self, audio_bytes: bytes, path: str) -> None:
        """Save 16kHz mono audio bytes to WAV file."""
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)  # mono
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.whisper_sample_rate)
            wf.writeframes(audio_bytes)

    def transcribe(self, wav_path: str) -> str:
        """
        Transcribe WAV file using whisper-cli.

        Args:
            wav_path: Path to WAV file

        Returns:
            Transcribed text (empty string on failure)
        """
        cmd = [
            str(self.whisper_binary),
            "-m", str(self.whisper_model),
            "-f", wav_path,
            "--language", self.language,
            "--no-timestamps",
        ]

        logger.info("Transcribing...")
        start = time.perf_counter()

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
        except subprocess.TimeoutExpired:
            logger.error("Transcription timed out")
            return ""
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

        elapsed = time.perf_counter() - start
        logger.info(f"Transcribed in {elapsed:.2f}s")

        if result.returncode != 0:
            logger.error(f"Whisper failed: {result.stderr}")
            return ""

        # Parse output
        lines = result.stdout.strip().split("\n")
        text_parts = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Remove timestamp brackets if present
            if line.startswith("["):
                bracket_end = line.find("]")
                if bracket_end != -1:
                    text = line[bracket_end + 1:].strip()
                    if text:
                        text_parts.append(text)
            else:
                text_parts.append(line)

        return " ".join(text_parts)

    def send_text(self, text: str) -> bool:
        """
        Send text over UART.

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
            return True

        try:
            self.uart.write(encoded)
            logger.info(f"Sent {len(encoded)} bytes: {text}")
            # Supervisor: mark activity on successful send
            if self.supervisor_enabled:
                self.supervisor.mark_activity()
            return True
        except TransportError as e:
            logger.error(f"UART write failed: {e}")
            if self.supervisor_enabled:
                self.supervisor._mark_unhealthy()
            return False

    def send_command(self, cmd: str, arg: Optional[str] = None) -> bool:
        """
        Send command over UART.

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
            self.uart.write(encoded)
            arg_str = f" {arg}" if arg else ""
            logger.info(f"Sent command: {cmd}{arg_str}")
            # Supervisor: mark activity on successful send
            if self.supervisor_enabled:
                self.supervisor.mark_activity()
            return True
        except TransportError as e:
            logger.error(f"UART write failed: {e}")
            if self.supervisor_enabled:
                self.supervisor._mark_unhealthy()
            return False

    def _reconnect(self) -> bool:
        """
        Attempt to reconnect UART transport.

        Returns:
            True if reconnection successful, False otherwise
        """
        self.supervisor.on_reconnect_attempt()

        try:
            # Close existing transport
            if self.uart:
                try:
                    self.uart.close()
                except Exception:
                    pass  # Ignore close errors

            # Reopen transport
            self.uart = UartTransport(self.uart_device, self.baud_rate)
            self.uart.open()

            # Success
            self.supervisor.on_reconnect_success()
            logger.info(f"UART reconnected: {self.uart_device}")
            return True

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False

    def run_once(self) -> Dict[str, any]:
        """
        Run single pipeline iteration.

        Returns:
            Dictionary with timing stats and results
        """
        stats = {}
        total_start = time.perf_counter()

        # Record
        try:
            record_start = time.perf_counter()
            audio_bytes = self.record_audio()
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
        Run continuous pipeline loop with supervisor health checks.

        Blocks until KeyboardInterrupt.
        """
        logger.info("Running continuous pipeline (Ctrl+C to stop)...")

        iteration = 0
        try:
            while True:
                # Supervisor: check health and handle reconnection
                if self.supervisor_enabled and not self.dry_run:
                    if not self.supervisor.check_health():
                        logger.warning("Link unhealthy, attempting reconnection...")
                        if not self._reconnect():
                            # Reconnection failed, wait and retry
                            delay = self.supervisor.reconnect_delay()
                            logger.info(f"Waiting {delay:.1f}s before retry...")
                            time.sleep(delay)
                            continue

                    # Supervisor: notify systemd watchdog
                    self.supervisor.notify_watchdog()

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

                time.sleep(0.5)  # Brief pause between iterations

        except KeyboardInterrupt:
            logger.info("Interrupted")
