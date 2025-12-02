"""Pytest configuration and fixtures for dictacode HID tests."""

import os
from pathlib import Path
from typing import Callable

import pytest


# Custom pytest markers
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "device_only: mark test to run only on actual devices (Raspberry Pi)",
    )
    config.addinivalue_line(
        "markers",
        "laptop: mark test to run on developer laptop (default)",
    )


def pytest_collection_modifyitems(config, items):
    """
    Automatically skip tests based on environment.

    - On device: skip laptop-only tests (if explicitly marked)
    - On laptop: skip device_only tests
    """
    # Detect if running on device (Raspberry Pi)
    is_device = os.path.exists("/dev/hidg0") or os.path.exists("/dev/serial0")

    skip_device = pytest.mark.skip(reason="requires actual device hardware")
    skip_laptop = pytest.mark.skip(reason="requires laptop environment")

    for item in items:
        if "device_only" in item.keywords:
            if not is_device:
                item.add_marker(skip_device)
        # No explicit laptop marker needed - tests without device_only run on laptop by default


# === Canonical Templates Fixtures ===

def _get_repo_root() -> Path:
    """Find repository root by walking up from this file."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "compatibility.json").exists() or (current / ".git").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repository root")


CANONICAL_TEMPLATES_DIR = _get_repo_root() / "ops" / "packaging" / "templates"


@pytest.fixture
def canonical_templates_dir() -> Path:
    """Return path to canonical templates directory."""
    if not CANONICAL_TEMPLATES_DIR.exists():
        pytest.skip(f"Canonical templates directory not found: {CANONICAL_TEMPLATES_DIR}")
    return CANONICAL_TEMPLATES_DIR


@pytest.fixture
def canonical_hid_conf() -> Path:
    """Return path to canonical hid.conf template."""
    conf_path = CANONICAL_TEMPLATES_DIR / "hid.conf"
    if not conf_path.exists():
        pytest.skip(f"Canonical hid.conf not found: {conf_path}")
    return conf_path


@pytest.fixture
def canonical_keymap_conf() -> Path:
    """Return path to canonical keymap.conf template."""
    conf_path = CANONICAL_TEMPLATES_DIR / "keymap.conf"
    if not conf_path.exists():
        pytest.skip(f"Canonical keymap.conf not found: {conf_path}")
    return conf_path


@pytest.fixture
def get_canonical_template() -> Callable[[str], Path]:
    """Return function to get path to any canonical template.

    Usage:
        def test_something(get_canonical_template):
            hid_conf = get_canonical_template("hid.conf")
            keymap_conf = get_canonical_template("keymap.conf")
    """
    def _get(template_name: str) -> Path:
        path = CANONICAL_TEMPLATES_DIR / template_name
        if not path.exists():
            pytest.skip(f"Canonical template not found: {path}")
        return path
    return _get
