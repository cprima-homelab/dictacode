"""FastAPI server for audio port management (v0.2.4 Phase 6)."""

import logging
import asyncio
from typing import List, Optional, Set
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from dictacode_stt.audio import AudioPortManager, AudioPort, PortStatus
from dictacode_stt.responses import AudioPortsListResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

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


def register_service(service: any) -> None:
    """Register STT service for WebSocket integration (v0.3.0).

    Args:
        service: SttService instance to register
    """
    global _stt_service
    _stt_service = service

    # Wire WebSocket manager to service
    if service and hasattr(service, 'websocket_manager'):
        service.websocket_manager = ws_manager
        logger.info("WebSocket manager wired to STT service")


# Create APIRouter for all routes (v0.3.0: proper FastAPI pattern)
router = APIRouter()


def create_app(config_dir: str = "/etc/dictacode/audio") -> FastAPI:
    """Create FastAPI application.

    Args:
        config_dir: Audio configuration directory

    Returns:
        FastAPI application instance
    """
    global _port_manager

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
    _port_manager = AudioPortManager(config_dir=config_dir)
    logger.info(f"AudioPortManager initialized with {len(_port_manager.list_ports())} ports")

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
    from dictacode_stt import health, diagnostics_api
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
        raise HTTPException(status_code=500, detail=f"Failed to list ports: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to select port: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Failed to get port: {str(e)}")


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

    return templates.TemplateResponse("control-panel.html", {
        "request": request,
        "version": __version__,
    })


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
    from dictacode_stt.metrics import metrics
    from fastapi import Response

    if not metrics.enabled:
        return Response(
            content="Metrics not enabled. Start API with --metrics flag or service with --metrics.",
            status_code=404,
        )

    return Response(
        content=metrics.get_metrics(),
        media_type="text/plain",
    )


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
        # Send initial status
        await ws_manager.send_to(
            websocket,
            {
                "type": "status",
                "data": {
                    "connected": True,
                    "api_version": "0.3.0",
                    "message": "WebSocket connected",
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
                        websocket, {"type": "pong", "data": {"timestamp": data.get("timestamp")}}
                    )

            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected")
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break

    finally:
        await ws_manager.disconnect(websocket)
