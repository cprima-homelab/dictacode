"""Command detection for voice commands.

This module provides infrastructure for detecting voice commands in transcribed text.
It's implemented as a stub in v0.3.1 to prepare for future voice command features.

Supported command types:
- WAKE: Wake word detection ("hey dictacode", etc.)
- ACTION: Action commands ("new paragraph", "stop typing", etc.)
- CANCEL: Cancel/abort commands
- MODE: Mode switching commands ("code mode", "formal mode", etc.)

Extension points:
- Add custom command patterns via CommandPattern
- Implement custom detectors by subclassing CommandDetector
- Extend CommandHandler for actual command execution
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Type of detected command."""

    NONE = "none"  # Not a command, pass through
    WAKE = "wake"  # Wake word detected
    ACTION = "action"  # Action command
    CANCEL = "cancel"  # Cancel/abort command
    MODE = "mode"  # Mode switch command


@dataclass
class DetectedCommand:
    """A detected voice command.

    Attributes:
        type: Type of command detected
        trigger: The phrase that triggered detection
        argument: Optional argument (e.g., mode name)
        confidence: Detection confidence (0.0 - 1.0)
        remaining_text: Text after command removed
    """

    type: CommandType
    trigger: str
    argument: Optional[str]
    confidence: float
    remaining_text: str


@dataclass
class CommandPattern:
    """Pattern for command detection.

    Attributes:
        type: Type of command this pattern detects
        patterns: List of phrases to match
        has_argument: Whether command expects an argument
    """

    type: CommandType
    patterns: list[str]
    has_argument: bool = False


# Built-in command patterns
DEFAULT_COMMANDS = [
    CommandPattern(
        type=CommandType.WAKE,
        patterns=["hey dictacode", "dictacode", "ok dictacode"],
    ),
    CommandPattern(
        type=CommandType.ACTION,
        patterns=["new paragraph", "new line", "stop typing", "delete that"],
    ),
    CommandPattern(
        type=CommandType.CANCEL,
        patterns=["cancel", "abort", "never mind", "scratch that"],
    ),
    CommandPattern(
        type=CommandType.MODE,
        patterns=["code mode", "prose mode", "formal mode", "casual mode"],
        has_argument=True,
    ),
]


class CommandDetector(ABC):
    """Abstract command detector interface.

    Subclass this to implement custom command detection logic.
    The default implementation (SimpleCommandDetector) uses simple
    prefix matching, but more sophisticated implementations could use:
    - Fuzzy string matching
    - Machine learning models
    - Audio-based wake word detection
    """

    @abstractmethod
    def detect(self, text: str) -> DetectedCommand:
        """Detect command in transcription text.

        Args:
            text: Transcription text to analyze

        Returns:
            DetectedCommand with type and remaining text
        """
        pass

    @abstractmethod
    def add_pattern(self, pattern: CommandPattern) -> None:
        """Add custom command pattern.

        Args:
            pattern: Command pattern to add
        """
        pass


class SimpleCommandDetector(CommandDetector):
    """Simple prefix-based command detection.

    This is a basic implementation that matches commands by checking
    if the transcribed text starts with any registered pattern.

    Limitations:
    - Only matches at the beginning of text
    - Case-insensitive but exact phrase matching
    - No fuzzy matching or typo tolerance
    - No audio-based detection

    For production use, consider implementing:
    - Fuzzy string matching (e.g., Levenshtein distance)
    - Wake word audio detection (e.g., Porcupine, Snowboy)
    - Context-aware command parsing
    """

    def __init__(self, patterns: Optional[list[CommandPattern]] = None):
        """Initialize detector with patterns.

        Args:
            patterns: List of command patterns (defaults to DEFAULT_COMMANDS)
        """
        self._patterns = patterns or DEFAULT_COMMANDS.copy()
        logger.debug(
            f"SimpleCommandDetector initialized with {len(self._patterns)} patterns"
        )

    def detect(self, text: str) -> DetectedCommand:
        """Detect command by prefix matching.

        Args:
            text: Transcribed text to check

        Returns:
            DetectedCommand (type=NONE if no command found)
        """
        if not text or not text.strip():
            return DetectedCommand(
                type=CommandType.NONE,
                trigger="",
                argument=None,
                confidence=0.0,
                remaining_text=text,
            )

        text_lower = text.lower().strip()

        for pattern in self._patterns:
            for phrase in pattern.patterns:
                if text_lower.startswith(phrase):
                    # Extract remaining text after command
                    remaining = text[len(phrase) :].strip()

                    # Extract argument for mode commands
                    argument = None
                    if pattern.has_argument:
                        # Mode name is part of the pattern (e.g., "code" from "code mode")
                        parts = phrase.split()
                        if len(parts) >= 2:
                            argument = parts[0]  # e.g., "code" from "code mode"

                    logger.debug(
                        f"Detected {pattern.type.value} command: '{phrase}' "
                        f"(remaining: '{remaining}')"
                    )

                    return DetectedCommand(
                        type=pattern.type,
                        trigger=phrase,
                        argument=argument,
                        confidence=1.0,  # Exact match = 100% confidence
                        remaining_text=remaining,
                    )

        # No command detected
        return DetectedCommand(
            type=CommandType.NONE,
            trigger="",
            argument=None,
            confidence=0.0,
            remaining_text=text,
        )

    def add_pattern(self, pattern: CommandPattern) -> None:
        """Add custom command pattern.

        Args:
            pattern: Command pattern to add
        """
        self._patterns.append(pattern)
        logger.info(
            f"Added command pattern: {pattern.type.value} with {len(pattern.patterns)} phrases"
        )

    def list_patterns(self) -> list[CommandPattern]:
        """List all registered patterns.

        Returns:
            List of command patterns
        """
        return self._patterns.copy()

    def remove_pattern(self, pattern_type: CommandType, phrase: str) -> bool:
        """Remove a specific command pattern.

        Args:
            pattern_type: Type of command pattern
            phrase: Phrase to remove

        Returns:
            True if pattern was removed, False if not found
        """
        for pattern in self._patterns:
            if pattern.type == pattern_type and phrase in pattern.patterns:
                pattern.patterns.remove(phrase)
                logger.info(f"Removed pattern '{phrase}' from {pattern_type.value}")
                return True
        return False
