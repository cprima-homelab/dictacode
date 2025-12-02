"""Tests for DiagnosticsAggregator (v0.3.13)."""

import time
from unittest.mock import MagicMock, patch

import pytest

from dictacode_stt.diagnostics.aggregator import (
    DEFAULT_STALENESS_THRESHOLD,
    DiagnosticsAggregator,
)
from dictacode_stt.state import SolutionState, SttState


class TestDiagnosticsAggregator:
    """Tests for DiagnosticsAggregator."""

    @pytest.fixture
    def mock_state(self):
        """Create mock SttState."""
        state = SttState()
        state.transition_to(SolutionState.LISTENING)
        return state

    @pytest.fixture
    def mock_service(self, mock_state):
        """Create mock SttService with required components."""
        service = MagicMock()
        service.state = mock_state

        # Mock audio_status
        service.audio_status.return_value = {
            "active_port": "port-1",
            "mic_present": True,
            "last_audio_ts": time.time(),
            "audio_chunks_total": 100,
        }

        # Mock transcriber with status
        service.transcriber = MagicMock()
        service.transcriber.status.return_value = {
            "backend": "whisper",
            "available": True,
            "last_asr_ts": time.time(),
            "asr_success_total": 10,
            "asr_error_total": 0,
        }

        # Mock transport with status
        service.transport = MagicMock()
        service.transport.status.return_value = {
            "type": "uart",
            "connected": True,
            "connection_status": "connected",
            "last_send_ts": time.time(),
            "send_success_total": 10,
            "send_error_total": 0,
        }

        return service

    @pytest.fixture
    def mock_ipc_server(self):
        """Create mock DiagnosticsIpcServer."""
        server = MagicMock()
        server.status.return_value = {
            "available": True,
            "socket_path": "/tmp/test.sock",
            "running": True,
        }
        return server

    @pytest.fixture
    def aggregator(self, mock_state, mock_service, mock_ipc_server):
        """Create DiagnosticsAggregator instance."""
        return DiagnosticsAggregator(
            state=mock_state,
            service=mock_service,
            ipc_server=mock_ipc_server,
        )

    def test_get_status_returns_complete_structure(self, aggregator):
        """Test get_status returns expected structure."""
        status = aggregator.get_status()

        # Check top-level keys
        assert "timestamp" in status
        assert "components" in status
        assert "flow" in status

        # Check component keys
        components = status["components"]
        assert "state" in components
        assert "audio" in components
        assert "asr" in components
        assert "transport" in components
        assert "ipc" in components

        # Check flow keys
        flow = status["flow"]
        assert "audio_fresh" in flow
        assert "asr_fresh" in flow
        assert "send_fresh" in flow
        assert "asr_stale" in flow
        assert "send_stale" in flow
        assert "threshold_sec" in flow

    def test_state_component_returns_status(self, aggregator):
        """Test state component status is included."""
        status = aggregator.get_status()
        state_status = status["components"]["state"]

        assert state_status["state"] == "listening"

    def test_audio_component_returns_status(self, aggregator, mock_service):
        """Test audio component status is included."""
        status = aggregator.get_status()
        audio_status = status["components"]["audio"]

        assert audio_status["active_port"] == "port-1"
        assert audio_status["mic_present"] is True
        mock_service.audio_status.assert_called_once()

    def test_asr_component_returns_status(self, aggregator, mock_service):
        """Test ASR/transcriber component status is included."""
        status = aggregator.get_status()
        asr_status = status["components"]["asr"]

        assert asr_status["backend"] == "whisper"
        assert asr_status["available"] is True
        mock_service.transcriber.status.assert_called_once()

    def test_transport_component_returns_status(self, aggregator, mock_service):
        """Test transport component status is included."""
        status = aggregator.get_status()
        transport_status = status["components"]["transport"]

        assert transport_status["type"] == "uart"
        assert transport_status["connected"] is True
        mock_service.transport.status.assert_called_once()

    def test_ipc_component_returns_status(self, aggregator, mock_ipc_server):
        """Test IPC server component status is included."""
        status = aggregator.get_status()
        ipc_status = status["components"]["ipc"]

        assert ipc_status["available"] is True
        mock_ipc_server.status.assert_called_once()

    def test_flow_freshness_all_fresh(self, aggregator, mock_service):
        """Test flow detection when all stages are fresh."""
        now = time.time()
        mock_service.audio_status.return_value["last_audio_ts"] = now
        mock_service.transcriber.status.return_value["last_asr_ts"] = now
        mock_service.transport.status.return_value["last_send_ts"] = now

        status = aggregator.get_status()
        flow = status["flow"]

        assert flow["audio_fresh"] is True
        assert flow["asr_fresh"] is True
        assert flow["send_fresh"] is True
        assert flow["asr_stale"] is False
        assert flow["send_stale"] is False

    def test_flow_freshness_audio_stale(self, aggregator, mock_service):
        """Test flow detection when audio is stale."""
        now = time.time()
        mock_service.audio_status.return_value["last_audio_ts"] = (
            now - DEFAULT_STALENESS_THRESHOLD - 5
        )
        mock_service.transcriber.status.return_value["last_asr_ts"] = (
            now - DEFAULT_STALENESS_THRESHOLD - 5
        )
        mock_service.transport.status.return_value["last_send_ts"] = (
            now - DEFAULT_STALENESS_THRESHOLD - 5
        )

        status = aggregator.get_status()
        flow = status["flow"]

        assert flow["audio_fresh"] is False
        assert flow["asr_fresh"] is False
        assert flow["send_fresh"] is False

    def test_flow_staleness_asr_stale_flag(self, aggregator, mock_service):
        """Test asr_stale flag when audio fresh but ASR stale."""
        now = time.time()
        mock_service.audio_status.return_value["last_audio_ts"] = now
        mock_service.transcriber.status.return_value["last_asr_ts"] = (
            now - DEFAULT_STALENESS_THRESHOLD - 5
        )
        mock_service.transport.status.return_value["last_send_ts"] = (
            now - DEFAULT_STALENESS_THRESHOLD - 5
        )

        status = aggregator.get_status()
        flow = status["flow"]

        assert flow["audio_fresh"] is True
        assert flow["asr_fresh"] is False
        assert flow["asr_stale"] is True  # audio fresh, ASR stale

    def test_flow_staleness_send_stale_flag(self, aggregator, mock_service):
        """Test send_stale flag when ASR fresh but send stale."""
        now = time.time()
        mock_service.audio_status.return_value["last_audio_ts"] = now
        mock_service.transcriber.status.return_value["last_asr_ts"] = now
        mock_service.transport.status.return_value["last_send_ts"] = (
            now - DEFAULT_STALENESS_THRESHOLD - 5
        )

        status = aggregator.get_status()
        flow = status["flow"]

        assert flow["asr_fresh"] is True
        assert flow["send_fresh"] is False
        assert flow["send_stale"] is True  # ASR fresh, send stale

    def test_custom_staleness_threshold(self, mock_state, mock_service, mock_ipc_server):
        """Test custom staleness threshold."""
        custom_threshold = 5.0
        aggregator = DiagnosticsAggregator(
            state=mock_state,
            service=mock_service,
            ipc_server=mock_ipc_server,
            staleness_threshold=custom_threshold,
        )

        status = aggregator.get_status()
        assert status["flow"]["threshold_sec"] == custom_threshold

    def test_component_error_handling(self, aggregator, mock_service):
        """Test error handling when component raises exception."""
        mock_service.audio_status.side_effect = Exception("Audio error")

        status = aggregator.get_status()
        audio_status = status["components"]["audio"]

        assert "error" in audio_status
        assert "Audio error" in audio_status["error"]

    def test_missing_transcriber(self, mock_state, mock_ipc_server):
        """Test handling when transcriber is None."""
        service = MagicMock()
        service.state = mock_state
        service.transcriber = None
        service.transport = None
        service.audio_status.return_value = {"last_audio_ts": None}

        aggregator = DiagnosticsAggregator(
            state=mock_state,
            service=service,
            ipc_server=mock_ipc_server,
        )

        status = aggregator.get_status()
        assert status["components"]["asr"]["available"] is False
        assert status["components"]["transport"]["connected"] is False

    def test_missing_ipc_server(self, mock_state, mock_service):
        """Test handling when IPC server is None."""
        aggregator = DiagnosticsAggregator(
            state=mock_state,
            service=mock_service,
            ipc_server=None,
        )

        status = aggregator.get_status()
        assert status["components"]["ipc"]["available"] is False

    def test_timestamp_is_current(self, aggregator):
        """Test that timestamp is current time."""
        before = time.time()
        status = aggregator.get_status()
        after = time.time()

        assert before <= status["timestamp"] <= after


class TestDiagnosticsAggregatorEnvVar:
    """Tests for staleness threshold environment variable."""

    def test_default_staleness_threshold(self):
        """Test default staleness threshold value."""
        assert DEFAULT_STALENESS_THRESHOLD == 10.0

    @patch.dict("os.environ", {"DICTACODE_STALENESS_THRESHOLD": "30.0"})
    def test_env_var_override(self):
        """Test staleness threshold override via env var."""
        # Re-import to pick up env var
        import importlib

        from dictacode_stt.diagnostics import aggregator

        importlib.reload(aggregator)

        # Check that the module-level constant was updated
        assert aggregator.STALENESS_THRESHOLD_SEC == 30.0
