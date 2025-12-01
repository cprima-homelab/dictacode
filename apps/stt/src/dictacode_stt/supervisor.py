"""
supervisor.py - Layer 5: Link health monitoring and fault tolerance.

v0.2.3: Detects conditions (prerequisites, link health) and signals state transitions.

Usage:
    state = SttState()
    supervisor = LinkSupervisor(state, config)

    # In main loop
    if state.should_poll_prerequisites():
        if supervisor.check_prerequisites():
            supervisor.signal_prerequisites_ready()

    # Pet systemd watchdog
    supervisor.notify_watchdog()
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dictacode_stt.state import SttState, SolutionState

logger = logging.getLogger(__name__)


@dataclass
class SupervisorConfig:
    """Configuration for LinkSupervisor."""

    whisper_binary: Path
    whisper_model: Path
    uart_device: str
    ping_interval: float = 5.0  # seconds between pings
    timeout: float = 30.0  # seconds without message = dead link
    max_backoff: float = 30.0  # max reconnect delay


@dataclass
class LinkSupervisor:
    """
    Detect conditions and signal state transitions.

    v0.2.3 responsibilities:
    - Detect prerequisites (whisper binary/model)
    - Detect UART link availability
    - Monitor link health
    - Signal state transitions to SttState
    - Calculate exponential backoff for reconnection
    - Notify systemd watchdog
    """

    state: SttState
    config: SupervisorConfig

    # Internal state (managed internally)
    link_healthy: bool = field(default=True, init=False)
    last_msg_time: float = field(default_factory=time.monotonic, init=False)
    last_ping_time: float = field(default_factory=time.monotonic, init=False)
    reconnect_attempts: int = field(default=0, init=False)

    # Detection methods (called in main loop)
    def check_prerequisites(self) -> bool:
        """Detect if whisper binary and model exist."""
        return (
            self.config.whisper_binary.exists()
            and self.config.whisper_model.exists()
        )

    def check_link_available(self) -> bool:
        """Detect if UART device exists."""
        return Path(self.config.uart_device).exists()

    def check_health(self) -> bool:
        """
        Check if link is healthy based on last activity time.

        Returns:
            True if link is healthy, False if timed out
        """
        elapsed = time.monotonic() - self.last_msg_time

        if elapsed > self.config.timeout:
            if self.link_healthy:
                logger.warning(
                    f"Link timeout: no activity for {elapsed:.1f}s (threshold: {self.config.timeout}s)"
                )
                self._mark_unhealthy()
            return False

        return self.link_healthy

    def mark_activity(self) -> None:
        """
        Called when any message is sent/received successfully.

        Updates last_msg_time and marks link healthy if it was unhealthy.
        """
        self.last_msg_time = time.monotonic()

        if not self.link_healthy:
            logger.info("Link recovered after activity")
            self._mark_healthy()

    def reconnect_delay(self) -> float:
        """
        Calculate exponential backoff delay for reconnection.

        Returns:
            Delay in seconds: 1s → 2s → 4s → 8s → 16s → 30s (max)
        """
        delay = min(2 ** self.reconnect_attempts, self.config.max_backoff)
        return delay

    def should_send_ping(self) -> bool:
        """
        Check if it's time to send a ping.

        Returns:
            True if ping_interval has elapsed since last ping
        """
        return time.monotonic() - self.last_ping_time > self.config.ping_interval

    def mark_ping_sent(self) -> None:
        """Record that a ping was sent."""
        self.last_ping_time = time.monotonic()

    # State transition signals
    def signal_prerequisites_ready(self) -> None:
        """Signal state: prerequisites are now available."""
        if self.state.state == SolutionState.UNCONFIGURED:
            self.state.transition_to(SolutionState.LINK_PENDING)

    def signal_link_available(self) -> None:
        """Signal state: UART is now available."""
        if self.state.state == SolutionState.LINK_PENDING:
            self.state.transition_to(SolutionState.HANDSHAKE_INIT)

    def signal_handshake_complete(self) -> None:
        """Signal state: peer responded to probe."""
        if self.state.state == SolutionState.HANDSHAKE_INIT:
            self.state.transition_to(SolutionState.LISTENING)

    def signal_link_degraded(self) -> None:
        """Signal state: link has issues but recoverable."""
        if self.state.state == SolutionState.LISTENING:
            self.state.transition_to(SolutionState.DEGRADED)

    def signal_link_lost(self) -> None:
        """Signal state: link is dead, need reconnect."""
        if self.state.is_operational():
            self.state.transition_to(SolutionState.LINK_PENDING)

    def on_reconnect_attempt(self) -> None:
        """Called before each reconnection attempt. Increments attempt counter."""
        self.reconnect_attempts += 1
        delay = self.reconnect_delay()
        logger.info(
            f"Reconnection attempt {self.reconnect_attempts} "
            f"(backoff: {delay:.1f}s)"
        )

    def on_reconnect_success(self) -> None:
        """Called after successful reconnection. Resets attempt counter."""
        if self.reconnect_attempts > 0:
            logger.info(
                f"Reconnected after {self.reconnect_attempts} attempts"
            )
        self.reconnect_attempts = 0
        self._mark_healthy()
        self.mark_activity()  # Reset timeout

    def _mark_healthy(self) -> None:
        """Internal: mark link as healthy."""
        self.link_healthy = True
        logger.debug("Link marked healthy")

    def _mark_unhealthy(self) -> None:
        """Internal: mark link as unhealthy."""
        self.link_healthy = False
        logger.debug("Link marked unhealthy")

    def notify_watchdog(self) -> bool:
        """
        Notify systemd watchdog if running under systemd.

        Returns:
            True if notification was sent, False otherwise
        """
        try:
            from systemd.daemon import notify
            notify("WATCHDOG=1")
            return True
        except ImportError:
            return False

    def get_status(self) -> dict:
        """
        Get current supervisor status as a dictionary.

        Returns:
            Dict with link_healthy, last_activity, reconnect_attempts
        """
        return {
            "link_healthy": self.link_healthy,
            "last_activity_ago": time.monotonic() - self.last_msg_time,
            "reconnect_attempts": self.reconnect_attempts,
            "timeout": self.config.timeout,
            "ping_interval": self.config.ping_interval,
            "state": self.state.state.value,
        }
