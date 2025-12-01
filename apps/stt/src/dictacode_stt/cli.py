"""CLI utilities for dictacode STT.

Provides entry points for:
- dictacode-stt-audio: Audio device listing and testing
- dictacode-stt-whisper: Whisper model info and transcription testing
- dictacode-stt-send: Send messages via UART for testing
"""

import argparse
import os
import subprocess
import sys
import wave
from pathlib import Path
from typing import List, Optional

import numpy as np

from .protocol import TextMessage, CommandMessage, JsonProtocol, MsgpackProtocol, get_protocol
from .transport import UartTransport, TransportError


# =============================================================================
# dictacode-stt-audio
# =============================================================================

def cmd_audio_list() -> int:
    """List available audio input devices."""
    try:
        import sounddevice as sd
    except ImportError:
        print("ERROR: sounddevice not installed", file=sys.stderr)
        return 1

    print("Audio Input Devices:")
    print("-" * 60)

    devices = sd.query_devices()
    for i, device in enumerate(devices):
        if device["max_input_channels"] > 0:
            marker = "*" if i == sd.default.device[0] else " "
            print(f"  {marker} [{i}] {device['name']}")
            print(f"        Channels: {device['max_input_channels']}, "
                  f"Sample Rate: {device['default_samplerate']:.0f} Hz")

    print()
    print(f"Default input device: {sd.default.device[0]}")
    return 0


def cmd_audio_test(device: Optional[int], duration: float) -> int:
    """Test audio recording - record and report levels."""
    try:
        import sounddevice as sd
    except ImportError:
        print("ERROR: sounddevice not installed", file=sys.stderr)
        return 1

    sample_rate = 16000
    print(f"Recording {duration} seconds from device {device or 'default'}...")

    try:
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype=np.float32,
            device=device,
        )
        sd.wait()

        # Calculate levels
        max_amplitude = np.max(np.abs(recording))
        rms = np.sqrt(np.mean(recording ** 2))

        print(f"\nRecording complete:")
        print(f"  Duration: {duration} seconds")
        print(f"  Sample rate: {sample_rate} Hz")
        print(f"  Max amplitude: {max_amplitude:.4f}")
        print(f"  RMS level: {rms:.4f}")

        if max_amplitude < 0.01:
            print("\nWARNING: Very low audio levels detected. Check microphone.")
            return 2

        print("\nAudio capture working correctly.")
        return 0

    except Exception as e:
        print(f"ERROR: Audio recording failed: {e}", file=sys.stderr)
        return 1


def cmd_audio_record(device: Optional[int], duration: float, output_file: str) -> int:
    """Record audio to WAV file."""
    try:
        import sounddevice as sd
    except ImportError:
        print("ERROR: sounddevice not installed", file=sys.stderr)
        return 1

    sample_rate = 16000
    print(f"Recording {duration} seconds to {output_file}...")

    try:
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype=np.int16,
            device=device,
        )
        sd.wait()

        # Write WAV file
        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(sample_rate)
            wf.writeframes(recording.tobytes())

        file_size = os.path.getsize(output_file)
        print(f"Saved: {output_file} ({file_size} bytes)")
        return 0

    except Exception as e:
        print(f"ERROR: Recording failed: {e}", file=sys.stderr)
        return 1


def audio_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-audio."""
    parser = argparse.ArgumentParser(
        prog="dictacode-stt-audio",
        description="Audio device utilities for dictacode STT",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list command
    subparsers.add_parser("list", help="List audio input devices")

    # test command
    test_parser = subparsers.add_parser("test", help="Test audio recording")
    test_parser.add_argument(
        "--device", "-d", type=int, help="Audio device index"
    )
    test_parser.add_argument(
        "--duration", "-t", type=float, default=3.0,
        help="Recording duration in seconds (default: 3)"
    )

    # record command
    record_parser = subparsers.add_parser("record", help="Record audio to WAV file")
    record_parser.add_argument("file", help="Output WAV file path")
    record_parser.add_argument(
        "--device", "-d", type=int, help="Audio device index"
    )
    record_parser.add_argument(
        "--duration", "-t", type=float, default=5.0,
        help="Recording duration in seconds (default: 5)"
    )

    parsed = parser.parse_args(args)

    if parsed.command is None:
        parser.print_help()
        return 0
    elif parsed.command == "list":
        return cmd_audio_list()
    elif parsed.command == "test":
        return cmd_audio_test(parsed.device, parsed.duration)
    elif parsed.command == "record":
        return cmd_audio_record(parsed.device, parsed.duration, parsed.file)
    else:
        parser.print_help()
        return 1


# =============================================================================
# dictacode-stt-whisper
# =============================================================================

def _find_whisper_binary() -> Optional[Path]:
    """Find whisper-cli binary in common locations."""
    common_paths = [
        Path.home() / "whisper.cpp" / "build" / "bin" / "whisper-cli",
        Path.home() / "whisper.cpp" / "main",
        Path("/usr/local/bin/whisper-cli"),
        Path("/usr/bin/whisper-cli"),
    ]
    for path in common_paths:
        if path.exists() and os.access(path, os.X_OK):
            return path
    return None


def _find_whisper_model() -> Optional[Path]:
    """Find whisper model in common locations."""
    common_paths = [
        Path.home() / "whisper.cpp" / "models" / "ggml-tiny.en.bin",
        Path.home() / "whisper.cpp" / "models" / "ggml-base.en.bin",
        Path.home() / "whisper.cpp" / "models" / "ggml-tiny.bin",
        Path("/usr/share/whisper/models/ggml-tiny.en.bin"),
    ]
    for path in common_paths:
        if path.exists():
            return path
    return None


def cmd_whisper_info(binary: Optional[Path], model: Optional[Path]) -> int:
    """Show whisper binary and model info."""
    binary = binary or _find_whisper_binary()
    model = model or _find_whisper_model()

    print("Whisper Configuration:")
    print("-" * 60)

    if binary:
        size = binary.stat().st_size
        print(f"  Binary: {binary}")
        print(f"          Size: {size:,} bytes")
        print(f"          Executable: {os.access(binary, os.X_OK)}")
    else:
        print("  Binary: NOT FOUND")

    print()

    if model:
        size = model.stat().st_size
        size_mb = size / (1024 * 1024)
        print(f"  Model: {model}")
        print(f"         Size: {size_mb:.1f} MB ({size:,} bytes)")
    else:
        print("  Model: NOT FOUND")

    if not binary or not model:
        return 1
    return 0


def cmd_whisper_check(binary: Optional[Path], model: Optional[Path]) -> int:
    """Check if whisper binary and model exist."""
    binary = binary or _find_whisper_binary()
    model = model or _find_whisper_model()

    errors = []
    if not binary:
        errors.append("Whisper binary not found")
    elif not os.access(binary, os.X_OK):
        errors.append(f"Whisper binary not executable: {binary}")

    if not model:
        errors.append("Whisper model not found")

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print("OK: Whisper binary and model found")
    return 0


def cmd_whisper_test(
    file: str,
    binary: Optional[Path],
    model: Optional[Path],
) -> int:
    """Test transcription on a WAV file."""
    binary = binary or _find_whisper_binary()
    model = model or _find_whisper_model()

    if not binary:
        print("ERROR: Whisper binary not found", file=sys.stderr)
        return 1
    if not model:
        print("ERROR: Whisper model not found", file=sys.stderr)
        return 1
    if not os.path.exists(file):
        print(f"ERROR: File not found: {file}", file=sys.stderr)
        return 1

    print(f"Transcribing: {file}")
    print(f"Using model: {model.name}")
    print("-" * 60)

    try:
        result = subprocess.run(
            [
                str(binary),
                "-m", str(model),
                "-f", file,
                "--no-timestamps",
                "-l", "en",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            print(f"ERROR: Whisper failed: {result.stderr}", file=sys.stderr)
            return 1

        # Extract transcription (whisper outputs to stdout)
        transcription = result.stdout.strip()
        print(f"Transcription:\n{transcription}")
        return 0

    except subprocess.TimeoutExpired:
        print("ERROR: Whisper timed out", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def whisper_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-whisper."""
    parser = argparse.ArgumentParser(
        prog="dictacode-stt-whisper",
        description="Whisper utilities for dictacode STT",
    )
    parser.add_argument(
        "--binary", "-b", type=Path,
        help="Path to whisper-cli binary",
    )
    parser.add_argument(
        "--model", "-m", type=Path,
        help="Path to whisper model file",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # info command
    subparsers.add_parser("info", help="Show whisper binary and model info")

    # check command
    subparsers.add_parser("check", help="Check if whisper binary and model exist")

    # test command
    test_parser = subparsers.add_parser("test", help="Test transcription on a WAV file")
    test_parser.add_argument("file", help="WAV file to transcribe")

    parsed = parser.parse_args(args)

    if parsed.command is None:
        parser.print_help()
        return 0
    elif parsed.command == "info":
        return cmd_whisper_info(parsed.binary, parsed.model)
    elif parsed.command == "check":
        return cmd_whisper_check(parsed.binary, parsed.model)
    elif parsed.command == "test":
        return cmd_whisper_test(parsed.file, parsed.binary, parsed.model)
    else:
        parser.print_help()
        return 1


# =============================================================================
# dictacode-stt-send
# =============================================================================

def send_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-send."""
    parser = argparse.ArgumentParser(
        prog="dictacode-stt-send",
        description="Send messages via UART for testing",
        epilog="""
Examples:
  dictacode-stt-send "hello world"           # Send text message
  dictacode-stt-send --cmd pause             # Send pause command
  dictacode-stt-send --cmd keymap de_de      # Send keymap command with arg
  dictacode-stt-send --protocol msgpack "hi" # Use msgpack protocol
  dictacode-stt-send --dry-run "test"        # Show encoded bytes only
        """,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "text",
        nargs="?",
        help="Text to send (for text messages)",
    )
    parser.add_argument(
        "--cmd", "-c",
        metavar="COMMAND",
        help="Send command message instead of text",
    )
    parser.add_argument(
        "--arg", "-a",
        metavar="ARGUMENT",
        help="Command argument (used with --cmd)",
    )
    parser.add_argument(
        "--device", "-d",
        default="/dev/serial0",
        help="UART device (default: /dev/serial0)",
    )
    parser.add_argument(
        "--protocol", "-p",
        choices=["json", "msgpack"],
        default="json",
        help="Protocol to use (default: json)",
    )
    parser.add_argument(
        "--dry-run", "-n",
        action="store_true",
        help="Show encoded bytes without sending",
    )

    parsed = parser.parse_args(args)

    # Validate arguments
    if parsed.cmd and parsed.text:
        print("ERROR: Cannot specify both text and --cmd", file=sys.stderr)
        return 1
    if not parsed.cmd and not parsed.text:
        print("ERROR: Must specify text or --cmd", file=sys.stderr)
        parser.print_help()
        return 1
    if parsed.arg and not parsed.cmd:
        print("ERROR: --arg requires --cmd", file=sys.stderr)
        return 1

    # Create message
    if parsed.cmd:
        msg = CommandMessage(command=parsed.cmd, argument=parsed.arg)
        print(f"Command: {parsed.cmd}" + (f" {parsed.arg}" if parsed.arg else ""))
    else:
        msg = TextMessage(payload=parsed.text)
        print(f"Text: {parsed.text}")

    # Encode
    protocol = get_protocol(parsed.protocol)
    encoded = protocol.encode(msg)
    print(f"Protocol: {parsed.protocol}")
    print(f"Encoded: {encoded!r} ({len(encoded)} bytes)")

    if parsed.dry_run:
        print("\n(dry-run: not sending)")
        return 0

    # Send via UART
    try:
        transport = UartTransport(parsed.device)
        transport.open()
        try:
            transport.write(encoded)
            print(f"\nSent to {parsed.device}")
            return 0
        finally:
            transport.close()
    except TransportError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


# =============================================================================
# Main entry points
# =============================================================================

if __name__ == "__main__":
    # Default to showing help
    print("Use one of the CLI commands:")
    print("  dictacode-stt-audio")
    print("  dictacode-stt-whisper")
    print("  dictacode-stt-send")
    sys.exit(0)
