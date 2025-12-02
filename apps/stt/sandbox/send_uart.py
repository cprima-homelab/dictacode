#!/usr/bin/env python3
"""
send_uart.py - Send protocol messages over UART to Pi Zero HID.

Sandbox script for dictacode STT.
Tests: UART reliability, protocol encoding, commands.

Usage:
    python send_uart.py "text to send"                  # send text message
    python send_uart.py --cmd keymap de_de              # send command
    python send_uart.py --cmd pause                     # send command (no arg)
    python send_uart.py --file input.txt                # send file contents
    python send_uart.py --stress 1000                   # send 1000 test messages
    DICTACODE_PROTOCOL=msgpack python send_uart.py "hello"  # use msgpack

Environment:
    DICTACODE_PROTOCOL  - Protocol: json (default) or msgpack
"""

import os
import sys
import time

# Import from src/ package
from dictacode_stt import (
    CommandMessage,
    TextMessage,
    get_protocol,
)


# Hardcoded from inventory - sandbox doesn't use config loader
UART_DEVICE = "/dev/serial0"
BAUD_RATE = 115200


def open_serial():
    """Open serial port."""
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        sys.exit(1)

    try:
        ser = serial.Serial(
            UART_DEVICE,
            BAUD_RATE,
            timeout=1,
        )
        return ser
    except Exception as e:
        print(f"[send_uart] ERROR opening {UART_DEVICE}: {e}")
        sys.exit(1)


def send_text(ser, protocol, text: str) -> None:
    """Send text message over UART."""
    msg = TextMessage(payload=text)
    encoded = protocol.encode(msg)

    start_time = time.perf_counter()
    ser.write(encoded)
    ser.flush()
    elapsed = time.perf_counter() - start_time

    chars_per_sec = len(encoded) / elapsed if elapsed > 0 else 0
    print(
        f"[send_uart] sent text ({len(encoded)} bytes) in {elapsed*1000:.2f} ms ({chars_per_sec:.0f} bytes/sec)"
    )
    print(f"[send_uart] payload: {text}")


def send_command(ser, protocol, cmd: str, arg: str = None) -> None:
    """Send command message over UART."""
    msg = CommandMessage(command=cmd, argument=arg)
    encoded = protocol.encode(msg)

    start_time = time.perf_counter()
    ser.write(encoded)
    ser.flush()
    elapsed = time.perf_counter() - start_time

    arg_str = f" {arg}" if arg else ""
    print(f"[send_uart] sent command ({len(encoded)} bytes) in {elapsed*1000:.2f} ms")
    print(f"[send_uart] command: {cmd}{arg_str}")


def stress_test(ser, protocol, count: int) -> None:
    """Send numbered messages for stress testing."""
    print(f"[send_uart] stress test: {count} messages")
    print()

    start_time = time.perf_counter()
    total_bytes = 0

    for i in range(count):
        msg = TextMessage(payload=f"stress-test-msg-{i:06d}")
        encoded = protocol.encode(msg)
        ser.write(encoded)
        total_bytes += len(encoded)

        if (i + 1) % 100 == 0:
            print(f"[send_uart] sent {i + 1}/{count}")

    ser.flush()
    elapsed = time.perf_counter() - start_time

    print()
    print("[send_uart] stress test complete")
    print(f"[send_uart] total: {total_bytes} bytes in {elapsed:.2f} sec")
    print(f"[send_uart] rate: {total_bytes / elapsed:.0f} bytes/sec")
    print(f"[send_uart] messages/sec: {count / elapsed:.0f}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Send protocol messages over UART")
    parser.add_argument("text", nargs="*", help="Text to send")
    parser.add_argument(
        "--cmd", nargs="+", help="Command to send (e.g., --cmd keymap de_de)"
    )
    parser.add_argument("--file", help="File to send")
    parser.add_argument("--stress", type=int, help="Stress test with N messages")
    parser.add_argument("--stdin", action="store_true", help="Read from stdin")
    args = parser.parse_args()

    # Get protocol from environment
    protocol_name = os.environ.get("DICTACODE_PROTOCOL", "json")
    protocol = get_protocol(protocol_name)

    print(f"[send_uart] device: {UART_DEVICE}")
    print(f"[send_uart] baud: {BAUD_RATE}")
    print(f"[send_uart] protocol: {protocol_name}")
    print()

    ser = open_serial()

    try:
        if args.cmd:
            # Send command
            cmd = args.cmd[0]
            arg = args.cmd[1] if len(args.cmd) > 1 else None
            send_command(ser, protocol, cmd, arg)

        elif args.file:
            # Send file contents
            with open(args.file) as f:
                text = f.read().strip()
            send_text(ser, protocol, text)

        elif args.stress:
            # Stress test
            stress_test(ser, protocol, args.stress)

        elif args.stdin:
            # Read from stdin
            text = sys.stdin.read().strip()
            send_text(ser, protocol, text)

        elif args.text:
            # Direct text argument
            text = " ".join(args.text)
            send_text(ser, protocol, text)

        else:
            parser.print_help()
            sys.exit(1)

    finally:
        ser.close()


if __name__ == "__main__":
    main()
