"""Central diagnostics service (v0.3.6, v0.3.7).

Provides unified interface for diagnostics consumed by API and CLI.

Environment:
    DICTACODE_DIAG_HISTORY_SIZE: History ring buffer size (default: 10)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import CheckCategory, DiagnosticResult
from .registry import get_registry


def _get_history_max() -> int:
    """Get history max size from env (v0.3.7).

    Returns:
        History max size (default: 10)
    """
    try:
        return int(os.environ.get("DICTACODE_DIAG_HISTORY_SIZE", "10"))
    except ValueError:
        return 10


@dataclass
class DiagnosticsService:
    """Central diagnostics service (v0.3.6, v0.3.7).

    Provides unified interface for diagnostics consumed by API and CLI.
    Wraps existing run_all_checks() and registry for consistency.

    v0.3.7: History size configurable via DICTACODE_DIAG_HISTORY_SIZE env.
    """

    # Default check parameters
    device_index: int = 0
    uart_device: str = "/dev/serial0"
    whisper_binary: Optional[Path] = None
    whisper_model: Optional[Path] = None

    # Recent run history (ring buffer)
    _history: List[Dict[str, Any]] = field(default_factory=list)
    _history_max: int = field(default_factory=_get_history_max)

    def list_checks(
        self,
        category: Optional[CheckCategory] = None,
        enabled_only: bool = True,
    ) -> List[Dict[str, Any]]:
        """List available diagnostic checks from registry.

        Args:
            category: Filter by category (None = all)
            enabled_only: Only list enabled checks

        Returns:
            List of check info dicts
        """
        registry = get_registry()
        checks = registry.list_checks(category=category, enabled_only=enabled_only)
        return [
            {
                "check_id": c.check_id,
                "name": c.name,
                "category": c.category.value,
                "description": c.description,
                "enabled": c.enabled,
                "severity": c.severity.value,
                "depends_on": c.depends_on,
            }
            for c in checks
        ]

    def run_all(
        self,
        device_index: Optional[int] = None,
        uart_device: Optional[str] = None,
        whisper_binary: Optional[Path] = None,
        whisper_model: Optional[Path] = None,
    ) -> DiagnosticResult:
        """Run all diagnostic checks.

        Args:
            device_index: Audio device index (default: instance default)
            uart_device: UART device path (default: instance default)
            whisper_binary: Path to whisper binary (default: instance default)
            whisper_model: Path to whisper model (default: instance default)

        Returns:
            DiagnosticResult with all check results
        """
        # Import here to avoid circular import
        from . import run_all_checks

        result = run_all_checks(
            device_index=device_index if device_index is not None else self.device_index,
            uart_device=uart_device or self.uart_device,
            whisper_binary=whisper_binary or self.whisper_binary,
            whisper_model=whisper_model or self.whisper_model,
        )
        self._add_to_history(result)
        return result

    def quick_status(self) -> Dict[str, Any]:
        """Get quick status summary.

        Returns:
            Dict with overall status and counts
        """
        result = self.run_all()
        return {
            "overall": result.overall_status.value,
            "passed": result.passed,
            "failed": result.failures,
            "warnings": result.warnings,
            "total": len(result.checks),
        }

    def list_categories(self) -> List[Dict[str, str]]:
        """List available check categories.

        Returns:
            List of category info dicts
        """
        return [
            {"id": cat.value, "name": cat.name.replace("_", " ").title()}
            for cat in CheckCategory
        ]

    def get_history(self) -> List[Dict[str, Any]]:
        """Get recent run history.

        Returns:
            List of historical run summaries (newest first)
        """
        # Return newest first
        return list(reversed(self._history))

    def _add_to_history(self, result: DiagnosticResult) -> None:
        """Add result to history ring buffer.

        Args:
            result: DiagnosticResult to add
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "overall": result.overall_status.value,
            "passed": result.passed,
            "failed": result.failures,
            "warnings": result.warnings,
        }
        self._history.append(entry)
        if len(self._history) > self._history_max:
            self._history.pop(0)
