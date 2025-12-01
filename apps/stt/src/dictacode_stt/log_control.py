"""Runtime log level control for dictacode STT (v0.2.13 Phase 2)."""

from __future__ import annotations

import logging
import signal
import threading
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class LogLevelController:
    """Runtime log level control with temporary debug mode (v0.2.13).

    Features:
    - Get/set log level permanently
    - Enable debug mode temporarily with auto-revert
    - Signal handler for SIGUSR1 to toggle debug
    - Track debug mode expiration time

    Example:
        >>> controller = LogLevelController()
        >>> controller.enable_debug(duration_seconds=300)  # 5 minutes
        >>> controller.get_debug_remaining()
        298
        >>> controller.disable_debug()
    """

    def __init__(self):
        """Initialize log level controller."""
        self._original_level: str = "INFO"
        self._debug_timer: Optional[threading.Timer] = None
        self._debug_until: Optional[datetime] = None

    def get_level(self) -> str:
        """Get current log level.

        Returns:
            Current log level name (e.g., "INFO", "DEBUG")
        """
        return logging.getLevelName(logging.getLogger().level)

    def set_level(self, level: str) -> None:
        """Set log level permanently.

        Args:
            level: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)

        Example:
            >>> controller.set_level("WARNING")
        """
        self._original_level = level
        self._cancel_debug_timer()
        logging.getLogger().setLevel(level)
        logger.info(f"Log level set to {level}")

    def enable_debug(self, duration_seconds: int = 300) -> None:
        """Enable DEBUG level temporarily.

        Args:
            duration_seconds: Auto-revert after this many seconds (default: 300 = 5 min)

        Example:
            >>> controller.enable_debug(duration_seconds=600)  # 10 minutes
        """
        # Cancel any existing debug timer
        self._cancel_debug_timer()

        # Save current level if not already in debug mode
        if self.get_level() != "DEBUG":
            self._original_level = self.get_level()

        # Enable debug
        logging.getLogger().setLevel("DEBUG")
        self._debug_until = datetime.now() + timedelta(seconds=duration_seconds)

        logger.warning(
            f"DEBUG logging enabled for {duration_seconds}s "
            f"(until {self._debug_until.strftime('%H:%M:%S')})"
        )

        # Schedule auto-revert
        self._debug_timer = threading.Timer(
            duration_seconds,
            self._revert_from_debug,
        )
        self._debug_timer.daemon = True
        self._debug_timer.start()

    def disable_debug(self) -> None:
        """Disable debug mode and revert to original level.

        Example:
            >>> controller.disable_debug()
        """
        self._revert_from_debug()

    def _revert_from_debug(self) -> None:
        """Revert from debug to original level (internal)."""
        self._cancel_debug_timer()

        # Only revert if currently in DEBUG mode
        if self.get_level() == "DEBUG":
            logging.getLogger().setLevel(self._original_level)
            logger.info(f"Debug mode ended, reverted to {self._original_level}")

    def _cancel_debug_timer(self) -> None:
        """Cancel pending debug timer (internal)."""
        if self._debug_timer:
            self._debug_timer.cancel()
            self._debug_timer = None
        self._debug_until = None

    def get_debug_remaining(self) -> Optional[int]:
        """Get seconds remaining in debug mode, or None.

        Returns:
            Seconds remaining in debug mode, or None if not in debug mode

        Example:
            >>> controller.enable_debug(300)
            >>> remaining = controller.get_debug_remaining()
            >>> print(f"{remaining} seconds left")
        """
        if self._debug_until:
            remaining = (self._debug_until - datetime.now()).total_seconds()
            return max(0, int(remaining))
        return None

    def is_debug_mode(self) -> bool:
        """Check if currently in temporary debug mode.

        Returns:
            True if in debug mode with auto-revert scheduled
        """
        return self._debug_until is not None

    def setup_signal_handler(self) -> None:
        """Setup SIGUSR1 to toggle debug mode.

        When SIGUSR1 is received:
        - If in debug mode: disable debug
        - If not in debug mode: enable debug for 5 minutes

        Example:
            >>> controller.setup_signal_handler()
            # Then from shell: kill -SIGUSR1 <pid>
        """
        def handler(signum, frame):
            if self.get_level() == "DEBUG":
                self.disable_debug()
            else:
                self.enable_debug()

        signal.signal(signal.SIGUSR1, handler)
        logger.debug("SIGUSR1 handler registered for debug toggle")


# Global instance
log_controller = LogLevelController()
