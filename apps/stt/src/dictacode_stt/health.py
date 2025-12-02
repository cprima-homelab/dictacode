"""Health and status endpoints for dictacode STT (v0.2.13 Phase 6)."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(tags=["health"])

# Startup time for uptime calculation
_start_time = time.time()


class HealthResponse(BaseModel):
    """Health check response (v0.2.13)."""

    status: str  # "healthy", "degraded", "unhealthy"
    timestamp: str
    checks: Dict[str, bool]


class ReadinessResponse(BaseModel):
    """Readiness check response (v0.2.13)."""

    ready: bool
    checks: Dict[str, bool]


class ComponentStatus(BaseModel):
    """Status of a single component (v0.2.13)."""

    available: bool
    details: Dict[str, Any]


class StatusResponse(BaseModel):
    """Detailed status response (v0.2.13)."""

    status: str
    version: str
    uptime_seconds: float
    components: Dict[str, ComponentStatus]


# Global service reference (set by API server)
_service_instance: Optional[Any] = None


def set_service_instance(service: Any) -> None:
    """Set the global service instance for health checks.

    Args:
        service: SttService instance

    Example:
        >>> from dictacode_stt.health import set_service_instance
        >>> service = SttService(...)
        >>> set_service_instance(service)
    """
    global _service_instance
    _service_instance = service


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe - is the service running?

    This endpoint should return 200 if the service process is alive.
    Used for Kubernetes liveness probes or load balancer health checks.

    Returns:
        HealthResponse with status and basic checks

    Example:
        >>> curl http://localhost:8000/health
        {"status": "healthy", "timestamp": "2025-01-15T10:30:00", "checks": {"service_running": true}}
    """
    checks = {
        "service_running": True,
    }

    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        checks=checks,
    )


@router.get("/ready", response_model=ReadinessResponse)
async def readiness_check() -> ReadinessResponse:
    """Readiness probe - is the service ready to accept requests?

    This endpoint checks if all dependencies are available and the service
    can handle requests. Used for Kubernetes readiness probes.

    Returns:
        ReadinessResponse with ready status and component checks

    Example:
        >>> curl http://localhost:8000/ready
        {"ready": true, "checks": {"audio_device": true, "transcriber": true, "transport": true}}
    """
    checks: Dict[str, bool] = {}

    if _service_instance:
        # Check audio device availability
        try:
            from dictacode_stt.audio import AudioPortManager

            manager = AudioPortManager()
            checks["audio_device"] = manager.get_default_port() is not None
        except Exception:
            checks["audio_device"] = False

        # Check transcriber availability
        try:
            if (
                hasattr(_service_instance, "transcriber")
                and _service_instance.transcriber
            ):
                checks["transcriber"] = _service_instance.transcriber.is_available()
            else:
                checks["transcriber"] = False
        except Exception:
            checks["transcriber"] = False

        # Check transport status
        try:
            if hasattr(_service_instance, "transport") and _service_instance.transport:
                checks["transport"] = _service_instance.transport.is_connected()
            else:
                checks["transport"] = False
        except Exception:
            checks["transport"] = False
    else:
        # No service instance - assume not ready
        checks["audio_device"] = False
        checks["transcriber"] = False
        checks["transport"] = False

    # Ready if all checks pass
    ready = all(checks.values())

    return ReadinessResponse(
        ready=ready,
        checks=checks,
    )


@router.get("/status", response_model=StatusResponse)
async def detailed_status() -> StatusResponse:
    """Detailed status for debugging and monitoring.

    Provides comprehensive information about all service components,
    their status, and runtime metrics.

    Returns:
        StatusResponse with detailed component information

    Example:
        >>> curl http://localhost:8000/status
        {"status": "running", "version": "0.2.13", "uptime_seconds": 123.45, "components": {...}}
    """
    uptime = time.time() - _start_time

    components: Dict[str, ComponentStatus] = {}

    if _service_instance:
        # Audio component status
        try:
            if (
                hasattr(_service_instance, "audio_source")
                and _service_instance.audio_source
            ):
                from dictacode_stt.audio import AudioPortManager

                manager = AudioPortManager()
                active_port = manager.get_active_port()

                components["audio"] = ComponentStatus(
                    available=active_port is not None,
                    details={
                        "port": active_port.port_id if active_port else None,
                        "streaming": (
                            _service_instance.audio_source.is_active()
                            if hasattr(_service_instance.audio_source, "is_active")
                            else False
                        ),
                    },
                )
            else:
                components["audio"] = ComponentStatus(
                    available=False,
                    details={"port": None, "streaming": False},
                )
        except Exception as e:
            components["audio"] = ComponentStatus(
                available=False,
                details={"error": str(e)},
            )

        # Transcriber component status
        try:
            if (
                hasattr(_service_instance, "transcriber")
                and _service_instance.transcriber
            ):
                transcriber = _service_instance.transcriber
                components["transcriber"] = ComponentStatus(
                    available=transcriber.is_available(),
                    details={
                        "name": transcriber.get_name(),
                        "streaming": (
                            transcriber.is_streaming()
                            if hasattr(transcriber, "is_streaming")
                            else False
                        ),
                    },
                )
            else:
                components["transcriber"] = ComponentStatus(
                    available=False,
                    details={"name": None, "streaming": False},
                )
        except Exception as e:
            components["transcriber"] = ComponentStatus(
                available=False,
                details={"error": str(e)},
            )

        # Transport component status
        try:
            if hasattr(_service_instance, "transport") and _service_instance.transport:
                transport = _service_instance.transport
                components["transport"] = ComponentStatus(
                    available=True,
                    details={
                        "type": transport.get_name(),
                        "status": transport.get_status().value,
                        "connected": transport.is_connected(),
                    },
                )
            else:
                components["transport"] = ComponentStatus(
                    available=False,
                    details={"type": None, "status": "unknown", "connected": False},
                )
        except Exception as e:
            components["transport"] = ComponentStatus(
                available=False,
                details={"error": str(e)},
            )

        # Logging component status
        try:
            from dictacode_stt.log_control import log_controller

            components["logging"] = ComponentStatus(
                available=True,
                details={
                    "level": log_controller.get_level(),
                    "debug_mode": log_controller.is_debug_mode(),
                    "debug_remaining": log_controller.get_debug_remaining(),
                },
            )
        except Exception as e:
            components["logging"] = ComponentStatus(
                available=False,
                details={"error": str(e)},
            )
    else:
        # No service instance
        components["audio"] = ComponentStatus(
            available=False,
            details={"error": "Service not initialized"},
        )
        components["transcriber"] = ComponentStatus(
            available=False,
            details={"error": "Service not initialized"},
        )
        components["transport"] = ComponentStatus(
            available=False,
            details={"error": "Service not initialized"},
        )
        components["logging"] = ComponentStatus(
            available=False,
            details={"error": "Service not initialized"},
        )

    # Determine overall status
    all_available = all(c.available for c in components.values())
    status = "running" if all_available else "degraded"

    return StatusResponse(
        status=status,
        version="0.2.13",
        uptime_seconds=uptime,
        components=components,
    )
