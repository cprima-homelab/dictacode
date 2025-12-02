"""
main.py - Entry point for dictacode HID service.

Provides CLI interface and service startup with proper signal handling for systemd.

Usage:
    python -m dictacode_hid                      # Start service
    python -m dictacode_hid --dry-run            # Dry run (no HID output)
    python -m dictacode_hid --maintenance        # Start in maintenance mode
    DICTACODE_PROTOCOL=msgpack python -m dictacode_hid  # Use msgpack protocol
"""

import argparse
import logging
import os
import signal
import sys

from dictacode_hid import DeviceMode, HidService


# Global flag for shutdown
_shutdown_requested = False


def request_shutdown(signum, frame):
    """Signal handler for graceful shutdown."""
    global _shutdown_requested
    _shutdown_requested = True


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(name)s] %(message)s",
        stream=sys.stdout,
    )


def main() -> int:
    """Main entry point."""
    global _shutdown_requested

    parser = argparse.ArgumentParser(
        description="dictacode HID Bridge - UART to HID keyboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  DICTACODE_PROTOCOL              Protocol: json (default) or msgpack
  DICTACODE_MODE                  Initial mode: normal, maintenance, paused
  DICTACODE_KEYMAP                Initial keymap: en_us (default), de_de
  DICTACODE_SUPERVISOR_TIMEOUT    Link timeout in seconds (default: 30)
  DICTACODE_SUPERVISOR_PING_INTERVAL  Ping interval in seconds (default: 5)
  DICTACODE_SUPERVISOR_ENABLED    Enable supervisor: true (default), false

Examples:
  python -m dictacode_hid
  python -m dictacode_hid --dry-run --verbose
  python -m dictacode_hid --no-supervisor
  DICTACODE_PROTOCOL=msgpack python -m dictacode_hid
        """,
    )
    parser.add_argument(
        "--uart",
        default="/dev/serial0",
        help="UART device path (default: /dev/serial0)",
    )
    parser.add_argument(
        "--hid",
        default="/dev/hidg0",
        help="HID device path (default: /dev/hidg0)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="UART baud rate (default: 115200)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't send to HID",
    )
    parser.add_argument(
        "--maintenance",
        action="store_true",
        help="Start in maintenance mode (log only, don't type)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose logging (DEBUG level)",
    )
    parser.add_argument(
        "--supervisor-timeout",
        type=float,
        default=30.0,
        help="Link timeout in seconds (default: 30)",
    )
    parser.add_argument(
        "--supervisor-ping-interval",
        type=float,
        default=5.0,
        help="Ping interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--no-supervisor",
        action="store_true",
        help="Disable supervisor (for debugging)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger("dictacode_hid")

    # Install signal handlers
    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    # Get configuration from environment
    protocol_name = os.environ.get("DICTACODE_PROTOCOL", "json")
    initial_mode_str = os.environ.get("DICTACODE_MODE", "normal")
    initial_keymap = os.environ.get("DICTACODE_KEYMAP", "en_us")

    if args.maintenance:
        initial_mode_str = "maintenance"

    initial_mode = {
        "normal": DeviceMode.NORMAL,
        "maintenance": DeviceMode.MAINTENANCE,
        "paused": DeviceMode.PAUSED,
    }.get(initial_mode_str, DeviceMode.NORMAL)

    logger.info("=" * 60)
    logger.info("dictacode HID Bridge starting...")
    logger.info(f"UART: {args.uart} @ {args.baud}")
    logger.info(f"HID: {args.hid}")
    logger.info(f"Protocol: {protocol_name}")
    logger.info(f"Mode: {initial_mode.name}")
    logger.info(f"Keymap: {initial_keymap}")
    if args.dry_run:
        logger.info("DRY RUN - HID output disabled")
    logger.info("=" * 60)

    # Get supervisor configuration from environment (fallback to args)
    supervisor_timeout = float(
        os.environ.get("DICTACODE_SUPERVISOR_TIMEOUT", args.supervisor_timeout)
    )
    supervisor_ping_interval = float(
        os.environ.get(
            "DICTACODE_SUPERVISOR_PING_INTERVAL", args.supervisor_ping_interval
        )
    )
    supervisor_enabled = (
        os.environ.get("DICTACODE_SUPERVISOR_ENABLED", "true").lower() != "false"
        and not args.no_supervisor
    )

    # Create service
    try:
        service = HidService(
            uart_device=args.uart,
            hid_device=args.hid,
            baud_rate=args.baud,
            protocol_name=protocol_name,
            initial_mode=initial_mode,
            initial_keymap=initial_keymap,
            dry_run=args.dry_run,
            supervisor_timeout=supervisor_timeout,
            supervisor_ping_interval=supervisor_ping_interval,
            supervisor_enabled=supervisor_enabled,
        )
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}", exc_info=True)
        return 1

    # Notify systemd if running under it
    try:
        from systemd.daemon import notify

        notify("READY=1")
        logger.info("Notified systemd: READY")
    except ImportError:
        pass  # Not running under systemd

    # Start service (blocking)
    try:
        service.start()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Service error: {e}", exc_info=True)
        return 1
    finally:
        service.stop()

    logger.info("Shutdown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
