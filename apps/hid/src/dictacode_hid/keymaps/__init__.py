"""Keymap module for dictacode HID."""

from .base import Keymap, KeyMapping, load_keymap, get_available_keymaps, get_current_keymap, set_current_keymap
from .en_us import EnUsKeymap
from .de_de import DeDeKeymap

__all__ = [
    "Keymap",
    "KeyMapping",
    "EnUsKeymap",
    "DeDeKeymap",
    "load_keymap",
    "get_available_keymaps",
    "get_current_keymap",
    "set_current_keymap",
]
