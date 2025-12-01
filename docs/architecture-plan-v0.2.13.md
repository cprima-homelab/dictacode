# dictacode Architecture Plan v0.2.13 - Logging & Observability

## Status

### Phase 1: Structured Logging
- [ ] Standardize logging across all components
- [ ] Configure log levels (DEBUG, INFO, WARNING, ERROR)
- [ ] JSON log format option for parsing
- [ ] Consistent log message format

### Phase 2: Runtime Log Level Control
- [ ] Implement `--log-level` CLI flag
- [ ] Config file log level setting
- [ ] Runtime log level change via signal (SIGUSR1)
- [ ] Runtime log level change via API endpoint
- [ ] Temporary debug mode with auto-revert

### Phase 3: Log Destinations
- [ ] Console (stdout/stderr) with colors
- [ ] File logging with rotation
- [ ] Journald integration (systemd)
- [ ] Syslog support (optional)

### Phase 4: Prometheus Metrics (Optional)
- [ ] Add prometheus_client dependency (optional)
- [ ] Define standard metrics (requests, latency, errors)
- [ ] Expose `/metrics` endpoint (disabled by default)
- [ ] Document Prometheus scrape config

### Phase 5: Grafana Integration
- [ ] Create Grafana dashboard JSON
- [ ] Document Prometheus + Grafana setup
- [ ] Pre-built alerting rules
- [ ] Homelab integration guide

### Phase 6: Health & Status Endpoints
- [ ] `/health` endpoint for liveness
- [ ] `/ready` endpoint for readiness
- [ ] `/status` endpoint with detailed info
- [ ] Integration with monitoring tools

**v0.2.13 NOT STARTED**

---

## Prerequisites

v0.2.13 builds on top of:
- ✅ v0.2.5: Backend/CLI/API separation
- ✅ v0.2.9: Diagnostics system

---

## Problem Statement

### Current Logging State

Inconsistent logging across components:
- No standard log format
- No runtime log level control
- No structured logging for parsing
- No observability metrics
- Difficult troubleshooting without restart

### Goals

1. **Consistent logging** - Same format across all components
2. **Runtime control** - Change log level without restart
3. **Temporary debug** - Enable debug, auto-revert after timeout
4. **Observability** - Optional Prometheus metrics
5. **Homelab friendly** - Easy Grafana integration

---

## Design

### Log Levels & When to Use

| Level | When to Use | Example |
|-------|-------------|---------|
| DEBUG | Detailed troubleshooting | `Audio chunk received: 1024 bytes` |
| INFO | Normal operations | `Service started on port 9876` |
| WARNING | Recoverable issues | `Transcription timeout, retrying` |
| ERROR | Failures requiring attention | `Failed to connect to HID device` |
| CRITICAL | System cannot continue | `No audio devices found, exiting` |

### Logging Configuration

```python
# logging_config.py

import logging
import logging.handlers
import sys
import json
from dataclasses import dataclass
from typing import Optional
from enum import Enum
from pathlib import Path

class LogFormat(Enum):
    SIMPLE = "simple"      # Human-readable
    JSON = "json"          # Machine-parseable
    SYSTEMD = "systemd"    # No timestamp (journald adds it)

@dataclass
class LogConfig:
    """Logging configuration."""
    level: str = "INFO"
    format: LogFormat = LogFormat.SIMPLE
    output: str = "console"          # console, file, journald
    file_path: Optional[Path] = None
    file_max_bytes: int = 10_000_000  # 10MB
    file_backup_count: int = 5
    color: bool = True
    include_timestamp: bool = True
    include_source: bool = True       # module:line

# Format strings
SIMPLE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
SIMPLE_FORMAT_NO_TIME = "[%(levelname)s] %(name)s: %(message)s"
DEBUG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s"

class JsonFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
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

        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                log_data[key] = value

        return json.dumps(log_data)


class ColorFormatter(logging.Formatter):
    """Colored console formatter."""

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def configure_logging(config: LogConfig) -> None:
    """Configure logging based on config."""
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
        formatter = ColorFormatter(DEBUG_FORMAT) if config.color else logging.Formatter(DEBUG_FORMAT)
    else:
        formatter = ColorFormatter(SIMPLE_FORMAT) if config.color else logging.Formatter(SIMPLE_FORMAT)

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
            handler = logging.StreamHandler(sys.stderr)
    else:
        handler = logging.StreamHandler(sys.stderr)

    handler.setFormatter(formatter)
    root.addHandler(handler)
```

### Runtime Log Level Control

```python
# log_control.py

import logging
import signal
import threading
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class LogLevelController:
    """Runtime log level control with temporary debug mode."""

    def __init__(self):
        self._original_level: str = "INFO"
        self._debug_timer: Optional[threading.Timer] = None
        self._debug_until: Optional[datetime] = None

    def get_level(self) -> str:
        """Get current log level."""
        return logging.getLevelName(logging.getLogger().level)

    def set_level(self, level: str) -> None:
        """Set log level permanently."""
        self._original_level = level
        self._cancel_debug_timer()
        logging.getLogger().setLevel(level)
        logger.info(f"Log level set to {level}")

    def enable_debug(self, duration_seconds: int = 300) -> None:
        """
        Enable DEBUG level temporarily.

        Args:
            duration_seconds: Auto-revert after this many seconds (default: 5 min)
        """
        self._cancel_debug_timer()
        self._original_level = self.get_level()

        logging.getLogger().setLevel("DEBUG")
        self._debug_until = datetime.now() + timedelta(seconds=duration_seconds)

        logger.warning(
            f"DEBUG logging enabled for {duration_seconds}s "
            f"(until {self._debug_until.strftime('%H:%M:%S')})"
        )

        # Schedule auto-revert
        self._debug_timer = threading.Timer(
            duration_seconds,
            self._revert_from_debug,
        )
        self._debug_timer.daemon = True
        self._debug_timer.start()

    def disable_debug(self) -> None:
        """Disable debug mode and revert to original level."""
        self._revert_from_debug()

    def _revert_from_debug(self) -> None:
        """Revert from debug to original level."""
        self._cancel_debug_timer()
        if self.get_level() == "DEBUG":
            logging.getLogger().setLevel(self._original_level)
            logger.info(f"Debug mode ended, reverted to {self._original_level}")

    def _cancel_debug_timer(self) -> None:
        """Cancel pending debug timer."""
        if self._debug_timer:
            self._debug_timer.cancel()
            self._debug_timer = None
        self._debug_until = None

    def get_debug_remaining(self) -> Optional[int]:
        """Get seconds remaining in debug mode, or None."""
        if self._debug_until:
            remaining = (self._debug_until - datetime.now()).total_seconds()
            return max(0, int(remaining))
        return None

    def setup_signal_handler(self) -> None:
        """Setup SIGUSR1 to toggle debug mode."""
        def handler(signum, frame):
            if self.get_level() == "DEBUG":
                self.disable_debug()
            else:
                self.enable_debug()

        signal.signal(signal.SIGUSR1, handler)
        logger.debug("SIGUSR1 handler registered for debug toggle")


# Global instance
log_controller = LogLevelController()
```

### CLI Integration

```python
# cli.py additions

@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Set log level",
)
@click.option(
    "--log-format",
    type=click.Choice(["simple", "json", "systemd"], case_sensitive=False),
    default="simple",
    help="Log output format",
)
@click.option(
    "--log-file",
    type=click.Path(),
    default=None,
    help="Log to file instead of console",
)
def main(log_level, log_format, log_file, ...):
    config = LogConfig(
        level=log_level.upper(),
        format=LogFormat(log_format),
        output="file" if log_file else "console",
        file_path=Path(log_file) if log_file else None,
    )
    configure_logging(config)
```

### API Endpoints for Log Control

```python
# api.py additions

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/logging", tags=["logging"])

class LogLevelRequest(BaseModel):
    level: str
    duration_seconds: Optional[int] = None  # For temporary debug

class LogLevelResponse(BaseModel):
    level: str
    debug_mode: bool
    debug_remaining_seconds: Optional[int]

@router.get("/level")
async def get_log_level() -> LogLevelResponse:
    """Get current log level."""
    return LogLevelResponse(
        level=log_controller.get_level(),
        debug_mode=log_controller.get_level() == "DEBUG",
        debug_remaining_seconds=log_controller.get_debug_remaining(),
    )

@router.post("/level")
async def set_log_level(request: LogLevelRequest) -> LogLevelResponse:
    """Set log level (optionally temporary)."""
    if request.level.upper() == "DEBUG" and request.duration_seconds:
        log_controller.enable_debug(request.duration_seconds)
    else:
        log_controller.set_level(request.level.upper())

    return await get_log_level()

@router.post("/debug")
async def enable_debug(duration_seconds: int = 300) -> LogLevelResponse:
    """Enable debug mode temporarily."""
    log_controller.enable_debug(duration_seconds)
    return await get_log_level()

@router.delete("/debug")
async def disable_debug() -> LogLevelResponse:
    """Disable debug mode."""
    log_controller.disable_debug()
    return await get_log_level()
```

### CLI Commands for Runtime Control

```bash
# Enable debug for 5 minutes (default)
dictacode-stt-log debug

# Enable debug for 10 minutes
dictacode-stt-log debug --duration 600

# Disable debug
dictacode-stt-log debug --off

# Set log level permanently
dictacode-stt-log level INFO
dictacode-stt-log level DEBUG

# Check current level
dictacode-stt-log status

# Via signal (toggle debug)
kill -SIGUSR1 $(pidof dictacode-stt)
```

---

## Prometheus Metrics

### Metrics Definition

```python
# metrics.py

from typing import Optional
import time

# Optional import - metrics disabled if not installed
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        Info,
        start_http_server,
        REGISTRY,
        generate_latest,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

class Metrics:
    """Application metrics for Prometheus."""

    def __init__(self, enabled: bool = False, port: int = 9100):
        self.enabled = enabled and PROMETHEUS_AVAILABLE
        self.port = port

        if not self.enabled:
            return

        # Info metric
        self.info = Info(
            "dictacode",
            "Dictacode application info",
        )

        # Counters
        self.transcriptions_total = Counter(
            "dictacode_transcriptions_total",
            "Total transcription attempts",
            ["status", "transcriber"],  # success, error, timeout
        )

        self.hid_commands_total = Counter(
            "dictacode_hid_commands_total",
            "Total HID commands sent",
            ["type"],  # text, keypress, command
        )

        self.audio_chunks_total = Counter(
            "dictacode_audio_chunks_total",
            "Total audio chunks processed",
        )

        # Histograms
        self.transcription_duration = Histogram(
            "dictacode_transcription_duration_seconds",
            "Transcription duration in seconds",
            ["transcriber"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

        self.audio_buffer_duration = Histogram(
            "dictacode_audio_buffer_duration_seconds",
            "Audio buffer duration before transcription",
            buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
        )

        # Gauges
        self.audio_buffer_size = Gauge(
            "dictacode_audio_buffer_bytes",
            "Current audio buffer size in bytes",
        )

        self.link_healthy = Gauge(
            "dictacode_link_healthy",
            "HID link health (1=healthy, 0=unhealthy)",
        )

        self.active_connections = Gauge(
            "dictacode_active_connections",
            "Number of active transport connections",
        )

    def start_server(self) -> None:
        """Start metrics HTTP server."""
        if not self.enabled:
            return
        start_http_server(self.port)
        logger.info(f"Prometheus metrics available at http://localhost:{self.port}/metrics")

    def set_info(self, version: str, transcriber: str, transport: str) -> None:
        """Set application info."""
        if not self.enabled:
            return
        self.info.info({
            "version": version,
            "transcriber": transcriber,
            "transport": transport,
        })

    def record_transcription(
        self,
        status: str,
        transcriber: str,
        duration: float,
    ) -> None:
        """Record a transcription attempt."""
        if not self.enabled:
            return
        self.transcriptions_total.labels(status=status, transcriber=transcriber).inc()
        self.transcription_duration.labels(transcriber=transcriber).observe(duration)

    def record_hid_command(self, cmd_type: str) -> None:
        """Record HID command sent."""
        if not self.enabled:
            return
        self.hid_commands_total.labels(type=cmd_type).inc()

    def get_metrics(self) -> bytes:
        """Get metrics in Prometheus format."""
        if not self.enabled:
            return b""
        return generate_latest(REGISTRY)


# Global metrics instance (disabled by default)
metrics = Metrics(enabled=False)


def init_metrics(enabled: bool = False, port: int = 9100) -> None:
    """Initialize metrics collection."""
    global metrics
    metrics = Metrics(enabled=enabled, port=port)
    if enabled:
        metrics.start_server()
```

### Metrics API Endpoint

```python
# api.py

from fastapi import Response

@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint."""
    if not metrics.enabled:
        return Response(
            content="Metrics not enabled. Start with --metrics flag.",
            status_code=404,
        )
    return Response(
        content=metrics.get_metrics(),
        media_type="text/plain",
    )
```

### Configuration

```ini
# /etc/dictacode/stt.conf

[logging]
level = INFO
format = simple          # simple, json, systemd
output = journald        # console, file, journald
# file = /var/log/dictacode/stt.log
# file_max_mb = 10
# file_backups = 5

[metrics]
enabled = false          # Enable Prometheus metrics
port = 9100              # Metrics HTTP port
```

```bash
# CLI flags
dictacode-stt --log-level DEBUG --log-format json
dictacode-stt --metrics --metrics-port 9100
```

---

## Prometheus & Grafana Integration

### Prometheus Scrape Config

```yaml
# /etc/prometheus/prometheus.yml (addition)

scrape_configs:
  - job_name: 'dictacode'
    static_configs:
      - targets:
          - 'dictacode-pi5:9100'   # STT metrics
          - 'dictacode-pi0:9100'   # HID metrics (if enabled)
    scrape_interval: 15s
    metrics_path: /metrics
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "Dictacode - Speech to Text",
    "uid": "dictacode-stt",
    "panels": [
      {
        "title": "Transcriptions per Minute",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(dictacode_transcriptions_total[1m])",
            "legendFormat": "{{status}}"
          }
        ]
      },
      {
        "title": "Transcription Latency (p95)",
        "type": "gauge",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(dictacode_transcription_duration_seconds_bucket[5m]))"
          }
        ]
      },
      {
        "title": "HID Link Health",
        "type": "stat",
        "targets": [
          {
            "expr": "dictacode_link_healthy"
          }
        ],
        "mappings": [
          {"value": 1, "text": "Healthy", "color": "green"},
          {"value": 0, "text": "Unhealthy", "color": "red"}
        ]
      },
      {
        "title": "Audio Buffer Size",
        "type": "graph",
        "targets": [
          {
            "expr": "dictacode_audio_buffer_bytes"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "stat",
        "targets": [
          {
            "expr": "rate(dictacode_transcriptions_total{status=\"error\"}[5m]) / rate(dictacode_transcriptions_total[5m]) * 100"
          }
        ],
        "unit": "percent"
      }
    ]
  }
}
```

### Alerting Rules

```yaml
# /etc/prometheus/rules/dictacode.yml

groups:
  - name: dictacode
    rules:
      - alert: DictacodeHIDLinkDown
        expr: dictacode_link_healthy == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Dictacode HID link is down"
          description: "The link between STT and HID has been unhealthy for more than 1 minute."

      - alert: DictacodeHighErrorRate
        expr: rate(dictacode_transcriptions_total{status="error"}[5m]) / rate(dictacode_transcriptions_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Dictacode error rate > 10%"
          description: "Transcription error rate has been above 10% for 5 minutes."

      - alert: DictacodeHighLatency
        expr: histogram_quantile(0.95, rate(dictacode_transcription_duration_seconds_bucket[5m])) > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Dictacode transcription latency high"
          description: "95th percentile transcription latency is above 5 seconds."

      - alert: DictacodeServiceDown
        expr: up{job="dictacode"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Dictacode service is down"
          description: "Prometheus cannot scrape dictacode metrics."
```

---

## Health Endpoints

```python
# health.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime

router = APIRouter(tags=["health"])

class HealthResponse(BaseModel):
    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    checks: Dict[str, bool]

class ReadinessResponse(BaseModel):
    ready: bool
    checks: Dict[str, bool]

class StatusResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    components: Dict[str, Any]

# Startup time
_start_time = datetime.now()

@router.get("/health")
async def health_check() -> HealthResponse:
    """
    Liveness probe - is the service running?
    Use for Kubernetes liveness probe or load balancer health check.
    """
    checks = {
        "service_running": True,
    }
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        checks=checks,
    )

@router.get("/ready")
async def readiness_check() -> ReadinessResponse:
    """
    Readiness probe - is the service ready to accept requests?
    Use for Kubernetes readiness probe.
    """
    checks = {
        "audio_device": audio_port_manager.get_default_port() is not None,
        "transcriber": transcriber.is_available(),
        "transport": transport.is_connected(),
    }
    return ReadinessResponse(
        ready=all(checks.values()),
        checks=checks,
    )

@router.get("/status")
async def detailed_status() -> StatusResponse:
    """
    Detailed status for debugging and monitoring.
    """
    uptime = (datetime.now() - _start_time).total_seconds()

    return StatusResponse(
        status="running",
        version=__version__,
        uptime_seconds=uptime,
        components={
            "audio": {
                "port": audio_port_manager.get_active_port().port_id if audio_port_manager.get_active_port() else None,
                "streaming": audio_source.is_active() if audio_source else False,
            },
            "transcriber": {
                "name": transcriber.get_name(),
                "available": transcriber.is_available(),
                "streaming": transcriber.is_streaming() if hasattr(transcriber, "is_streaming") else False,
            },
            "transport": {
                "type": transport.get_name(),
                "status": transport.get_status().value,
                "connected": transport.is_connected(),
            },
            "logging": {
                "level": log_controller.get_level(),
                "debug_mode": log_controller.get_level() == "DEBUG",
                "debug_remaining": log_controller.get_debug_remaining(),
            },
        },
    )
```

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── logging_config.py             # NEW: Logging configuration
├── log_control.py                # NEW: Runtime log level control
├── metrics.py                    # NEW: Prometheus metrics
├── health.py                     # NEW: Health endpoints
├── cli.py                        # MODIFIED: Add logging flags
├── api.py                        # MODIFIED: Add logging/metrics endpoints
└── ...

ops/grafana/
├── dashboards/
│   └── dictacode.json            # NEW: Grafana dashboard
└── provisioning/
    └── dashboards.yaml           # NEW: Dashboard provisioning

ops/prometheus/
├── prometheus.yml                # NEW: Prometheus config example
└── rules/
    └── dictacode.yml             # NEW: Alerting rules

docs/
└── observability.md              # NEW: Setup guide
```

---

## Files to Create/Modify

1. `apps/stt/src/dictacode_stt/logging_config.py` - NEW: Logging setup
2. `apps/stt/src/dictacode_stt/log_control.py` - NEW: Runtime control
3. `apps/stt/src/dictacode_stt/metrics.py` - NEW: Prometheus metrics
4. `apps/stt/src/dictacode_stt/health.py` - NEW: Health endpoints
5. `apps/stt/src/dictacode_stt/cli.py` - Add logging flags
6. `apps/stt/src/dictacode_stt/api.py` - Add logging/metrics endpoints
7. `apps/stt/pyproject.toml` - Add prometheus_client as optional dep
8. `apps/hid/src/dictacode_hid/logging_config.py` - NEW: Same for HID
9. `ops/grafana/dashboards/dictacode.json` - NEW: Grafana dashboard
10. `ops/prometheus/prometheus.yml` - NEW: Example config
11. `ops/prometheus/rules/dictacode.yml` - NEW: Alert rules
12. `docs/observability.md` - NEW: Setup documentation

---

## CLI Summary

```bash
# Logging flags
dictacode-stt --log-level DEBUG
dictacode-stt --log-level INFO --log-format json
dictacode-stt --log-file /var/log/dictacode/stt.log

# Enable metrics
dictacode-stt --metrics
dictacode-stt --metrics --metrics-port 9100

# Runtime log control
dictacode-stt-log debug                    # Enable debug for 5 min
dictacode-stt-log debug --duration 600     # Enable debug for 10 min
dictacode-stt-log debug --off              # Disable debug
dictacode-stt-log level WARNING            # Set level permanently
dictacode-stt-log status                   # Show current level

# Via signal
kill -SIGUSR1 $(pidof dictacode-stt)       # Toggle debug mode

# Via API
curl -X POST localhost:8080/api/logging/debug?duration_seconds=300
curl -X DELETE localhost:8080/api/logging/debug
curl localhost:8080/api/logging/level
```

---

## Success Criteria

v0.2.13 is complete when:

1. ✅ Consistent logging format across all components
2. ✅ `--log-level` and `--log-format` CLI flags work
3. ✅ JSON log format available for parsing
4. ✅ File logging with rotation works
5. ✅ Runtime log level change via API endpoint
6. ✅ Temporary debug mode with auto-revert
7. ✅ SIGUSR1 toggles debug mode
8. ✅ `dictacode-stt-log` CLI commands work
9. ✅ Prometheus metrics (optional, disabled by default)
10. ✅ `/metrics` endpoint exposes Prometheus format
11. ✅ `/health`, `/ready`, `/status` endpoints work
12. ✅ Grafana dashboard JSON available
13. ✅ Prometheus alerting rules documented
14. ✅ Observability setup guide in docs

---

## Out of Scope (v0.2.13)

- Distributed tracing (OpenTelemetry)
- Log aggregation (Loki, ELK)
- Custom metric exporters
- Real-time log streaming via WebSocket
- Log encryption
- Audit logging
