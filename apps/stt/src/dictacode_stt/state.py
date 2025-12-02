"""Device state management for STT.

v0.2.3: Expanded SolutionState covering full lifecycle from install to operation.
v0.3.5: Added state history tracking and serialization for IPC.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


logger = logging.getLogger(__name__)

# v0.3.5: Configurable history buffer size
DEFAULT_HISTORY_SIZE = 20
_history_max_size = int(os.environ.get("DICTACODE_STATE_HISTORY_SIZE", DEFAULT_HISTORY_SIZE))


class SolutionState(Enum):
    """
    Full solution state - covers entire lifecycle from install to operation.
    State name tells you what to do next.
    Authoritative source: STT controller.
    """

    # Setup phases
    UNCONFIGURED = "unconfigured"  # Prerequisites missing (whisper, model)
    LINK_PENDING = "link_pending"  # Prerequisites OK, UART not available
    HANDSHAKE_INIT = "handshake_init"  # UART open, waiting for peer response

    # Operational phases
    LISTENING = "listening"  # Normal transcription mode
    MAINTENANCE = "maintenance"  # Diagnostic mode (no transcription)
    PAUSED = "paused"  # User-requested pause

    # Failure phases
    DEGRADED = "degraded"  # Running with issues (retries, latency)
    FAILED = "failed"  # Unrecoverable error


@dataclass
class StateTransition:
    """Record of a state transition (v0.3.5).

    Used for history tracking in the state ring buffer.
    """

    timestamp: datetime
    old_state: str
    new_state: str
    reason: str | None
    source: str  # "service", "api", "supervisor"

    def to_dict(self) -> dict:
        """Serialize transition for API/IPC response."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "old_state": self.old_state,
            "new_state": self.new_state,
            "reason": self.reason,
            "source": self.source,
        }


@dataclass
class SttState:
    """Single source of truth for solution state (on STT controller).

    v0.3.5: Added history tracking and serialization for IPC.
    """

    state: SolutionState = SolutionState.UNCONFIGURED
    failure_reason: str | None = None
    model: str = "tiny"
    language: str = "en"
    hid_keymap: str = "en_us"  # track what we told HID to use

    # v0.3.5: History tracking (ring buffer)
    _history: list[StateTransition] = field(default_factory=list, repr=False)
    _history_max: int = field(default_factory=lambda: _history_max_size, repr=False)

    def transition_to(
        self,
        new_state: SolutionState,
        reason: str | None = None,
        source: str = "service",
    ) -> None:
        """Transition to new state with logging and history tracking.

        Args:
            new_state: The target state.
            reason: Optional reason for the transition (shown in FAILED/DEGRADED).
            source: Origin of the transition ("service", "api", "supervisor").
        """
        old = self.state
        self.state = new_state
        self.failure_reason = reason if new_state in (
            SolutionState.FAILED,
            SolutionState.DEGRADED,
        ) else None
        logger.info(f"State transition: {old.value} → {new_state.value}")

        # v0.3.5: Record transition in history
        self._history.append(
            StateTransition(
                timestamp=datetime.now(),
                old_state=old.value,
                new_state=new_state.value,
                reason=reason,
                source=source,
            )
        )
        # Trim to max size
        if len(self._history) > self._history_max:
            self._history = self._history[-self._history_max :]

        # v0.3.5: Record metric (if metrics enabled)
        try:
            from dictacode_stt.metrics import metrics

            metrics.record_state_transition(old.value, new_state.value)
        except Exception:
            pass  # Metrics may not be initialized yet

    def set_hid_keymap(self, keymap: str) -> None:
        """Track the keymap we've sent to HID."""
        old = self.hid_keymap
        self.hid_keymap = keymap
        logger.info(f"hid_keymap: {old} → {keymap}")

    # v0.3.5: Serialization methods for IPC
    def to_dict(self) -> dict:
        """Serialize state for API/IPC response."""
        return {
            "state": self.state.value,
            "failure_reason": self.failure_reason,
            "model": self.model,
            "language": self.language,
            "hid_keymap": self.hid_keymap,
        }

    def get_history(self) -> list[dict]:
        """Get state transition history as serializable list."""
        return [t.to_dict() for t in self._history]

    # Behavior predicates
    def should_transcribe(self) -> bool:
        """Return True if device should transcribe audio."""
        return self.state == SolutionState.LISTENING

    def should_send(self) -> bool:
        """Return True if device should send to HID."""
        return self.state in (
            SolutionState.LISTENING,
            SolutionState.MAINTENANCE,
            SolutionState.DEGRADED,
        )

    def should_poll_prerequisites(self) -> bool:
        """Return True if should poll for prerequisites."""
        return self.state == SolutionState.UNCONFIGURED

    def should_poll_link(self) -> bool:
        """Return True if should poll for UART link."""
        return self.state == SolutionState.LINK_PENDING

    def should_handshake(self) -> bool:
        """Return True if should attempt handshake."""
        return self.state == SolutionState.HANDSHAKE_INIT

    def is_operational(self) -> bool:
        """Return True if in an operational state."""
        return self.state in (
            SolutionState.LISTENING,
            SolutionState.MAINTENANCE,
            SolutionState.PAUSED,
            SolutionState.DEGRADED,
        )
