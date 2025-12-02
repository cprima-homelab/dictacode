"""Tests for dictacode_stt.state module - v0.2.3."""

from dictacode_stt.state import SolutionState, SttState


class TestSolutionState:
    """Tests for SolutionState enum."""

    def test_all_states_exist(self):
        """Test all states are defined."""
        assert SolutionState.UNCONFIGURED
        assert SolutionState.LINK_PENDING
        assert SolutionState.HANDSHAKE_INIT
        assert SolutionState.LISTENING
        assert SolutionState.MAINTENANCE
        assert SolutionState.PAUSED
        assert SolutionState.DEGRADED
        assert SolutionState.FAILED

    def test_state_values(self):
        """Test state string values."""
        assert SolutionState.UNCONFIGURED.value == "unconfigured"
        assert SolutionState.LISTENING.value == "listening"
        assert SolutionState.FAILED.value == "failed"


class TestSttState:
    """Tests for SttState dataclass."""

    def test_default_values(self):
        """Test default initialization."""
        state = SttState()
        assert state.state == SolutionState.UNCONFIGURED
        assert state.failure_reason is None
        assert state.model == "tiny"
        assert state.language == "en"
        assert state.hid_keymap == "en_us"

    def test_transition_to(self, caplog):
        """Test state transitions."""
        import logging

        caplog.set_level(logging.INFO, logger="dictacode_stt.state")

        state = SttState()

        state.transition_to(SolutionState.LINK_PENDING)
        assert state.state == SolutionState.LINK_PENDING
        assert "unconfigured → link_pending" in caplog.text

    def test_transition_to_failed_with_reason(self):
        """Test transition to FAILED state with reason."""
        state = SttState()
        state.transition_to(SolutionState.FAILED, reason="Test failure")

        assert state.state == SolutionState.FAILED
        assert state.failure_reason == "Test failure"

    def test_transition_clears_failure_reason(self):
        """Test that non-FAILED transitions clear failure_reason."""
        state = SttState()
        state.transition_to(SolutionState.FAILED, reason="Error")
        assert state.failure_reason == "Error"

        state.transition_to(SolutionState.UNCONFIGURED)
        assert state.failure_reason is None


class TestSttStateBehaviorPredicates:
    """Tests for state behavior predicates."""

    def test_should_transcribe(self):
        """Test should_transcribe predicate."""
        state = SttState()

        # Only LISTENING should transcribe
        state.transition_to(SolutionState.LISTENING)
        assert state.should_transcribe() is True

        state.transition_to(SolutionState.MAINTENANCE)
        assert state.should_transcribe() is False

        state.transition_to(SolutionState.UNCONFIGURED)
        assert state.should_transcribe() is False

    def test_should_send(self):
        """Test should_send predicate."""
        state = SttState()

        # LISTENING, MAINTENANCE, DEGRADED should send
        state.transition_to(SolutionState.LISTENING)
        assert state.should_send() is True

        state.transition_to(SolutionState.MAINTENANCE)
        assert state.should_send() is True

        state.transition_to(SolutionState.DEGRADED)
        assert state.should_send() is True

        # Others should not send
        state.transition_to(SolutionState.PAUSED)
        assert state.should_send() is False

        state.transition_to(SolutionState.UNCONFIGURED)
        assert state.should_send() is False

    def test_should_poll_prerequisites(self):
        """Test should_poll_prerequisites predicate."""
        state = SttState()

        # Only UNCONFIGURED should poll prerequisites
        assert state.should_poll_prerequisites() is True

        state.transition_to(SolutionState.LINK_PENDING)
        assert state.should_poll_prerequisites() is False

    def test_should_poll_link(self):
        """Test should_poll_link predicate."""
        state = SttState()

        # Only LINK_PENDING should poll link
        assert state.should_poll_link() is False

        state.transition_to(SolutionState.LINK_PENDING)
        assert state.should_poll_link() is True

        state.transition_to(SolutionState.LISTENING)
        assert state.should_poll_link() is False

    def test_should_handshake(self):
        """Test should_handshake predicate."""
        state = SttState()

        # Only HANDSHAKE_INIT should handshake
        assert state.should_handshake() is False

        state.transition_to(SolutionState.HANDSHAKE_INIT)
        assert state.should_handshake() is True

        state.transition_to(SolutionState.LISTENING)
        assert state.should_handshake() is False

    def test_is_operational(self):
        """Test is_operational predicate."""
        state = SttState()

        # Setup states are not operational
        assert state.is_operational() is False

        state.transition_to(SolutionState.LINK_PENDING)
        assert state.is_operational() is False

        # Operational states
        state.transition_to(SolutionState.LISTENING)
        assert state.is_operational() is True

        state.transition_to(SolutionState.MAINTENANCE)
        assert state.is_operational() is True

        state.transition_to(SolutionState.PAUSED)
        assert state.is_operational() is True

        state.transition_to(SolutionState.DEGRADED)
        assert state.is_operational() is True

        # FAILED is not operational
        state.transition_to(SolutionState.FAILED)
        assert state.is_operational() is False


class TestSttStateWorkflow:
    """Test realistic state workflows."""

    def test_fresh_install_workflow(self):
        """Test lifecycle from fresh install to normal operation."""
        state = SttState()

        # 1. Fresh install - UNCONFIGURED
        assert state.state == SolutionState.UNCONFIGURED
        assert state.should_poll_prerequisites() is True

        # 2. Prerequisites installed - LINK_PENDING
        state.transition_to(SolutionState.LINK_PENDING)
        assert state.should_poll_link() is True

        # 3. UART available - HANDSHAKE_INIT
        state.transition_to(SolutionState.HANDSHAKE_INIT)
        assert state.should_handshake() is True

        # 4. Handshake successful - LISTENING
        state.transition_to(SolutionState.LISTENING)
        assert state.should_transcribe() is True
        assert state.should_send() is True
        assert state.is_operational() is True

    def test_link_lost_recovery(self):
        """Test recovery from link loss."""
        state = SttState()
        state.transition_to(SolutionState.LISTENING)

        # Link degrades
        state.transition_to(SolutionState.DEGRADED)
        assert state.is_operational() is True
        assert state.should_send() is True  # Still try to send

        # Link completely lost
        state.transition_to(SolutionState.LINK_PENDING)
        assert state.is_operational() is False
        assert state.should_poll_link() is True

        # Recover through handshake
        state.transition_to(SolutionState.HANDSHAKE_INIT)
        state.transition_to(SolutionState.LISTENING)
        assert state.is_operational() is True

    def test_maintenance_mode(self):
        """Test maintenance mode for diagnostics."""
        state = SttState()
        state.transition_to(SolutionState.LISTENING)

        # Enter maintenance
        state.transition_to(SolutionState.MAINTENANCE)
        assert state.should_transcribe() is False  # No transcription
        assert state.should_send() is True  # Can send diagnostic commands
        assert state.is_operational() is True

        # Return to normal
        state.transition_to(SolutionState.LISTENING)
        assert state.should_transcribe() is True


class TestSttStateHistory:
    """Tests for state history tracking (v0.3.5)."""

    def test_history_records_transitions(self):
        """History records state transitions."""
        state = SttState()
        state.transition_to(SolutionState.LINK_PENDING)
        state.transition_to(SolutionState.LISTENING)

        history = state.get_history()
        assert len(history) == 2
        assert history[0]["old_state"] == "unconfigured"
        assert history[0]["new_state"] == "link_pending"
        assert history[1]["old_state"] == "link_pending"
        assert history[1]["new_state"] == "listening"

    def test_history_includes_timestamp(self):
        """History entries include ISO timestamp."""
        state = SttState()
        state.transition_to(SolutionState.LISTENING)

        history = state.get_history()
        assert len(history) == 1
        assert "timestamp" in history[0]
        # Timestamp should be ISO format
        assert "T" in history[0]["timestamp"]

    def test_history_includes_reason(self):
        """History entries include reason when provided."""
        state = SttState()
        state.transition_to(SolutionState.FAILED, reason="Test failure")

        history = state.get_history()
        assert len(history) == 1
        assert history[0]["reason"] == "Test failure"

    def test_history_includes_source(self):
        """History entries include source."""
        state = SttState()
        state.transition_to(SolutionState.PAUSED, source="api")

        history = state.get_history()
        assert len(history) == 1
        assert history[0]["source"] == "api"

    def test_history_respects_max_size(self):
        """History is bounded by max size."""
        state = SttState()
        state._history_max = 3

        # Make 5 transitions
        state.transition_to(SolutionState.LINK_PENDING)
        state.transition_to(SolutionState.HANDSHAKE_INIT)
        state.transition_to(SolutionState.LISTENING)
        state.transition_to(SolutionState.PAUSED)
        state.transition_to(SolutionState.LISTENING)

        # Only last 3 should be kept
        assert len(state._history) == 3
        history = state.get_history()
        assert history[0]["new_state"] == "listening"
        assert history[1]["new_state"] == "paused"
        assert history[2]["new_state"] == "listening"

    def test_to_dict_serialization(self):
        """to_dict serializes state for IPC."""
        state = SttState()
        state.transition_to(SolutionState.LISTENING)
        state.model = "base"
        state.language = "de"

        result = state.to_dict()
        assert result["state"] == "listening"
        assert result["model"] == "base"
        assert result["language"] == "de"
        assert result["hid_keymap"] == "en_us"
        assert result["failure_reason"] is None

    def test_to_dict_includes_failure_reason(self):
        """to_dict includes failure_reason when set."""
        state = SttState()
        state.transition_to(SolutionState.FAILED, reason="No audio device")

        result = state.to_dict()
        assert result["state"] == "failed"
        assert result["failure_reason"] == "No audio device"

    def test_default_source_is_service(self):
        """Default source for transitions is 'service'."""
        state = SttState()
        state.transition_to(SolutionState.LISTENING)

        history = state.get_history()
        assert history[0]["source"] == "service"
