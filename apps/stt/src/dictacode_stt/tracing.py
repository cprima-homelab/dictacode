"""Per-utterance tracing for pipeline diagnostics.

v0.3.17: Track each utterance through the processing pipeline to diagnose
where content is dropped.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class TraceStatus(Enum):
    """Status of an utterance trace."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DROPPED = "dropped"
    TIMEOUT = "timeout"


@dataclass
class UtteranceTrace:
    """Per-utterance trace record tracking journey through pipeline."""

    trace_id: str
    created_at: float  # timestamp when trace started

    # Stage timestamps (None = not reached)
    audio_captured_at: Optional[float] = None
    transcription_started_at: Optional[float] = None
    transcription_completed_at: Optional[float] = None
    transport_sent_at: Optional[float] = None
    hid_received_at: Optional[float] = None
    hid_typed_at: Optional[float] = None

    # Outcome
    status: TraceStatus = TraceStatus.IN_PROGRESS
    drop_point: Optional[str] = None
    drop_reason: Optional[str] = None

    # Content (for debugging)
    audio_duration_sec: Optional[float] = None
    text_raw: Optional[str] = None
    char_count: int = 0

    def mark_stage(self, stage: str, timestamp: Optional[float] = None) -> None:
        """Mark a stage as reached."""
        ts = timestamp or time.time()
        attr_name = f"{stage}_at"
        if hasattr(self, attr_name):
            setattr(self, attr_name, ts)
        else:
            logger.warning(f"Unknown trace stage: {stage}")

    def mark_drop(self, point: str, reason: str) -> None:
        """Mark trace as dropped at a specific point."""
        self.status = TraceStatus.DROPPED
        self.drop_point = point
        self.drop_reason = reason
        logger.warning(
            f"TRACE DROP: {point} - {reason}",
            extra={
                "trace_id": self.trace_id,
                "trace_stage": "dropped",
                "drop_point": point,
            },
        )

    def mark_completed(self, hid_typed_at: Optional[float] = None) -> None:
        """Mark trace as successfully completed."""
        self.status = TraceStatus.COMPLETED
        if hid_typed_at:
            self.hid_typed_at = hid_typed_at

    def mark_timeout(self, timeout_sec: float) -> None:
        """Mark trace as timed out."""
        self.status = TraceStatus.TIMEOUT
        self.drop_point = "timeout"
        self.drop_reason = f"No response within {timeout_sec}s"

    def latency_ms(self) -> Optional[float]:
        """Total end-to-end latency in milliseconds."""
        if self.hid_typed_at and self.created_at:
            return (self.hid_typed_at - self.created_at) * 1000
        return None

    def to_dict(self) -> dict:
        """Serialize for IPC/API."""
        return {
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "status": self.status.value,
            "drop_point": self.drop_point,
            "drop_reason": self.drop_reason,
            "latency_ms": self.latency_ms(),
            "stages": {
                "audio_captured": self.audio_captured_at,
                "transcription_started": self.transcription_started_at,
                "transcription_completed": self.transcription_completed_at,
                "transport_sent": self.transport_sent_at,
                "hid_received": self.hid_received_at,
                "hid_typed": self.hid_typed_at,
            },
            "content": {
                "audio_duration_sec": self.audio_duration_sec,
                "text_raw": self.text_raw,
                "char_count": self.char_count,
            },
        }


class TraceRegistry:
    """Ring buffer of recent traces for diagnostics."""

    def __init__(self, max_traces: int = 100, timeout_sec: float = 30.0):
        self._traces: OrderedDict[str, UtteranceTrace] = OrderedDict()
        self._max_traces = max_traces
        self._timeout_sec = timeout_sec
        self._counter = 0
        self._lock = threading.Lock()
        self._current_trace: Optional[UtteranceTrace] = None

    def create_trace(self) -> UtteranceTrace:
        """Create and register a new trace."""
        with self._lock:
            now = time.time()
            self._counter += 1
            trace_id = f"utt-{int(now * 1000)}-{self._counter:04d}"

            trace = UtteranceTrace(trace_id=trace_id, created_at=now)
            self._traces[trace_id] = trace
            self._current_trace = trace

            # Trim to max size
            while len(self._traces) > self._max_traces:
                self._traces.popitem(last=False)

            logger.debug(
                f"Created trace {trace_id}",
                extra={"trace_id": trace_id, "trace_stage": "created"},
            )
            return trace

    @property
    def current_trace(self) -> Optional[UtteranceTrace]:
        """Get the current active trace."""
        return self._current_trace

    def get_trace(self, trace_id: str) -> Optional[UtteranceTrace]:
        """Get trace by ID."""
        return self._traces.get(trace_id)

    def mark_stage(
        self, trace_id: str, stage: str, timestamp: Optional[float] = None
    ) -> None:
        """Mark a stage timestamp on a trace."""
        trace = self._traces.get(trace_id)
        if trace:
            trace.mark_stage(stage, timestamp)

    def mark_drop(self, trace_id: str, point: str, reason: str) -> None:
        """Mark trace as dropped."""
        trace = self._traces.get(trace_id)
        if trace:
            trace.mark_drop(point, reason)

    def mark_completed(
        self, trace_id: str, hid_typed_at: Optional[float] = None
    ) -> None:
        """Mark trace as completed (received HID response)."""
        trace = self._traces.get(trace_id)
        if trace:
            trace.mark_completed(hid_typed_at)
            logger.info(
                f"Trace {trace_id} completed, latency={trace.latency_ms():.0f}ms",
                extra={"trace_id": trace_id, "trace_stage": "completed"},
            )

    def get_recent(self, limit: int = 20) -> list[UtteranceTrace]:
        """Get most recent traces."""
        with self._lock:
            traces = list(self._traces.values())[-limit:]
            return list(reversed(traces))

    def get_drops(self, limit: int = 20) -> list[UtteranceTrace]:
        """Get recent dropped traces."""
        with self._lock:
            drops = [t for t in self._traces.values() if t.status == TraceStatus.DROPPED]
            return list(reversed(drops[-limit:]))

    def get_stats(self) -> dict:
        """Get aggregate statistics."""
        with self._lock:
            traces = list(self._traces.values())
            completed = [t for t in traces if t.status == TraceStatus.COMPLETED]
            dropped = [t for t in traces if t.status == TraceStatus.DROPPED]
            in_progress = [t for t in traces if t.status == TraceStatus.IN_PROGRESS]
            timeouts = [t for t in traces if t.status == TraceStatus.TIMEOUT]

            # Drop point histogram
            drop_points: dict[str, int] = {}
            for t in dropped:
                pt = t.drop_point or "unknown"
                drop_points[pt] = drop_points.get(pt, 0) + 1

            # Average latency
            latencies = [t.latency_ms() for t in completed if t.latency_ms()]
            avg_latency = sum(latencies) / len(latencies) if latencies else None

            return {
                "total_traces": len(traces),
                "completed": len(completed),
                "dropped": len(dropped),
                "in_progress": len(in_progress),
                "timeout": len(timeouts),
                "avg_latency_ms": avg_latency,
                "drop_points": drop_points,
            }

    def cleanup_stale(self) -> int:
        """Mark stale traces as timeout. Returns count of traces marked."""
        now = time.time()
        count = 0
        with self._lock:
            for trace in self._traces.values():
                if trace.status == TraceStatus.IN_PROGRESS:
                    if now - trace.created_at > self._timeout_sec:
                        trace.mark_timeout(self._timeout_sec)
                        count += 1
        return count
