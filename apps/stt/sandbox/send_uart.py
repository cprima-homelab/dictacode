#!/usr/bin/env python3
"""
send_uart.py - Send text over UART to Pi Zero HID.

Sandbox script for dictacode STT.
Tests: UART reliability, throughput, latency.

Usage:
    python send_uart.py "text to send"
    python send_uart.py --file input.txt
    python send_uart.py --stress 1000    # send 1000 numbered messages
    echo "hello" | python send_uart.py --stdin
"""

import sys
import time

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


def send_text(ser, text: str) -> None:
    """Send text over UART with newline delimiter."""
    # Simple protocol: text followed by newline
    message = text + "\n"
    encoded = message.encode("utf-8")

    start_time = time.perf_counter()
    ser.write(encoded)
    ser.flush()
    elapsed = time.perf_counter() - start_time

    chars_per_sec = len(encoded) / elapsed if elapsed > 0 else 0

    print(f"[send_uart] sent {len(encoded)} bytes in {elapsed*1000:.2f} ms ({chars_per_sec:.0f} chars/sec)")


def stress_test(ser, count: int) -> None:
    """Send numbered messages for stress testing."""
    print(f"[send_uart] stress test: {count} messages")
    print()

    start_time = time.perf_counter()
    total_bytes = 0

    for i in range(count):
        message = f"stress-test-msg-{i:06d}"
        encoded = (message + "\n").encode("utf-8")
        ser.write(encoded)
        total_bytes += len(encoded)

        if (i + 1) % 100 == 0:
            print(f"[send_uart] sent {i + 1}/{count}")

    ser.flush()
    elapsed = time.perf_counter() - start_time

    print()
    print(f"[send_uart] stress test complete")
    print(f"[send_uart] total: {total_bytes} bytes in {elapsed:.2f} sec")
    print(f"[send_uart] rate: {total_bytes / elapsed:.0f} bytes/sec")
    print(f"[send_uart] messages/sec: {count / elapsed:.0f}")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python send_uart.py <text>")
        print("       python send_uart.py --file <path>")
        print("       python send_uart.py --stress <count>")
        print("       python send_uart.py --stdin")
        sys.exit(1)

    print(f"[send_uart] device: {UART_DEVICE}")
    print(f"[send_uart] baud: {BAUD_RATE}")
    print()

    ser = open_serial()

    try:
        arg = sys.argv[1]

        if arg == "--file":
            if len(sys.argv) < 3:
                print("ERROR: --file requires path")
                sys.exit(1)
            with open(sys.argv[2], "r") as f:
                text = f.read().strip()
            send_text(ser, text)

        elif arg == "--stress":
            count = int(sys.argv[2]) if len(sys.argv) > 2 else 100
            stress_test(ser, count)

        elif arg == "--stdin":
            text = sys.stdin.read().strip()
            send_text(ser, text)

        else:
            # Direct text argument
            text = " ".join(sys.argv[1:])
            send_text(ser, text)

    finally:
        ser.close()


if __name__ == "__main__":
    main()
