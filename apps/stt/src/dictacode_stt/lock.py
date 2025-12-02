"""
lock.py - Serial port locking to prevent concurrent access.

Uses fcntl.flock() for advisory file locking with lock files.

Usage:
    lock = SerialLock("/dev/serial0")
    if lock.acquire():
        try:
            # Use serial port
            pass
        finally:
            lock.release()

    # Or use as context manager:
    with SerialLock("/dev/serial0") as lock:
        # Use serial port
        pass
"""

import fcntl
import os
from typing import Optional


class LockError(Exception):
    """Exception raised when lock acquisition fails."""

    pass


class SerialLock:
    """
    Advisory file lock for serial ports.

    Prevents multiple processes from accessing the same serial port
    simultaneously by using fcntl.flock() with a lock file.

    Lock file locations:
    - /run/lock/dictacode-{device}.lock (when running as systemd service)
    - /tmp/dictacode-{device}.lock (fallback for manual runs)
    """

    def __init__(self, device: str, lock_dir: Optional[str] = None):
        """
        Initialize serial lock.

        Args:
            device: Serial device path (e.g., /dev/serial0)
            lock_dir: Optional lock directory override (for testing)
        """
        self.device = device
        device_name = os.path.basename(device)

        # Determine lock directory
        if lock_dir:
            self._lock_dir = lock_dir
        elif os.path.isdir("/run/lock") and os.access("/run/lock", os.W_OK):
            self._lock_dir = "/run/lock"
        else:
            self._lock_dir = "/tmp"

        self.lock_path = os.path.join(self._lock_dir, f"dictacode-{device_name}.lock")
        self._lock_fd: Optional[int] = None

    def acquire(self, blocking: bool = False) -> bool:
        """
        Try to acquire exclusive lock.

        Args:
            blocking: If True, block until lock is available.
                     If False (default), return immediately if locked.

        Returns:
            True if lock acquired successfully.

        Raises:
            LockError: If lock file cannot be created or other OS error.
        """
        if self._lock_fd is not None:
            return True  # Already have lock

        try:
            # Create/open lock file
            self._lock_fd = os.open(self.lock_path, os.O_CREAT | os.O_RDWR, 0o644)

            # Try to acquire lock
            flags = fcntl.LOCK_EX
            if not blocking:
                flags |= fcntl.LOCK_NB

            fcntl.flock(self._lock_fd, flags)

            # Write PID to lock file (for debugging)
            os.ftruncate(self._lock_fd, 0)
            os.write(self._lock_fd, f"{os.getpid()}\n".encode())

            return True

        except BlockingIOError:
            # Lock held by another process
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None
            return False

        except OSError as e:
            if self._lock_fd is not None:
                os.close(self._lock_fd)
                self._lock_fd = None
            raise LockError(f"Failed to create lock file {self.lock_path}: {e}")

    def release(self) -> None:
        """Release the lock and remove lock file."""
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
            except OSError:
                pass  # Ignore unlock errors

            try:
                os.close(self._lock_fd)
            except OSError:
                pass  # Ignore close errors

            try:
                os.unlink(self.lock_path)
            except OSError:
                pass  # Ignore removal errors (file may not exist)

            self._lock_fd = None

    def is_locked(self) -> bool:
        """Check if this instance holds the lock."""
        return self._lock_fd is not None

    def get_owner_pid(self) -> Optional[int]:
        """
        Get PID of process holding the lock (if any).

        Returns:
            PID of lock owner, or None if lock file doesn't exist or is invalid.
        """
        try:
            with open(self.lock_path) as f:
                content = f.read().strip()
                return int(content) if content else None
        except (OSError, ValueError):
            return None

    def is_stale(self) -> bool:
        """
        Check if lock file exists but owning process is gone.

        Returns:
            True if lock file exists but owner process doesn't exist.
        """
        pid = self.get_owner_pid()
        if pid is None:
            return False

        # Check if process exists
        try:
            os.kill(pid, 0)  # Signal 0 = check existence
            return False
        except ProcessLookupError:
            return True  # Process doesn't exist
        except PermissionError:
            return False  # Process exists but we can't signal it

    def force_release(self) -> bool:
        """
        Force-remove a stale lock file.

        Only removes the lock file if the owning process no longer exists.

        Returns:
            True if lock file was removed, False otherwise.
        """
        if not self.is_stale():
            return False

        try:
            os.unlink(self.lock_path)
            return True
        except OSError:
            return False

    def __enter__(self) -> "SerialLock":
        """Context manager entry - acquire lock or raise."""
        if not self.acquire():
            pid = self.get_owner_pid()
            msg = f"{self.device} is locked by another process."
            if pid:
                msg += f" Check {self.lock_path} (PID: {pid})"
            raise LockError(msg)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - release lock."""
        self.release()

    def __del__(self) -> None:
        """Destructor - ensure lock is released."""
        self.release()
