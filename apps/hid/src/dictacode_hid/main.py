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
from typing import Optional

from dictacode_hid import DeviceMode, HidService
from dictacode_hid.hid_config import load_hid_config


# Global flag for shutdown
_shutdown_requested = False


def request_shutdown(signum, frame):
    """Signal handler for graceful shutdown."""
    global _shutdown_requested
    _shutdown_requested = True


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "simple",
    log_file: Optional[str] = None,
) -> None:
    """Configure logging (v0.3.2).

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Format style (simple, json, systemd)
        log_file: Optional log file path
    """
    # Detect if running under systemd
    if os.environ.get("INVOCATION_ID"):  # systemd sets this
        log_format = "systemd"  # Override format for journald

    # Format string based on style
    if log_format == "json":
        fmt = '{"time":"%(asctime)s","name":"%(name)s",' \
              '"level":"%(levelname)s","msg":"%(message)s"}'
    elif log_format == "systemd":
        fmt = "[%(name)s] %(message)s"
    else:  # simple
        fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    handlers = []
    if log_file:
        handlers.append(logging.FileHandler(log_file))
    else:
        handlers.append(logging.StreamHandler(sys.stdout))

    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format=fmt,
        handlers=handlers,
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
    # v0.3.2: Logging options
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Log level (v0.3.2, default: INFO or DEBUG if --verbose)",
    )
    parser.add_argument(
        "--log-format",
        type=str,
        choices=["simple", "json", "systemd"],
        default="simple",
        help="Log output format (v0.3.2, default: simple, auto: systemd under systemd)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log to file instead of console (v0.3.2)",
    )

    args = parser.parse_args()

    # v0.3.2: Load configuration file
    try:
        config = load_hid_config()
    except Exception as e:
        # Minimal logging before setup
        print(f"[WARN] Config load failed: {e}, using CLI args only", file=sys.stderr)
        config = None

    # v0.3.2: Determine log level with precedence: CLI > env > config > default
    if args.log_level:
        log_level = args.log_level
    elif os.environ.get("DICTACODE_LOG_LEVEL"):
        log_level = os.environ.get("DICTACODE_LOG_LEVEL")
    elif args.verbose:
        log_level = "DEBUG"
    elif config:
        log_level = config.log_level
    else:
        log_level = "INFO"

    # Determine log format with precedence: CLI > env > config > default
    log_format = args.log_format
    if os.environ.get("DICTACODE_LOG_FORMAT"):
        log_format = os.environ.get("DICTACODE_LOG_FORMAT")
    elif config and args.log_format == "simple":  # only override if CLI is default
        log_format = "simple"  # config.log_format is full format string, use simple

    # Determine log file with precedence: CLI > env > config > default
    log_file = args.log_file
    if not log_file and os.environ.get("DICTACODE_LOG_FILE"):
        log_file = os.environ.get("DICTACODE_LOG_FILE")
    elif not log_file and config:
        log_file = config.log_file

    # Setup logging (v0.3.2)
    setup_logging(
        log_level=log_level,
        log_format=log_format,
        log_file=log_file,
    )
    logger = logging.getLogger("dictacode_hid")

    # Install signal handlers
    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    # v0.3.2: Apply precedence for all settings: CLI > env > config > default
    # Protocol: CLI arg not available, env > config > default
    protocol_name = os.environ.get(
        "DICTACODE_PROTOCOL",
        config.protocol if config else "json"
    )

    # Mode: --maintenance CLI > env > config > default
    if args.maintenance:
        initial_mode_str = "maintenance"
    elif os.environ.get("DICTACODE_MODE"):
        initial_mode_str = os.environ.get("DICTACODE_MODE")
    elif config:
        initial_mode_str = config.initial_mode
    else:
        initial_mode_str = "normal"

    # Keymap: env > config > default
    initial_keymap = os.environ.get(
        "DICTACODE_KEYMAP",
        config.initial_keymap if config else "en_us"
    )

    initial_mode = {
        "normal": DeviceMode.NORMAL,
        "maintenance": DeviceMode.MAINTENANCE,
        "paused": DeviceMode.PAUSED,
    }.get(initial_mode_str, DeviceMode.NORMAL)

    # v0.3.2: Supervisor config with precedence: CLI > env > config > default
    # Timeout: CLI > env > config > default
    if args.supervisor_timeout != 30.0:  # CLI explicitly set
        supervisor_timeout = args.supervisor_timeout
    elif os.environ.get("DICTACODE_SUPERVISOR_TIMEOUT"):
        supervisor_timeout = float(os.environ.get("DICTACODE_SUPERVISOR_TIMEOUT"))
    elif config:
        supervisor_timeout = config.supervisor_timeout
    else:
        supervisor_timeout = 30.0

    # Ping interval: CLI > env > config > default
    if args.supervisor_ping_interval != 5.0:  # CLI explicitly set
        supervisor_ping_interval = args.supervisor_ping_interval
    elif os.environ.get("DICTACODE_SUPERVISOR_PING_INTERVAL"):
        env_val = os.environ.get("DICTACODE_SUPERVISOR_PING_INTERVAL")
        supervisor_ping_interval = float(env_val)
    elif config:
        supervisor_ping_interval = config.supervisor_ping_interval
    else:
        supervisor_ping_interval = 5.0

    # Enabled: --no-supervisor CLI > env > config > default
    if args.no_supervisor:
        supervisor_enabled = False
    elif os.environ.get("DICTACODE_SUPERVISOR_ENABLED"):
        env_val = os.environ.get("DICTACODE_SUPERVISOR_ENABLED")
        supervisor_enabled = env_val.lower() != "false"
    elif config:
        supervisor_enabled = config.supervisor_enabled
    else:
        supervisor_enabled = True

    # UART/HID devices: CLI > config > default
    uart_device = args.uart if args.uart != "/dev/serial0" else (
        config.uart_device if config else "/dev/serial0"
    )
    hid_device = args.hid if args.hid != "/dev/hidg0" else (
        config.hid_device if config else "/dev/hidg0"
    )
    baud_rate = args.baud if args.baud != 115200 else (
        config.uart_baud if config else 115200
    )
    dry_run = args.dry_run or (config.dry_run if config else False)

    # Log resolved configuration (v0.3.2: shows actual values after precedence)
    logger.info("=" * 60)
    logger.info("dictacode HID Bridge starting...")
    logger.info(f"Config source: {'file+CLI' if config else 'CLI only'}")
    logger.info(f"UART: {uart_device} @ {baud_rate}")
    logger.info(f"HID: {hid_device}")
    logger.info(f"Protocol: {protocol_name}")
    logger.info(f"Mode: {initial_mode.name}")
    logger.info(f"Keymap: {initial_keymap}")
    logger.info(
        f"Supervisor: {supervisor_enabled} "
        f"(timeout={supervisor_timeout}s, ping={supervisor_ping_interval}s)"
    )
    if dry_run:
        logger.info("DRY RUN - HID output disabled")
    logger.info("=" * 60)

    # Create service
    try:
        service = HidService(
            uart_device=uart_device,
            hid_device=hid_device,
            baud_rate=baud_rate,
            protocol_name=protocol_name,
            initial_mode=initial_mode,
            initial_keymap=initial_keymap,
            dry_run=dry_run,
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
