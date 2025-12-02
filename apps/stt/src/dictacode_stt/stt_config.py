"""Configuration file loader for dictacode STT."""

import logging
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


logger = logging.getLogger("dictacode.config")
DEFAULT_CONFIG_PATH = Path("/etc/dictacode/stt.conf")
DROP_IN_DIR = Path("/etc/dictacode/stt.d")


class ValidationPolicy:
    """Config validation behavior."""

    STRICT = "strict"  # Raise ValueError, service won't start
    WARN = "warn"  # Log WARNING, use default
    SILENT = "silent"  # Log DEBUG, use default (not recommended)


DEFAULT_POLICY = ValidationPolicy.WARN


def validate_field(
    name: str,
    value: Any,
    validator: Callable[[Any], bool],
    default: Any,
    policy: str = DEFAULT_POLICY,
) -> Any:
    """Validate config value with explicit failure semantics."""
    if not validator(value):
        msg = f"Config '{name}': invalid value {value!r}"
        if policy == ValidationPolicy.STRICT:
            raise ValueError(msg)
        elif policy == ValidationPolicy.WARN:
            logger.warning("%s, using default %r", msg, default)
            return default
        else:
            logger.debug("%s, using default %r", msg, default)
            return default
    return value


@dataclass
class SttConfig:
    """STT service configuration with validation.

    All fields match CLI args and environment variables from main.py.
    """

    # === Prometheus metrics (main service) ===
    metrics_enabled: bool = False
    metrics_port: int = 9100

    # === API server ===
    api_host: str = "127.0.0.1"  # Secure default
    api_port: int = 8000
    api_config_dir: str = "/etc/dictacode/audio"
    api_metrics_enabled: bool = False
    api_metrics_port: int = 9101

    # === STT settings ===
    model: str = "tiny"
    language: str = "en"
    uart_device: str = "/dev/serial0"
    uart_baud: int = 115200
    chunk_duration: float = 5.0

    # === Transport (v0.3.2) ===
    transport_type: Optional[str] = None  # "uart", "tcp", etc. (--transport)
    hid_device_id: Optional[str] = None  # From HID registry (--hid-device)
    protocol: str = "json"  # DICTACODE_PROTOCOL env

    # === Handshake & Link (v0.3.2) ===
    handshake_timeout: float = 10.0
    link_poll_interval: float = 5.0
    prerequisite_poll_interval: float = 30.0

    # === Audio (v0.3.2) ===
    native_sample_rate: int = 48000
    native_channels: int = 2
    whisper_sample_rate: int = 16000
    audio_config_dir: str = "/etc/dictacode/audio"
    audio_profiles_dir: str = "/etc/dictacode/audio/profiles"
    audio_source: Optional[str] = None  # --audio-source (testing)
    audio_port: Optional[str] = None  # --port
    audio_device: Optional[str] = None  # --device

    # === Whisper paths (v0.3.2) ===
    whisper_binary: Optional[str] = None  # --whisper-binary
    whisper_model: Optional[str] = None  # --whisper-model
    streaming_enabled: bool = False  # --streaming

    # === Supervisor (v0.3.2) ===
    supervisor_enabled: bool = True  # --no-supervisor
    supervisor_timeout: float = 30.0  # --supervisor-timeout
    supervisor_ping_interval: float = 5.0  # --supervisor-ping-interval

    # === Logging (v0.3.2) ===
    log_level: str = "INFO"  # --log-level
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None  # --log-file

    # === Behavior ===
    dry_run: bool = False  # --dry-run
    run_once: bool = False  # --once

    # === LLM post-processing (v0.2.14) ===
    llm_enabled: bool = False
    llm_provider: str = "ollama"  # "ollama", "openai", "openrouter"
    llm_model: str = "llama3.2"
    llm_profile: str = (
        "passthrough"  # "grammar", "punctuation", "formal", "casual", "code", "passthrough"
    )
    llm_fallback: bool = True  # Return original text on error
    llm_base_url: Optional[str] = None  # Override provider default URL
    llm_api_key: Optional[str] = None  # API key for openai/openrouter

    # === Compatibility (v0.3.2) ===
    compatibility_matrix: Optional[str] = None  # Override search path

    def __post_init__(self):
        """Validate configuration values using WARN policy."""
        # Validate ports
        for field_name in ["metrics_port", "api_port", "api_metrics_port"]:
            port = getattr(self, field_name)
            validated = validate_field(
                field_name,
                port,
                lambda v: isinstance(v, int) and 1 <= v <= 65535,
                9100 if "metrics" in field_name else 8000,
            )
            setattr(self, field_name, validated)

        # Validate UART baud rate
        valid_bauds = [9600, 19200, 38400, 57600, 115200, 230400]
        self.uart_baud = validate_field(
            "uart_baud",
            self.uart_baud,
            lambda v: v in valid_bauds,
            115200,
        )

        # Validate chunk_duration
        self.chunk_duration = validate_field(
            "chunk_duration",
            self.chunk_duration,
            lambda v: isinstance(v, (int, float)) and 0.1 <= v <= 60.0,
            5.0,
        )

        # Validate protocol
        valid_protocols = ["json", "msgpack"]
        self.protocol = validate_field(
            "protocol",
            self.protocol,
            lambda v: v in valid_protocols,
            "json",
        )

        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.log_level = validate_field(
            "log_level",
            self.log_level.upper(),
            lambda v: v in valid_levels,
            "INFO",
        )

        # Validate supervisor timeouts (positive numbers)
        self.supervisor_timeout = validate_field(
            "supervisor_timeout",
            self.supervisor_timeout,
            lambda v: isinstance(v, (int, float)) and v > 0,
            30.0,
        )
        self.supervisor_ping_interval = validate_field(
            "supervisor_ping_interval",
            self.supervisor_ping_interval,
            lambda v: isinstance(v, (int, float)) and v > 0,
            5.0,
        )

        # Validate sample rates (positive integers)
        for field_name in ["native_sample_rate", "whisper_sample_rate"]:
            rate = getattr(self, field_name)
            validated = validate_field(
                field_name,
                rate,
                lambda v: isinstance(v, int) and v > 0,
                48000 if "native" in field_name else 16000,
            )
            setattr(self, field_name, validated)

        # Security: warn if API bound to non-localhost
        if self.api_host not in ("127.0.0.1", "localhost", "::1"):
            logger.warning(
                "API host set to %s (not localhost) - ensure this is intentional!",
                self.api_host,
            )


def load_stt_config(
    config_path: Optional[Path] = None,
    drop_in_dir: Optional[Path] = None,
) -> SttConfig:
    """
    Load configuration with drop-in merging.

    Args:
        config_path: Base config file path (default: /etc/dictacode/stt.conf)
        drop_in_dir: Drop-in directory (default: /etc/dictacode/stt.d)

    Returns:
        SttConfig with validated values, or safe defaults if file missing/invalid

    Drop-ins are merged in sorted filename order on top of base config.
    Files without section headers get [DEFAULT] prepended automatically.
    """
    config_path = config_path or DEFAULT_CONFIG_PATH
    drop_in_dir = drop_in_dir or DROP_IN_DIR

    parser = ConfigParser()

    # 1. Load base config (if exists)
    if config_path.exists():
        try:
            content = config_path.read_text()
            # Tolerate missing section header
            if content.strip() and not content.strip().startswith("["):
                content = "[DEFAULT]\n" + content
            parser.read_string(content, source=str(config_path))
            logger.info("Loaded base config: %s", config_path)
        except Exception as e:
            logger.warning("Failed to read base config %s: %s", config_path, e)
    else:
        logger.debug("Base config not found: %s, using defaults", config_path)

    # 2. Merge drop-ins in sorted order
    if drop_in_dir.exists() and drop_in_dir.is_dir():
        for drop_in in sorted(drop_in_dir.glob("*.conf")):
            try:
                content = drop_in.read_text()
                if content.strip() and not content.strip().startswith("["):
                    content = "[DEFAULT]\n" + content
                parser.read_string(content, source=str(drop_in))
                logger.info("Merged drop-in: %s", drop_in)
            except Exception as e:
                logger.warning("Failed to read drop-in %s: %s", drop_in, e)

    # 3. Build config from merged values
    section = "stt" if parser.has_section("stt") else "DEFAULT"

    # Helper functions with validation logging
    def getbool(key: str, default: bool) -> bool:
        try:
            return parser.getboolean(section, key, fallback=default)
        except ValueError as e:
            logger.warning("Invalid boolean for %s: %s, using default %s", key, e, default)
            return default

    def getint(key: str, default: int) -> int:
        try:
            return parser.getint(section, key, fallback=default)
        except ValueError as e:
            logger.warning("Invalid integer for %s: %s, using default %s", key, e, default)
            return default

    def getfloat(key: str, default: float) -> float:
        try:
            return parser.getfloat(section, key, fallback=default)
        except ValueError as e:
            logger.warning("Invalid float for %s: %s, using default %s", key, e, default)
            return default

    def getstr(key: str, default: str) -> str:
        return parser.get(section, key, fallback=default)

    def getstr_optional(key: str) -> Optional[str]:
        val = parser.get(section, key, fallback=None)
        return val if val else None

    try:
        config = SttConfig(
            # Metrics
            metrics_enabled=getbool("metrics_enabled", False),
            metrics_port=getint("metrics_port", 9100),
            # API
            api_host=getstr("api_host", "127.0.0.1"),
            api_port=getint("api_port", 8000),
            api_config_dir=getstr("api_config_dir", "/etc/dictacode/audio"),
            api_metrics_enabled=getbool("api_metrics_enabled", False),
            api_metrics_port=getint("api_metrics_port", 9101),
            # STT
            model=getstr("model", "tiny"),
            language=getstr("language", "en"),
            uart_device=getstr("uart_device", "/dev/serial0"),
            uart_baud=getint("uart_baud", 115200),
            chunk_duration=getfloat("chunk_duration", 5.0),
            # Transport (v0.3.2)
            transport_type=getstr_optional("transport_type"),
            hid_device_id=getstr_optional("hid_device_id"),
            protocol=getstr("protocol", "json"),
            # Handshake & Link (v0.3.2)
            handshake_timeout=getfloat("handshake_timeout", 10.0),
            link_poll_interval=getfloat("link_poll_interval", 5.0),
            prerequisite_poll_interval=getfloat("prerequisite_poll_interval", 30.0),
            # Audio (v0.3.2)
            native_sample_rate=getint("native_sample_rate", 48000),
            native_channels=getint("native_channels", 2),
            whisper_sample_rate=getint("whisper_sample_rate", 16000),
            audio_config_dir=getstr("audio_config_dir", "/etc/dictacode/audio"),
            audio_profiles_dir=getstr("audio_profiles_dir", "/etc/dictacode/audio/profiles"),
            audio_source=getstr_optional("audio_source"),
            audio_port=getstr_optional("audio_port"),
            audio_device=getstr_optional("audio_device"),
            # Whisper (v0.3.2)
            whisper_binary=getstr_optional("whisper_binary"),
            whisper_model=getstr_optional("whisper_model"),
            streaming_enabled=getbool("streaming_enabled", False),
            # Supervisor (v0.3.2)
            supervisor_enabled=getbool("supervisor_enabled", True),
            supervisor_timeout=getfloat("supervisor_timeout", 30.0),
            supervisor_ping_interval=getfloat("supervisor_ping_interval", 5.0),
            # Logging (v0.3.2)
            log_level=getstr("log_level", "INFO"),
            log_format=getstr(
                "log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
            log_file=getstr_optional("log_file"),
            # Behavior
            dry_run=getbool("dry_run", False),
            run_once=getbool("run_once", False),
            # LLM post-processing (v0.2.14)
            llm_enabled=getbool("llm_enabled", False),
            llm_provider=getstr("llm_provider", "ollama"),
            llm_model=getstr("llm_model", "llama3.2"),
            llm_profile=getstr("llm_profile", "passthrough"),
            llm_fallback=getbool("llm_fallback", True),
            llm_base_url=getstr_optional("llm_base_url"),
            llm_api_key=getstr_optional("llm_api_key"),
            # Compatibility (v0.3.2)
            compatibility_matrix=getstr_optional("compatibility_matrix"),
        )

        logger.debug("Configuration loaded: %s", config)
        # Validation happens in __post_init__
        return config

    except ValueError as e:
        logger.error("Configuration validation failed: %s", e)
        logger.error("Falling back to safe defaults")
        return SttConfig()
    except Exception as e:
        logger.error("Failed to build config: %s", e)
        logger.error("Falling back to safe defaults")
        return SttConfig()
