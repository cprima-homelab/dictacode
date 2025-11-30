"""Device state management for HID.

Minimal state module for Phase 1. Will be expanded in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class DeviceMode(Enum):
    """Operating modes for the HID device."""

    NORMAL = auto()  # Normal operation: type received text
    MAINTENANCE = auto()  # Maintenance: log but don't type (for testing)
    PAUSED = auto()  # Paused: buffer text, don't type until resumed


@dataclass
class HidState:
    """Mutable state for HID device."""

    mode: DeviceMode = DeviceMode.NORMAL
    keymap: str = "en_us"
    buffer: list[str] = field(default_factory=list)  # buffered text when paused

    def set_mode(self, mode: DeviceMode) -> None:
        """Change device mode."""
        old_mode = self.mode
        self.mode = mode
        print(f"[state] mode: {old_mode.name} -> {mode.name}")

    def set_keymap(self, keymap: str) -> None:
        """Change keyboard layout."""
        old = self.keymap
        self.keymap = keymap
        print(f"[state] keymap: {old} -> {keymap}")

    def should_type(self) -> bool:
        """Return True if device should type text."""
        return self.mode == DeviceMode.NORMAL

    def should_buffer(self) -> bool:
        """Return True if device should buffer text."""
        return self.mode == DeviceMode.PAUSED

    def add_to_buffer(self, text: str) -> None:
        """Add text to buffer (when paused)."""
        self.buffer.append(text)
        print(f"[state] buffered: {text!r}")

    def flush_buffer(self) -> list[str]:
        """Return and clear the buffer."""
        items = self.buffer.copy()
        self.buffer.clear()
        if items:
            print(f"[state] flushing {len(items)} buffered items")
        return items
