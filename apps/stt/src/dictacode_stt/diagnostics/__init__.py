"""Diagnostic tools for dictacode STT.

Provides CLI entry points for hardware checks and diagnostics.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from .audio import run_audio_checks
from .base import (
    CheckCategory,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    DiagnosticResult,
)
from .bugreport import (
    BugReportGenerator,
    SystemReport,
)
from .registry import (
    DiagnosticCheck,
    DiagnosticRegistry,
    get_registry,
)
from .uart import run_uart_checks
from .whisper import run_whisper_checks


__all__ = [
    # v0.2.9 Types
    "CheckStatus",
    "CheckCategory",
    "CheckSeverity",
    "CheckResult",
    "DiagnosticResult",
    # v0.2.9 Phase 2: Registry
    "DiagnosticCheck",
    "DiagnosticRegistry",
    "get_registry",
    # v0.2.9 Phase 5: Bug Report Generation
    "BugReportGenerator",
    "SystemReport",
    # Check runners
    "run_audio_checks",
    "run_whisper_checks",
    "run_uart_checks",
    # CLI entry points
    "check_main",
    "diagnose_main",
    "run_all_checks",
]


def check_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-check.

    Quick hardware prerequisite check for systemd ExecStartPre.
    """
    parser = argparse.ArgumentParser(
        description="Check dictacode STT hardware prerequisites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0  All checks passed (READY)
  1  Critical failures (NOT READY - service should not start)
  2  Warnings only (READY with warnings)

Examples:
  dictacode-stt-check              # Run all checks
  dictacode-stt-check --json       # Output as JSON
  dictacode-stt-check --quiet      # Only show failures
        """,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON (for machine parsing)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed check information",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only show failures",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=0,
        help="Audio device index (default: 0)",
    )
    parser.add_argument(
        "--uart",
        default="/dev/serial0",
        help="UART device to check (default: /dev/serial0)",
    )
    parser.add_argument(
        "--whisper-binary",
        type=Path,
        help="Path to whisper-cli binary",
    )
    parser.add_argument(
        "--whisper-model",
        type=Path,
        help="Path to whisper model file",
    )

    parsed = parser.parse_args(args)

    # Create combined result
    result = DiagnosticResult(component="stt")

    # Run audio checks
    audio_result = run_audio_checks(parsed.device)
    for check in audio_result.checks:
        result.add(check)

    # Run whisper checks
    whisper_result = run_whisper_checks(parsed.whisper_binary, parsed.whisper_model)
    for check in whisper_result.checks:
        result.add(check)

    # Run UART checks
    uart_result = run_uart_checks(parsed.uart)
    for check in uart_result.checks:
        result.add(check)

    # Output
    if parsed.json:
        print(result.to_json())
    else:
        print(result.to_human(verbose=parsed.verbose, quiet=parsed.quiet))

    return result.exit_code


def diagnose_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-diagnose.

    Full diagnostic suite with all checks and detailed output.
    """
    parser = argparse.ArgumentParser(
        description="Run full dictacode STT diagnostics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0  All checks passed
  1  Critical failures
  2  Warnings only

Examples:
  dictacode-stt-diagnose                       # Run all diagnostics
  dictacode-stt-diagnose --json                # Output as JSON
  dictacode-stt-diagnose --check audio_device  # Run specific check
        """,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON (for machine parsing)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed check information",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Only show failures",
    )
    parser.add_argument(
        "--check",
        metavar="NAME",
        help="Run specific check only",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=0,
        help="Audio device index (default: 0)",
    )
    parser.add_argument(
        "--uart",
        default="/dev/serial0",
        help="UART device to check (default: /dev/serial0)",
    )
    parser.add_argument(
        "--whisper-binary",
        type=Path,
        help="Path to whisper-cli binary",
    )
    parser.add_argument(
        "--whisper-model",
        type=Path,
        help="Path to whisper model file",
    )

    parsed = parser.parse_args(args)

    # Create combined result
    result = DiagnosticResult(component="stt")

    # Run all checks
    audio_result = run_audio_checks(parsed.device)
    for check in audio_result.checks:
        result.add(check)

    whisper_result = run_whisper_checks(parsed.whisper_binary, parsed.whisper_model)
    for check in whisper_result.checks:
        result.add(check)

    uart_result = run_uart_checks(parsed.uart)
    for check in uart_result.checks:
        result.add(check)

    # Filter to specific check if requested
    if parsed.check:
        filtered_checks = [c for c in result.checks if c.name == parsed.check]
        if not filtered_checks:
            print(f"Error: Unknown check '{parsed.check}'", file=sys.stderr)
            print("Available checks:", file=sys.stderr)
            for check in result.checks:
                print(f"  - {check.name}", file=sys.stderr)
            return 1
        result.checks = filtered_checks

    # Output
    if parsed.json:
        print(result.to_json())
    else:
        print(result.to_human(verbose=parsed.verbose, quiet=parsed.quiet))

    return result.exit_code


def run_all_checks(
    device_index: int = 0,
    uart_device: str = "/dev/serial0",
    whisper_binary: Optional[Path] = None,
    whisper_model: Optional[Path] = None,
) -> DiagnosticResult:
    """Run all diagnostic checks and return combined result.

    Used by service for runtime diagnostics.
    """
    result = DiagnosticResult(component="stt")

    audio_result = run_audio_checks(device_index)
    for check in audio_result.checks:
        result.add(check)

    whisper_result = run_whisper_checks(whisper_binary, whisper_model)
    for check in whisper_result.checks:
        result.add(check)

    uart_result = run_uart_checks(uart_device)
    for check in uart_result.checks:
        result.add(check)

    return result
