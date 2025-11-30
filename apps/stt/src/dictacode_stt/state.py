"""Device state management for STT.

Minimal state module for Phase 1. Will be expanded in later phases.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class DeviceMode(Enum):
    """Operating modes for the STT device."""

    LISTENING = auto()  # Normal: capture audio, transcribe, send
    MAINTENANCE = auto()  # Maintenance: don't transcribe (for testing protocol)
    PAUSED = auto()  # Paused: don't send to HID


@dataclass
class SttState:
    """Mutable state for STT device."""

    mode: DeviceMode = DeviceMode.LISTENING
    model: str = "tiny"
    language: str = "en"
    hid_keymap: str = "en_us"  # track what we told HID to use

    def set_mode(self, mode: DeviceMode) -> None:
        """Change device mode."""
        old_mode = self.mode
        self.mode = mode
        print(f"[state] mode: {old_mode.name} -> {mode.name}")

    def set_hid_keymap(self, keymap: str) -> None:
        """Track the keymap we've sent to HID."""
        old = self.hid_keymap
        self.hid_keymap = keymap
        print(f"[state] hid_keymap: {old} -> {keymap}")

    def should_transcribe(self) -> bool:
        """Return True if device should transcribe audio."""
        return self.mode == DeviceMode.LISTENING

    def should_send(self) -> bool:
        """Return True if device should send to HID."""
        return self.mode in (DeviceMode.LISTENING, DeviceMode.MAINTENANCE)
