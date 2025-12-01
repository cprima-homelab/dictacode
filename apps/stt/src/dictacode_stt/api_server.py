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

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="[%(name)s] %(message)s",
    )

    # Initialize app with config
    from dictacode_stt.api import create_app

    app = create_app(config_dir=args.config_dir)

    logger.info(f"Starting dictacode STT API server on {args.host}:{args.port}")
    logger.info(f"OpenAPI docs: http://{args.host}:{args.port}/docs")
    logger.info(f"Audio config: {args.config_dir}")

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
