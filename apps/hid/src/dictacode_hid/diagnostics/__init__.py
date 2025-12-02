"""Diagnostic tools for dictacode HID.

Provides CLI entry points for hardware checks and diagnostics.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .base import CheckResult, CheckStatus, DiagnosticResult
from .hardware import run_hardware_checks, run_uart_checks


__all__ = [
    "CheckResult",
    "CheckStatus",
    "DiagnosticResult",
    "check_main",
    "diagnose_main",
    "run_hardware_checks",
    "run_uart_checks",
]


def check_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-hid-check.

    Quick hardware prerequisite check for systemd ExecStartPre.
    """
    parser = argparse.ArgumentParser(
        description="Check dictacode HID hardware prerequisites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0  All checks passed (READY)
  1  Critical failures (NOT READY - service should not start)
  2  Warnings only (READY with warnings)

Examples:
  dictacode-hid-check              # Run all checks
  dictacode-hid-check --json       # Output as JSON
  dictacode-hid-check --quiet      # Only show failures
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
        "--uart",
        default="/dev/serial0",
        help="UART device to check (default: /dev/serial0)",
    )

    parsed = parser.parse_args(args)

    # Run hardware checks
    result = run_hardware_checks(quick=True)

    # Add UART checks
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
    """CLI entry point for dictacode-hid-diagnose.

    Full diagnostic suite with all checks and detailed output.
    """
    parser = argparse.ArgumentParser(
        description="Run full dictacode HID diagnostics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exit codes:
  0  All checks passed
  1  Critical failures
  2  Warnings only

Examples:
  dictacode-hid-diagnose                    # Run all diagnostics
  dictacode-hid-diagnose --json             # Output as JSON
  dictacode-hid-diagnose --check boot_config  # Run specific check
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
        "--uart",
        default="/dev/serial0",
        help="UART device to check (default: /dev/serial0)",
    )

    parsed = parser.parse_args(args)

    # Run all diagnostics
    result = run_hardware_checks(quick=False)

    # Add UART checks
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


def run_all_checks(uart_device: str = "/dev/serial0") -> DiagnosticResult:
    """Run all diagnostic checks and return combined result.

    Used by service for runtime diagnostics.
    """
    result = run_hardware_checks(quick=False)

    uart_result = run_uart_checks(uart_device)
    for check in uart_result.checks:
        result.add(check)

    return result
