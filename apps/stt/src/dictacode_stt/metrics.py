"""Prometheus metrics for dictacode STT (v0.2.13 Phase 4)."""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)

# Optional import - metrics disabled if not installed
try:
    from prometheus_client import (
        REGISTRY,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
        start_http_server,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.debug("prometheus_client not available, metrics disabled")


class Metrics:
    """Application metrics for Prometheus (v0.2.13).

    Provides counters, histograms, and gauges for monitoring dictacode STT
    performance and health.

    Example:
        >>> metrics = Metrics(enabled=True, port=9100)
        >>> metrics.start_server()
        >>> metrics.set_info(version="0.2.13", transcriber="whisper", transport="uart")
        >>> metrics.record_transcription("success", "whisper", 1.23)
    """

    def __init__(self, enabled: bool = False, port: int = 9100):
        """Initialize metrics collection.

        Args:
            enabled: Enable Prometheus metrics
            port: Port for metrics HTTP server
        """
        self.enabled = enabled and PROMETHEUS_AVAILABLE
        self.port = port

        if not self.enabled:
            return

        # Info metric
        self.info = Info(
            "dictacode",
            "Dictacode application info",
        )

        # Counters
        self.transcriptions_total = Counter(
            "dictacode_transcriptions_total",
            "Total transcription attempts",
            ["status", "transcriber"],  # success, error, timeout
        )

        self.hid_commands_total = Counter(
            "dictacode_hid_commands_total",
            "Total HID commands sent",
            ["type"],  # text, keypress, command
        )

        self.audio_chunks_total = Counter(
            "dictacode_audio_chunks_total",
            "Total audio chunks processed",
        )

        self.transport_reconnects_total = Counter(
            "dictacode_transport_reconnects_total",
            "Total transport reconnection attempts",
            ["transport"],
        )

        # Histograms
        self.transcription_duration = Histogram(
            "dictacode_transcription_duration_seconds",
            "Transcription duration in seconds",
            ["transcriber"],
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
        )

        self.audio_buffer_duration = Histogram(
            "dictacode_audio_buffer_duration_seconds",
            "Audio buffer duration before transcription",
            buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0],
        )

        # Gauges
        self.audio_buffer_size = Gauge(
            "dictacode_audio_buffer_bytes",
            "Current audio buffer size in bytes",
        )

        self.link_healthy = Gauge(
            "dictacode_link_healthy",
            "HID link health (1=healthy, 0=unhealthy)",
        )

        self.active_connections = Gauge(
            "dictacode_active_connections",
            "Number of active transport connections",
        )

        self.transcription_queue_size = Gauge(
            "dictacode_transcription_queue_size",
            "Number of items in transcription queue",
        )

        # v0.3.5: State metrics
        self.state_transitions_total = Counter(
            "dictacode_state_transitions_total",
            "Total state transitions",
            ["from_state", "to_state"],
        )

        self.current_state = Gauge(
            "dictacode_current_state",
            "Current service state (1=active, 0=inactive)",
            ["state"],
        )

        logger.info("Prometheus metrics initialized")

    def start_server(self) -> None:
        """Start metrics HTTP server.

        Starts an HTTP server on the configured port to expose /metrics endpoint.

        Example:
            >>> metrics.start_server()
            # Metrics available at http://localhost:9100/metrics
        """
        if not self.enabled:
            return

        try:
            start_http_server(self.port)
            logger.info(
                f"Prometheus metrics available at http://localhost:{self.port}/metrics"
            )
        except Exception as e:
            logger.error(f"Failed to start metrics server: {e}")

    def set_info(self, version: str, transcriber: str, transport: str) -> None:
        """Set application info metric.

        Args:
            version: Application version
            transcriber: Transcriber name (whisper, vosk)
            transport: Transport type (uart, usb-serial, wifi)
        """
        if not self.enabled:
            return

        self.info.info(
            {
                "version": version,
                "transcriber": transcriber,
                "transport": transport,
            }
        )

    def record_transcription(
        self,
        status: str,
        transcriber: str,
        duration: float,
    ) -> None:
        """Record a transcription attempt.

        Args:
            status: Transcription status (success, error, timeout)
            transcriber: Transcriber name
            duration: Transcription duration in seconds
        """
        if not self.enabled:
            return

        self.transcriptions_total.labels(status=status, transcriber=transcriber).inc()
        self.transcription_duration.labels(transcriber=transcriber).observe(duration)

    def record_hid_command(self, cmd_type: str) -> None:
        """Record HID command sent.

        Args:
            cmd_type: Command type (text, keypress, command)
        """
        if not self.enabled:
            return

        self.hid_commands_total.labels(type=cmd_type).inc()

    def record_audio_chunk(
        self, buffer_duration: float = None, buffer_size: int = None
    ) -> None:
        """Record audio chunk processed.

        Args:
            buffer_duration: Audio buffer duration in seconds (optional)
            buffer_size: Audio buffer size in bytes (optional)
        """
        if not self.enabled:
            return

        self.audio_chunks_total.inc()

        if buffer_duration is not None:
            self.audio_buffer_duration.observe(buffer_duration)

        if buffer_size is not None:
            self.audio_buffer_size.set(buffer_size)

    def set_link_health(self, healthy: bool) -> None:
        """Set HID link health status.

        Args:
            healthy: True if link is healthy, False otherwise
        """
        if not self.enabled:
            return

        self.link_healthy.set(1 if healthy else 0)

    def set_active_connections(self, count: int) -> None:
        """Set number of active transport connections.

        Args:
            count: Number of active connections
        """
        if not self.enabled:
            return

        self.active_connections.set(count)

    def set_transcription_queue_size(self, size: int) -> None:
        """Set transcription queue size.

        Args:
            size: Queue size
        """
        if not self.enabled:
            return

        self.transcription_queue_size.set(size)

    def record_transport_reconnect(self, transport: str) -> None:
        """Record transport reconnection attempt.

        Args:
            transport: Transport type (uart, usb-serial, wifi)
        """
        if not self.enabled:
            return

        self.transport_reconnects_total.labels(transport=transport).inc()

    def record_state_transition(self, old_state: str, new_state: str) -> None:
        """Record a state transition (v0.3.5).

        Args:
            old_state: Previous state value
            new_state: New state value
        """
        if not self.enabled:
            return

        # Increment transition counter
        self.state_transitions_total.labels(
            from_state=old_state, to_state=new_state
        ).inc()

        # Update current state gauge - set new state to 1, others implicitly 0
        # We need to know all possible states to reset them
        from dictacode_stt.state import SolutionState

        for state in SolutionState:
            self.current_state.labels(state=state.value).set(
                1 if state.value == new_state else 0
            )

    def get_metrics(self) -> bytes:
        """Get metrics in Prometheus format.

        Returns:
            Metrics in Prometheus text format

        Example:
            >>> metrics_data = metrics.get_metrics()
            >>> print(metrics_data.decode())
        """
        if not self.enabled:
            return b""

        return generate_latest(REGISTRY)


# Global metrics instance (disabled by default)
metrics = Metrics(enabled=False)


def init_metrics(enabled: bool = False, port: int = 9100) -> Metrics:
    """Initialize metrics collection.

    Args:
        enabled: Enable Prometheus metrics
        port: Port for metrics HTTP server

    Returns:
        Initialized Metrics instance

    Example:
        >>> from dictacode_stt.metrics import init_metrics
        >>> metrics = init_metrics(enabled=True, port=9100)
        >>> metrics.start_server()
    """
    global metrics
    metrics = Metrics(enabled=enabled, port=port)

    if enabled:
        if not PROMETHEUS_AVAILABLE:
            logger.warning(
                "Prometheus metrics requested but prometheus_client not installed. "
                "Install with: pip install prometheus_client"
            )
        else:
            metrics.start_server()

    return metrics
