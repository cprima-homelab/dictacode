"""Logging configuration for dictacode STT (v0.2.13)."""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class LogFormat(Enum):
    """Log output format (v0.2.13)."""

    SIMPLE = "simple"  # Human-readable
    JSON = "json"  # Machine-parseable
    SYSTEMD = "systemd"  # No timestamp (journald adds it)


@dataclass
class LogConfig:
    """Logging configuration (v0.2.13)."""

    level: str = "INFO"
    format: LogFormat = LogFormat.SIMPLE
    output: str = "console"  # console, file, journald
    file_path: Optional[Path] = None
    file_max_bytes: int = 10_000_000  # 10MB
    file_backup_count: int = 5
    color: bool = True
    include_timestamp: bool = True
    include_source: bool = True  # module:line


# Format strings
SIMPLE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
SIMPLE_FORMAT_NO_TIME = "[%(levelname)s] %(name)s: %(message)s"
DEBUG_FORMAT = (
    "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
)


class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging (v0.2.13)."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields (any custom fields added to log record)
        for key, value in record.__dict__.items():
            if key not in [
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "thread",
                "threadName",
                "exc_info",
                "exc_text",
                "stack_info",
            ] and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data)


class ColorFormatter(logging.Formatter):
    """Colored console formatter (v0.2.13)."""

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with color."""
        color = self.COLORS.get(record.levelname, "")
        levelname_colored = f"{color}{record.levelname}{self.RESET}"

        # Store original levelname
        original_levelname = record.levelname

        # Temporarily replace levelname for formatting
        record.levelname = levelname_colored

        # Format the message
        formatted = super().format(record)

        # Restore original levelname
        record.levelname = original_levelname

        return formatted


def configure_logging(config: LogConfig) -> None:
    """Configure logging based on config (v0.2.13).

    Args:
        config: Logging configuration

    Example:
        >>> config = LogConfig(level="DEBUG", format=LogFormat.JSON)
        >>> configure_logging(config)
    """
    root = logging.getLogger()
    root.setLevel(config.level)

    # Remove existing handlers
    root.handlers.clear()

    # Select formatter
    if config.format == LogFormat.JSON:
        formatter = JsonFormatter()
    elif config.format == LogFormat.SYSTEMD:
        formatter = logging.Formatter(SIMPLE_FORMAT_NO_TIME)
    elif config.level == "DEBUG":
        if config.color:
            formatter = ColorFormatter(DEBUG_FORMAT)
        else:
            formatter = logging.Formatter(DEBUG_FORMAT)
    elif config.color:
        formatter = ColorFormatter(SIMPLE_FORMAT)
    else:
        formatter = logging.Formatter(SIMPLE_FORMAT)

    # Configure handler based on output
    if config.output == "console":
        handler = logging.StreamHandler(sys.stderr)
    elif config.output == "file" and config.file_path:
        handler = logging.handlers.RotatingFileHandler(
            config.file_path,
            maxBytes=config.file_max_bytes,
            backupCount=config.file_backup_count,
        )
    elif config.output == "journald":
        try:
            from systemd.journal import JournalHandler

            handler = JournalHandler()
        except ImportError:
            # Fallback to console if systemd not available
            handler = logging.StreamHandler(sys.stderr)
            root.warning(
                "systemd.journal not available, falling back to console logging"
            )
    else:
        handler = logging.StreamHandler(sys.stderr)

    handler.setFormatter(formatter)
    root.addHandler(handler)
