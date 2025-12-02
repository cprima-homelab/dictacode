"""Base keymap class and utilities."""

from dataclasses import dataclass
from typing import Dict, Optional

from dictacode_hid.paths import KEYMAP_CONFIG


# Config file location (uses paths.py constant)
CONFIG_FILE = KEYMAP_CONFIG
DEFAULT_KEYMAP = "en_us"


@dataclass
class KeyMapping:
    """Represents a single key mapping."""

    scancode: int
    modifier: int = 0  # 0=none, 2=left_shift, 64=right_alt (AltGr)


class Keymap:
    """Base class for keyboard layouts."""

    name: str = ""
    description: str = ""

    def __init__(self):
        self.mappings: Dict[str, KeyMapping] = {}
        self._build_mappings()

    def _build_mappings(self) -> None:
        """Override in subclasses to populate mappings."""
        pass

    def get(self, char: str) -> Optional[KeyMapping]:
        """Get the key mapping for a character."""
        return self.mappings.get(char)

    def __len__(self) -> int:
        return len(self.mappings)


# Registry of available keymaps
_KEYMAP_REGISTRY: Dict[str, type] = {}


def register_keymap(keymap_class: type) -> type:
    """Decorator to register a keymap class."""
    _KEYMAP_REGISTRY[keymap_class.name] = keymap_class
    return keymap_class


def get_available_keymaps() -> Dict[str, str]:
    """Return dict of keymap name -> description."""
    return {name: cls.description for name, cls in _KEYMAP_REGISTRY.items()}


def load_keymap(name: str) -> Keymap:
    """Load a keymap by name."""
    if name not in _KEYMAP_REGISTRY:
        raise ValueError(
            f"Unknown keymap: {name}. Available: {list(_KEYMAP_REGISTRY.keys())}"
        )
    return _KEYMAP_REGISTRY[name]()


def get_current_keymap() -> str:
    """Read current keymap from config file."""
    if CONFIG_FILE.exists():
        try:
            content = CONFIG_FILE.read_text()
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == "keymap":
                    return value.strip()
        except Exception:
            pass
    return DEFAULT_KEYMAP


def set_current_keymap(name: str) -> None:
    """Write keymap to config file."""
    if name not in _KEYMAP_REGISTRY:
        raise ValueError(
            f"Unknown keymap: {name}. Available: {list(_KEYMAP_REGISTRY.keys())}"
        )

    # Ensure directory exists
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write config
    CONFIG_FILE.write_text(f"# dictacode keymap configuration\nkeymap={name}\n")
