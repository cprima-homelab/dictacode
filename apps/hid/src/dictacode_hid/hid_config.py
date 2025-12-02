"""Configuration file loader for dictacode HID."""

import logging
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


logger = logging.getLogger("dictacode.hid.config")

DEFAULT_CONFIG_PATH = Path("/etc/dictacode/hid.conf")
DROP_IN_DIR = Path("/etc/dictacode/hid.d")


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
class HidConfig:
    """HID service configuration with validation.

    All fields match CLI args and environment variables from main.py.
    """

    # === Transport (from main.py args) ===
    uart_device: str = "/dev/serial0"  # --uart
    uart_baud: int = 115200  # --baud
    hid_device: str = "/dev/hidg0"  # --hid
    protocol: str = "json"  # DICTACODE_PROTOCOL env

    # === Mode & Keymap (from main.py args + env) ===
    initial_mode: str = "normal"  # DICTACODE_MODE env, --maintenance
    initial_keymap: str = "en_us"  # DICTACODE_KEYMAP env
    keymap_config: str = "/etc/dictacode/keymap.conf"
    hid_registry_dir: str = "/etc/dictacode/hid/devices.d"

    # === Supervisor (from main.py args + env) ===
    supervisor_enabled: bool = True  # --no-supervisor, env
    supervisor_timeout: float = 30.0  # --supervisor-timeout, env
    supervisor_ping_interval: float = 5.0  # --supervisor-ping-interval

    # === Logging (NEW - currently basicConfig in main.py) ===
    log_level: str = "INFO"  # --log-level (to be added)
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None  # --log-file (to be added)
    verbose: bool = False  # --verbose / -v

    # === Behavior (from main.py args) ===
    dry_run: bool = False  # --dry-run

    # === Compatibility ===
    compatibility_matrix: Optional[str] = None  # Override search path

    def __post_init__(self):
        """Validate configuration values using WARN policy."""
        # Validate baud rate
        valid_bauds = [9600, 19200, 38400, 57600, 115200, 230400]
        self.uart_baud = validate_field(
            "uart_baud",
            self.uart_baud,
            lambda v: v in valid_bauds,
            115200,
        )

        # Validate protocol
        valid_protocols = ["json", "msgpack"]
        self.protocol = validate_field(
            "protocol",
            self.protocol,
            lambda v: v in valid_protocols,
            "json",
        )

        # Validate mode
        valid_modes = ["normal", "maintenance", "paused"]
        self.initial_mode = validate_field(
            "initial_mode",
            self.initial_mode,
            lambda v: v in valid_modes,
            "normal",
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


def load_hid_config(
    config_path: Optional[Path] = None,
    drop_in_dir: Optional[Path] = None,
) -> HidConfig:
    """
    Load configuration with drop-in merging.

    Args:
        config_path: Base config file path (default: /etc/dictacode/hid.conf)
        drop_in_dir: Drop-in directory (default: /etc/dictacode/hid.d)

    Returns:
        HidConfig with validated values, or safe defaults if file missing/invalid

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
    section = "hid" if parser.has_section("hid") else "DEFAULT"

    # Helper functions with validation logging
    def getbool(key: str, default: bool) -> bool:
        try:
            return parser.getboolean(section, key, fallback=default)
        except ValueError as e:
            logger.warning("Invalid boolean for %s: %s, default %s", key, e, default)
            return default

    def getint(key: str, default: int) -> int:
        try:
            return parser.getint(section, key, fallback=default)
        except ValueError as e:
            logger.warning("Invalid integer for %s: %s, default %s", key, e, default)
            return default

    def getfloat(key: str, default: float) -> float:
        try:
            return parser.getfloat(section, key, fallback=default)
        except ValueError as e:
            logger.warning("Invalid float for %s: %s, default %s", key, e, default)
            return default

    def getstr(key: str, default: str) -> str:
        return parser.get(section, key, fallback=default)

    def getstr_optional(key: str) -> Optional[str]:
        val = parser.get(section, key, fallback=None)
        return val if val else None

    try:
        config = HidConfig(
            # Transport
            uart_device=getstr("uart_device", "/dev/serial0"),
            uart_baud=getint("uart_baud", 115200),
            hid_device=getstr("hid_device", "/dev/hidg0"),
            protocol=getstr("protocol", "json"),
            # Mode & Keymap
            initial_mode=getstr("initial_mode", "normal"),
            initial_keymap=getstr("initial_keymap", "en_us"),
            keymap_config=getstr("keymap_config", "/etc/dictacode/keymap.conf"),
            hid_registry_dir=getstr("hid_registry_dir", "/etc/dictacode/hid/devices.d"),
            # Supervisor
            supervisor_enabled=getbool("supervisor_enabled", True),
            supervisor_timeout=getfloat("supervisor_timeout", 30.0),
            supervisor_ping_interval=getfloat("supervisor_ping_interval", 5.0),
            # Logging
            log_level=getstr("log_level", "INFO"),
            log_format=getstr(
                "log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
            log_file=getstr_optional("log_file"),
            verbose=getbool("verbose", False),
            # Behavior
            dry_run=getbool("dry_run", False),
            # Compatibility
            compatibility_matrix=getstr_optional("compatibility_matrix"),
        )

        logger.debug("Configuration loaded: %s", config)
        # Validation happens in __post_init__
        return config

    except ValueError as e:
        logger.error("Configuration validation failed: %s", e)
        logger.error("Falling back to safe defaults")
        return HidConfig()
    except Exception as e:
        logger.error("Failed to build config: %s", e)
        logger.error("Falling back to safe defaults")
        return HidConfig()
