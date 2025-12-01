"""CLI entrypoint for dictacode STT API server (v0.2.4 Phase 6)."""

import argparse
import logging
import uvicorn

logger = logging.getLogger(__name__)


def api_main():
    """Main entrypoint for dictacode-stt-api command."""
    parser = argparse.ArgumentParser(
        description="dictacode STT REST API Server (v0.2.4)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start API server on default port
  dictacode-stt-api

  # Start on custom port
  dictacode-stt-api --port 8080

  # Enable auto-reload for development
  dictacode-stt-api --reload

  # Bind to all interfaces
  dictacode-stt-api --host 0.0.0.0
""",
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )

    parser.add_argument(
        "--config-dir",
        default="/etc/dictacode/audio",
        help="Audio configuration directory (default: /etc/dictacode/audio)",
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )

    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Logging level (default: info)",
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

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="[%(name)s] %(message)s",
    )

    # Load configuration file (v0.2.15)
    from dictacode_stt.stt_config import load_stt_config
    import os

    try:
        config = load_stt_config()
    except Exception as e:
        logger.error(f"Config load failed: {e}, using CLI defaults")
        config = None

    # Apply config file values if CLI args are defaults
    if config:
        if args.host == "127.0.0.1":  # Default
            args.host = os.getenv("DICTACODE_API_HOST", config.api_host)

        if args.port == 8000:  # Default
            args.port = int(os.getenv("DICTACODE_API_PORT", str(config.api_port)))

        if args.config_dir == "/etc/dictacode/audio":  # Default
            args.config_dir = os.getenv("DICTACODE_API_CONFIG_DIR", config.api_config_dir)

    # Security warning if binding to non-localhost
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        logger.warning("=" * 70)
        logger.warning("SECURITY WARNING: API server binding to %s", args.host)
        logger.warning("This exposes the API to ALL network interfaces")
        logger.warning("The API has NO AUTHENTICATION configured")
        logger.warning("Only use this in trusted networks or behind auth proxy")
        logger.warning("=" * 70)

    # Initialize metrics (v0.2.15: config file support, separate from main service)
    # Precedence: CLI > env > config > default
    api_metrics_enabled = args.metrics
    api_metrics_port = args.metrics_port

    if config and not args.metrics:
        api_metrics_enabled = os.getenv(
            "DICTACODE_API_METRICS_ENABLED", str(config.api_metrics_enabled)
        ).lower() in ("true", "1", "yes")

        if args.metrics_port == 9100:  # Default value
            api_metrics_port = int(
                os.getenv("DICTACODE_API_METRICS_PORT", str(config.api_metrics_port))
            )

    if api_metrics_enabled:
        from dictacode_stt.metrics import init_metrics

        init_metrics(enabled=True, port=api_metrics_port)
        logger.info(f"API Prometheus metrics enabled on port {api_metrics_port}")

    # Initialize app with config
    from dictacode_stt.api import create_app

    app = create_app(config_dir=args.config_dir)

    logger.info(f"Starting dictacode STT API server on {args.host}:{args.port}")
    logger.info(f"OpenAPI docs: http://{args.host}:{args.port}/docs")
    logger.info(f"Audio config: {args.config_dir}")
    if api_metrics_enabled:
        logger.info(f"Metrics endpoint: http://{args.host}:{api_metrics_port}/metrics")

    # Run server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    api_main()
