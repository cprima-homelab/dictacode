"""Unit tests for pause/resume functionality (v0.3.0 Phase 3.4)."""

from unittest.mock import Mock

import pytest

from dictacode_stt.service import SttService
from dictacode_stt.state import SolutionState


@pytest.fixture
def mock_service():
    """Create a mock SttService with minimal dependencies."""
    service = Mock(spec=SttService)
    service.state = Mock()
    service.state.state = SolutionState.LISTENING
    service._broadcast_websocket = Mock()

    # Import actual methods from service
    from dictacode_stt.service import SttService as RealService

    service.pause = lambda: RealService.pause(service)
    service.resume = lambda: RealService.resume(service)
    service.get_state = lambda: RealService.get_state(service)

    return service


def test_pause_from_listening(mock_service):
    """Test pause() when in LISTENING state."""
    mock_service.state.state = SolutionState.LISTENING
    mock_service.state.transition_to = Mock()

    result = mock_service.pause()

    assert result is True
    mock_service.state.transition_to.assert_called_once_with(SolutionState.PAUSED)
    mock_service._broadcast_websocket.assert_called_once()

    # Verify broadcast message structure
    call_args = mock_service._broadcast_websocket.call_args[0][0]
    assert call_args["type"] == "state_change"
    assert call_args["data"]["new_state"] == "paused"
    assert call_args["data"]["old_state"] == "listening"


def test_pause_from_wrong_state(mock_service):
    """Test pause() when not in LISTENING state."""
    mock_service.state.state = SolutionState.PAUSED
    mock_service.state.transition_to = Mock()

    result = mock_service.pause()

    assert result is False
    mock_service.state.transition_to.assert_not_called()
    mock_service._broadcast_websocket.assert_not_called()


def test_pause_from_degraded_state(mock_service):
    """Test pause() fails from DEGRADED state."""
    mock_service.state.state = SolutionState.DEGRADED
    mock_service.state.transition_to = Mock()

    result = mock_service.pause()

    assert result is False
    mock_service.state.transition_to.assert_not_called()


def test_resume_from_paused(mock_service):
    """Test resume() when in PAUSED state."""
    mock_service.state.state = SolutionState.PAUSED
    mock_service.state.transition_to = Mock()

    result = mock_service.resume()

    assert result is True
    mock_service.state.transition_to.assert_called_once_with(SolutionState.LISTENING)
    mock_service._broadcast_websocket.assert_called_once()

    # Verify broadcast message structure
    call_args = mock_service._broadcast_websocket.call_args[0][0]
    assert call_args["type"] == "state_change"
    assert call_args["data"]["new_state"] == "listening"
    assert call_args["data"]["old_state"] == "paused"


def test_resume_from_wrong_state(mock_service):
    """Test resume() when not in PAUSED state."""
    mock_service.state.state = SolutionState.LISTENING
    mock_service.state.transition_to = Mock()

    result = mock_service.resume()

    assert result is False
    mock_service.state.transition_to.assert_not_called()
    mock_service._broadcast_websocket.assert_not_called()


def test_resume_from_unconfigured_state(mock_service):
    """Test resume() fails from UNCONFIGURED state."""
    mock_service.state.state = SolutionState.UNCONFIGURED
    mock_service.state.transition_to = Mock()

    result = mock_service.resume()

    assert result is False
    mock_service.state.transition_to.assert_not_called()


def test_get_state_listening(mock_service):
    """Test get_state() returns current state string."""
    mock_service.state.state = SolutionState.LISTENING

    state = mock_service.get_state()

    assert state == "listening"


def test_get_state_paused(mock_service):
    """Test get_state() returns 'paused'."""
    mock_service.state.state = SolutionState.PAUSED

    state = mock_service.get_state()

    assert state == "paused"


def test_get_state_degraded(mock_service):
    """Test get_state() returns 'degraded'."""
    mock_service.state.state = SolutionState.DEGRADED

    state = mock_service.get_state()

    assert state == "degraded"


def test_pause_resume_cycle(mock_service):
    """Test full pause/resume cycle."""
    mock_service.state.state = SolutionState.LISTENING
    mock_service.state.transition_to = Mock(
        side_effect=lambda s: setattr(mock_service.state, "state", s)
    )

    # Pause
    result1 = mock_service.pause()
    assert result1 is True
    assert mock_service.state.state == SolutionState.PAUSED

    # Resume
    result2 = mock_service.resume()
    assert result2 is True
    assert mock_service.state.state == SolutionState.LISTENING

    # Verify broadcast was called twice (once for pause, once for resume)
    assert mock_service._broadcast_websocket.call_count == 2


def test_pause_idempotency(mock_service):
    """Test pause() returns False when already paused (idempotent)."""
    mock_service.state.state = SolutionState.PAUSED
    mock_service.state.transition_to = Mock()

    # Try to pause again
    result = mock_service.pause()

    assert result is False
    mock_service.state.transition_to.assert_not_called()


def test_resume_idempotency(mock_service):
    """Test resume() returns False when already listening (idempotent)."""
    mock_service.state.state = SolutionState.LISTENING
    mock_service.state.transition_to = Mock()

    # Try to resume again
    result = mock_service.resume()

    assert result is False
    mock_service.state.transition_to.assert_not_called()
