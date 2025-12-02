"""Diagnostics Aggregator - Live status from all components (v0.3.13).

Collects status() from each component and produces a unified live view
with staleness detection for pipeline stages (audio → ASR → send).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional


if TYPE_CHECKING:
    from dictacode_stt.state import SttState


# Configurable staleness threshold via environment variable
DEFAULT_STALENESS_THRESHOLD = 10.0
STALENESS_THRESHOLD_SEC = float(
    os.environ.get("DICTACODE_STALENESS_THRESHOLD", str(DEFAULT_STALENESS_THRESHOLD))
)


@dataclass
class DiagnosticsAggregator:
    """Aggregates live status from all components (v0.3.13).

    Visits each component's status() method and merges results into a single
    payload with flow staleness detection.

    Attributes:
        state: SttState instance
        service: SttService instance (for audio/transcriber/transport access)
        ipc_server: Optional DiagnosticsIpcServer instance
    """

    state: SttState
    service: Any  # SttService - avoid circular import
    ipc_server: Optional[Any] = None  # DiagnosticsIpcServer

    # Configurable threshold (class attribute, can be overridden)
    staleness_threshold: float = field(default=STALENESS_THRESHOLD_SEC)

    def get_status(self) -> dict[str, Any]:
        """Return aggregated live status from all components.

        Each component's status() is called and wrapped in try/except to
        ensure one failing component doesn't break the whole response.

        Returns:
            Dict with:
                - timestamp: Current time
                - components: Dict of component statuses
                - flow: Staleness detection results
        """
        now = time.time()
        components: dict[str, Any] = {}

        # State component
        try:
            components["state"] = self.state.status()
        except Exception as e:
            components["state"] = {"error": str(e)}

        # Audio component (via service)
        try:
            if hasattr(self.service, "audio_status"):
                components["audio"] = self.service.audio_status()
            else:
                components["audio"] = {"error": "audio_status not implemented"}
        except Exception as e:
            components["audio"] = {"error": str(e)}

        # ASR/Transcription component
        try:
            transcriber = getattr(self.service, "transcriber", None)
            if transcriber and hasattr(transcriber, "status"):
                components["asr"] = transcriber.status()
            elif transcriber:
                # Fallback for transcribers without status()
                components["asr"] = {
                    "backend": getattr(transcriber, "get_name", lambda: "unknown")(),
                    "available": getattr(transcriber, "is_available", lambda: True)(),
                }
            else:
                components["asr"] = {"available": False, "error": "No transcriber"}
        except Exception as e:
            components["asr"] = {"error": str(e)}

        # Transport component
        try:
            transport = getattr(self.service, "transport", None)
            if transport and hasattr(transport, "status"):
                components["transport"] = transport.status()
            elif transport:
                # Fallback for transports without status()
                components["transport"] = {
                    "type": getattr(transport, "get_name", lambda: "unknown")(),
                    "connected": getattr(transport, "is_connected", lambda: False)(),
                }
            else:
                components["transport"] = {"connected": False, "error": "No transport"}
        except Exception as e:
            components["transport"] = {"error": str(e)}

        # IPC server component
        try:
            if self.ipc_server and hasattr(self.ipc_server, "status"):
                components["ipc"] = self.ipc_server.status()
            else:
                components["ipc"] = {"available": False}
        except Exception as e:
            components["ipc"] = {"error": str(e)}

        # Compute flow staleness
        flow = self._compute_flow_staleness(components, now)

        return {
            "timestamp": now,
            "components": components,
            "flow": flow,
        }

    def _compute_flow_staleness(
        self, components: dict[str, Any], now: float
    ) -> dict[str, Any]:
        """Detect stale pipeline stages.

        Compares timestamps across audio → ASR → send stages to identify
        where the pipeline might be stuck.

        Args:
            components: Dict of component statuses
            now: Current timestamp

        Returns:
            Dict with freshness flags and staleness indicators
        """
        # Extract timestamps (safe for missing/None values)
        audio_ts = components.get("audio", {}).get("last_audio_ts")
        asr_ts = components.get("asr", {}).get("last_asr_ts")
        send_ts = components.get("transport", {}).get("last_send_ts")

        # Compute freshness (True if timestamp exists and is recent)
        audio_fresh = bool(
            audio_ts and (now - audio_ts) < self.staleness_threshold
        )
        asr_fresh = bool(
            asr_ts and (now - asr_ts) < self.staleness_threshold
        )
        send_fresh = bool(
            send_ts and (now - send_ts) < self.staleness_threshold
        )

        return {
            "audio_fresh": audio_fresh,
            "asr_fresh": asr_fresh,
            "send_fresh": send_fresh,
            # Staleness flags: upstream fresh but downstream stale
            "asr_stale": audio_fresh and not asr_fresh,
            "send_stale": asr_fresh and not send_fresh,
            # Thresholds for debugging
            "threshold_sec": self.staleness_threshold,
        }
