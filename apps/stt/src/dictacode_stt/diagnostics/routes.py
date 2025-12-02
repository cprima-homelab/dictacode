"""Diagnostics API endpoints (v0.3.6, v0.3.7, v0.3.8).

Thin wrappers around DiagnosticsService using FastAPI dependency injection.

v0.3.7/v0.3.8: API uses IPC to query the running service by default.
Fallback to local service only when IPC is unreachable.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .base import CheckCategory, CheckStatus
from .service import DiagnosticsService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


# Pydantic models for API
class CheckInfoResponse(BaseModel):
    """Response for check information."""

    check_id: str
    name: str
    category: str
    description: str
    depends_on: list[str]
    enabled: bool


class DiagnosticRunRequest(BaseModel):
    """Request to run diagnostics."""

    category: str | None = None
    device_index: int = 0
    uart_device: str = "/dev/serial0"
    whisper_binary: str | None = None
    whisper_model: str | None = None


class DiagnosticRunResponse(BaseModel):
    """Response from diagnostic run."""

    status: str
    passed: int
    failed: int
    warnings: int
    checks: list[dict[str, Any]]


class DiagnosticStatusResponse(BaseModel):
    """Quick status response."""

    healthy: bool
    passed: int
    failed: int
    warnings: int


# v0.3.7/v0.3.8: IPC client for querying running service
_ipc_client = None
_default_diagnostics_service: DiagnosticsService | None = None


def _get_ipc_client():
    """Get or create IPC client (lazy initialization)."""
    global _ipc_client
    if _ipc_client is None:
        try:
            from .ipc import DiagnosticsIpcClient
            _ipc_client = DiagnosticsIpcClient()
        except Exception as e:
            logger.warning(f"Failed to create IPC client: {e}")
            _ipc_client = False  # Sentinel to avoid repeated failures
    return _ipc_client if _ipc_client else None


def _try_ipc_call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Try to make an IPC call to the running service.

    Args:
        method: IPC method name (e.g., "diag.run")
        params: Method parameters

    Returns:
        Result dict if successful, None if IPC unavailable
    """
    client = _get_ipc_client()
    if client is None:
        return None

    try:
        if client.is_available():
            return client._call(method, params)
    except Exception as e:
        logger.debug(f"IPC call failed: {e}")

    return None


def get_diagnostics_service() -> DiagnosticsService:
    """Get diagnostics service fallback for when IPC is unavailable.

    v0.3.7/v0.3.8: This is only used as fallback when IPC is not reachable.
    API endpoints try IPC first, then fall back to this local service.

    Returns:
        DiagnosticsService - local default instance
    """
    global _default_diagnostics_service

    # Check if we have a local service instance (rare: same-process mode)
    from dictacode_stt.health import _service_instance
    if _service_instance and hasattr(_service_instance, "diagnostics"):
        return _service_instance.diagnostics

    # Create default local service
    if _default_diagnostics_service is None:
        logger.warning(
            "IPC unavailable - using local DiagnosticsService fallback. "
            "Diagnostics may not reflect running service state."
        )
        _default_diagnostics_service = DiagnosticsService()

    return _default_diagnostics_service


@router.get("/checks", response_model=list[CheckInfoResponse])
async def list_checks(
    category: str | None = None,
    enabled_only: bool = True,
):
    """List available diagnostic checks.

    v0.3.7/v0.3.8: Queries running service via IPC by default.

    Args:
        category: Filter by category (system, audio, transcription, transport, hid, config)
        enabled_only: Only list enabled checks (default: True)

    Returns:
        List of available diagnostic checks

    Example:
        >>> curl http://localhost:8000/v1/api/diagnostics/checks
        >>> curl http://localhost:8000/v1/api/diagnostics/checks?category=audio
    """
    try:
        # Parse category
        cat = None
        if category:
            try:
                cat = CheckCategory(category.lower())
            except ValueError as exc:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category: {category}. Valid categories: {[c.value for c in CheckCategory]}",
                ) from exc

        # Try IPC first
        ipc_result = _try_ipc_call(
            "diag.list",
            {"category": cat.value if cat else None, "enabled_only": enabled_only}
        )
        if ipc_result is not None:
            checks = ipc_result.get("checks", [])
            return [
                CheckInfoResponse(
                    check_id=check["check_id"],
                    name=check["name"],
                    category=check["category"],
                    description=check["description"],
                    depends_on=check.get("depends_on", []),
                    enabled=check["enabled"],
                )
                for check in checks
            ]

        # Fallback to local service
        service = get_diagnostics_service()
        checks = service.list_checks(category=cat, enabled_only=enabled_only)

        return [
            CheckInfoResponse(
                check_id=check["check_id"],
                name=check["name"],
                category=check["category"],
                description=check["description"],
                depends_on=check.get("depends_on", []),
                enabled=check["enabled"],
            )
            for check in checks
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list checks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list checks: {e!s}") from e


@router.post("/run", response_model=DiagnosticRunResponse)
async def run_diagnostics(
    request: DiagnosticRunRequest,
):
    """Run diagnostic checks.

    v0.3.7/v0.3.8: Queries running service via IPC by default.

    Args:
        request: Diagnostic run configuration

    Returns:
        Diagnostic results with summary

    Example:
        >>> curl -X POST http://localhost:8000/v1/api/diagnostics/run \\
            -H "Content-Type: application/json" \\
            -d '{"device_index": 0}'
    """
    try:
        # Try IPC first
        ipc_result = _try_ipc_call("diag.run")
        if ipc_result is not None:
            return DiagnosticRunResponse(
                status=ipc_result.get("status", "unknown"),
                passed=ipc_result.get("passed", 0),
                failed=ipc_result.get("failed", 0),
                warnings=ipc_result.get("warnings", 0),
                checks=ipc_result.get("checks", []),
            )

        # Fallback to local service
        service = get_diagnostics_service()
        result = service.run_all(
            device_index=request.device_index,
            uart_device=request.uart_device,
            whisper_binary=Path(request.whisper_binary) if request.whisper_binary else None,
            whisper_model=Path(request.whisper_model) if request.whisper_model else None,
        )

        # Convert to response format
        return DiagnosticRunResponse(
            status=result.overall_status.value,
            passed=result.passed,
            failed=result.failures,
            warnings=result.warnings,
            checks=[check.to_dict() for check in result.checks],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to run diagnostics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to run diagnostics: {e!s}") from e


@router.get("/status", response_model=DiagnosticStatusResponse)
async def get_status():
    """Get quick health status.

    v0.3.7/v0.3.8: Queries running service via IPC by default.

    Returns:
        Quick status summary

    Example:
        >>> curl http://localhost:8000/v1/api/diagnostics/status
    """
    try:
        # Try IPC first
        ipc_result = _try_ipc_call("diag.status")
        if ipc_result is not None:
            return DiagnosticStatusResponse(
                healthy=ipc_result.get("overall") == "passed",
                passed=ipc_result.get("passed", 0),
                failed=ipc_result.get("failed", 0),
                warnings=ipc_result.get("warnings", 0),
            )

        # Fallback to local service
        service = get_diagnostics_service()
        status = service.quick_status()

        return DiagnosticStatusResponse(
            healthy=status["overall"] == CheckStatus.PASSED.value,
            passed=status["passed"],
            failed=status["failed"],
            warnings=status["warnings"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e!s}") from e


@router.get("/categories")
async def list_categories():
    """List available check categories.

    v0.3.7/v0.3.8: Queries running service via IPC by default.

    Returns:
        List of diagnostic check categories

    Example:
        >>> curl http://localhost:8000/v1/api/diagnostics/categories
    """
    # Try IPC first
    ipc_result = _try_ipc_call("diag.categories")
    if ipc_result is not None:
        return {"categories": ipc_result.get("categories", [])}

    # Fallback to local service
    service = get_diagnostics_service()
    return {"categories": service.list_categories()}


@router.get("/history")
async def get_history():
    """Get recent diagnostic run history.

    v0.3.7/v0.3.8: Queries running service via IPC by default.
    Note: History is only available from the running service via IPC.
    Local fallback returns empty history.

    Returns:
        List of recent run summaries (newest first)

    Example:
        >>> curl http://localhost:8000/v1/api/diagnostics/history
    """
    # Try IPC first - history only meaningful from running service
    ipc_result = _try_ipc_call("diag.history")
    if ipc_result is not None:
        return {"history": ipc_result.get("history", [])}

    # Fallback: local service has no shared history
    service = get_diagnostics_service()
    return {"history": service.get_history()}
