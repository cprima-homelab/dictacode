"""Tests for LinkSupervisor class - v0.2.3."""

import time
from pathlib import Path
from unittest.mock import patch, MagicMock
import tempfile

import pytest

from dictacode_stt.supervisor import LinkSupervisor, SupervisorConfig
from dictacode_stt.state import SttState, SolutionState


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
