"""Canonical paths for dictacode HID.

All paths in code should use these constants. Environment variables
can override defaults for development or custom deployments.

Platform-specific defaults:
- Linux: /etc/dictacode/, /opt/dictacode/
- macOS: /Library/Application Support/dictacode/
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional


logger = logging.getLogger("dictacode.hid.paths")


# === Platform Detection ===
def _is_macos() -> bool:
    return sys.platform == "darwin"


def _is_linux() -> bool:
    return sys.platform.startswith("linux")


# === Platform-Specific Base Paths ===
def _get_config_base() -> Path:
    """Get platform-specific config base directory."""
    if _is_macos():
        return Path("/Library/Application Support/dictacode")
    return Path("/etc/dictacode")


def _get_shared_base() -> Path:
    """Get platform-specific shared data directory."""
    if _is_macos():
        return Path("/Library/Application Support/dictacode/shared")
    return Path("/opt/dictacode/shared")


# === Config Files (platform-aware) ===
_CONFIG_BASE = _get_config_base()
HID_CONFIG_FILE = Path(
    os.getenv("DICTACODE_HID_CONFIG", str(_CONFIG_BASE / "hid.conf"))
)
HID_DROP_IN_DIR = Path(
    os.getenv("DICTACODE_HID_DROP_IN_DIR", str(_CONFIG_BASE / "hid.d"))
)

# === Keymap ===
KEYMAP_CONFIG = Path(
    os.getenv("DICTACODE_KEYMAP_CONFIG", str(_CONFIG_BASE / "keymap.conf"))
)

# === HID Registry ===
HID_REGISTRY_DIR = Path(
    os.getenv("DICTACODE_HID_REGISTRY_DIR", str(_CONFIG_BASE / "hid/devices.d"))
)

# === Canonical Paths Dict (for packaging validation) ===
# These are the expected paths after installation, by platform
CANONICAL_PATHS = {
    "linux": {
        "hid_config": "/etc/dictacode/hid.conf",
        "hid_drop_in": "/etc/dictacode/hid.d",
        "keymap_config": "/etc/dictacode/keymap.conf",
        "hid_registry_dir": "/etc/dictacode/hid/devices.d",
        "shared_dir": "/opt/dictacode/shared",
        "compatibility_matrix": "/opt/dictacode/shared/compatibility.json",
    },
    "darwin": {
        "hid_config": "/Library/Application Support/dictacode/hid.conf",
        "hid_drop_in": "/Library/Application Support/dictacode/hid.d",
        "keymap_config": "/Library/Application Support/dictacode/keymap.conf",
        "hid_registry_dir": "/Library/Application Support/dictacode/hid/devices.d",
        "shared_dir": "/Library/Application Support/dictacode/shared",
        "compatibility_matrix": (
            "/Library/Application Support/dictacode/shared/compatibility.json"
        ),
    },
}


def get_canonical_paths() -> dict:
    """Get canonical paths for the current platform."""
    platform_key = "darwin" if _is_macos() else "linux"
    return CANONICAL_PATHS.get(platform_key, CANONICAL_PATHS["linux"])


def _find_repo_root() -> Optional[Path]:
    """Find repository root for development fallbacks."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
            return parent
    return None


def find_asset(
    asset_name: str,
    override: Optional[str],
    env_var: str,
    search_paths: list,
) -> Path:
    """
    Authoritative search order for shared assets.

    Used by: compatibility matrix, keymap config, HID registry.

    Args:
        asset_name: Human-readable name for logging
        override: Explicit path override (highest priority)
        env_var: Environment variable name to check
        search_paths: List of paths to search (in order)

    Returns:
        Path to the found asset

    Raises:
        FileNotFoundError: If asset not found in any location
    """
    candidates = [
        override,
        os.getenv(env_var),
        *[str(p) if p else None for p in search_paths],
    ]

    for path in candidates:
        if path and Path(path).exists():
            logger.debug("Found %s at %s", asset_name, path)
            return Path(path)

    searched = [p for p in candidates if p]
    raise FileNotFoundError(f"{asset_name} not found. Searched: {searched}")


def find_compatibility_matrix(override: Optional[str] = None) -> Path:
    """Find compatibility matrix using authoritative search order.

    Order (first found wins):
    1. Explicit override (from config or CLI)
    2. DICTACODE_COMPATIBILITY_MATRIX env var
    3. Platform-specific shared dir (Linux: /opt/dictacode/shared/,
       macOS: /Library/Application Support/dictacode/shared/)
    4. Legacy /etc/dictacode/ location (Linux only)
    5. {repo}/compatibility.json (development)
    """
    repo_root = _find_repo_root()
    repo_fallback = str(repo_root / "compatibility.json") if repo_root else None

    # Build platform-specific search paths
    shared_base = _get_shared_base()
    search_paths = [
        str(shared_base / "compatibility.json"),
    ]

    # Legacy fallback for Linux only
    if _is_linux():
        search_paths.append("/etc/dictacode/compatibility.json")

    if repo_fallback:
        search_paths.append(repo_fallback)

    return find_asset(
        "compatibility matrix",
        override,
        "DICTACODE_COMPATIBILITY_MATRIX",
        search_paths,
    )


def find_keymap_config(override: Optional[str] = None) -> Path:
    """Find keymap config file."""
    return find_asset(
        "keymap config",
        override,
        "DICTACODE_KEYMAP_CONFIG",
        [str(KEYMAP_CONFIG)],
    )


def find_hid_registry_dir(override: Optional[str] = None) -> Path:
    """Find HID registry directory."""
    return find_asset(
        "HID registry",
        override,
        "DICTACODE_HID_REGISTRY_DIR",
        [str(HID_REGISTRY_DIR)],
    )
