"""
supervisor.py - Layer 5: Link health monitoring and fault tolerance.

Monitors UART link health and handles reconnection with exponential backoff.

Usage:
    supervisor = LinkSupervisor()

    # In main loop
    if not supervisor.check_health():
        reconnect()

    # When message received
    supervisor.mark_activity()

    # Pet systemd watchdog
    supervisor.notify_watchdog()
"""

import logging
import time
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class LinkSupervisor:
    """
    Monitor UART link health and handle failures.

    Responsibilities:
    - Track last message time
    - Detect link timeout (no activity for TIMEOUT seconds)
    - Calculate exponential backoff for reconnection
    - Optionally send periodic pings
    - Notify systemd watchdog
    """

    # Configuration (can be overridden at init)
    ping_interval: float = 5.0  # seconds between pings
    timeout: float = 30.0  # seconds without message = dead link
    max_backoff: float = 30.0  # max reconnect delay

    # State (managed internally)
    link_healthy: bool = field(default=True, init=False)
    last_msg_time: float = field(default_factory=time.monotonic, init=False)
    last_ping_time: float = field(default_factory=time.monotonic, init=False)
    reconnect_attempts: int = field(default=0, init=False)

    def check_health(self) -> bool:
        """
        Check if link is healthy based on last activity time.

        Returns:
            True if link is healthy, False if timed out
        """
        elapsed = time.monotonic() - self.last_msg_time

        if elapsed > self.timeout:
            if self.link_healthy:
                logger.warning(
                    f"Link timeout: no activity for {elapsed:.1f}s (threshold: {self.timeout}s)"
                )
                self._mark_unhealthy()
            return False

        return self.link_healthy

    def mark_activity(self) -> None:
        """
        Called when any message is received.

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
        delay = min(2**self.reconnect_attempts, self.max_backoff)
        return delay

    def should_send_ping(self) -> bool:
        """
        Check if it's time to send a ping.

        Returns:
            True if ping_interval has elapsed since last ping
        """
        return time.monotonic() - self.last_ping_time > self.ping_interval

    def mark_ping_sent(self) -> None:
        """Record that a ping was sent."""
        self.last_ping_time = time.monotonic()

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
            logger.info(f"Reconnected after {self.reconnect_attempts} attempts")
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
            "timeout": self.timeout,
            "ping_interval": self.ping_interval,
        }
