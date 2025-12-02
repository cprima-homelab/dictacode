"""
main.py - Entry point for dictacode STT service.

Provides CLI interface and service startup with proper signal handling for systemd.

Usage:
    python -m dictacode_stt                      # Start continuous pipeline
    python -m dictacode_stt --once               # Run once and exit
    python -m dictacode_stt --port rode-videomic-ntg  # Use specific audio port
    python -m dictacode_stt --dry-run            # Dry run (no UART output)
    DICTACODE_PROTOCOL=msgpack python -m dictacode_stt  # Use msgpack protocol
"""

import argparse
import logging
import os
import signal
import sys
from pathlib import Path

from dictacode_stt import SolutionState, SttService
from dictacode_stt.audio import AudioPortManager
from dictacode_stt.log_control import log_controller
from dictacode_stt.logging_config import LogConfig, LogFormat, configure_logging


# Global flag for shutdown
_shutdown_requested = False


def request_shutdown(signum, frame):
    """Signal handler for graceful shutdown."""
    global _shutdown_requested
    _shutdown_requested = True


def setup_logging_v0_2_13(
    log_level: str = "INFO",
    log_format: str = "simple",
    log_file: str = None,
) -> None:
    """Configure logging (v0.2.13)."""
    # Detect if running under systemd
    output = "console"
    if os.environ.get("INVOCATION_ID"):  # systemd sets this
        output = "journald"
        log_format = "systemd"  # Override format for journald

    config = LogConfig(
        level=log_level.upper(),
        format=LogFormat(log_format),
        output="file" if log_file else output,
        file_path=Path(log_file) if log_file else None,
    )
    configure_logging(config)

    # Setup signal handler for debug toggle (SIGUSR1)
    log_controller.setup_signal_handler()


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
  python -m dictacode_stt --port rode-videomic-ntg
  python -m dictacode_stt --duration 10 --language de
  python -m dictacode_stt --no-supervisor
  python -m dictacode_stt --audio-source file:test.wav:fast --dry-run
  python -m dictacode_stt --audio-source synthetic:silence:1000 --once
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
        default=None,
        help="Audio device index (legacy, use --port instead)",
    )
    parser.add_argument(
        "--port",
        "-p",
        type=str,
        default=None,
        help="Audio port ID (e.g., rode-videomic-ntg, hw:0)",
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
        help="Verbose logging (DEBUG level, legacy - use --log-level DEBUG)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=None,
        help="Log level (v0.2.13, default: INFO or DEBUG if --verbose)",
    )
    parser.add_argument(
        "--log-format",
        type=str,
        choices=["simple", "json", "systemd"],
        default="simple",
        help="Log output format (v0.2.13, default: simple, auto: systemd under systemd)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log to file instead of console (v0.2.13)",
    )
    parser.add_argument(
        "--metrics",
        action="store_true",
        help="Enable Prometheus metrics (v0.2.13, default: disabled)",
    )
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=9100,
        help="Prometheus metrics port (v0.2.13, default: 9100)",
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
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Enable streaming transcription (v0.2.7, real-time partial results)",
    )
    parser.add_argument(
        "--hid-device",
        type=str,
        default=None,
        help="HID device ID to use (v0.2.8, from /etc/dictacode/hid/devices.d/)",
    )
    parser.add_argument(
        "--transport",
        "-t",
        type=str,
        choices=["uart", "usb-serial", "wifi"],
        default=None,
        help="Transport type to use (v0.2.8, default: auto-select from registry)",
    )
    parser.add_argument(
        "--audio-source",
        type=str,
        default=None,
        metavar="SPEC",
        help=(
            "Audio source for testing (v0.2.11, default: microphone). "
            "Examples: file:path/to/audio.wav:fast, synthetic:silence:1000"
        ),
    )
    # LLM post-processing (v0.3.1)
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Enable LLM post-processing (v0.3.1, default: disabled)",
    )
    parser.add_argument(
        "--llm-provider",
        type=str,
        choices=["ollama", "openai", "openrouter"],
        default=None,
        help="LLM provider (v0.3.1, default: ollama from config)",
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=None,
        help="LLM model identifier (v0.3.1, default: llama3.2 from config)",
    )
    parser.add_argument(
        "--llm-profile",
        type=str,
        choices=["grammar", "punctuation", "formal", "casual", "code", "passthrough"],
        default=None,
        help="Processing profile (v0.3.1, default: passthrough from config)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Disable LLM post-processing (v0.3.1, overrides config)",
    )

    args = parser.parse_args()

    # Determine log level (v0.2.13 with backward compatibility)
    if args.log_level:
        log_level = args.log_level
    elif args.verbose:
        log_level = "DEBUG"
    else:
        log_level = "INFO"

    # Setup logging (v0.2.13)
    setup_logging_v0_2_13(
        log_level=log_level,
        log_format=args.log_format,
        log_file=args.log_file,
    )
    logger = logging.getLogger("dictacode_stt")

    # Load configuration file (v0.2.15)
    from dictacode_stt.stt_config import load_stt_config

    try:
        config = load_stt_config()
    except Exception as e:
        logger.error(f"Config load failed: {e}, using CLI args only")
        config = None

    # Initialize metrics (v0.2.15: config file support)
    # Precedence: CLI > env > config > default
    metrics_enabled = args.metrics
    metrics_port = args.metrics_port

    # Apply config file values if CLI args are defaults
    if config and not args.metrics:
        metrics_enabled = os.getenv(
            "DICTACODE_METRICS_ENABLED", str(config.metrics_enabled)
        ).lower() in ("true", "1", "yes")

        if args.metrics_port == 9100:  # Default value
            metrics_port = int(
                os.getenv("DICTACODE_METRICS_PORT", str(config.metrics_port))
            )

    if metrics_enabled:
        from dictacode_stt.metrics import init_metrics

        init_metrics(enabled=True, port=metrics_port)
        logger.info(f"Prometheus metrics enabled on port {metrics_port}")

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

    # Resolve audio port to device index
    device_index = None
    port_name = None

    if args.port:
        # Use port ID to find device
        try:
            manager = AudioPortManager()
            port = manager.get_port(args.port)
            if port:
                device_index = port.device_index
                port_name = f"{port.port_id} ({port.name})"
                logger.info(f"Resolved port '{args.port}' to device {device_index}")
            else:
                logger.error(f"Audio port '{args.port}' not found")
                logger.info("Available ports:")
                for p in manager.list_ports():
                    logger.info(f"  {p.port_id} - {p.name}")
                return 1
        except Exception as e:
            logger.error(f"Failed to resolve audio port: {e}", exc_info=True)
            return 1
    elif args.device is not None:
        # Legacy device index
        device_index = args.device
        port_name = f"device {device_index}"
    else:
        # Default to device 0
        device_index = 0
        port_name = f"device {device_index} (default)"

    # v0.2.11: Create audio source if specified
    audio_source = None
    if args.audio_source:
        try:
            from dictacode_stt.audio.sources import create_audio_source

            audio_source = create_audio_source(args.audio_source)
            logger.info(f"Created audio source: {args.audio_source}")
        except Exception as e:
            logger.error(f"Failed to create audio source '{args.audio_source}': {e}")
            return 1

    # v0.3.1: LLM post-processing configuration
    # Precedence: CLI (--no-llm, --llm) > CLI params > config > defaults
    llm_enabled = False
    llm_provider = "ollama"
    llm_model = "llama3.2"
    llm_profile = "passthrough"
    llm_fallback = True
    llm_base_url = None
    llm_api_key = None

    if args.no_llm:
        # Explicit disable via CLI
        llm_enabled = False
    elif args.llm:
        # Explicit enable via CLI
        llm_enabled = True
        llm_provider = args.llm_provider or (
            config.llm_provider if config else "ollama"
        )
        llm_model = args.llm_model or (config.llm_model if config else "llama3.2")
        llm_profile = args.llm_profile or (
            config.llm_profile if config else "passthrough"
        )
        if config:
            llm_fallback = config.llm_fallback
            llm_base_url = config.llm_base_url
            llm_api_key = config.llm_api_key
    elif config:
        # Use config file settings
        llm_enabled = config.llm_enabled
        llm_provider = args.llm_provider or config.llm_provider
        llm_model = args.llm_model or config.llm_model
        llm_profile = args.llm_profile or config.llm_profile
        llm_fallback = config.llm_fallback
        llm_base_url = config.llm_base_url
        llm_api_key = config.llm_api_key

    logger.info("=" * 60)
    logger.info("dictacode STT Service starting...")
    logger.info(f"UART: {args.uart} @ {args.baud}")
    logger.info(f"Protocol: {protocol_name}")
    logger.info(f"Mode: {initial_mode.name}")
    if audio_source:
        logger.info(f"Audio source: {args.audio_source} (TESTING MODE)")
    else:
        logger.info(f"Audio port: {port_name}")
    logger.info(f"Recording duration: {args.duration}s")
    logger.info(f"Language: {args.language}")
    if args.streaming:
        logger.info("Streaming mode: ENABLED (real-time transcription)")
    if llm_enabled:
        logger.info(
            f"LLM post-processing: ENABLED ({llm_provider}/{llm_model} + {llm_profile})"
        )
    else:
        logger.info("LLM post-processing: DISABLED")
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
        service = SttService(
            uart_device=args.uart,
            baud_rate=args.baud,
            protocol_name=protocol_name,
            whisper_binary=args.whisper_binary,
            whisper_model=args.whisper_model,
            device_index=device_index,
            recording_duration=args.duration,
            language=args.language,
            streaming=args.streaming,
            dry_run=args.dry_run,
            supervisor_timeout=supervisor_timeout,
            supervisor_ping_interval=supervisor_ping_interval,
            supervisor_enabled=supervisor_enabled,
            transport_type=args.transport,  # v0.2.8
            hid_device_id=args.hid_device,  # v0.2.8
            audio_source=audio_source,  # v0.2.11
            llm_enabled=llm_enabled,  # v0.3.1
            llm_provider=llm_provider,  # v0.3.1
            llm_model=llm_model,  # v0.3.1
            llm_profile=llm_profile,  # v0.3.1
            llm_fallback=llm_fallback,  # v0.3.1
            llm_base_url=llm_base_url,  # v0.3.1
            llm_api_key=llm_api_key,  # v0.3.1
        )
    except Exception as e:
        logger.error(f"Failed to initialize service: {e}", exc_info=True)
        return 1

    # v0.2.3: Service handles prerequisites, startup, and sd_notify internally via state machine
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
