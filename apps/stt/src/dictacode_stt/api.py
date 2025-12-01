"""FastAPI server for audio port management (v0.2.4 Phase 6)."""

import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dictacode_stt.audio import AudioPortManager, AudioPort, PortStatus
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

    return app


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


@app.get("/api/audio/ports", response_model=AudioPortsResponse)
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


@app.post("/api/audio/select", response_model=SelectPortResponse)
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


@app.get("/api/audio/ports/{port_id}", response_model=AudioPortModel)
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


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "dictacode-stt-api",
        "version": "0.2.4",
    }
