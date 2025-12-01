"""Device state management for STT.

v0.2.3: Expanded SolutionState covering full lifecycle from install to operation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import logging

logger = logging.getLogger(__name__)


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
class SttState:
    """Single source of truth for solution state (on STT controller)."""

    state: SolutionState = SolutionState.UNCONFIGURED
    failure_reason: Optional[str] = None
    model: str = "tiny"
    language: str = "en"
    hid_keymap: str = "en_us"  # track what we told HID to use

    def transition_to(self, new_state: SolutionState, reason: str = None) -> None:
        """Transition to new state with logging."""
        old = self.state
        self.state = new_state
        self.failure_reason = reason if new_state == SolutionState.FAILED else None
        logger.info(f"State transition: {old.value} → {new_state.value}")

    def set_hid_keymap(self, keymap: str) -> None:
        """Track the keymap we've sent to HID."""
        old = self.hid_keymap
        self.hid_keymap = keymap
        logger.info(f"hid_keymap: {old} → {keymap}")

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
