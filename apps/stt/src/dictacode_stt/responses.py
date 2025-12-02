"""Shared response types for CLI and API (v0.2.5 Phase 3).

These dataclasses provide a common data format that can be:
- Rendered as human-readable text by CLI
- Serialized to JSON by API endpoints
- Used by both without duplication
"""

from dataclasses import asdict, dataclass
from typing import List, Optional


@dataclass
class AudioPortCapabilitiesResponse:
    """Audio port hardware capabilities."""

    sample_rates: List[int]
    channels: int
    formats: List[str]
    native_rate: int


@dataclass
class AudioPortResponse:
    """Single audio port information."""

    port_id: str
    port_type: str
    name: str
    status: str
    capabilities: AudioPortCapabilitiesResponse
    device_index: int

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "port_id": self.port_id,
            "port_type": self.port_type,
            "name": self.name,
            "status": self.status,
            "capabilities": asdict(self.capabilities),
            "device_index": self.device_index,
        }


@dataclass
class AudioPortsListResponse:
    """Response for audio port listing (shared by CLI and API)."""

    ports: List[AudioPortResponse]
    active_port: Optional[str] = None
    default_port: Optional[str] = None
    pipeline_target_rate: int = 16000

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "ports": [p.to_dict() for p in self.ports],
            "active_port": self.active_port,
            "default_port": self.default_port,
            "pipeline_target_rate": self.pipeline_target_rate,
        }

    @classmethod
    def from_audio_port_manager(cls, manager) -> "AudioPortsListResponse":
        """Create response from AudioPortManager.

        Args:
            manager: AudioPortManager instance

        Returns:
            AudioPortsListResponse with all port data
        """

        ports = manager.list_ports()
        active = manager.get_active_port()
        default = manager.get_default_port()

        return cls(
            ports=[
                AudioPortResponse(
                    port_id=port.port_id,
                    port_type=port.port_type,
                    name=port.name,
                    status=port.status.value,
                    capabilities=AudioPortCapabilitiesResponse(
                        sample_rates=port.capabilities.sample_rates,
                        channels=port.capabilities.channels,
                        formats=port.capabilities.formats,
                        native_rate=port.capabilities.native_rate,
                    ),
                    device_index=port.device_index,
                )
                for port in ports
            ],
            active_port=active.port_id if active else None,
            default_port=default.port_id if default else None,
        )


@dataclass
class ServiceStatusResponse:
    """Service status information (for future API endpoints)."""

    state: str
    uptime_seconds: float
    iterations: int
    last_transcription: Optional[str] = None
    audio_port: Optional[str] = None
    supervisor_healthy: bool = True


@dataclass
class TranscriptionResult:
    """Transcription result (for future API endpoints)."""

    text: str
    duration_seconds: float
    language: str
    confidence: Optional[float] = None


@dataclass
class ErrorResponse:
    """Error response for API."""

    error: str
    detail: Optional[str] = None
    code: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {"error": self.error}
        if self.detail:
            result["detail"] = self.detail
        if self.code:
            result["code"] = self.code
        return result
