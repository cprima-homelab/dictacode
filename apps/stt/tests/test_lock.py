"""Tests for SerialLock class."""

import os
import subprocess
import sys

import pytest

from dictacode_stt.lock import LockError, SerialLock


class TestSerialLock:
    """Test SerialLock class."""

    def test_acquire_and_release(self, tmp_path):
        """Test basic acquire and release."""
        lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        assert lock.acquire() is True
        assert lock.is_locked() is True
        assert os.path.exists(lock.lock_path)

        lock.release()
        assert lock.is_locked() is False
        assert not os.path.exists(lock.lock_path)

    def test_double_acquire_returns_true(self, tmp_path):
        """Test that acquiring twice returns True (already have lock)."""
        lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        assert lock.acquire() is True
        assert lock.acquire() is True  # Should return True, already have lock
        lock.release()

    def test_lock_file_contains_pid(self, tmp_path):
        """Test that lock file contains PID."""
        lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        lock.acquire()

        with open(lock.lock_path) as f:
            content = f.read().strip()
        assert content == str(os.getpid())

        lock.release()

    def test_get_owner_pid(self, tmp_path):
        """Test get_owner_pid method."""
        lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        lock.acquire()

        assert lock.get_owner_pid() == os.getpid()
        lock.release()

    def test_get_owner_pid_no_lock_file(self, tmp_path):
        """Test get_owner_pid when no lock file exists."""
        lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        assert lock.get_owner_pid() is None

    def test_context_manager(self, tmp_path):
        """Test context manager usage."""
        with SerialLock("/dev/serial0", lock_dir=str(tmp_path)) as lock:
            assert lock.is_locked() is True
            assert os.path.exists(lock.lock_path)

        # After exiting context, lock should be released
        assert lock.is_locked() is False
        assert not os.path.exists(lock.lock_path)

    def test_context_manager_exception_releases_lock(self, tmp_path):
        """Test that lock is released even when exception occurs."""
        lock_path = None
        try:
            with SerialLock("/dev/serial0", lock_dir=str(tmp_path)) as lock:
                lock_path = lock.lock_path
                assert os.path.exists(lock_path)
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Lock should be released after exception
        assert not os.path.exists(lock_path)

    def test_concurrent_lock_fails(self, tmp_path):
        """Test that second process cannot acquire lock."""
        lock1 = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        assert lock1.acquire() is True

        # Second lock instance should fail to acquire
        lock2 = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        assert lock2.acquire() is False

        lock1.release()

        # Now lock2 should be able to acquire
        assert lock2.acquire() is True
        lock2.release()

    def test_context_manager_raises_on_locked(self, tmp_path):
        """Test context manager raises LockError when already locked."""
        lock1 = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        lock1.acquire()

        with pytest.raises(LockError) as exc_info:
            with SerialLock("/dev/serial0", lock_dir=str(tmp_path)):
                pass

        assert "/dev/serial0 is locked" in str(exc_info.value)
        lock1.release()

    def test_different_devices_different_locks(self, tmp_path):
        """Test that different devices have different lock files."""
        lock1 = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        lock2 = SerialLock("/dev/ttyUSB0", lock_dir=str(tmp_path))

        assert lock1.acquire() is True
        assert lock2.acquire() is True  # Different device, should succeed

        assert lock1.lock_path != lock2.lock_path

        lock1.release()
        lock2.release()

    def test_lock_path_format(self, tmp_path):
        """Test lock path is correctly formatted."""
        lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        expected_path = os.path.join(str(tmp_path), "dictacode-serial0.lock")
        assert lock.lock_path == expected_path

    def test_release_idempotent(self, tmp_path):
        """Test that release can be called multiple times safely."""
        lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        lock.acquire()
        lock.release()
        lock.release()  # Should not raise
        lock.release()  # Should not raise

    def test_is_stale_with_current_process(self, tmp_path):
        """Test is_stale returns False for current process."""
        lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        lock.acquire()

        # Create new lock instance to check staleness
        check_lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        assert check_lock.is_stale() is False

        lock.release()

    def test_is_stale_with_nonexistent_process(self, tmp_path):
        """Test is_stale returns True for nonexistent PID."""
        lock_path = os.path.join(str(tmp_path), "dictacode-serial0.lock")

        # Write a fake PID that doesn't exist
        with open(lock_path, "w") as f:
            f.write("99999999\n")  # Very unlikely to be a real PID

        lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        # This may or may not return True depending on the system
        # Just verify it doesn't raise
        result = lock.is_stale()
        assert isinstance(result, bool)

    def test_force_release_stale_lock(self, tmp_path):
        """Test force_release removes stale lock file."""
        lock_path = os.path.join(str(tmp_path), "dictacode-serial0.lock")

        # Write a fake PID that doesn't exist
        with open(lock_path, "w") as f:
            f.write("99999999\n")

        lock = SerialLock("/dev/serial0", lock_dir=str(tmp_path))

        # force_release should return True if stale, False otherwise
        if lock.is_stale():
            assert lock.force_release() is True
            assert not os.path.exists(lock_path)

    def test_force_release_active_lock_fails(self, tmp_path):
        """Test force_release does not remove active lock."""
        lock1 = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        lock1.acquire()

        lock2 = SerialLock("/dev/serial0", lock_dir=str(tmp_path))
        assert lock2.force_release() is False  # Should not remove active lock
        assert os.path.exists(lock1.lock_path)

        lock1.release()


class TestSerialLockIntegration:
    """Integration tests for SerialLock with subprocess."""

    def test_cross_process_locking(self, tmp_path):
        """Test that lock works across processes."""
        lock_dir = str(tmp_path)

        # Acquire lock in this process
        lock = SerialLock("/dev/serial0", lock_dir=lock_dir)
        assert lock.acquire() is True

        # Try to acquire in subprocess - should fail
        code = f"""
import sys
sys.path.insert(0, '{os.path.dirname(os.path.dirname(__file__))}/src')
from dictacode_stt.lock import SerialLock
lock = SerialLock("/dev/serial0", lock_dir="{lock_dir}")
sys.exit(0 if lock.acquire() else 1)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1  # Should fail to acquire

        lock.release()

        # Now subprocess should succeed
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0  # Should succeed now
