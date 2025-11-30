#!/usr/bin/env python3
"""
recv_uart_type.py - Receive text from UART, type via HID.

Sandbox script for dictacode HID.
Listens on UART, types received text to /dev/hidg0.

Usage:
    python recv_uart_type.py              # listen and type
    python recv_uart_type.py --dry-run    # show what would type (no HID)
"""

import sys
import time

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


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="UART to HID bridge")
    parser.add_argument("--dry-run", action="store_true", help="Don't send to HID")
    args = parser.parse_args()

    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        sys.exit(1)

    print(f"[recv_uart_type] UART: {UART_DEVICE} @ {BAUD_RATE}")
    print(f"[recv_uart_type] HID: {HID_DEVICE}")
    if args.dry_run:
        print("[recv_uart_type] DRY RUN - not sending to HID")
    print("[recv_uart_type] Listening... (Ctrl+C to stop)")
    print()

    ser = serial.Serial(UART_DEVICE, BAUD_RATE, timeout=1)
    hid_file = None if args.dry_run else open(HID_DEVICE, "wb")

    try:
        while True:
            line = ser.readline()
            if line:
                text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                if text:
                    print(f"[recv_uart_type] received: {text}")
                    if hid_file:
                        typed = type_text(hid_file, text)
                        # Add space after each utterance
                        type_char(hid_file, " ")
                        print(f"[recv_uart_type] typed {typed} chars")
                    else:
                        print(f"[recv_uart_type] would type: {text}")
    except KeyboardInterrupt:
        print("\n[recv_uart_type] stopped")
    finally:
        ser.close()
        if hid_file:
            hid_file.close()


if __name__ == "__main__":
    main()
