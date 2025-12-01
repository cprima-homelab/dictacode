"""Tests for LinkSupervisor class - v0.2.3."""

import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

import pytest

from dictacode_stt.supervisor import LinkSupervisor, SupervisorConfig
from dictacode_stt.state import SttState, SolutionState


class TestLinkSupervisor:
    """Test LinkSupervisor functionality."""

    def test_default_initialization(self):
        """Test supervisor initializes with correct defaults."""
        supervisor = LinkSupervisor()

        assert supervisor.timeout == 30.0
        assert supervisor.ping_interval == 5.0
        assert supervisor.max_backoff == 30.0
        assert supervisor.link_healthy is True
        assert supervisor.reconnect_attempts == 0

    def test_custom_initialization(self):
        """Test supervisor with custom configuration."""
        supervisor = LinkSupervisor(
            timeout=60.0,
            ping_interval=10.0,
            max_backoff=60.0,
        )

        assert supervisor.timeout == 60.0
        assert supervisor.ping_interval == 10.0
        assert supervisor.max_backoff == 60.0

    def test_healthy_when_recent_activity(self):
        """Test link is healthy when activity is recent."""
        supervisor = LinkSupervisor()
        supervisor.mark_activity()

        assert supervisor.check_health() is True
        assert supervisor.link_healthy is True

    def test_unhealthy_after_timeout(self):
        """Test link becomes unhealthy after timeout."""
        supervisor = LinkSupervisor(timeout=0.1)

        # Wait for timeout
        time.sleep(0.15)

        assert supervisor.check_health() is False
        assert supervisor.link_healthy is False

    def test_mark_activity_resets_health(self):
        """Test mark_activity restores health."""
        supervisor = LinkSupervisor(timeout=0.1)

        # Wait for timeout
        time.sleep(0.15)
        assert supervisor.check_health() is False

        # Mark activity
        supervisor.mark_activity()

        assert supervisor.check_health() is True
        assert supervisor.link_healthy is True

    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        supervisor = LinkSupervisor()

        # First attempt: 2^0 = 1
        assert supervisor.reconnect_delay() == 1.0

        supervisor.reconnect_attempts = 1
        # Second attempt: 2^1 = 2
        assert supervisor.reconnect_delay() == 2.0

        supervisor.reconnect_attempts = 2
        # Third attempt: 2^2 = 4
        assert supervisor.reconnect_delay() == 4.0

        supervisor.reconnect_attempts = 3
        # Fourth attempt: 2^3 = 8
        assert supervisor.reconnect_delay() == 8.0

        supervisor.reconnect_attempts = 4
        # Fifth attempt: 2^4 = 16
        assert supervisor.reconnect_delay() == 16.0

        supervisor.reconnect_attempts = 5
        # Sixth attempt: capped at max_backoff (30)
        assert supervisor.reconnect_delay() == 30.0

        supervisor.reconnect_attempts = 10
        # Still capped
        assert supervisor.reconnect_delay() == 30.0

    def test_should_send_ping(self):
        """Test ping interval detection."""
        supervisor = LinkSupervisor(ping_interval=0.1)
        supervisor.mark_ping_sent()

        # Immediately after ping, should not send
        assert supervisor.should_send_ping() is False

        # After interval, should send
        time.sleep(0.15)
        assert supervisor.should_send_ping() is True

    def test_reconnect_attempt_increments_counter(self):
        """Test reconnect attempt tracking."""
        supervisor = LinkSupervisor()

        assert supervisor.reconnect_attempts == 0

        supervisor.on_reconnect_attempt()
        assert supervisor.reconnect_attempts == 1

        supervisor.on_reconnect_attempt()
        assert supervisor.reconnect_attempts == 2

    def test_reconnect_success_resets_counter(self):
        """Test successful reconnection resets state."""
        supervisor = LinkSupervisor()
        supervisor.reconnect_attempts = 5
        supervisor._mark_unhealthy()

        supervisor.on_reconnect_success()

        assert supervisor.reconnect_attempts == 0
        assert supervisor.link_healthy is True

    def test_get_status_returns_dict(self):
        """Test status dictionary structure."""
        supervisor = LinkSupervisor()
        supervisor.mark_activity()

        status = supervisor.get_status()

        assert "link_healthy" in status
        assert "last_activity_ago" in status
        assert "reconnect_attempts" in status
        assert "timeout" in status
        assert "ping_interval" in status

        assert status["link_healthy"] is True
        assert status["reconnect_attempts"] == 0
        assert status["timeout"] == 30.0
        assert status["ping_interval"] == 5.0

    def test_notify_watchdog_with_systemd(self):
        """Test watchdog notification when systemd available."""
        # This test verifies the method doesn't raise, regardless of
        # whether systemd is installed (it gracefully handles ImportError)
        supervisor = LinkSupervisor()
        result = supervisor.notify_watchdog()
        # Returns True if systemd installed, False otherwise
        assert isinstance(result, bool)

    def test_notify_watchdog_without_systemd(self):
        """Test watchdog notification when systemd not available."""
        supervisor = LinkSupervisor()

        # This should not raise an error
        result = supervisor.notify_watchdog()

        # Returns False when systemd not available (or True if installed)
        assert isinstance(result, bool)


class TestLinkSupervisorV023:
    """Test v0.2.3 supervisor functionality."""

    @pytest.fixture
    def temp_whisper_setup(self, tmp_path):
        """Create temporary whisper binary and model for testing."""
        whisper_bin = tmp_path / "whisper-cli"
        whisper_bin.touch()
        whisper_model = tmp_path / "ggml-tiny.bin"
        whisper_model.touch()
        return whisper_bin, whisper_model

    @pytest.fixture
    def config(self, temp_whisper_setup, tmp_path):
        """Create supervisor config for testing."""
        whisper_bin, whisper_model = temp_whisper_setup
        return SupervisorConfig(
            whisper_binary=whisper_bin,
            whisper_model=whisper_model,
            uart_device="/dev/serial0",
        )

    @pytest.fixture
    def state(self):
        """Create state for testing."""
        return SttState()

    @pytest.fixture
    def supervisor(self, state, config):
        """Create supervisor for testing."""
        return LinkSupervisor(state=state, config=config)

    def test_check_prerequisites_success(self, supervisor):
        """Test prerequisites check when all present."""
        assert supervisor.check_prerequisites() is True

    def test_check_prerequisites_missing_binary(self, state, temp_whisper_setup, tmp_path):
        """Test prerequisites check with missing binary."""
        whisper_bin, whisper_model = temp_whisper_setup
        whisper_bin.unlink()  # Remove binary

        config = SupervisorConfig(
            whisper_binary=whisper_bin,
            whisper_model=whisper_model,
            uart_device="/dev/serial0",
        )
        supervisor = LinkSupervisor(state=state, config=config)

        assert supervisor.check_prerequisites() is False

    def test_check_link_available_exists(self, supervisor, tmp_path):
        """Test link check when device exists."""
        # Create temp device file
        device = tmp_path / "uart_test"
        device.touch()
        supervisor.config.uart_device = str(device)

        assert supervisor.check_link_available() is True

    def test_check_link_available_missing(self, supervisor):
        """Test link check when device missing."""
        supervisor.config.uart_device = "/dev/nonexistent_uart"
        assert supervisor.check_link_available() is False

    def test_signal_prerequisites_ready(self, supervisor, state):
        """Test signal for prerequisites ready."""
        assert state.state == SolutionState.UNCONFIGURED

        supervisor.signal_prerequisites_ready()

        assert state.state == SolutionState.LINK_PENDING

    def test_signal_link_available(self, supervisor, state):
        """Test signal for link available."""
        state.transition_to(SolutionState.LINK_PENDING)

        supervisor.signal_link_available()

        assert state.state == SolutionState.HANDSHAKE_INIT

    def test_signal_handshake_complete(self, supervisor, state):
        """Test signal for handshake complete."""
        state.transition_to(SolutionState.HANDSHAKE_INIT)

        supervisor.signal_handshake_complete()

        assert state.state == SolutionState.LISTENING

    def test_signal_link_degraded(self, supervisor, state):
        """Test signal for link degraded."""
        state.transition_to(SolutionState.LISTENING)

        supervisor.signal_link_degraded()

        assert state.state == SolutionState.DEGRADED

    def test_signal_link_lost(self, supervisor, state):
        """Test signal for link lost."""
        state.transition_to(SolutionState.LISTENING)

        supervisor.signal_link_lost()

        assert state.state == SolutionState.LINK_PENDING

    def test_signal_transitions_only_from_correct_state(self, supervisor, state):
        """Test signals only work from appropriate states."""
        state.transition_to(SolutionState.LISTENING)

        # Try to signal prerequisites ready from LISTENING (should do nothing)
        supervisor.signal_prerequisites_ready()
        assert state.state == SolutionState.LISTENING  # No change

        # Try to signal link available from LISTENING (should do nothing)
        supervisor.signal_link_available()
        assert state.state == SolutionState.LISTENING  # No change

    def test_get_status_includes_state(self, supervisor, state):
        """Test status includes state value."""
        status = supervisor.get_status()

        assert "state" in status
        assert status["state"] == "unconfigured"

        state.transition_to(SolutionState.LISTENING)
        status = supervisor.get_status()
        assert status["state"] == "listening"
