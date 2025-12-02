"""Tests for command detection (v0.3.1)."""

import pytest

from dictacode_stt.commands import (
    CommandDetector,
    CommandPattern,
    CommandType,
    DetectedCommand,
    SimpleCommandDetector,
)


class TestCommandType:
    """Test CommandType enum."""

    def test_command_types(self):
        """Test command type values."""
        assert CommandType.NONE.value == "none"
        assert CommandType.WAKE.value == "wake"
        assert CommandType.ACTION.value == "action"
        assert CommandType.CANCEL.value == "cancel"
        assert CommandType.MODE.value == "mode"


class TestCommandPattern:
    """Test CommandPattern dataclass."""

    def test_pattern_creation(self):
        """Test creating a command pattern."""
        pattern = CommandPattern(
            type=CommandType.WAKE,
            patterns=["hey dictacode", "dictacode"],
        )

        assert pattern.type == CommandType.WAKE
        assert len(pattern.patterns) == 2
        assert "hey dictacode" in pattern.patterns
        assert pattern.has_argument is False

    def test_pattern_with_argument(self):
        """Test pattern with argument."""
        pattern = CommandPattern(
            type=CommandType.MODE,
            patterns=["code mode", "formal mode"],
            has_argument=True,
        )

        assert pattern.has_argument is True


class TestDetectedCommand:
    """Test DetectedCommand dataclass."""

    def test_detected_command(self):
        """Test creating a detected command."""
        cmd = DetectedCommand(
            type=CommandType.WAKE,
            trigger="hey dictacode",
            argument=None,
            confidence=1.0,
            remaining_text="start typing",
        )

        assert cmd.type == CommandType.WAKE
        assert cmd.trigger == "hey dictacode"
        assert cmd.argument is None
        assert cmd.confidence == 1.0
        assert cmd.remaining_text == "start typing"

    def test_command_with_argument(self):
        """Test command with argument."""
        cmd = DetectedCommand(
            type=CommandType.MODE,
            trigger="code mode",
            argument="code",
            confidence=1.0,
            remaining_text="",
        )

        assert cmd.argument == "code"


class TestSimpleCommandDetector:
    """Test SimpleCommandDetector."""

    def test_detector_initialization(self):
        """Test detector with default patterns."""
        detector = SimpleCommandDetector()

        patterns = detector.list_patterns()
        assert len(patterns) > 0

    def test_detector_with_custom_patterns(self):
        """Test detector with custom patterns."""
        custom_patterns = [
            CommandPattern(
                type=CommandType.WAKE,
                patterns=["hello"],
            )
        ]

        detector = SimpleCommandDetector(patterns=custom_patterns)
        patterns = detector.list_patterns()

        assert len(patterns) == 1
        assert patterns[0].patterns == ["hello"]

    def test_detect_wake_word(self):
        """Test detecting wake word."""
        detector = SimpleCommandDetector()

        result = detector.detect("hey dictacode start typing")

        assert result.type == CommandType.WAKE
        assert result.trigger == "hey dictacode"
        assert result.remaining_text == "start typing"
        assert result.confidence == 1.0

    def test_detect_action_command(self):
        """Test detecting action command."""
        detector = SimpleCommandDetector()

        result = detector.detect("new paragraph and continue")

        assert result.type == CommandType.ACTION
        assert result.trigger == "new paragraph"
        assert result.remaining_text == "and continue"

    def test_detect_cancel_command(self):
        """Test detecting cancel command."""
        detector = SimpleCommandDetector()

        result = detector.detect("never mind that")

        assert result.type == CommandType.CANCEL
        assert result.trigger == "never mind"
        assert result.remaining_text == "that"

    def test_detect_mode_command(self):
        """Test detecting mode switch command."""
        detector = SimpleCommandDetector()

        result = detector.detect("code mode")

        assert result.type == CommandType.MODE
        assert result.trigger == "code mode"
        assert result.argument == "code"
        assert result.remaining_text == ""

    def test_detect_no_command(self):
        """Test when no command is detected."""
        detector = SimpleCommandDetector()

        result = detector.detect("this is just regular text")

        assert result.type == CommandType.NONE
        assert result.trigger == ""
        assert result.remaining_text == "this is just regular text"
        assert result.confidence == 0.0

    def test_detect_empty_text(self):
        """Test detection with empty text."""
        detector = SimpleCommandDetector()

        result = detector.detect("")

        assert result.type == CommandType.NONE
        assert result.remaining_text == ""

    def test_detect_case_insensitive(self):
        """Test case-insensitive detection."""
        detector = SimpleCommandDetector()

        # Test uppercase
        result1 = detector.detect("HEY DICTACODE hello")
        assert result1.type == CommandType.WAKE

        # Test mixed case
        result2 = detector.detect("Hey Dictacode hello")
        assert result2.type == CommandType.WAKE

    def test_detect_prefix_matching(self):
        """Test that detection is prefix-based."""
        detector = SimpleCommandDetector()

        # Should match at the beginning
        result1 = detector.detect("dictacode start")
        assert result1.type == CommandType.WAKE

        # Should NOT match in the middle
        result2 = detector.detect("I said dictacode earlier")
        assert result2.type == CommandType.NONE

    def test_add_pattern(self):
        """Test adding a custom pattern."""
        detector = SimpleCommandDetector()
        initial_count = len(detector.list_patterns())

        new_pattern = CommandPattern(
            type=CommandType.WAKE,
            patterns=["hello assistant"],
        )
        detector.add_pattern(new_pattern)

        assert len(detector.list_patterns()) == initial_count + 1

        # Test that new pattern works
        result = detector.detect("hello assistant please help")
        assert result.type == CommandType.WAKE
        assert result.trigger == "hello assistant"

    def test_remove_pattern(self):
        """Test removing a pattern phrase."""
        detector = SimpleCommandDetector()

        # Remove a pattern
        removed = detector.remove_pattern(CommandType.WAKE, "dictacode")

        assert removed is True

        # Verify it's removed
        result = detector.detect("dictacode test")
        # Should still detect "hey dictacode" but not standalone "dictacode"
        assert result.type == CommandType.NONE

    def test_remove_nonexistent_pattern(self):
        """Test removing a pattern that doesn't exist."""
        detector = SimpleCommandDetector()

        removed = detector.remove_pattern(CommandType.WAKE, "nonexistent")

        assert removed is False

    def test_multiple_wake_words(self):
        """Test detection with multiple wake word options."""
        detector = SimpleCommandDetector()

        # Test different wake words
        result1 = detector.detect("hey dictacode hello")
        result2 = detector.detect("dictacode start")
        result3 = detector.detect("ok dictacode go")

        assert result1.type == CommandType.WAKE
        assert result2.type == CommandType.WAKE
        assert result3.type == CommandType.WAKE

    def test_action_commands(self):
        """Test various action commands."""
        detector = SimpleCommandDetector()

        actions = [
            ("new paragraph", "new paragraph"),
            ("new line more text", "new line"),
            ("stop typing now", "stop typing"),
            ("delete that please", "delete that"),
        ]

        for text, expected_trigger in actions:
            result = detector.detect(text)
            assert result.type == CommandType.ACTION
            assert result.trigger == expected_trigger

    def test_mode_commands(self):
        """Test mode switch commands."""
        detector = SimpleCommandDetector()

        modes = [
            ("code mode", "code"),
            ("prose mode", "prose"),
            ("formal mode", "formal"),
            ("casual mode", "casual"),
        ]

        for text, expected_arg in modes:
            result = detector.detect(text)
            assert result.type == CommandType.MODE
            assert result.argument == expected_arg

    def test_remaining_text_trimmed(self):
        """Test that remaining text is properly trimmed."""
        detector = SimpleCommandDetector()

        result = detector.detect("hey dictacode   start typing")

        # Remaining text should have leading/trailing whitespace removed
        assert result.remaining_text == "start typing"
        assert not result.remaining_text.startswith(" ")
