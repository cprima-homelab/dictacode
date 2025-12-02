"""CLI utilities for dictacode STT.

Provides entry points for:
- dictacode-stt-audio: Audio device listing and testing
- dictacode-stt-whisper: Whisper model info and transcription testing
- dictacode-stt-send: Send messages via UART for testing
"""

import argparse
import json
import os
import subprocess
import sys
import wave
from pathlib import Path
from typing import List, Optional

import numpy as np

from .audio import AudioPortManager
from .protocol import (
    CommandMessage,
    TextMessage,
    get_protocol,
)
from .responses import AudioPortsListResponse
from .transport import TransportError, UartTransport


# =============================================================================
# dictacode-stt-audio
# =============================================================================


def cmd_audio_ports(as_json: bool = False) -> int:
    """List audio input ports with stable IDs and capabilities."""
    try:
        manager = AudioPortManager()
        ports = manager.list_ports()

        if as_json:
            # JSON output for programmatic use / web frontend
            response = AudioPortsListResponse.from_audio_port_manager(manager)
            print(json.dumps(response.to_dict(), indent=2))
            return 0

        # Human-readable output
        if not ports:
            print("No audio input ports found.")
            return 1

        print("AUDIO PORTS")
        print("─" * 70)
        print(f"{'PORT_ID':<20} {'TYPE':<6} {'NAME':<30} {'STATUS':<12} {'RATES'}")
        print("─" * 70)

        for port in ports:
            # Format sample rates for display
            if len(port.capabilities.sample_rates) <= 3:
                rates_str = ",".join(str(r) for r in port.capabilities.sample_rates)
            else:
                rates_str = f"{port.capabilities.native_rate} (+{len(port.capabilities.sample_rates)-1} more)"

            # Truncate name if too long
            name = port.name[:28] + ".." if len(port.name) > 30 else port.name

            print(
                f"{port.port_id:<20} {port.port_type:<6} {name:<30} "
                f"{port.status.value:<12} {rates_str}"
            )

        print()

        # Show active and default ports
        active_port = manager.get_active_port()
        default_port = manager.get_default_port()

        if active_port:
            print(
                f"Active: {active_port.port_id} (streaming @ {active_port.capabilities.native_rate}Hz)"
            )
        else:
            print("Active: None")

        if default_port:
            print(f"Default: {default_port.port_id}")

        print()
        print("Pipeline target rate: 16000 Hz (Whisper)")

        return 0

    except Exception as e:
        print(f"ERROR: Failed to enumerate audio ports: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


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
            print(
                f"        Channels: {device['max_input_channels']}, "
                f"Sample Rate: {device['default_samplerate']:.0f} Hz"
            )

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

    try:
        # Get device's native sample rate
        device_info = sd.query_devices(device, "input")
        sample_rate = int(device_info["default_samplerate"])
        device_name = device_info["name"]

        print(f"Recording {duration} seconds from '{device_name}'...")
        print(f"  Native sample rate: {sample_rate} Hz")

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
        rms = np.sqrt(np.mean(recording**2))

        print("\nRecording complete:")
        print(f"  Duration: {duration} seconds")
        print(f"  Sample rate: {sample_rate} Hz")
        print(f"  Samples: {len(recording)}")
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
    """Record audio to WAV file (resamples to 16kHz for whisper compatibility)."""
    try:
        import sounddevice as sd
    except ImportError:
        print("ERROR: sounddevice not installed", file=sys.stderr)
        return 1

    target_rate = 16000  # Whisper expects 16kHz

    try:
        # Get device's native sample rate
        device_info = sd.query_devices(device, "input")
        native_rate = int(device_info["default_samplerate"])
        device_name = device_info["name"]

        print(f"Recording {duration} seconds from '{device_name}'...")
        print(f"  Native sample rate: {native_rate} Hz")

        # Record at native sample rate
        recording = sd.rec(
            int(duration * native_rate),
            samplerate=native_rate,
            channels=1,
            dtype=np.float32,
            device=device,
        )
        sd.wait()

        # Resample to 16kHz if needed
        if native_rate != target_rate:
            print(f"  Resampling: {native_rate} Hz -> {target_rate} Hz")
            # Simple linear interpolation resampling
            ratio = target_rate / native_rate
            new_length = int(len(recording) * ratio)
            indices = np.linspace(0, len(recording) - 1, new_length)
            recording = np.interp(
                indices, np.arange(len(recording)), recording.flatten()
            )
            recording = recording.reshape(-1, 1)

        # Convert to int16 for WAV
        recording_int16 = (recording * 32767).astype(np.int16)

        # Write WAV file
        with wave.open(output_file, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(target_rate)
            wf.writeframes(recording_int16.tobytes())

        file_size = os.path.getsize(output_file)
        print(f"Saved: {output_file} ({file_size} bytes, {target_rate} Hz)")
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

    # ports command (NEW - uses audio port abstraction)
    ports_parser = subparsers.add_parser(
        "ports", help="List audio ports with stable IDs"
    )
    ports_parser.add_argument(
        "--json", action="store_true", help="Output as JSON (for programmatic use)"
    )

    # list command (legacy - uses sounddevice directly)
    subparsers.add_parser("list", help="List audio input devices (legacy)")

    # test command
    test_parser = subparsers.add_parser("test", help="Test audio recording")
    test_parser.add_argument(
        "--device", "-d", type=int, help="Audio device index (legacy)"
    )
    test_parser.add_argument(
        "--port", "-p", type=str, help="Audio port ID (e.g., rode-videomic-ntg)"
    )
    test_parser.add_argument(
        "--duration",
        "-t",
        type=float,
        default=3.0,
        help="Recording duration in seconds (default: 3)",
    )

    # record command
    record_parser = subparsers.add_parser("record", help="Record audio to WAV file")
    record_parser.add_argument("file", help="Output WAV file path")
    record_parser.add_argument(
        "--device", "-d", type=int, help="Audio device index (legacy)"
    )
    record_parser.add_argument(
        "--port", "-p", type=str, help="Audio port ID (e.g., rode-videomic-ntg)"
    )
    record_parser.add_argument(
        "--duration",
        "-t",
        type=float,
        default=5.0,
        help="Recording duration in seconds (default: 5)",
    )

    parsed = parser.parse_args(args)

    if parsed.command is None:
        parser.print_help()
        return 0
    elif parsed.command == "ports":
        return cmd_audio_ports(as_json=parsed.json)
    elif parsed.command == "list":
        return cmd_audio_list()
    elif parsed.command == "test":
        # Support both --device (legacy) and --port (new)
        device = getattr(parsed, "device", None)
        port_id = getattr(parsed, "port", None)
        if port_id:
            # Convert port_id to device index
            manager = AudioPortManager()
            port = manager.get_port(port_id)
            if port:
                device = port.device_index
            else:
                print(f"ERROR: Port not found: {port_id}", file=sys.stderr)
                return 1
        return cmd_audio_test(device, parsed.duration)
    elif parsed.command == "record":
        # Support both --device (legacy) and --port (new)
        device = getattr(parsed, "device", None)
        port_id = getattr(parsed, "port", None)
        if port_id:
            # Convert port_id to device index
            manager = AudioPortManager()
            port = manager.get_port(port_id)
            if port:
                device = port.device_index
            else:
                print(f"ERROR: Port not found: {port_id}", file=sys.stderr)
                return 1
        return cmd_audio_record(device, parsed.duration, parsed.file)
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
                "-m",
                str(model),
                "-f",
                file,
                "--no-timestamps",
                "-l",
                "en",
            ],
            check=False,
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
        "--binary",
        "-b",
        type=Path,
        help="Path to whisper-cli binary",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=Path,
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
        "--cmd",
        "-c",
        metavar="COMMAND",
        help="Send command message instead of text",
    )
    parser.add_argument(
        "--arg",
        "-a",
        metavar="ARGUMENT",
        help="Command argument (used with --cmd)",
    )
    parser.add_argument(
        "--device",
        "-d",
        default="/dev/serial0",
        help="UART device (default: /dev/serial0)",
    )
    parser.add_argument(
        "--protocol",
        "-p",
        choices=["json", "msgpack"],
        default="json",
        help="Protocol to use (default: json)",
    )
    parser.add_argument(
        "--dry-run",
        "-n",
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
# dictacode-stt-hid (v0.2.8)
# =============================================================================


def cmd_hid_list() -> int:
    """List configured HID devices from registry."""
    try:
        from dictacode_stt.hid import HidDeviceRegistry

        registry = HidDeviceRegistry()
        registry.load_devices()

        devices = registry.list_devices()
        if not devices:
            print("No HID devices configured in /etc/dictacode/hid/devices.d/")
            return 1

        print("CONFIGURED HID DEVICES")
        print("─" * 80)
        print(f"{'DEVICE_ID':<20} {'NAME':<30} {'TRANSPORT':<12} {'ADDRESS':<18}")
        print("─" * 80)

        for device in devices:
            # Truncate name if too long
            name = device.name[:28] + ".." if len(device.name) > 30 else device.name
            addr = (
                device.address[:16] + ".."
                if len(device.address) > 18
                else device.address
            )

            print(
                f"{device.device_id:<20} {name:<30} "
                f"{device.transport:<12} {addr:<18}"
            )

        print()

        # Show default device
        default_device = registry.get_default_device()
        if default_device:
            print(
                f"Default: {default_device.device_id} (priority: {default_device.priority})"
            )

        # Show active device
        active_device = registry.get_active_device()
        if active_device:
            print(f"Active: {active_device.device_id}")

        print(f"\nTotal devices: {len(devices)}")
        return 0

    except Exception as e:
        print(f"ERROR: Failed to list HID devices: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def cmd_hid_usb_list() -> int:
    """List available USB-serial devices."""
    try:
        from dictacode_stt.transport import list_usb_serial_devices

        devices = list_usb_serial_devices()
        if not devices:
            print("No USB-serial devices found.")
            return 1

        print("USB-SERIAL DEVICES")
        print("─" * 90)
        print(f"{'VENDOR:PRODUCT':<16} {'DESCRIPTION':<30} {'SERIAL':<20} {'PORT':<20}")
        print("─" * 90)

        for device in devices:
            vid_pid = f"{device.vendor_id:04x}:{device.product_id:04x}"
            desc = (
                device.description[:28] + ".."
                if len(device.description) > 30
                else device.description
            )
            serial = device.serial_number or "N/A"
            serial = serial[:18] + ".." if len(serial) > 20 else serial
            port = device.port[:18] + ".." if len(device.port) > 20 else device.port

            print(f"{vid_pid:<16} {desc:<30} {serial:<20} {port:<20}")

        print(f"\nTotal devices: {len(devices)}")
        print(
            "\nTo use a USB-serial device, create a config file in /etc/dictacode/hid/devices.d/"
        )
        print("Example:")
        print("  [device]")
        print("  id = my-usb-device")
        print("  name = My USB HID Device")
        print("  transport = usb-serial")
        print("  address = 0403:6011  # vendor:product ID")
        print("  priority = 10")
        return 0

    except Exception as e:
        print(f"ERROR: Failed to list USB devices: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def hid_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-hid."""
    parser = argparse.ArgumentParser(
        prog="dictacode-stt-hid",
        description="HID device management for dictacode STT (v0.2.8)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list command
    subparsers.add_parser("list", help="List configured HID devices from registry")

    # usb-list command
    subparsers.add_parser("usb-list", help="List available USB-serial devices")

    parsed = parser.parse_args(args)

    if parsed.command is None:
        parser.print_help()
        return 0
    elif parsed.command == "list":
        return cmd_hid_list()
    elif parsed.command == "usb-list":
        return cmd_hid_usb_list()
    else:
        parser.print_help()
        return 1


# =============================================================================
# dictacode-stt-log (v0.2.13)
# =============================================================================


def cmd_log_status() -> int:
    """Show current log level and debug mode status."""
    try:
        from dictacode_stt.log_control import log_controller

        level = log_controller.get_level()
        debug_mode = log_controller.is_debug_mode()
        debug_remaining = log_controller.get_debug_remaining()

        print(f"Log level: {level}")
        if debug_mode and debug_remaining:
            minutes, seconds = divmod(debug_remaining, 60)
            print(f"Debug mode: ENABLED ({int(minutes)}m {int(seconds)}s remaining)")
        else:
            print("Debug mode: DISABLED")

        return 0

    except Exception as e:
        print(f"ERROR: Failed to get log status: {e}", file=sys.stderr)
        return 1


def cmd_log_set_level(level: str) -> int:
    """Set log level permanently."""
    try:
        from dictacode_stt.log_control import log_controller

        log_controller.set_level(level.upper())
        print(f"Log level set to {level.upper()}")
        return 0

    except Exception as e:
        print(f"ERROR: Failed to set log level: {e}", file=sys.stderr)
        return 1


def cmd_log_debug(duration: int = 300, disable: bool = False) -> int:
    """Enable or disable debug mode."""
    try:
        from dictacode_stt.log_control import log_controller

        if disable:
            log_controller.disable_debug()
            print("Debug mode disabled")
        else:
            log_controller.enable_debug(duration_seconds=duration)
            minutes, seconds = divmod(duration, 60)
            print(
                f"Debug mode enabled for {duration}s ({int(minutes)}m {int(seconds)}s)"
            )

        return 0

    except Exception as e:
        print(f"ERROR: Failed to control debug mode: {e}", file=sys.stderr)
        return 1


def log_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-log (v0.2.13)."""
    parser = argparse.ArgumentParser(
        prog="dictacode-stt-log",
        description="Runtime log level control for dictacode STT (v0.2.13)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dictacode-stt-log status                   # Show current log level
  dictacode-stt-log level INFO               # Set log level permanently
  dictacode-stt-log level DEBUG              # Set to DEBUG permanently
  dictacode-stt-log debug                    # Enable debug for 5 minutes (default)
  dictacode-stt-log debug --duration 600     # Enable debug for 10 minutes
  dictacode-stt-log debug --off              # Disable debug mode

Signal Control:
  kill -SIGUSR1 $(pidof dictacode-stt)       # Toggle debug mode via signal
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # status command
    subparsers.add_parser("status", help="Show current log level and debug mode status")

    # level command
    level_parser = subparsers.add_parser("level", help="Set log level permanently")
    level_parser.add_argument(
        "level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log level to set",
    )

    # debug command
    debug_parser = subparsers.add_parser("debug", help="Enable/disable debug mode")
    debug_parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=300,
        help="Duration in seconds (default: 300 = 5 minutes)",
    )
    debug_parser.add_argument(
        "--off",
        action="store_true",
        help="Disable debug mode",
    )

    parsed = parser.parse_args(args)

    if parsed.command is None:
        parser.print_help()
        return 0
    elif parsed.command == "status":
        return cmd_log_status()
    elif parsed.command == "level":
        return cmd_log_set_level(parsed.level)
    elif parsed.command == "debug":
        return cmd_log_debug(duration=parsed.duration, disable=parsed.off)
    else:
        parser.print_help()
        return 1


# =============================================================================
# dictacode-stt-bugreport (v0.2.9 Phase 5)
# =============================================================================


def cmd_bugreport(
    output: Optional[str],
    device_index: int,
    uart_device: str,
    whisper_binary: Optional[str],
    whisper_model: Optional[str],
    submit: bool = False,
) -> int:
    """Generate comprehensive bug report."""
    try:
        import json
        import subprocess
        from pathlib import Path

        from dictacode_stt.diagnostics.bugreport import BugReportGenerator

        print("Generating bug report...")
        print("This may take a few moments...\n")

        # Generate report
        generator = BugReportGenerator()
        report = generator.generate(
            device_index=device_index,
            uart_device=uart_device,
            whisper_binary=whisper_binary,
            whisper_model=whisper_model,
        )

        # Determine output path
        if output:
            output_path = Path(output)
        else:
            output_path = Path(f"dictacode-bugreport-{report.report_id}.json")

        # Save JSON report
        with open(output_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)
        print(f"Bug report saved: {output_path}")

        # Save markdown for GitHub
        md_path = output_path.with_suffix(".md")
        markdown_content = generator.to_markdown(report)
        with open(md_path, "w") as f:
            f.write(markdown_content)
        print(f"Markdown report: {md_path}")

        # Summary
        print(f"\nReport ID: {report.report_id}")
        print(f"Status: {report.summary['status']}")

        if report.summary["critical_issues"]:
            print("\nCritical Issues:")
            for issue in report.summary["critical_issues"]:
                print(f"  - {issue}")

        if report.summary["warnings"]:
            print("\nWarnings:")
            for warning in report.summary["warnings"]:
                print(f"  - {warning}")

        # Optional: Submit via gh CLI
        if submit:
            print("\nAttempting to submit issue via GitHub CLI...")
            try:
                # Check if gh is installed
                gh_check = subprocess.run(
                    ["gh", "--version"],
                    check=False,
                    capture_output=True,
                    timeout=5,
                )
                if gh_check.returncode != 0:
                    print("ERROR: GitHub CLI (gh) not installed", file=sys.stderr)
                    print("Install from: https://cli.github.com/", file=sys.stderr)
                    return 1

                # Create issue
                title = f"[Bug]: {report.summary['status']} - Report {report.report_id}"
                result = subprocess.run(
                    [
                        "gh",
                        "issue",
                        "create",
                        "--repo",
                        "cprima-homelab/dictacode",
                        "--title",
                        title,
                        "--body-file",
                        str(md_path),
                        "--label",
                        "bug",
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                if result.returncode == 0:
                    issue_url = result.stdout.strip()
                    print(f"\nIssue created: {issue_url}")
                    return 0
                else:
                    print(
                        f"ERROR: Failed to create issue: {result.stderr}",
                        file=sys.stderr,
                    )
                    print("\nManual submission required:", file=sys.stderr)
                    print(
                        "  1. Open: https://github.com/cprima-homelab/dictacode/issues/new",
                        file=sys.stderr,
                    )
                    print(f"  2. Paste contents of: {md_path}", file=sys.stderr)
                    return 1

            except subprocess.TimeoutExpired:
                print("ERROR: GitHub CLI timed out", file=sys.stderr)
                return 1
            except Exception as e:
                print(f"ERROR: Failed to submit via gh: {e}", file=sys.stderr)
                print("\nManual submission required:", file=sys.stderr)
                print(
                    "  1. Open: https://github.com/cprima-homelab/dictacode/issues/new",
                    file=sys.stderr,
                )
                print(f"  2. Paste contents of: {md_path}", file=sys.stderr)
                return 1
        else:
            print("\nTo submit a bug report:")
            print("  Option 1 (Manual):")
            print("    1. Open: https://github.com/cprima-homelab/dictacode/issues/new")
            print(f"    2. Paste contents of: {md_path}")
            print("  Option 2 (Automatic):")
            print("    dictacode-stt-bugreport --submit")

        return 0

    except Exception as e:
        print(f"ERROR: Failed to generate bug report: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


def bugreport_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-bugreport (v0.2.9)."""
    parser = argparse.ArgumentParser(
        prog="dictacode-stt-bugreport",
        description="Generate comprehensive bug report for dictacode STT (v0.2.9)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dictacode-stt-bugreport                        # Generate report with defaults
  dictacode-stt-bugreport --output /tmp/report   # Save to specific location
  dictacode-stt-bugreport --device 1             # Use specific audio device

The tool will generate:
  - JSON report with full diagnostic data
  - Markdown report ready for GitHub issue submission

All sensitive data (passwords, tokens, API keys) is automatically redacted.
        """,
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (without extension, will create .json and .md)",
    )
    parser.add_argument(
        "--device",
        "-d",
        type=int,
        default=0,
        help="Audio device index for diagnostics (default: 0)",
    )
    parser.add_argument(
        "--uart",
        type=str,
        default="/dev/serial0",
        help="UART device path (default: /dev/serial0)",
    )
    parser.add_argument(
        "--whisper-binary",
        type=str,
        default=None,
        help="Path to whisper binary (default: auto-detect)",
    )
    parser.add_argument(
        "--whisper-model",
        type=str,
        default=None,
        help="Path to whisper model (default: auto-detect)",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Submit bug report directly to GitHub via gh CLI (requires gh installed and authenticated)",
    )

    parsed = parser.parse_args(args)

    return cmd_bugreport(
        output=parsed.output,
        device_index=parsed.device,
        uart_device=parsed.uart,
        whisper_binary=parsed.whisper_binary,
        whisper_model=parsed.whisper_model,
        submit=parsed.submit,
    )


# =============================================================================
# Main entry points
# =============================================================================

if __name__ == "__main__":
    # Default to showing help
    print("Use one of the CLI commands:")
    print("  dictacode-stt-audio")
    print("  dictacode-stt-whisper")
    print("  dictacode-stt-send")
    print("  dictacode-stt-hid")
    print("  dictacode-stt-log         (v0.2.13 - runtime log level control)")
    print("  dictacode-stt-bugreport   (v0.2.9 - bug report generation)")
    sys.exit(0)
