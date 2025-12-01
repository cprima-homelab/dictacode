"""Base classes for diagnostic framework (v0.2.9).

Provides CheckStatus, CheckResult, and DiagnosticResult for structured diagnostics.
Enhanced with categories, severity, timestamps, and duration tracking.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any


class CheckStatus(Enum):
    """Status of a diagnostic check (v0.2.9)."""

    PENDING = "pending"  # Not yet run
    RUNNING = "running"  # Currently executing
    PASSED = "passed"    # Equivalent to OK (v0.2.9 naming)
    WARNING = "warning"  # Equivalent to WARN (v0.2.9 naming)
    FAILED = "failed"    # Equivalent to FAIL (v0.2.9 naming)
    SKIPPED = "skipped"  # Check was skipped
    ERROR = "error"      # Check encountered error

    # Legacy aliases for backward compatibility
    OK = "passed"
    WARN = "warning"
    FAIL = "failed"


class CheckCategory(Enum):
    """Category of diagnostic check (v0.2.9)."""

    SYSTEM = "system"           # OS, Python, dependencies
    AUDIO = "audio"             # Audio devices, recording
    TRANSCRIPTION = "transcription"  # Whisper, Vosk, etc.
    TRANSPORT = "transport"     # UART, USB-Serial, WiFi
    HID = "hid"                 # HID device status
    CONFIG = "config"           # Configuration files


class CheckSeverity(Enum):
    """Severity of check failure (v0.2.9)."""

    INFO = "info"           # Informational
    WARNING = "warning"     # May cause issues
    CRITICAL = "critical"   # Will prevent operation


@dataclass
class CheckResult:
    """Result of a single diagnostic check (v0.2.9 enhanced)."""

    name: str
    status: CheckStatus
    message: str
    # v0.2.9 enhancements:
    check_id: Optional[str] = None          # Unique check identifier
    category: Optional[CheckCategory] = None  # Check category
    details: Optional[Dict[str, Any]] = None  # Additional details
    severity: CheckSeverity = CheckSeverity.INFO  # Severity level
    duration_ms: Optional[int] = None       # Execution duration
    timestamp: Optional[datetime] = None    # When check was run
    next_step: Optional[str] = None         # Remediation hint (legacy)

    def __post_init__(self):
        """Set default values for v0.2.9 fields."""
        if self.check_id is None:
            # Default: derive check_id from name
            self.check_id = self.name.replace(" ", "_").lower()
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization (v0.2.9 format)."""
        result = {
            "check_id": self.check_id,
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

        if self.category:
            result["category"] = self.category.value
        if self.details:
            result["details"] = self.details
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.next_step:
            result["next_step"] = self.next_step

        return result


@dataclass
class DiagnosticResult:
    """Collection of check results for a component."""

    component: str
    checks: List[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        """Add a check result."""
        self.checks.append(result)

    def ok(self, name: str, message: str) -> None:
        """Add an OK result."""
        self.add(CheckResult(name=name, status=CheckStatus.OK, message=message))

    def warn(self, name: str, message: str, next_step: Optional[str] = None) -> None:
        """Add a WARNING result."""
        self.add(
            CheckResult(
                name=name, status=CheckStatus.WARN, message=message, next_step=next_step
            )
        )

    def fail(self, name: str, message: str, next_step: Optional[str] = None) -> None:
        """Add a FAIL result."""
        self.add(
            CheckResult(
                name=name, status=CheckStatus.FAIL, message=message, next_step=next_step
            )
        )

    @property
    def passed(self) -> int:
        """Count of passed checks."""
        return sum(1 for c in self.checks if c.status == CheckStatus.OK)

    @property
    def warnings(self) -> int:
        """Count of warning checks."""
        return sum(1 for c in self.checks if c.status == CheckStatus.WARN)

    @property
    def failures(self) -> int:
        """Count of failed checks."""
        return sum(1 for c in self.checks if c.status == CheckStatus.FAIL)

    @property
    def overall_status(self) -> CheckStatus:
        """Overall status based on all checks."""
        if self.failures > 0:
            return CheckStatus.FAIL
        if self.warnings > 0:
            return CheckStatus.WARN
        return CheckStatus.OK

    @property
    def exit_code(self) -> int:
        """Exit code for CLI: 0=OK, 1=FAIL, 2=WARN."""
        if self.failures > 0:
            return 1
        if self.warnings > 0:
            return 2
        return 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "status": self.overall_status.value,
            "component": self.component,
            "checks": [c.to_dict() for c in self.checks],
            "summary": {
                "passed": self.passed,
                "failed": self.failures,
                "warnings": self.warnings,
            },
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_human(self, verbose: bool = False, quiet: bool = False) -> str:
        """Convert to human-readable string."""
        lines = []

        if quiet:
            # Only show failures and warnings
            for check in self.checks:
                if check.status == CheckStatus.FAIL:
                    lines.append(f"[FAIL] {check.name}: {check.message}")
                    if check.next_step:
                        lines.append(f"       -> {check.next_step}")
                elif check.status == CheckStatus.WARN:
                    lines.append(f"[WARN] {check.name}: {check.message}")
            return "\n".join(lines)

        lines.append(f"=== dictacode {self.component.upper()} Hardware Check ===")
        lines.append("")

        # Group checks by category (based on name prefix)
        current_category = None
        for check in self.checks:
            # Extract category from check name (e.g., "audio_device" -> "Audio")
            category = check.name.split("_")[0].title()
            if category != current_category:
                if current_category is not None:
                    lines.append("")
                lines.append(f"{category}:")
                current_category = category

            status_str = {
                CheckStatus.OK: "[OK]",
                CheckStatus.WARN: "[WARN]",
                CheckStatus.FAIL: "[FAIL]",
            }[check.status]

            lines.append(f"  {status_str} {check.message}")

            if verbose and check.next_step:
                lines.append(f"       -> {check.next_step}")

        lines.append("")
        lines.append("=== Summary ===")

        status_str = {
            CheckStatus.OK: "READY",
            CheckStatus.WARN: "READY (with warnings)",
            CheckStatus.FAIL: "NOT READY",
        }[self.overall_status]

        lines.append(f"Status: {status_str}")
        lines.append(
            f"Checks: {self.passed} passed, {self.failures} failed, {self.warnings} warnings"
        )

        # Show next steps for failures
        if self.failures > 0:
            next_steps = [c.next_step for c in self.checks if c.next_step and c.status == CheckStatus.FAIL]
            if next_steps:
                lines.append("")
                lines.append("Next steps:")
                for i, step in enumerate(next_steps, 1):
                    lines.append(f"  {i}. {step}")

        return "\n".join(lines)
