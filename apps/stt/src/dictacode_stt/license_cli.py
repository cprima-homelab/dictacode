#!/usr/bin/env python3
"""CLI tool for managing dictacode license tokens (v0.3.11 multi-badge support).

Usage:
    dictacode-license save <token>           # Save to user config
    dictacode-license save <token> --system  # Save to system config
    dictacode-license show                   # Show current license status
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    """Main entry point for the license CLI."""
    parser = argparse.ArgumentParser(
        description="Manage dictacode license tokens",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dictacode-license save eyJraWQ...       Save token to ~/.config/dictacode/license.key
  dictacode-license save eyJraWQ... --system  Save to /etc/dictacode/license.key
  dictacode-license show                  Show current license status
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # save command
    save_parser = subparsers.add_parser("save", help="Save license token")
    save_parser.add_argument("token", help="License token string")
    save_parser.add_argument(
        "--system",
        action="store_true",
        help="Save to system location (/etc/dictacode/license.key)",
    )

    # show command
    subparsers.add_parser("show", help="Show current license status")

    args = parser.parse_args()

    if args.command == "save":
        return cmd_save(args.token, args.system)
    elif args.command == "show":
        return cmd_show()
    else:
        parser.print_help()
        return 1


def cmd_save(token: str, system: bool) -> int:
    """Save a license token to file."""
    if system:
        path = Path("/etc/dictacode/license.key")
    else:
        path = Path.home() / ".config/dictacode/license.key"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(token.strip() + "\n")
        print(f"License saved to: {path}")

        # Validate the token we just saved
        from dictacode_stt.license import load_badge_state

        state = load_badge_state(token)

        if state.badges:
            print(f"Validated: {len(state.badges)} badge(s)")
            for badge in state.badges:
                print(f"  - {badge.tier}: {badge.name or '(unnamed)'}")
        else:
            print("Warning: No valid badges in token. Check token format.")

        return 0

    except PermissionError:
        print(f"Error: Permission denied writing to {path}", file=sys.stderr)
        if system:
            print("Hint: Use sudo for system-wide installation", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_show() -> int:
    """Show current license status (v0.3.11 multi-badge support)."""
    from dictacode_stt.license import LICENSE_PATHS, load_badge_state

    # Find which file is being used
    active_path = None
    for path in LICENSE_PATHS:
        if path.exists():
            active_path = path
            break

    state = load_badge_state()

    if not state.token_present:
        print("No license token found")
        print(f"Tier:   free")
        print(f"File:   (not found)")
        return 0

    if not state.badges:
        print("License token present but invalid")
        print(f"Tier:   free")
        print(f"File:   {active_path or '(unknown)'}")
        return 0

    # Show all badges
    print(f"Badges: {len(state.badges)}")
    for i, badge in enumerate(state.badges, 1):
        print(f"\n  [{i}] {badge.tier}")
        print(f"      Name:   {badge.name or '(none)'}")
        print(f"      Issued: {badge.issued_at or '(none)'}")

    print(f"\nPrimary: {state.tier}")
    print(f"File:    {active_path or '(unknown)'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
