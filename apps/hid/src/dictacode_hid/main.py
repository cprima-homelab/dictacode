"""dictacode HID bridge - UART to HID keyboard."""

import sys
import time

from .keymaps import load_keymap, get_current_keymap, Keymap

# Hardware constants
UART_DEVICE = "/dev/serial0"
BAUD_RATE = 115200
HID_DEVICE = "/dev/hidg0"


def send_key(hid_file, scancode: int, modifier: int = 0) -> None:
    """Send a single key press and release."""
    # Key press
    report = bytes([modifier, 0, scancode, 0, 0, 0, 0, 0])
    hid_file.write(report)
    hid_file.flush()
    time.sleep(0.02)
    # Key release
    report = bytes([0, 0, 0, 0, 0, 0, 0, 0])
    hid_file.write(report)
    hid_file.flush()
    time.sleep(0.02)


def type_char(hid_file, keymap: Keymap, char: str) -> bool:
    """Type a single character using the keymap. Returns True if typed."""
    mapping = keymap.get(char)
    if mapping:
        send_key(hid_file, mapping.scancode, mapping.modifier)
        return True
    return False


def type_text(hid_file, keymap: Keymap, text: str) -> int:
    """Type a string. Returns number of characters typed."""
    count = 0
    for char in text:
        if type_char(hid_file, keymap, char):
            count += 1
    return count


def main() -> None:
    """Main entry point - UART to HID bridge."""
    import argparse

    parser = argparse.ArgumentParser(description="dictacode UART to HID bridge")
    parser.add_argument("--dry-run", action="store_true", help="Don't send to HID")
    args = parser.parse_args()

    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed. Run: pip install pyserial")
        sys.exit(1)

    # Load keymap
    keymap_name = get_current_keymap()
    keymap = load_keymap(keymap_name)

    print(f"[dictacode-hid] Keymap: {keymap_name} ({keymap.description})")
    print(f"[dictacode-hid] UART: {UART_DEVICE} @ {BAUD_RATE}")
    print(f"[dictacode-hid] HID: {HID_DEVICE}")
    if args.dry_run:
        print("[dictacode-hid] DRY RUN - not sending to HID")
    print("[dictacode-hid] Listening... (Ctrl+C to stop)")
    print()

    ser = serial.Serial(UART_DEVICE, BAUD_RATE, timeout=1)
    hid_file = None if args.dry_run else open(HID_DEVICE, "wb")

    try:
        while True:
            line = ser.readline()
            if line:
                text = line.decode("utf-8", errors="replace").rstrip("\r\n")
                if text:
                    print(f"[dictacode-hid] received: {text}")
                    if hid_file:
                        typed = type_text(hid_file, keymap, text)
                        # Add space after each utterance
                        type_char(hid_file, keymap, " ")
                        print(f"[dictacode-hid] typed {typed} chars")
                    else:
                        print(f"[dictacode-hid] would type: {text}")
    except KeyboardInterrupt:
        print("\n[dictacode-hid] stopped")
    finally:
        ser.close()
        if hid_file:
            hid_file.close()
