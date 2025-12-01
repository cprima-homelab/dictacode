"""
main.py - Entry point for dictacode STT service.

Provides CLI interface and service startup with proper signal handling for systemd.

Usage:
    python -m dictacode_stt                      # Start continuous pipeline
    python -m dictacode_stt --once               # Run once and exit
    python -m dictacode_stt --dry-run            # Dry run (no UART output)
    DICTACODE_PROTOCOL=msgpack python -m dictacode_stt  # Use msgpack protocol
"""

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from dictacode_stt import SttService, SolutionState

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
        description="dictacode STT Service - Speech-to-text pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  DICTACODE_PROTOCOL              Protocol: json (default) or msgpack
  DICTACODE_MODE                  Initial mode: normal, maintenance
  DICTACODE_SUPERVISOR_TIMEOUT    Link timeout in seconds (default: 30)
  DICTACODE_SUPERVISOR_PING_INTERVAL  Ping interval in seconds (default: 5)
  DICTACODE_SUPERVISOR_ENABLED    Enable supervisor: true (default), false

Examples:
  python -m dictacode_stt
  python -m dictacode_stt --once --verbose
  python -m dictacode_stt --duration 10 --language de
  python -m dictacode_stt --no-supervisor
  DICTACODE_PROTOCOL=msgpack python -m dictacode_stt
        """,
    )
    parser.add_argument(
        "--uart",
        default="/dev/serial0",
        help="UART device path (default: /dev/serial0)",
    )
    parser.add_argument(
        "--baud",
        type=int,
        default=115200,
        help="UART baud rate (default: 115200)",
    )
    parser.add_argument(
        "--whisper-binary",
        type=Path,
        help="Path to whisper-cli (default: ~/whisper.cpp/build/bin/whisper-cli)",
    )
    parser.add_argument(
        "--whisper-model",
        type=Path,
        help="Path to whisper model (default: ~/whisper.cpp/models/ggml-tiny.bin)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=0,
        help="Audio device index (default: 0)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Recording duration in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--language",
        default="en",
        help="Transcription language (default: en)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (default: continuous loop)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't send to UART",
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
    logger = logging.getLogger("dictacode_stt")

    # Install signal handlers
    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    # Get configuration from environment
    protocol_name = os.environ.get("DICTACODE_PROTOCOL", "json")
    initial_mode_str = os.environ.get("DICTACODE_MODE", "normal")

    initial_mode = {
        "listening": SolutionState.LISTENING,
        "normal": SolutionState.LISTENING,  # Alias
        "maintenance": SolutionState.MAINTENANCE,
    }.get(initial_mode_str, SolutionState.LISTENING)

    logger.info("=" * 60)
    logger.info("dictacode STT Service starting...")
    logger.info(f"UART: {args.uart} @ {args.baud}")
    logger.info(f"Protocol: {protocol_name}")
    logger.info(f"Mode: {initial_mode.name}")
    logger.info(f"Audio device: {args.device}")
    logger.info(f"Recording duration: {args.duration}s")
    logger.info(f"Language: {args.language}")
    if args.dry_run:
        logger.info("DRY RUN - UART output disabled")
    if args.once:
        logger.info("Run mode: ONCE")
    else:
        logger.info("Run mode: CONTINUOUS")
    logger.info("=" * 60)

    # Get supervisor configuration from environment (fallback to args)
    supervisor_timeout = float(
        os.environ.get("DICTACODE_SUPERVISOR_TIMEOUT", args.supervisor_timeout)
    )
    supervisor_ping_interval = float(
        os.environ.get("DICTACODE_SUPERVISOR_PING_INTERVAL", args.supervisor_ping_interval)
    )
    supervisor_enabled = os.environ.get(
        "DICTACODE_SUPERVISOR_ENABLED", "true"
    ).lower() != "false" and not args.no_supervisor

    # Create service
    try:
        service = SttService(
            uart_device=args.uart,
            baud_rate=args.baud,
            protocol_name=protocol_name,
            whisper_binary=args.whisper_binary,
            whisper_model=args.whisper_model,
            device_index=args.device,
            recording_duration=args.duration,
            language=args.language,
            initial_mode=initial_mode,
            dry_run=args.dry_run,
            supervisor_timeout=supervisor_timeout,
            supervisor_ping_interval=supervisor_ping_interval,
            supervisor_enabled=supervisor_enabled,
        )
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}", exc_info=True)
        return 1

    # Check prerequisites
    if not service.check_prerequisites():
        logger.error("Prerequisites check failed")
        return 1

    # Start transport
    try:
        service.start()
    except Exception as e:
        logger.error(f"Failed to start service: {e}", exc_info=True)
        return 1

    # Notify systemd if running under it
    try:
        from systemd.daemon import notify
        notify("READY=1")
        logger.info("Notified systemd: READY")
    except ImportError:
        pass  # Not running under systemd

    # Run pipeline
    try:
        if args.once:
            logger.info("Running once...")
            stats = service.run_once()
            if "error" in stats:
                logger.error(f"Pipeline failed: {stats['error']}")
                return 1
            logger.info("Completed successfully")
        else:
            logger.info("Starting continuous pipeline...")
            service.run_continuous()
    except KeyboardInterrupt:
        logger.info("Interrupted")
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        return 1
    finally:
        service.stop()

    logger.info("Shutdown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
