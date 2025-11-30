"""Base classes for diagnostic framework.

Provides CheckStatus, CheckResult, and DiagnosticResult for structured diagnostics.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class CheckStatus(Enum):
    """Status of a diagnostic check."""

    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    """Result of a single diagnostic check."""

    name: str
    status: CheckStatus
    message: str
    next_step: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
        }
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
            # Extract category from check name (e.g., "boot_config" -> "Boot")
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
