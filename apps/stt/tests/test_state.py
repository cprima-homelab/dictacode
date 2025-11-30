"""Tests for dictacode_stt.state module."""

import pytest

from dictacode_stt import DeviceMode, SttState


class TestDeviceMode:
    """Tests for DeviceMode enum."""

    def test_values_exist(self):
        assert DeviceMode.LISTENING
        assert DeviceMode.MAINTENANCE
        assert DeviceMode.PAUSED

    def test_values_distinct(self):
        modes = [DeviceMode.LISTENING, DeviceMode.MAINTENANCE, DeviceMode.PAUSED]
        assert len(set(modes)) == 3


class TestSttState:
    """Tests for SttState dataclass."""

    def test_default_values(self):
        state = SttState()
        assert state.mode == DeviceMode.LISTENING
        assert state.model == "tiny"
        assert state.language == "en"
        assert state.hid_keymap == "en_us"

    def test_set_mode(self, capsys):
        state = SttState()
        state.set_mode(DeviceMode.MAINTENANCE)
        assert state.mode == DeviceMode.MAINTENANCE

        captured = capsys.readouterr()
        assert "LISTENING -> MAINTENANCE" in captured.out

    def test_set_hid_keymap(self, capsys):
        state = SttState()
        state.set_hid_keymap("de_de")
        assert state.hid_keymap == "de_de"

        captured = capsys.readouterr()
        assert "en_us -> de_de" in captured.out

    def test_should_transcribe_listening(self):
        state = SttState(mode=DeviceMode.LISTENING)
        assert state.should_transcribe() is True

    def test_should_transcribe_maintenance(self):
        state = SttState(mode=DeviceMode.MAINTENANCE)
        assert state.should_transcribe() is False

    def test_should_transcribe_paused(self):
        state = SttState(mode=DeviceMode.PAUSED)
        assert state.should_transcribe() is False

    def test_should_send_listening(self):
        state = SttState(mode=DeviceMode.LISTENING)
        assert state.should_send() is True

    def test_should_send_maintenance(self):
        state = SttState(mode=DeviceMode.MAINTENANCE)
        assert state.should_send() is True  # Can still send commands for testing

    def test_should_send_paused(self):
        state = SttState(mode=DeviceMode.PAUSED)
        assert state.should_send() is False


class TestSttStateWorkflow:
    """Test realistic state workflows."""

    def test_maintenance_mode_for_protocol_testing(self):
        """Test maintenance mode for testing protocol without transcription."""
        state = SttState()

        # Normal operation
        assert state.should_transcribe() is True
        assert state.should_send() is True

        # Enter maintenance mode
        state.set_mode(DeviceMode.MAINTENANCE)
        assert state.should_transcribe() is False  # Don't run whisper
        assert state.should_send() is True  # Can still send test messages

        # Can change HID keymap while in maintenance
        state.set_hid_keymap("de_de")
        assert state.hid_keymap == "de_de"

        # Return to normal
        state.set_mode(DeviceMode.LISTENING)
        assert state.should_transcribe() is True
        assert state.should_send() is True

    def test_pause_mode(self):
        """Test pause mode - no transcription, no sending."""
        state = SttState()

        # Pause
        state.set_mode(DeviceMode.PAUSED)
        assert state.should_transcribe() is False
        assert state.should_send() is False

        # Settings can still be changed
        state.hid_keymap = "de_de"
        state.model = "small"

        # Resume
        state.set_mode(DeviceMode.LISTENING)
        assert state.should_transcribe() is True
        assert state.should_send() is True
        assert state.hid_keymap == "de_de"  # Settings preserved
        assert state.model == "small"
