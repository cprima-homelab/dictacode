"""Configuration file loader for dictacode STT."""

import logging
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


logger = logging.getLogger("dictacode.config")
DEFAULT_CONFIG_PATH = Path("/etc/dictacode/stt.conf")


@dataclass
class SttConfig:
    """STT service configuration with validation."""

    # Prometheus metrics (main service)
    metrics_enabled: bool = False
    metrics_port: int = 9100

    # API server
    api_host: str = "127.0.0.1"  # Secure default
    api_port: int = 8000
    api_config_dir: str = "/etc/dictacode/audio"
    api_metrics_enabled: bool = False
    api_metrics_port: int = 9101

    # Legacy STT settings
    model: str = "tiny"
    language: str = "en"
    uart_device: str = "/dev/serial0"
    uart_baud: int = 115200
    chunk_duration: float = 5.0

    def __post_init__(self):
        """Validate configuration values."""
        # Validate ports
        for field_name in ["metrics_port", "api_port", "api_metrics_port"]:
            port = getattr(self, field_name)
            if not isinstance(port, int) or not (1 <= port <= 65535):
                raise ValueError(
                    f"Invalid {field_name}: {port!r} (must be integer 1-65535)"
                )

        # Validate UART baud rate
        valid_bauds = [9600, 19200, 38400, 57600, 115200, 230400]
        if self.uart_baud not in valid_bauds:
            raise ValueError(
                f"Invalid uart_baud: {self.uart_baud} "
                f"(must be one of {valid_bauds})"
            )

        # Validate chunk_duration
        if not (0.1 <= self.chunk_duration <= 60.0):
            raise ValueError(
                f"Invalid chunk_duration: {self.chunk_duration} "
                "(must be 0.1-60.0 seconds)"
            )

        # Security: warn if API bound to non-localhost
        if self.api_host not in ("127.0.0.1", "localhost", "::1"):
            logger.warning(
                "API host set to %s (not localhost) - ensure this is intentional!",
                self.api_host,
            )


def load_stt_config(config_path: Optional[Path] = None) -> SttConfig:
    """
    Load configuration from file with validation.

    Returns:
        SttConfig with validated values, or safe defaults if file missing/invalid
    """
    config_path = config_path or DEFAULT_CONFIG_PATH

    if not config_path.exists():
        logger.info("Config file not found: %s, using defaults", config_path)
        return SttConfig()

    try:
        parser = ConfigParser()
        parser.read(config_path)

        # Support both flat (DEFAULT) and sectioned config
        section = "stt" if parser.has_section("stt") else "DEFAULT"

        # Helper functions with validation
        def getbool(key: str, default: bool) -> bool:
            try:
                return parser.getboolean(section, key, fallback=default)
            except ValueError as e:
                logger.warning(
                    "Invalid boolean for %s: %s, using default %s", key, e, default
                )
                return default

        def getint(key: str, default: int) -> int:
            try:
                return parser.getint(section, key, fallback=default)
            except ValueError as e:
                logger.warning(
                    "Invalid integer for %s: %s, using default %s", key, e, default
                )
                return default

        def getfloat(key: str, default: float) -> float:
            try:
                return parser.getfloat(section, key, fallback=default)
            except ValueError as e:
                logger.warning(
                    "Invalid float for %s: %s, using default %s", key, e, default
                )
                return default

        def getstr(key: str, default: str) -> str:
            return parser.get(section, key, fallback=default)

        # Build config with parsed values
        config = SttConfig(
            metrics_enabled=getbool("metrics_enabled", False),
            metrics_port=getint("metrics_port", 9100),
            api_host=getstr("api_host", "127.0.0.1"),
            api_port=getint("api_port", 8000),
            api_config_dir=getstr("api_config_dir", "/etc/dictacode/audio"),
            api_metrics_enabled=getbool("api_metrics_enabled", False),
            api_metrics_port=getint("api_metrics_port", 9101),
            model=getstr("model", "tiny"),
            language=getstr("language", "en"),
            uart_device=getstr("uart_device", "/dev/serial0"),
            uart_baud=getint("uart_baud", 115200),
            chunk_duration=getfloat("chunk_duration", 5.0),
        )

        logger.info("Loaded configuration from %s", config_path)
        # Validation happens in __post_init__
        return config

    except ValueError as e:
        logger.error("Configuration validation failed: %s", e)
        logger.error("Falling back to safe defaults")
        return SttConfig()
    except Exception as e:
        logger.error("Failed to load config from %s: %s", config_path, e)
        logger.error("Falling back to safe defaults")
        return SttConfig()
