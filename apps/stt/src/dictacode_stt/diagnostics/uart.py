"""UART diagnostic checks for STT.

Checks UART device availability and writability.
"""

from __future__ import annotations

import os
from pathlib import Path

from .base import DiagnosticResult


def run_uart_checks(uart_device: str = "/dev/serial0") -> DiagnosticResult:
    """Run UART device checks.

    Args:
        uart_device: Path to UART device.
    """
    result = DiagnosticResult(component="stt")

    uart_path = Path(uart_device)
    if uart_path.exists():
        result.ok("uart_exists", f"{uart_device} exists")

        if os.access(uart_path, os.W_OK):
            result.ok("uart_writable", f"{uart_device} is writable")
        else:
            result.warn(
                "uart_writable",
                f"{uart_device} not writable by current user",
                "Run as root or add user to dialout group",
            )

        if os.access(uart_path, os.R_OK):
            result.ok("uart_readable", f"{uart_device} is readable")
        else:
            result.warn(
                "uart_readable",
                f"{uart_device} not readable by current user",
                "Run as root or add user to dialout group",
            )
    else:
        result.fail(
            "uart_exists",
            f"{uart_device} does not exist",
            "Check UART configuration and device path",
        )

    return result
