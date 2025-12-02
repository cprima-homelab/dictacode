"""Diagnostic tools for dictacode STT (v0.3.6, v0.3.7).

Provides CLI entry points for hardware checks and diagnostics.

v0.3.7: CLI uses IPC by default to query running service.
        Use --standalone to run local checks explicitly.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional

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
from .service import DiagnosticsService
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
    # v0.3.6: Central Diagnostics Service
    "DiagnosticsService",
    # v0.3.7: IPC server/client
    "DiagnosticsIpcServer",
    "DiagnosticsIpcClient",
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
    "state_main",  # v0.3.5
    "run_all_checks",
]

# Lazy imports for IPC (avoid import errors if socket module unavailable)
def __getattr__(name: str):
    if name == "DiagnosticsIpcServer":
        from .ipc import DiagnosticsIpcServer
        return DiagnosticsIpcServer
    elif name == "DiagnosticsIpcClient":
        from .ipc import DiagnosticsIpcClient
        return DiagnosticsIpcClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def _create_diagnostics_service_from_args(parsed) -> "DiagnosticsService":
    """Create DiagnosticsService from CLI args (v0.3.6).

    Creates a standalone service instance for CLI use when --standalone
    is specified or when IPC is not available.

    Args:
        parsed: Parsed argparse namespace

    Returns:
        DiagnosticsService configured from CLI args
    """
    from .service import DiagnosticsService

    return DiagnosticsService(
        device_index=parsed.device,
        uart_device=parsed.uart,
        whisper_binary=parsed.whisper_binary,
        whisper_model=parsed.whisper_model,
    )


def _try_ipc_run() -> Optional[Dict[str, Any]]:
    """Try to run diagnostics via IPC (v0.3.7).

    Returns:
        Response dict if successful, None if IPC not available
    """
    try:
        from .ipc import DiagnosticsIpcClient

        client = DiagnosticsIpcClient()
        if client.is_available():
            return client.run_diagnostics()
    except Exception:
        pass
    return None


def _format_ipc_result(
    response: Dict[str, Any], json_output: bool, verbose: bool, quiet: bool
) -> str:
    """Format IPC response for output (v0.3.7).

    Args:
        response: IPC response dict
        json_output: Output as JSON
        verbose: Show detailed info
        quiet: Only show failures

    Returns:
        Formatted output string
    """
    if json_output:
        return json.dumps(response, indent=2)

    # Human-readable format
    lines = []
    status = response.get("status", "unknown")

    if status == "passed":
        status_icon = "[OK]"
    elif status == "warning":
        status_icon = "[WARN]"
    else:
        status_icon = "[FAIL]"

    lines.append(f"Diagnostics: {status_icon} {status.upper()}")
    lines.append(
        f"  Passed: {response.get('passed', 0)}, "
        f"Failed: {response.get('failed', 0)}, "
        f"Warnings: {response.get('warnings', 0)}"
    )

    if verbose or not quiet:
        checks = response.get("checks", [])
        for check in checks:
            check_status = check.get("status", "unknown")
            if quiet and check_status == "passed":
                continue

            if check_status == "passed":
                icon = "✓"
            elif check_status == "warning":
                icon = "⚠"
            else:
                icon = "✗"

            lines.append(f"  {icon} {check.get('name', 'unknown')}: {check.get('message', '')}")

    return "\n".join(lines)


def check_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-check.

    Quick hardware prerequisite check for systemd ExecStartPre.
    v0.3.6: Uses DiagnosticsService instead of direct function calls.
    v0.3.7: Uses IPC to query running service by default.
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
  dictacode-stt-check              # Query running service via IPC
  dictacode-stt-check --standalone # Run local checks (no IPC)
  dictacode-stt-check --json       # Output as JSON
  dictacode-stt-check --quiet      # Only show failures

Environment:
  DICTACODE_DIAG_SOCKET  Path to IPC socket (default: /run/dictacode/diag.sock)
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
        "--standalone",
        "-s",
        action="store_true",
        help="Run local checks (don't query running service via IPC)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=0,
        help="Audio device index (default: 0, for --standalone)",
    )
    parser.add_argument(
        "--uart",
        default="/dev/serial0",
        help="UART device to check (default: /dev/serial0, for --standalone)",
    )
    parser.add_argument(
        "--whisper-binary",
        type=Path,
        help="Path to whisper-cli binary (for --standalone)",
    )
    parser.add_argument(
        "--whisper-model",
        type=Path,
        help="Path to whisper model file (for --standalone)",
    )

    parsed = parser.parse_args(args)

    # v0.3.7: Try IPC first unless --standalone
    if not parsed.standalone:
        ipc_result = _try_ipc_run()
        if ipc_result is not None:
            print(_format_ipc_result(
                ipc_result, parsed.json, parsed.verbose, parsed.quiet
            ))
            return ipc_result.get("exit_code", 0)
        else:
            # IPC not available - fall through to standalone
            if not parsed.quiet:
                print(
                    "Note: Service not running or IPC unavailable. "
                    "Running standalone checks.",
                    file=sys.stderr,
                )

    # v0.3.6: Use DiagnosticsService (standalone mode)
    service = _create_diagnostics_service_from_args(parsed)
    result = service.run_all()

    # Output
    if parsed.json:
        print(result.to_json())
    else:
        print(result.to_human(verbose=parsed.verbose, quiet=parsed.quiet))

    return result.exit_code


def diagnose_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-diagnose.

    Full diagnostic suite with all checks and detailed output.
    v0.3.6: Uses DiagnosticsService instead of direct function calls.
    v0.3.7: Uses IPC to query running service by default.
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
  dictacode-stt-diagnose                       # Query running service via IPC
  dictacode-stt-diagnose --standalone          # Run local checks (no IPC)
  dictacode-stt-diagnose --json                # Output as JSON
  dictacode-stt-diagnose --check audio_device  # Run specific check (standalone only)

Environment:
  DICTACODE_DIAG_SOCKET  Path to IPC socket (default: /run/dictacode/diag.sock)
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
        "--standalone",
        "-s",
        action="store_true",
        help="Run local checks (don't query running service via IPC)",
    )
    parser.add_argument(
        "--check",
        metavar="NAME",
        help="Run specific check only (implies --standalone)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=0,
        help="Audio device index (default: 0, for --standalone)",
    )
    parser.add_argument(
        "--uart",
        default="/dev/serial0",
        help="UART device to check (default: /dev/serial0, for --standalone)",
    )
    parser.add_argument(
        "--whisper-binary",
        type=Path,
        help="Path to whisper-cli binary (for --standalone)",
    )
    parser.add_argument(
        "--whisper-model",
        type=Path,
        help="Path to whisper model file (for --standalone)",
    )

    parsed = parser.parse_args(args)

    # --check implies standalone (filter only works locally)
    use_standalone = parsed.standalone or parsed.check

    # v0.3.7: Try IPC first unless --standalone or --check
    if not use_standalone:
        ipc_result = _try_ipc_run()
        if ipc_result is not None:
            print(_format_ipc_result(
                ipc_result, parsed.json, parsed.verbose, parsed.quiet
            ))
            return ipc_result.get("exit_code", 0)
        else:
            # IPC not available - fall through to standalone
            if not parsed.quiet:
                print(
                    "Note: Service not running or IPC unavailable. "
                    "Running standalone checks.",
                    file=sys.stderr,
                )

    # v0.3.6: Use DiagnosticsService (standalone mode)
    service = _create_diagnostics_service_from_args(parsed)
    result = service.run_all()

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
    warnings.warn(
        "run_all_checks is legacy and will be replaced by component status/aggregator flow in a future release.",
        DeprecationWarning,
        stacklevel=2,
    )
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


def _format_state_output(data: Dict[str, Any], is_history: bool) -> None:
    """Format state data for terminal output (v0.3.5).

    Args:
        data: State dict or list of history entries
        is_history: True if displaying history
    """
    if is_history:
        history = data if isinstance(data, list) else data.get("history", [])
        if not history:
            print("No state history available.")
            return
        print("State History:")
        for entry in history:
            timestamp = entry.get("timestamp", "?")
            old_state = entry.get("old_state", "?")
            new_state = entry.get("new_state", "?")
            print(f"  {timestamp}: {old_state} → {new_state}")
            reason = entry.get("reason")
            if reason:
                print(f"    Reason: {reason}")
            source = entry.get("source")
            if source:
                print(f"    Source: {source}")
    else:
        print(f"State:    {data.get('state', 'unknown')}")
        print(f"Model:    {data.get('model', 'N/A')}")
        print(f"Language: {data.get('language', 'N/A')}")
        print(f"Keymap:   {data.get('hid_keymap', 'N/A')}")
        failure = data.get("failure_reason")
        if failure:
            print(f"Failure:  {failure}")


def state_main(args: Optional[List[str]] = None) -> int:
    """CLI entry point for dictacode-stt-state (v0.3.5).

    Queries running service via IPC for current state.
    Use --standalone for local mode (default state only).
    """
    parser = argparse.ArgumentParser(
        description="Display dictacode STT service state",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  dictacode-stt-state              # Query running service
  dictacode-stt-state --history    # Show state transition history
  dictacode-stt-state --json       # Output as JSON
  dictacode-stt-state --standalone # Local mode (no IPC)

Environment:
  DICTACODE_IPC_SOCKET  Path to IPC socket (default: /run/dictacode/diag.sock)
        """,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON",
    )
    parser.add_argument(
        "--history",
        action="store_true",
        help="Show state transition history",
    )
    parser.add_argument(
        "--standalone",
        "-s",
        action="store_true",
        help="Local mode (no IPC, shows default state)",
    )

    parsed = parser.parse_args(args)

    # v0.3.5: Try IPC first unless --standalone
    if not parsed.standalone:
        try:
            from .ipc import DiagnosticsIpcClient

            client = DiagnosticsIpcClient()
            if client.is_available():
                if parsed.history:
                    result = client.get_state_history()
                    data = result.get("history", [])
                else:
                    data = client.get_state()

                if parsed.json:
                    print(json.dumps(data, indent=2))
                else:
                    _format_state_output(data, parsed.history)
                return 0
        except Exception as e:
            print(f"Error: Could not connect to service: {e}", file=sys.stderr)
            return 1

        # IPC not available and not standalone - error
        print(
            "Error: Service not running or IPC unavailable. "
            "Use --standalone for local mode.",
            file=sys.stderr,
        )
        return 1

    # Standalone mode - show default state
    print("Note: Running in standalone mode (no IPC)", file=sys.stderr)

    from dictacode_stt.state import SttState

    state = SttState()

    if parsed.history:
        if parsed.json:
            print(json.dumps([], indent=2))
        else:
            print("No state history in standalone mode.")
    else:
        if parsed.json:
            print(json.dumps(state.to_dict(), indent=2))
        else:
            _format_state_output(state.to_dict(), False)

    return 0
