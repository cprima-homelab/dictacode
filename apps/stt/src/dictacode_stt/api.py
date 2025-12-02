"""FastAPI server for audio port management (v0.2.4 Phase 6)."""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Set

from fastapi import (
    APIRouter,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from dictacode_stt.audio import AudioPort, AudioPortManager
from dictacode_stt.paths import AUDIO_CONFIG_DIR
from dictacode_stt.responses import AudioPortsListResponse


logger = logging.getLogger(__name__)


# Pydantic models for API
class AudioPortCapabilitiesModel(BaseModel):
    """Audio port capabilities."""

    sample_rates: List[int]
    channels: int
    formats: List[str]
    native_rate: int


class AudioPortModel(BaseModel):
    """Audio port information."""

    port_id: str
    port_type: str
    name: str
    capabilities: AudioPortCapabilitiesModel
    status: str
    device_index: int


class AudioPortsResponse(BaseModel):
    """Response for GET /api/audio/ports."""

    ports: List[AudioPortModel]
    active_port: Optional[str] = None
    pipeline_target_rate: int = 16000


class SelectPortRequest(BaseModel):
    """Request body for POST /api/audio/select."""

    port_id: str


class SelectPortResponse(BaseModel):
    """Response for POST /api/audio/select."""

    success: bool
    message: str
    selected_port: Optional[AudioPortModel] = None


# Global port manager (initialized by create_app)
_port_manager: Optional[AudioPortManager] = None

# Global service reference (v0.3.0: for WebSocket integration)
_stt_service: Optional[any] = None

# Global Jinja2 templates (v0.3.0 Phase 3)
templates: Optional[Jinja2Templates] = None

# Global badge state (v0.3.3: cosmetic license system)
_badge_state: Optional["BadgeState"] = None


def set_badge_state(state: "BadgeState") -> None:
    """Set badge state (called from main.py at startup).

    Args:
        state: BadgeState from license validation
    """
    global _badge_state
    _badge_state = state
    logger.info(f"Badge state set: tier={state.tier}, badge={state.badge}")


def register_service(service: any) -> None:
    """Register STT service for WebSocket integration (v0.3.0).

    Args:
        service: SttService instance to register
    """
    global _stt_service
    _stt_service = service

    # Wire WebSocket manager to service
    if service and hasattr(service, "websocket_manager"):
        service.websocket_manager = ws_manager
        logger.info("WebSocket manager wired to STT service")


# Create APIRouter for all routes (v0.3.0: proper FastAPI pattern)
router = APIRouter()


def create_app(config_dir: Optional[str] = None) -> FastAPI:
    """Create FastAPI application.

    Args:
        config_dir: Audio configuration directory. Defaults to AUDIO_CONFIG_DIR.

    Returns:
        FastAPI application instance
    """
    global _port_manager

    # Use paths.py constant if not explicitly provided
    effective_config_dir = config_dir or str(AUDIO_CONFIG_DIR)

    app = FastAPI(
        title="dictacode STT Audio API",
        description="REST API for audio port management (v0.2.4)",
        version="0.2.4",
    )

    # CORS for web console
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize port manager
    _port_manager = AudioPortManager(config_dir=effective_config_dir)
    logger.info(
        f"AudioPortManager initialized with {len(_port_manager.list_ports())} ports"
    )

    # v0.3.0 Phase 2: Mount static files for WebSocket test client
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
        logger.info(f"Static files mounted from {static_dir}")

    # v0.3.0 Phase 3: Configure Jinja2 templates
    templates_dir = Path(__file__).parent / "templates"
    if templates_dir.exists():
        global templates
        templates = Jinja2Templates(directory=str(templates_dir))
        logger.info(f"Jinja2 templates configured from {templates_dir}")

    # Include routers (v0.3.0: use module-level router)
    from dictacode_stt import diagnostics_api, health

    app.include_router(router)
    app.include_router(health.router)
    app.include_router(diagnostics_api.router)

    return app


# Create default app instance (routes defined below will use this)
app = create_app()


def _port_to_model(port: AudioPort) -> AudioPortModel:
    """Convert AudioPort to Pydantic model."""
    return AudioPortModel(
        port_id=port.port_id,
        port_type=port.port_type,
        name=port.name,
        capabilities=AudioPortCapabilitiesModel(
            sample_rates=port.capabilities.sample_rates,
            channels=port.capabilities.channels,
            formats=port.capabilities.formats,
            native_rate=port.capabilities.native_rate,
        ),
        status=port.status.value,
        device_index=port.device_index,
    )


@router.get("/api/audio/ports", response_model=AudioPortsResponse)
async def list_audio_ports(refresh: bool = False):
    """List all available audio input ports.

    Args:
        refresh: If true, re-scan for devices (hot-plug support)

    Returns:
        AudioPortsResponse with all ports and active port
    """
    if not _port_manager:
        raise HTTPException(status_code=500, detail="AudioPortManager not initialized")

    try:
        # Use shared response type to build data
        response = AudioPortsListResponse.from_audio_port_manager(_port_manager)
        response_dict = response.to_dict()

        # Convert to Pydantic model for FastAPI
        return AudioPortsResponse(
            ports=[
                AudioPortModel(
                    port_id=p["port_id"],
                    port_type=p["port_type"],
                    name=p["name"],
                    capabilities=AudioPortCapabilitiesModel(**p["capabilities"]),
                    status=p["status"],
                    device_index=p["device_index"],
                )
                for p in response_dict["ports"]
            ],
            active_port=response_dict["active_port"],
            pipeline_target_rate=response_dict["pipeline_target_rate"],
        )
    except Exception as e:
        logger.error(f"Failed to list audio ports: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list ports: {e!s}")


@router.post("/api/audio/select", response_model=SelectPortResponse)
async def select_audio_port(request: SelectPortRequest):
    """Select an audio port for recording.

    Args:
        request: SelectPortRequest with port_id

    Returns:
        SelectPortResponse indicating success/failure

    Note:
        In v0.2.4, this endpoint only validates the port exists.
        Actual port switching requires service restart.
        Full hot-swap support planned for v0.3.0.
    """
    if not _port_manager:
        raise HTTPException(status_code=500, detail="AudioPortManager not initialized")

    try:
        port = _port_manager.get_port(request.port_id)

        if not port:
            return SelectPortResponse(
                success=False,
                message=f"Port not found: {request.port_id}",
            )

        # v0.2.4: Validate port exists but don't switch
        # Full switching requires integration with SttService
        logger.info(f"Port selection requested: {request.port_id}")

        return SelectPortResponse(
            success=True,
            message=f"Port validated: {request.port_id}. Restart service with --port {request.port_id} to activate.",
            selected_port=_port_to_model(port),
        )

    except Exception as e:
        logger.error(f"Failed to select port: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to select port: {e!s}")


@router.get("/api/audio/ports/{port_id}", response_model=AudioPortModel)
async def get_audio_port(port_id: str):
    """Get details for a specific audio port.

    Args:
        port_id: Port identifier (e.g., "rode-videomic-ntg")

    Returns:
        AudioPortModel with port details
    """
    if not _port_manager:
        raise HTTPException(status_code=500, detail="AudioPortManager not initialized")

    try:
        port = _port_manager.get_port(port_id)

        if not port:
            raise HTTPException(status_code=404, detail=f"Port not found: {port_id}")

        return _port_to_model(port)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get port: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get port: {e!s}")


# v0.3.0 Phase 3: Web Panel Routes
@router.get("/cp", response_class=HTMLResponse)
async def control_panel(request: Request):
    """Control panel page (v0.3.0 Phase 3)."""
    if not templates:
        raise HTTPException(status_code=500, detail="Templates not initialized")

    try:
        from dictacode_stt import __version__
    except ImportError:
        __version__ = "unknown"

    return templates.TemplateResponse(
        "control-panel.html",
        {
            "request": request,
            "version": __version__,
        },
    )


@router.get("/cp/config", response_class=HTMLResponse)
async def config_page(request: Request):
    """Configuration page (v0.3.0 Phase 3)."""
    if not templates:
        raise HTTPException(status_code=500, detail="Templates not initialized")

    try:
        from dictacode_stt import __version__
    except ImportError:
        __version__ = "unknown"

    return templates.TemplateResponse(
        "config.html",
        {
            "request": request,
            "version": __version__,
        },
    )


@router.get("/cp/diagnostics", response_class=HTMLResponse)
async def diagnostics_page(request: Request):
    """Diagnostics page (v0.3.0 Phase 3)."""
    if not templates:
        raise HTTPException(status_code=500, detail="Templates not initialized")

    try:
        from dictacode_stt import __version__
    except ImportError:
        __version__ = "unknown"

    return templates.TemplateResponse(
        "diagnostics.html",
        {
            "request": request,
            "version": __version__,
        },
    )


@router.get("/cp/metrics", response_class=HTMLResponse)
async def metrics_page(request: Request):
    """Metrics page (v0.3.0 Phase 3)."""
    if not templates:
        raise HTTPException(status_code=500, detail="Templates not initialized")

    try:
        from dictacode_stt import __version__
    except ImportError:
        __version__ = "unknown"

    return templates.TemplateResponse(
        "metrics.html",
        {
            "request": request,
            "version": __version__,
        },
    )


# v0.2.13: Health endpoints moved to health.py module (routers now included in _register_routes)
# v0.2.9: Diagnostics API endpoints (routers now included in _register_routes)


# v0.2.13 Phase 4: Prometheus metrics endpoint
@router.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint (v0.2.13).

    Exposes metrics in Prometheus text format for scraping.

    Returns:
        Metrics in Prometheus format or 404 if metrics disabled
    """
    from fastapi import Response

    from dictacode_stt.metrics import metrics

    if not metrics.enabled:
        return Response(
            content="Metrics not enabled. Start API with --metrics flag or service with --metrics.",
            status_code=404,
        )

    return Response(
        content=metrics.get_metrics(),
        media_type="text/plain",
    )


# v0.3.0 Phase 3.4: Service state control endpoints
@router.post("/api/service/pause")
async def pause_service():
    """Pause transcription service.

    Transitions service from LISTENING to PAUSED state.
    Audio recording continues but transcription is paused.

    Returns:
        {"status": "ok", "state": "paused"} on success
        {"status": "error", "message": "..."} on failure
    """
    from dictacode_stt.health import _service_instance

    if not _service_instance:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        success = _service_instance.pause()
        if success:
            return {
                "status": "ok",
                "state": _service_instance.get_state(),
                "message": "Service paused",
            }
        else:
            current_state = _service_instance.get_state()
            return {
                "status": "error",
                "state": current_state,
                "message": f"Cannot pause from state '{current_state}'",
            }
    except Exception as e:
        logger.error(f"Failed to pause service: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/service/resume")
async def resume_service():
    """Resume transcription service.

    Transitions service from PAUSED to LISTENING state.
    Resumes normal transcription operation.

    Returns:
        {"status": "ok", "state": "listening"} on success
        {"status": "error", "message": "..."} on failure
    """
    from dictacode_stt.health import _service_instance

    if not _service_instance:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        success = _service_instance.resume()
        if success:
            return {
                "status": "ok",
                "state": _service_instance.get_state(),
                "message": "Service resumed",
            }
        else:
            current_state = _service_instance.get_state()
            return {
                "status": "error",
                "state": current_state,
                "message": f"Cannot resume from state '{current_state}'",
            }
    except Exception as e:
        logger.error(f"Failed to resume service: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/service/state")
async def get_service_state():
    """Get current service state.

    Returns:
        {"state": "listening|paused|degraded|...", "timestamp": "..."}
    """
    from datetime import datetime

    from dictacode_stt.health import _service_instance

    if not _service_instance:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        return {
            "state": _service_instance.get_state(),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get service state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# v0.3.3: License badge endpoints (cosmetic, never gates features)
@router.get("/api/license")
async def get_license_state():
    """Get badge license state (v0.3.3).

    Returns the current badge state from license validation.
    This is purely cosmetic and never gates features.

    Returns:
        {
            "tier": "free|supporter|donor|contributor|multiplicator",
            "badge": "Name or null",
            "name": "Name or null",
            "issued_at": "YYYY-MM-DD or null"
        }
    """
    from dictacode_stt.license import BadgeState

    if _badge_state is None:
        # Return default free state if not initialized
        return BadgeState().to_dict()

    return _badge_state.to_dict()


class LicenseSetRequest(BaseModel):
    """Request body for POST /api/license."""

    token: str
    scope: str = "user"  # "user" or "system"


@router.post("/api/license")
async def set_license_token(request: LicenseSetRequest):
    """Save license token and update badge state (v0.3.3).

    Saves the token to the appropriate location and validates it.
    This is purely cosmetic and never gates features.

    Args:
        request: LicenseSetRequest with token and optional scope

    Returns:
        {
            "status": "ok|error",
            "message": "...",
            "state": {...}  # Current badge state after update
        }
    """
    from pathlib import Path

    from dictacode_stt.license import BadgeState, load_badge_state

    global _badge_state

    # Determine save path based on scope
    if request.scope == "system":
        save_path = Path("/etc/dictacode/license.key")
    else:
        save_path = Path.home() / ".config/dictacode/license.key"

    try:
        # Create parent directory if needed
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # Save token
        save_path.write_text(request.token.strip() + "\n")
        logger.info(f"License token saved to: {save_path}")

        # Validate and update badge state
        new_state = load_badge_state(token=request.token)
        _badge_state = new_state

        if new_state.tier == "free":
            return {
                "status": "warning",
                "message": "Token saved but validation failed. Check token format.",
                "path": str(save_path),
                "state": new_state.to_dict(),
            }

        return {
            "status": "ok",
            "message": f"License saved and validated: {new_state.tier}",
            "path": str(save_path),
            "state": new_state.to_dict(),
        }

    except PermissionError:
        return {
            "status": "error",
            "message": f"Permission denied writing to {save_path}. Use scope='user' or run with elevated privileges.",
            "state": (_badge_state.to_dict() if _badge_state else BadgeState().to_dict()),
        }
    except Exception as e:
        logger.error(f"Failed to save license: {e}", exc_info=True)
        return {
            "status": "error",
            "message": str(e),
            "state": (_badge_state.to_dict() if _badge_state else BadgeState().to_dict()),
        }


@router.delete("/api/license")
async def delete_license_token():
    """Remove license token and reset to free tier (v0.3.3).

    Removes license files from both user and system locations.

    Returns:
        {
            "status": "ok",
            "message": "...",
            "state": {...}  # Badge state after deletion (free)
        }
    """
    from pathlib import Path

    from dictacode_stt.license import BadgeState, LICENSE_PATHS

    global _badge_state

    removed = []
    for path in LICENSE_PATHS:
        if path.exists():
            try:
                path.unlink()
                removed.append(str(path))
                logger.info(f"Removed license file: {path}")
            except PermissionError:
                logger.warning(f"Permission denied removing {path}")
            except Exception as e:
                logger.warning(f"Failed to remove {path}: {e}")

    # Reset to free state
    _badge_state = BadgeState()

    return {
        "status": "ok",
        "message": f"License removed from: {', '.join(removed)}" if removed else "No license files found",
        "removed": removed,
        "state": _badge_state.to_dict(),
    }


# v0.3.0 Phase 2: WebSocket support
class WebSocketConnectionManager:
    """Manages active WebSocket connections for live updates."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket connected, total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        """Unregister a WebSocket connection."""
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket disconnected, total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        if not self.active_connections:
            return

        async with self._lock:
            disconnected = set()
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending to WebSocket: {e}")
                    disconnected.add(connection)

            # Remove disconnected clients
            self.active_connections -= disconnected

    async def send_to(self, websocket: WebSocket, message: dict):
        """Send a message to a specific WebSocket client."""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending to WebSocket: {e}")
            await self.disconnect(websocket)


# Global WebSocket manager
ws_manager = WebSocketConnectionManager()


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live updates (v0.3.0).

    Provides real-time updates for:
    - Transcription results
    - Service status changes
    - Audio port events
    - Errors and warnings

    Message format:
        {
            "type": "transcription" | "status" | "error" | "ping",
            "data": {...}
        }
    """
    await ws_manager.connect(websocket)

    try:
        # Send initial status with current service state (v0.3.0 Phase 3.4)
        from dictacode_stt.health import _service_instance

        current_state = (
            _service_instance.get_state() if _service_instance else "unknown"
        )

        await ws_manager.send_to(
            websocket,
            {
                "type": "status",
                "data": {
                    "connected": True,
                    "api_version": "0.3.0",
                    "message": "WebSocket connected",
                    "state": current_state,
                },
            },
        )

        # Keep connection alive and handle client messages
        while True:
            try:
                data = await websocket.receive_json()

                # Handle ping/pong
                if data.get("type") == "ping":
                    await ws_manager.send_to(
                        websocket,
                        {"type": "pong", "data": {"timestamp": data.get("timestamp")}},
                    )

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    finally:
        await ws_manager.disconnect(websocket)
