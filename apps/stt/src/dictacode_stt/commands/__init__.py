"""Voice command detection and handling (v0.3.1 stub).

This package provides infrastructure for detecting and handling voice commands
in transcribed text. In v0.3.1, this is a stub implementation to prepare for
future voice command features.

Basic usage:
    from dictacode_stt.commands import SimpleCommandDetector, CommandHandler

    # Create detector
    detector = SimpleCommandDetector()

    # Detect command in text
    command = detector.detect("hey dictacode start typing")

    # Handle command (stub - logs only)
    handler = CommandHandler(service)
    handled = await handler.handle(command)

Command types:
    - WAKE: Wake word detection
    - ACTION: Action commands (new paragraph, stop typing, etc.)
    - CANCEL: Cancel/abort commands
    - MODE: Mode switching (code mode, formal mode, etc.)

Extension points:
    - Subclass CommandDetector for custom detection logic
    - Override CommandHandler methods for actual execution
    - Add custom CommandPattern instances
    - Implement audio-based wake word detection

See architecture-plan-v0.3.1.md for future implementation details.
"""

from dictacode_stt.commands.detector import (
    DEFAULT_COMMANDS,
    CommandDetector,
    CommandPattern,
    CommandType,
    DetectedCommand,
    SimpleCommandDetector,
)
from dictacode_stt.commands.handler import CommandHandler


__all__ = [
    # Detector
    "CommandDetector",
    "SimpleCommandDetector",
    # Types
    "CommandType",
    "CommandPattern",
    "DetectedCommand",
    "DEFAULT_COMMANDS",
    # Handler
    "CommandHandler",
]
