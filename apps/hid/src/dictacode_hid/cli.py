"""CLI tool for managing dictacode keymaps."""

import argparse
import sys

from .keymaps import get_available_keymaps, get_current_keymap, set_current_keymap, load_keymap


def cmd_list() -> int:
    """List available keymaps."""
    keymaps = get_available_keymaps()
    current = get_current_keymap()

    print("Available keymaps:")
    for name, description in sorted(keymaps.items()):
        marker = "*" if name == current else " "
        print(f"  {marker} {name:10} - {description}")
    print()
    print(f"Current: {current}")
    return 0


def cmd_get() -> int:
    """Get current keymap."""
    current = get_current_keymap()
    print(current)
    return 0


def cmd_set(name: str) -> int:
    """Set current keymap."""
    try:
        # Validate keymap exists
        keymap = load_keymap(name)
        set_current_keymap(name)
        print(f"Keymap set to: {name} ({keymap.description})")
        return 0
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    except PermissionError:
        print("ERROR: Permission denied. Run with sudo to change system keymap.", file=sys.stderr)
        return 1


def cmd_info(name: str) -> int:
    """Show info about a keymap."""
    try:
        keymap = load_keymap(name)
        print(f"Name: {keymap.name}")
        print(f"Description: {keymap.description}")
        print(f"Mapped characters: {len(keymap)}")
        return 0
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for dictacode-keymap CLI."""
    parser = argparse.ArgumentParser(
        prog="dictacode-keymap",
        description="Manage dictacode keyboard layouts"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # list command
    subparsers.add_parser("list", help="List available keymaps")

    # get command
    subparsers.add_parser("get", help="Get current keymap")

    # set command
    set_parser = subparsers.add_parser("set", help="Set current keymap")
    set_parser.add_argument("name", help="Keymap name (e.g., en_us, de_de)")

    # info command
    info_parser = subparsers.add_parser("info", help="Show keymap info")
    info_parser.add_argument("name", help="Keymap name")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0
    elif args.command == "list":
        return cmd_list()
    elif args.command == "get":
        return cmd_get()
    elif args.command == "set":
        return cmd_set(args.name)
    elif args.command == "info":
        return cmd_info(args.name)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
