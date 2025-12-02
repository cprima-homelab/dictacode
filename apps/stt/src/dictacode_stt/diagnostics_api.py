"""Diagnostics API endpoints for dictacode STT (v0.2.9 Phase 4)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dictacode_stt.diagnostics import (
    CheckCategory,
    CheckStatus,
    run_all_checks,
)
from dictacode_stt.diagnostics.registry import get_registry


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


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

    category: Optional[str] = None
    device_index: int = 0
    uart_device: str = "/dev/serial0"
    whisper_binary: Optional[str] = None
    whisper_model: Optional[str] = None


class DiagnosticRunResponse(BaseModel):
    """Response from diagnostic run."""

    status: str
    passed: int
    failed: int
    warnings: int
    checks: list[Dict[str, Any]]


class DiagnosticStatusResponse(BaseModel):
    """Quick status response."""

    healthy: bool
    passed: int
    failed: int
    warnings: int


@router.get("/checks", response_model=list[CheckInfoResponse])
async def list_checks(category: Optional[str] = None, enabled_only: bool = True):
    """List available diagnostic checks.

    Args:
        category: Filter by category (system, audio, transcription, transport, hid, config)
        enabled_only: Only list enabled checks (default: True)

    Returns:
        List of available diagnostic checks

    Example:
        >>> curl http://localhost:8000/api/diagnostics/checks
        >>> curl http://localhost:8000/api/diagnostics/checks?category=audio
    """
    try:
        registry = get_registry()

        # Parse category
        cat = None
        if category:
            try:
                cat = CheckCategory(category.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid category: {category}. Valid categories: {[c.value for c in CheckCategory]}",
                )

        checks = registry.list_checks(category=cat, enabled_only=enabled_only)

        return [
            CheckInfoResponse(
                check_id=check.check_id,
                name=check.name,
                category=check.category.value,
                description=check.description,
                depends_on=check.depends_on,
                enabled=check.enabled,
            )
            for check in checks
        ]

    except Exception as e:
        logger.error(f"Failed to list checks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list checks: {e!s}")


@router.post("/run", response_model=DiagnosticRunResponse)
async def run_diagnostics(request: DiagnosticRunRequest):
    """Run diagnostic checks.

    Args:
        request: Diagnostic run configuration

    Returns:
        Diagnostic results with summary

    Example:
        >>> curl -X POST http://localhost:8000/api/diagnostics/run \
            -H "Content-Type: application/json" \
            -d '{"device_index": 0}'
    """
    try:
        # Run all checks with provided configuration
        result = run_all_checks(
            device_index=request.device_index,
            uart_device=request.uart_device,
            whisper_binary=request.whisper_binary,
            whisper_model=request.whisper_model,
        )

        # Convert to response format
        return DiagnosticRunResponse(
            status=result.overall_status.value,
            passed=result.passed,
            failed=result.failures,
            warnings=result.warnings,
            checks=[check.to_dict() for check in result.checks],
        )

    except Exception as e:
        logger.error(f"Failed to run diagnostics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to run diagnostics: {e!s}")


@router.get("/status", response_model=DiagnosticStatusResponse)
async def get_status():
    """Get quick health status.

    Runs all diagnostic checks and returns summary status.

    Returns:
        Quick status summary

    Example:
        >>> curl http://localhost:8000/api/diagnostics/status
    """
    try:
        # Run all checks
        result = run_all_checks()

        # Return summary
        return DiagnosticStatusResponse(
            healthy=result.overall_status == CheckStatus.OK,
            passed=result.passed,
            failed=result.failures,
            warnings=result.warnings,
        )

    except Exception as e:
        logger.error(f"Failed to get status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {e!s}")


@router.get("/categories")
async def list_categories():
    """List available check categories.

    Returns:
        List of diagnostic check categories

    Example:
        >>> curl http://localhost:8000/api/diagnostics/categories
    """
    return {
        "categories": [
            {
                "value": cat.value,
                "name": cat.name.replace("_", " ").title(),
            }
            for cat in CheckCategory
        ]
    }
