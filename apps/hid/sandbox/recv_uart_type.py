#!/usr/bin/env python3
"""
recv_uart_type.py - Receive protocol messages from UART, type via HID.

Sandbox script for dictacode HID.
Listens on UART, decodes protocol messages, types text to /dev/hidg0.

Usage:
    python recv_uart_type.py                    # listen and type
    python recv_uart_type.py --dry-run          # show what would type (no HID)
    python recv_uart_type.py --maintenance      # log only, don't type
    DICTACODE_PROTOCOL=msgpack python recv_uart_type.py  # use msgpack

Environment:
    DICTACODE_PROTOCOL  - Protocol: json (default) or msgpack
    DICTACODE_MODE      - Initial mode: normal, maintenance, paused
"""

import os
import sys
import time

# Import from src/ package
from dictacode_hid import (
    get_protocol,
    detect_protocol,
    TextMessage,
    CommandMessage,
    DeviceMode,
    HidState,
)

# Hardcoded from inventory
UART_DEVICE = "/dev/serial0"
BAUD_RATE = 115200
HID_DEVICE = "/dev/hidg0"

# US keyboard keycodes (basic)
KEYMAP = {
    "a": 4, "b": 5, "c": 6, "d": 7, "e": 8, "f": 9, "g": 10, "h": 11,
    "i": 12, "j": 13, "k": 14, "l": 15, "m": 16, "n": 17, "o": 18, "p": 19,
    "q": 20, "r": 21, "s": 22, "t": 23, "u": 24, "v": 25, "w": 26, "x": 27,
    "y": 28, "z": 29, "1": 30, "2": 31, "3": 32, "4": 33, "5": 34, "6": 35,
    "7": 36, "8": 37, "9": 38, "0": 39, " ": 44, "\n": 40, "\t": 43,
    "-": 45, "=": 46, "[": 47, "]": 48, "\\": 49, ";": 51, "'": 52,
    "`": 53, ",": 54, ".": 55, "/": 56,
}

# Shifted characters
SHIFT_KEYMAP = {
    "A": 4, "B": 5, "C": 6, "D": 7, "E": 8, "F": 9, "G": 10, "H": 11,
    "I": 12, "J": 13, "K": 14, "L": 15, "M": 16, "N": 17, "O": 18, "P": 19,
    "Q": 20, "R": 21, "S": 22, "T": 23, "U": 24, "V": 25, "W": 26, "X": 27,
    "Y": 28, "Z": 29, "!": 30, "@": 31, "#": 32, "$": 33, "%": 34, "^": 35,
    "&": 36, "*": 37, "(": 38, ")": 39, "_": 45, "+": 46, "{": 47, "}": 48,
    "|": 49, ":": 51, '"': 52, "~": 53, "<": 54, ">": 55, "?": 56,
}


def send_key(hid_file, keycode: int, modifier: int = 0) -> None:
    """Send a single key press and release."""
    # Key press
    report = bytes([modifier, 0, keycode, 0, 0, 0, 0, 0])
    hid_file.write(report)
    hid_file.flush()
    time.sleep(0.02)
    # Key release
    report = bytes([0, 0, 0, 0, 0, 0, 0, 0])
    hid_file.write(report)
    hid_file.flush()
    time.sleep(0.02)


def type_char(hid_file, char: str) -> bool:
    """Type a single character. Returns True if typed."""
    if char in KEYMAP:
        send_key(hid_file, KEYMAP[char])
        return True
    elif char in SHIFT_KEYMAP:
        send_key(hid_file, SHIFT_KEYMAP[char], modifier=2)  # Left Shift
        return True
    else:
        # Unknown character, skip
        return False


def type_text(hid_file, text: str) -> int:
    """Type a string. Returns number of characters typed."""
    count = 0
    for char in text:
        if type_char(hid_file, char):
            count += 1
    return count


def handle_command(msg: CommandMessage, state: HidState) -> None:
    """Process a command message."""
    cmd = msg.command
    arg = msg.argument

    if cmd == "keymap" and arg:
        state.set_keymap(arg)

    elif cmd == "pause":
        state.set_mode(DeviceMode.PAUSED)

    elif cmd == "resume":
        state.set_mode(DeviceMode.NORMAL)

    elif cmd == "maintenance":
        state.set_mode(DeviceMode.MAINTENANCE)

    elif cmd == "normal":
        state.set_mode(DeviceMode.NORMAL)

    else:
        print(f"[recv_uart_type] unknown command: {cmd}")


def handle_text(msg: TextMessage, state: HidState, hid_file) -> None:
    """Process a text message based on current state."""
    text = msg.payload

    if state.should_type():
        if hid_file:
            typed = type_text(hid_file, text)
            type_char(hid_file, " ")  # Add space after each utterance
            print(f"[recv_uart_type] typed {typed} chars: {text}")
        else:
            print(f"[recv_uart_type] would type: {text}")

    elif state.should_buffer():
        state.add_to_buffer(text)
        print(f"[recv_uart_type] buffered (paused): {text}")

    else:
        # Maintenance mode - log only
        print(f"[recv_uart_type] received (maintenance): {text}")


def flush_buffer(state: HidState, hid_file) -> None:
    """Flush buffered text after resume."""
    buffered = state.flush_buffer()
    for text in buffered:
        if hid_file:
            typed = type_text(hid_file, text)
            type_char(hid_file, " ")
            print(f"[recv_uart_type] typed (from buffer) {typed} chars: {text}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="UART to HID bridge with protocol support")
    parser.add_argument("--dry-run", action="store_true", help="Don't send to HID")
    parser.add_argument("--maintenance", action="store_true", help="Start in maintenance mode")
    args = parser.parse_args()

    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        sys.exit(1)

    # Get protocol from environment
    protocol_name = os.environ.get("DICTACODE_PROTOCOL", "json")
    protocol = get_protocol(protocol_name)

    # Initialize state
    initial_mode_str = os.environ.get("DICTACODE_MODE", "normal")
    if args.maintenance:
        initial_mode_str = "maintenance"

    initial_mode = {
        "normal": DeviceMode.NORMAL,
        "maintenance": DeviceMode.MAINTENANCE,
        "paused": DeviceMode.PAUSED,
    }.get(initial_mode_str, DeviceMode.NORMAL)

    state = HidState(mode=initial_mode)

    print(f"[recv_uart_type] UART: {UART_DEVICE} @ {BAUD_RATE}")
    print(f"[recv_uart_type] HID: {HID_DEVICE}")
    print(f"[recv_uart_type] Protocol: {protocol_name}")
    print(f"[recv_uart_type] Mode: {state.mode.name}")
    if args.dry_run:
        print("[recv_uart_type] DRY RUN - not sending to HID")
    print("[recv_uart_type] Listening... (Ctrl+C to stop)")
    print()

    ser = serial.Serial(UART_DEVICE, BAUD_RATE, timeout=1)
    hid_file = None if args.dry_run else open(HID_DEVICE, "wb")

    try:
        while True:
            if protocol_name == "json":
                # JSON: read until newline
                line = ser.readline()
                if not line:
                    continue
                raw_data = line
            else:
                # Msgpack: read 2-byte length prefix, then payload
                length_bytes = ser.read(2)
                if len(length_bytes) < 2:
                    continue
                length = int.from_bytes(length_bytes, "big")
                payload = ser.read(length)
                if len(payload) < length:
                    print(f"[recv_uart_type] incomplete message: got {len(payload)}/{length} bytes")
                    continue
                raw_data = payload

            try:
                msg = protocol.decode(raw_data)
            except Exception as e:
                # Try auto-detection on decode failure
                detected = detect_protocol(raw_data if protocol_name == "json" else length_bytes + raw_data)
                if detected != protocol_name:
                    print(f"[recv_uart_type] protocol mismatch? detected {detected}, expected {protocol_name}")
                print(f"[recv_uart_type] decode error: {e}")
                continue

            if isinstance(msg, TextMessage):
                handle_text(msg, state, hid_file)
            elif isinstance(msg, CommandMessage):
                old_mode = state.mode
                handle_command(msg, state)
                # If resumed from paused, flush buffer
                if old_mode == DeviceMode.PAUSED and state.mode == DeviceMode.NORMAL:
                    flush_buffer(state, hid_file)

    except KeyboardInterrupt:
        print("\n[recv_uart_type] stopped")
    finally:
        ser.close()
        if hid_file:
            hid_file.close()


if __name__ == "__main__":
    main()
