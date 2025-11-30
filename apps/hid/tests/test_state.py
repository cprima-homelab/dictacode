"""Tests for dictacode_hid.state module."""

import pytest

from dictacode_hid import DeviceMode, HidState


class TestDeviceMode:
    """Tests for DeviceMode enum."""

    def test_values_exist(self):
        assert DeviceMode.NORMAL
        assert DeviceMode.MAINTENANCE
        assert DeviceMode.PAUSED

    def test_values_distinct(self):
        modes = [DeviceMode.NORMAL, DeviceMode.MAINTENANCE, DeviceMode.PAUSED]
        assert len(set(modes)) == 3


class TestHidState:
    """Tests for HidState dataclass."""

    def test_default_values(self):
        state = HidState()
        assert state.mode == DeviceMode.NORMAL
        assert state.keymap == "en_us"
        assert state.buffer == []

    def test_set_mode(self, capsys):
        state = HidState()
        state.set_mode(DeviceMode.MAINTENANCE)
        assert state.mode == DeviceMode.MAINTENANCE

        captured = capsys.readouterr()
        assert "NORMAL -> MAINTENANCE" in captured.out

    def test_set_keymap(self, capsys):
        state = HidState()
        state.set_keymap("de_de")
        assert state.keymap == "de_de"

        captured = capsys.readouterr()
        assert "en_us -> de_de" in captured.out

    def test_should_type_normal(self):
        state = HidState(mode=DeviceMode.NORMAL)
        assert state.should_type() is True

    def test_should_type_maintenance(self):
        state = HidState(mode=DeviceMode.MAINTENANCE)
        assert state.should_type() is False

    def test_should_type_paused(self):
        state = HidState(mode=DeviceMode.PAUSED)
        assert state.should_type() is False

    def test_should_buffer_normal(self):
        state = HidState(mode=DeviceMode.NORMAL)
        assert state.should_buffer() is False

    def test_should_buffer_paused(self):
        state = HidState(mode=DeviceMode.PAUSED)
        assert state.should_buffer() is True

    def test_add_to_buffer(self):
        state = HidState()
        state.add_to_buffer("hello")
        state.add_to_buffer("world")
        assert state.buffer == ["hello", "world"]

    def test_flush_buffer(self):
        state = HidState()
        state.add_to_buffer("hello")
        state.add_to_buffer("world")

        flushed = state.flush_buffer()
        assert flushed == ["hello", "world"]
        assert state.buffer == []

    def test_flush_empty_buffer(self):
        state = HidState()
        flushed = state.flush_buffer()
        assert flushed == []


class TestHidStateWorkflow:
    """Test realistic state workflows."""

    def test_pause_resume_workflow(self):
        """Test pausing, buffering, and resuming."""
        state = HidState()

        # Normal typing
        assert state.should_type() is True

        # Pause
        state.set_mode(DeviceMode.PAUSED)
        assert state.should_type() is False
        assert state.should_buffer() is True

        # Buffer some text
        state.add_to_buffer("buffered text 1")
        state.add_to_buffer("buffered text 2")

        # Resume
        state.set_mode(DeviceMode.NORMAL)
        assert state.should_type() is True

        # Flush buffer
        buffered = state.flush_buffer()
        assert len(buffered) == 2
        assert state.buffer == []

    def test_maintenance_mode_workflow(self):
        """Test maintenance mode for protocol testing."""
        state = HidState()

        # Enter maintenance mode
        state.set_mode(DeviceMode.MAINTENANCE)
        assert state.should_type() is False
        assert state.should_buffer() is False  # Don't buffer in maintenance

        # Keymap can still be changed
        state.set_keymap("de_de")
        assert state.keymap == "de_de"

        # Return to normal
        state.set_mode(DeviceMode.NORMAL)
        assert state.should_type() is True
        assert state.keymap == "de_de"  # Keymap preserved
