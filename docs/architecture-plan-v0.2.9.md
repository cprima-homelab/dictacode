# dictacode Architecture Plan v0.2.9 - Unified Diagnostics & Bug Reports

## Status

### Phase 1: Diagnostics Backend Service ✅ COMPLETE
- [x] Create `diagnostics/` package with unified backend
- [x] Define `DiagnosticCheck`, `DiagnosticResult`, `SystemReport` types
- [x] Extract existing CLI diagnostics to backend methods
- [x] Unit tests for diagnostic types

### Phase 2: Check Registry ✅ COMPLETE
- [x] Implement `DiagnosticRegistry` for check registration
- [x] Categorize checks: audio, whisper, transport, hid, system
- [x] Support check dependencies (e.g., transport before hid)
- [x] Async check execution with timeouts

### Phase 3: CLI Integration ✅ COMPLETE
- [x] Refactor `dictacode-stt-diagnose` to use backend
- [x] Refactor `dictacode-stt-check` (quick health check)
- [x] Add `--json` output for all diagnostic commands
- [x] Add `--category` filter for specific checks

### Phase 4: API Integration ✅ COMPLETE
- [x] Add `/api/diagnostics/run` endpoint
- [x] Add `/api/diagnostics/status` endpoint
- [x] Add `/api/diagnostics/checks` endpoint
- [x] Add `/api/diagnostics/categories` endpoint
- [ ] WebSocket for real-time check progress (optional, deferred)

### Phase 5: Bug Report Generation ✅ COMPLETE
- [x] Implement `BugReportGenerator` class
- [x] Collect system info, logs, config, diagnostic results
- [x] Redact sensitive data (API keys, passwords)
- [x] Generate shareable report (JSON + text summary)
- [x] Add `dictacode-stt-bugreport` command

### Phase 6: Report Submission Helper ✅ COMPLETE
- [x] Add GitHub issue template integration
- [x] Generate markdown for GitHub issues
- [x] Optional: direct submission via `gh` CLI

**v0.2.9 COMPLETE** ✅

---

## Prerequisites

v0.2.9 builds on top of:
- ✅ v0.2.2: Basic diagnostics (whisper, audio checks)
- ✅ v0.2.5: Backend/CLI/API separation
- ✅ v0.2.6: TranscriptionAdapter (adapter-agnostic checks)
- ✅ v0.2.8: TransportAdapter (transport-agnostic checks)

---

## Problem Statement

### Current Diagnostics Limitations

Diagnostics are CLI-only and scattered:

```python
# Current: CLI-embedded logic
def cmd_diagnose():
    print("Checking whisper...")
    # Business logic mixed with presentation
    if check_whisper_binary():
        print("✓ Whisper OK")
    else:
        print("✗ Whisper not found")
```

**Issues:**
- Diagnostics logic embedded in CLI
- Can't run diagnostics from web UI (v0.3.0)
- No structured output for programmatic use
- No comprehensive bug report generation
- Users report issues with incomplete information

### Bug Report Problem

When users report issues, they often provide:
- "It doesn't work" (no details)
- Incomplete logs
- Missing system information
- No diagnostic results

**Goal:** Unified diagnostics backend + automated bug report generation.

---

## Design

### Diagnostic Types

```python
# diagnostics/types.py

from dataclasses import dataclass, field
from typing import Optional, List, Any
from enum import Enum
from datetime import datetime

class CheckStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"

class CheckCategory(Enum):
    SYSTEM = "system"       # OS, Python, dependencies
    AUDIO = "audio"         # Audio devices, recording
    TRANSCRIPTION = "transcription"  # Whisper, Vosk, etc.
    TRANSPORT = "transport" # UART, WiFi connection
    HID = "hid"             # HID device status
    CONFIG = "config"       # Configuration files

class CheckSeverity(Enum):
    INFO = "info"           # Informational
    WARNING = "warning"     # May cause issues
    CRITICAL = "critical"   # Will prevent operation

@dataclass
class DiagnosticResult:
    """Result of a single diagnostic check."""
    check_id: str
    name: str
    category: CheckCategory
    status: CheckStatus
    message: str
    details: Optional[dict] = None
    severity: CheckSeverity = CheckSeverity.INFO
    duration_ms: Optional[int] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "category": self.category.value,
            "status": self.status.value,
            "message": self.message,
            "details": self.details,
            "severity": self.severity.value,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
        }

@dataclass
class SystemReport:
    """Comprehensive system status report."""
    report_id: str
    generated_at: datetime
    version: str
    platform: dict
    diagnostics: List[DiagnosticResult]
    logs: dict
    config: dict
    summary: dict

    def to_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "version": self.version,
            "platform": self.platform,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "logs": self.logs,
            "config": self.config,
            "summary": self.summary,
        }
```

### Diagnostic Check Interface

```python
# diagnostics/check.py

from abc import ABC, abstractmethod
from typing import List, Optional

class DiagnosticCheck(ABC):
    """Base class for diagnostic checks."""

    @property
    @abstractmethod
    def check_id(self) -> str:
        """Unique identifier for this check."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name."""
        pass

    @property
    @abstractmethod
    def category(self) -> CheckCategory:
        """Check category."""
        pass

    @property
    def dependencies(self) -> List[str]:
        """List of check_ids that must pass first."""
        return []

    @property
    def timeout_ms(self) -> int:
        """Maximum execution time."""
        return 5000

    @abstractmethod
    def run(self) -> DiagnosticResult:
        """Execute the diagnostic check."""
        pass

    def skip_reason(self) -> Optional[str]:
        """Return reason to skip, or None to run."""
        return None
```

### Built-in Checks

```python
# diagnostics/checks/system.py

class PythonVersionCheck(DiagnosticCheck):
    check_id = "system.python_version"
    name = "Python Version"
    category = CheckCategory.SYSTEM

    def run(self) -> DiagnosticResult:
        import sys
        version = sys.version_info
        ok = version >= (3, 9)
        return DiagnosticResult(
            check_id=self.check_id,
            name=self.name,
            category=self.category,
            status=CheckStatus.PASSED if ok else CheckStatus.FAILED,
            message=f"Python {version.major}.{version.minor}.{version.micro}",
            details={"version": list(version[:3]), "required": [3, 9]},
            severity=CheckSeverity.CRITICAL if not ok else CheckSeverity.INFO,
        )

class DiskSpaceCheck(DiagnosticCheck):
    check_id = "system.disk_space"
    name = "Disk Space"
    category = CheckCategory.SYSTEM

    def run(self) -> DiagnosticResult:
        import shutil
        usage = shutil.disk_usage("/")
        free_gb = usage.free / (1024**3)
        ok = free_gb > 1.0  # At least 1GB free
        return DiagnosticResult(
            check_id=self.check_id,
            name=self.name,
            category=self.category,
            status=CheckStatus.PASSED if ok else CheckStatus.WARNING,
            message=f"{free_gb:.1f} GB free",
            details={
                "total_gb": usage.total / (1024**3),
                "used_gb": usage.used / (1024**3),
                "free_gb": free_gb,
            },
            severity=CheckSeverity.WARNING if not ok else CheckSeverity.INFO,
        )

# diagnostics/checks/audio.py

class AudioDeviceCheck(DiagnosticCheck):
    check_id = "audio.devices"
    name = "Audio Devices"
    category = CheckCategory.AUDIO

    def run(self) -> DiagnosticResult:
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d["max_input_channels"] > 0]

            if not input_devices:
                return DiagnosticResult(
                    check_id=self.check_id,
                    name=self.name,
                    category=self.category,
                    status=CheckStatus.FAILED,
                    message="No audio input devices found",
                    severity=CheckSeverity.CRITICAL,
                )

            return DiagnosticResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASSED,
                message=f"{len(input_devices)} input device(s) found",
                details={"devices": [d["name"] for d in input_devices]},
            )
        except Exception as e:
            return DiagnosticResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.ERROR,
                message=str(e),
                severity=CheckSeverity.CRITICAL,
            )

# diagnostics/checks/transcription.py

class TranscriberAvailableCheck(DiagnosticCheck):
    check_id = "transcription.available"
    name = "Transcriber Available"
    category = CheckCategory.TRANSCRIPTION

    def __init__(self, transcriber: TranscriptionAdapter):
        self.transcriber = transcriber

    def run(self) -> DiagnosticResult:
        available = self.transcriber.is_available()
        name = self.transcriber.get_name()

        return DiagnosticResult(
            check_id=self.check_id,
            name=self.name,
            category=self.category,
            status=CheckStatus.PASSED if available else CheckStatus.FAILED,
            message=f"{name}: {'available' if available else 'not available'}",
            details={"transcriber": name, "available": available},
            severity=CheckSeverity.CRITICAL if not available else CheckSeverity.INFO,
        )

# diagnostics/checks/transport.py

class TransportConnectionCheck(DiagnosticCheck):
    check_id = "transport.connection"
    name = "Transport Connection"
    category = CheckCategory.TRANSPORT
    dependencies = ["system.python_version"]

    def __init__(self, transport: TransportAdapter):
        self.transport = transport

    def run(self) -> DiagnosticResult:
        try:
            connected = self.transport.connect()
            status = self.transport.get_status()

            if connected:
                self.transport.disconnect()

            return DiagnosticResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.PASSED if connected else CheckStatus.FAILED,
                message=f"{self.transport.get_name()}: {status.value}",
                details={
                    "transport": self.transport.get_name(),
                    "connected": connected,
                },
                severity=CheckSeverity.CRITICAL if not connected else CheckSeverity.INFO,
            )
        except Exception as e:
            return DiagnosticResult(
                check_id=self.check_id,
                name=self.name,
                category=self.category,
                status=CheckStatus.ERROR,
                message=str(e),
                severity=CheckSeverity.CRITICAL,
            )
```

### Diagnostic Registry

```python
# diagnostics/registry.py

from typing import List, Optional, Dict
import time

class DiagnosticRegistry:
    """Registry and runner for diagnostic checks."""

    def __init__(self):
        self._checks: Dict[str, DiagnosticCheck] = {}
        self._results: Dict[str, DiagnosticResult] = {}

    def register(self, check: DiagnosticCheck) -> None:
        """Register a diagnostic check."""
        self._checks[check.check_id] = check

    def register_defaults(self) -> None:
        """Register built-in checks."""
        from .checks import system, audio, transcription, transport

        self.register(system.PythonVersionCheck())
        self.register(system.DiskSpaceCheck())
        self.register(system.MemoryCheck())
        self.register(audio.AudioDeviceCheck())
        self.register(audio.AudioRecordingCheck())
        # Transcription and transport checks added dynamically
        # based on configured adapters

    def get_checks(
        self,
        category: Optional[CheckCategory] = None,
    ) -> List[DiagnosticCheck]:
        """Get checks, optionally filtered by category."""
        checks = list(self._checks.values())
        if category:
            checks = [c for c in checks if c.category == category]
        return checks

    def run_all(
        self,
        category: Optional[CheckCategory] = None,
        on_progress: Optional[Callable[[DiagnosticResult], None]] = None,
    ) -> List[DiagnosticResult]:
        """Run all checks with dependency resolution."""
        checks = self.get_checks(category)
        results = []

        # Topological sort by dependencies
        ordered = self._resolve_dependencies(checks)

        for check in ordered:
            # Check if dependencies passed
            skip_reason = self._check_dependencies(check)
            if skip_reason:
                result = DiagnosticResult(
                    check_id=check.check_id,
                    name=check.name,
                    category=check.category,
                    status=CheckStatus.SKIPPED,
                    message=skip_reason,
                )
            else:
                result = self._run_check(check)

            self._results[check.check_id] = result
            results.append(result)

            if on_progress:
                on_progress(result)

        return results

    def _run_check(self, check: DiagnosticCheck) -> DiagnosticResult:
        """Run a single check with timeout."""
        start = time.monotonic()
        try:
            result = check.run()
            result.duration_ms = int((time.monotonic() - start) * 1000)
            return result
        except Exception as e:
            return DiagnosticResult(
                check_id=check.check_id,
                name=check.name,
                category=check.category,
                status=CheckStatus.ERROR,
                message=f"Check failed: {e}",
                duration_ms=int((time.monotonic() - start) * 1000),
            )

    def _check_dependencies(self, check: DiagnosticCheck) -> Optional[str]:
        """Check if dependencies passed."""
        for dep_id in check.dependencies:
            if dep_id not in self._results:
                return f"Dependency not run: {dep_id}"
            if self._results[dep_id].status not in (CheckStatus.PASSED, CheckStatus.WARNING):
                return f"Dependency failed: {dep_id}"
        return None

    def get_summary(self) -> dict:
        """Get summary of check results."""
        results = list(self._results.values())
        return {
            "total": len(results),
            "passed": len([r for r in results if r.status == CheckStatus.PASSED]),
            "warnings": len([r for r in results if r.status == CheckStatus.WARNING]),
            "failed": len([r for r in results if r.status == CheckStatus.FAILED]),
            "errors": len([r for r in results if r.status == CheckStatus.ERROR]),
            "skipped": len([r for r in results if r.status == CheckStatus.SKIPPED]),
        }
```

### Bug Report Generator

```python
# diagnostics/bugreport.py

import platform
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

class BugReportGenerator:
    """Generate comprehensive bug reports for issue submission."""

    SENSITIVE_KEYS = ["api_key", "password", "secret", "token", "credential"]
    LOG_LINES = 500  # Last N lines of logs

    def __init__(
        self,
        registry: DiagnosticRegistry,
        log_dir: Path = Path("/var/log/dictacode"),
        config_dir: Path = Path("/etc/dictacode"),
    ):
        self.registry = registry
        self.log_dir = log_dir
        self.config_dir = config_dir

    def generate(self) -> SystemReport:
        """Generate a complete bug report."""
        report_id = str(uuid.uuid4())[:8]

        # Run all diagnostics
        diagnostics = self.registry.run_all()

        # Collect system info
        platform_info = self._collect_platform_info()

        # Collect logs (redacted)
        logs = self._collect_logs()

        # Collect config (redacted)
        config = self._collect_config()

        # Generate summary
        summary = self._generate_summary(diagnostics)

        return SystemReport(
            report_id=report_id,
            generated_at=datetime.now(),
            version=self._get_version(),
            platform=platform_info,
            diagnostics=diagnostics,
            logs=logs,
            config=config,
            summary=summary,
        )

    def _collect_platform_info(self) -> dict:
        """Collect system/platform information."""
        return {
            "os": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
            "kernel": self._run_cmd("uname -r"),
            "uptime": self._run_cmd("uptime -p"),
            "memory": self._get_memory_info(),
            "disk": self._get_disk_info(),
        }

    def _collect_logs(self) -> dict:
        """Collect recent logs (redacted)."""
        logs = {}

        # journalctl logs
        for service in ["dictacode-stt", "dictacode-hid"]:
            output = self._run_cmd(
                f"journalctl -u {service} --no-pager -n {self.LOG_LINES}"
            )
            logs[service] = self._redact(output)

        # File-based logs
        if self.log_dir.exists():
            for log_file in self.log_dir.glob("*.log"):
                content = self._read_tail(log_file, self.LOG_LINES)
                logs[log_file.name] = self._redact(content)

        return logs

    def _collect_config(self) -> dict:
        """Collect configuration (redacted)."""
        config = {}

        if self.config_dir.exists():
            for conf_file in self.config_dir.rglob("*.conf"):
                rel_path = conf_file.relative_to(self.config_dir)
                content = conf_file.read_text()
                config[str(rel_path)] = self._redact(content)

        return config

    def _redact(self, text: str) -> str:
        """Redact sensitive information."""
        if not text:
            return text

        lines = text.split("\n")
        redacted_lines = []

        for line in lines:
            lower = line.lower()
            for key in self.SENSITIVE_KEYS:
                if key in lower:
                    # Redact value after = or :
                    if "=" in line:
                        parts = line.split("=", 1)
                        line = f"{parts[0]}=[REDACTED]"
                    elif ":" in line:
                        parts = line.split(":", 1)
                        line = f"{parts[0]}: [REDACTED]"
            redacted_lines.append(line)

        return "\n".join(redacted_lines)

    def _generate_summary(self, diagnostics: List[DiagnosticResult]) -> dict:
        """Generate human-readable summary."""
        failed = [d for d in diagnostics if d.status == CheckStatus.FAILED]
        warnings = [d for d in diagnostics if d.status == CheckStatus.WARNING]

        summary = {
            "status": "healthy" if not failed else "unhealthy",
            "checks_passed": len([d for d in diagnostics if d.status == CheckStatus.PASSED]),
            "checks_failed": len(failed),
            "checks_warning": len(warnings),
            "critical_issues": [
                f"{d.name}: {d.message}"
                for d in diagnostics
                if d.severity == CheckSeverity.CRITICAL and d.status == CheckStatus.FAILED
            ],
            "warnings": [
                f"{d.name}: {d.message}"
                for d in warnings
            ],
        }

        return summary

    def to_markdown(self, report: SystemReport) -> str:
        """Generate markdown for GitHub issue."""
        md = []
        md.append(f"# Bug Report {report.report_id}")
        md.append(f"\n**Generated:** {report.generated_at.isoformat()}")
        md.append(f"**Version:** {report.version}")

        # Summary
        md.append("\n## Summary")
        md.append(f"- Status: **{report.summary['status']}**")
        md.append(f"- Checks Passed: {report.summary['checks_passed']}")
        md.append(f"- Checks Failed: {report.summary['checks_failed']}")

        if report.summary["critical_issues"]:
            md.append("\n### Critical Issues")
            for issue in report.summary["critical_issues"]:
                md.append(f"- ❌ {issue}")

        if report.summary["warnings"]:
            md.append("\n### Warnings")
            for warning in report.summary["warnings"]:
                md.append(f"- ⚠️ {warning}")

        # Platform
        md.append("\n## System Information")
        md.append("```")
        md.append(f"OS: {report.platform['os']} {report.platform['os_release']}")
        md.append(f"Kernel: {report.platform.get('kernel', 'N/A')}")
        md.append(f"Machine: {report.platform['machine']}")
        md.append(f"Python: {report.platform['python_version']}")
        md.append("```")

        # Diagnostic Results
        md.append("\n## Diagnostic Results")
        md.append("\n| Check | Status | Message |")
        md.append("|-------|--------|---------|")
        for diag in report.diagnostics:
            status_icon = {
                "passed": "✅",
                "warning": "⚠️",
                "failed": "❌",
                "error": "💥",
                "skipped": "⏭️",
            }.get(diag.status.value, "❓")
            md.append(f"| {diag.name} | {status_icon} {diag.status.value} | {diag.message} |")

        # Logs (collapsible)
        md.append("\n## Logs")
        md.append("\n<details>")
        md.append("<summary>Click to expand logs</summary>\n")
        for name, content in report.logs.items():
            md.append(f"### {name}")
            md.append("```")
            # Truncate very long logs
            lines = content.split("\n")
            if len(lines) > 100:
                md.append("\n".join(lines[:50]))
                md.append(f"\n... ({len(lines) - 100} lines omitted) ...\n")
                md.append("\n".join(lines[-50:]))
            else:
                md.append(content)
            md.append("```\n")
        md.append("</details>")

        return "\n".join(md)

    def _run_cmd(self, cmd: str) -> str:
        """Run shell command and return output."""
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def _read_tail(self, path: Path, lines: int) -> str:
        """Read last N lines of a file."""
        try:
            with open(path) as f:
                return "".join(f.readlines()[-lines:])
        except Exception:
            return ""

    def _get_version(self) -> str:
        """Get dictacode version."""
        try:
            from dictacode_stt import __version__
            return __version__
        except Exception:
            return "unknown"

    def _get_memory_info(self) -> dict:
        """Get memory information."""
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            info = {}
            for line in lines[:5]:
                key, val = line.split(":")
                info[key.strip()] = val.strip()
            return info
        except Exception:
            return {}

    def _get_disk_info(self) -> dict:
        """Get disk information."""
        import shutil
        try:
            usage = shutil.disk_usage("/")
            return {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
            }
        except Exception:
            return {}
```

---

## CLI Integration

```python
# cli.py

def cmd_diagnose(args):
    """Run full diagnostics."""
    registry = DiagnosticRegistry()
    registry.register_defaults()

    # Add adapter-specific checks
    if args.transcriber:
        transcriber = get_transcriber(args.transcriber)
        registry.register(TranscriberAvailableCheck(transcriber))

    # Filter by category
    category = CheckCategory(args.category) if args.category else None

    # Progress callback for CLI
    def on_progress(result: DiagnosticResult):
        icon = {"passed": "✓", "warning": "!", "failed": "✗", "error": "E", "skipped": "-"}
        print(f"  [{icon.get(result.status.value, '?')}] {result.name}: {result.message}")

    print("Running diagnostics...\n")
    results = registry.run_all(category=category, on_progress=on_progress)

    # Summary
    summary = registry.get_summary()
    print(f"\nSummary: {summary['passed']} passed, {summary['failed']} failed, {summary['warnings']} warnings")

    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=2))

    return 0 if summary["failed"] == 0 else 1


def cmd_check(args):
    """Quick health check (critical checks only)."""
    registry = DiagnosticRegistry()
    registry.register_defaults()

    # Only run critical checks
    critical_ids = ["system.python_version", "audio.devices", "transcription.available"]
    results = []

    for check_id in critical_ids:
        check = registry._checks.get(check_id)
        if check:
            results.append(registry._run_check(check))

    all_passed = all(r.status == CheckStatus.PASSED for r in results)
    print("OK" if all_passed else "FAIL")
    return 0 if all_passed else 1


def cmd_bugreport(args):
    """Generate bug report."""
    registry = DiagnosticRegistry()
    registry.register_defaults()

    generator = BugReportGenerator(registry)
    report = generator.generate()

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(f"dictacode-bugreport-{report.report_id}.json")

    # Save JSON report
    with open(output_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)
    print(f"Bug report saved: {output_path}")

    # Save markdown for GitHub
    md_path = output_path.with_suffix(".md")
    with open(md_path, "w") as f:
        f.write(generator.to_markdown(report))
    print(f"Markdown report: {md_path}")

    # Summary
    print(f"\nReport ID: {report.report_id}")
    print(f"Status: {report.summary['status']}")
    if report.summary["critical_issues"]:
        print("\nCritical Issues:")
        for issue in report.summary["critical_issues"]:
            print(f"  - {issue}")

    print("\nTo submit a bug report:")
    print(f"  1. Open: https://github.com/cprima-homelab/dictacode/issues/new")
    print(f"  2. Paste contents of: {md_path}")

    return 0
```

### CLI Commands

```bash
# Full diagnostics (human-readable)
dictacode-stt-diagnose
Running diagnostics...

  [✓] Python Version: Python 3.11.2
  [✓] Disk Space: 12.4 GB free
  [✓] Audio Devices: 2 input device(s) found
  [✓] Transcriber Available: whisper: available
  [✓] Transport Connection: uart: connected

Summary: 5 passed, 0 failed, 0 warnings

# Diagnostics with JSON output
dictacode-stt-diagnose --json

# Filter by category
dictacode-stt-diagnose --category audio

# Quick health check (exit code 0/1)
dictacode-stt-check
OK

# Generate bug report
dictacode-stt-bugreport
Bug report saved: dictacode-bugreport-a1b2c3d4.json
Markdown report: dictacode-bugreport-a1b2c3d4.md

Report ID: a1b2c3d4
Status: unhealthy

Critical Issues:
  - Transcriber Available: whisper: not available

To submit a bug report:
  1. Open: https://github.com/cprima-homelab/dictacode/issues/new
  2. Paste contents of: dictacode-bugreport-a1b2c3d4.md

# Bug report to specific file
dictacode-stt-bugreport --output /tmp/report.json
```

---

## API Integration

```python
# api.py

from fastapi import APIRouter, BackgroundTasks
from typing import Optional

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])

# Shared registry instance
_registry: Optional[DiagnosticRegistry] = None

def get_registry() -> DiagnosticRegistry:
    global _registry
    if _registry is None:
        _registry = DiagnosticRegistry()
        _registry.register_defaults()
    return _registry

@router.get("/checks")
async def list_checks(category: Optional[str] = None):
    """List available diagnostic checks."""
    registry = get_registry()
    cat = CheckCategory(category) if category else None
    checks = registry.get_checks(category=cat)
    return {
        "checks": [
            {
                "check_id": c.check_id,
                "name": c.name,
                "category": c.category.value,
                "dependencies": c.dependencies,
            }
            for c in checks
        ]
    }

@router.post("/run")
async def run_diagnostics(category: Optional[str] = None):
    """Run diagnostic checks."""
    registry = get_registry()
    cat = CheckCategory(category) if category else None
    results = registry.run_all(category=cat)
    return {
        "results": [r.to_dict() for r in results],
        "summary": registry.get_summary(),
    }

@router.get("/status")
async def get_status():
    """Get quick health status."""
    registry = get_registry()
    # Run only critical checks
    results = registry.run_all()
    summary = registry.get_summary()
    return {
        "healthy": summary["failed"] == 0,
        "summary": summary,
    }

@router.post("/report")
async def generate_report():
    """Generate full bug report."""
    registry = get_registry()
    generator = BugReportGenerator(registry)
    report = generator.generate()
    return report.to_dict()

@router.get("/report/{report_id}/markdown")
async def get_report_markdown(report_id: str):
    """Get markdown version of report for GitHub issue."""
    # Would need to cache reports or regenerate
    registry = get_registry()
    generator = BugReportGenerator(registry)
    report = generator.generate()
    return {"markdown": generator.to_markdown(report)}
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/diagnostics/checks` | List available checks |
| POST | `/api/diagnostics/run` | Run all diagnostics |
| GET | `/api/diagnostics/status` | Quick health check |
| POST | `/api/diagnostics/report` | Generate bug report |
| GET | `/api/diagnostics/report/{id}/markdown` | Get markdown report |

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── diagnostics/                  # Unified diagnostics package
│   ├── __init__.py               # Public exports
│   ├── types.py                  # DiagnosticResult, SystemReport, etc.
│   ├── check.py                  # DiagnosticCheck ABC
│   ├── registry.py               # DiagnosticRegistry
│   ├── bugreport.py              # BugReportGenerator
│   └── checks/                   # Built-in checks
│       ├── __init__.py
│       ├── system.py             # Python, disk, memory
│       ├── audio.py              # Audio devices, recording
│       ├── transcription.py      # Transcriber availability
│       ├── transport.py          # Connection checks
│       └── config.py             # Config file validation
├── cli.py                        # Add diagnose, check, bugreport commands
├── api.py                        # Add /diagnostics endpoints
└── ...
```

---

## Files to Modify

1. `apps/stt/src/dictacode_stt/diagnostics/__init__.py` - NEW: Package exports
2. `apps/stt/src/dictacode_stt/diagnostics/types.py` - NEW: Types
3. `apps/stt/src/dictacode_stt/diagnostics/check.py` - NEW: DiagnosticCheck ABC
4. `apps/stt/src/dictacode_stt/diagnostics/registry.py` - NEW: DiagnosticRegistry
5. `apps/stt/src/dictacode_stt/diagnostics/bugreport.py` - NEW: BugReportGenerator
6. `apps/stt/src/dictacode_stt/diagnostics/checks/system.py` - NEW: System checks
7. `apps/stt/src/dictacode_stt/diagnostics/checks/audio.py` - NEW: Audio checks
8. `apps/stt/src/dictacode_stt/diagnostics/checks/transcription.py` - NEW: Transcription checks
9. `apps/stt/src/dictacode_stt/diagnostics/checks/transport.py` - NEW: Transport checks
10. `apps/stt/src/dictacode_stt/cli.py` - Refactor diagnostic commands
11. `apps/stt/src/dictacode_stt/api.py` - Add diagnostic endpoints
12. `apps/stt/pyproject.toml` - Add entry points for new commands

---

## Success Criteria

v0.2.9 is complete when:

1. ✅ `DiagnosticCheck` ABC defined with check interface
2. ✅ `DiagnosticRegistry` manages and runs checks
3. ✅ Built-in checks for system, audio, transcription, transport
4. ✅ Check dependencies resolved correctly
5. ✅ `dictacode-stt-diagnose` uses backend (not embedded logic)
6. ✅ `dictacode-stt-check` provides quick health check
7. ✅ `--json` output for all diagnostic commands
8. ✅ `/api/diagnostics/*` endpoints work
9. ✅ `BugReportGenerator` collects comprehensive info
10. ✅ Sensitive data redacted in reports
11. ✅ `dictacode-stt-bugreport` generates JSON + markdown
12. ✅ Markdown suitable for GitHub issue submission
13. ✅ Unit tests for diagnostic checks
14. ✅ Unit tests for report generation

---

## Out of Scope (v0.2.9)

- Direct GitHub issue submission (use copy-paste)
- Report upload to cloud service
- Historical report comparison
- Real-time diagnostic streaming via WebSocket
- Automated issue triage/categorization
