"""Pytest configuration and fixtures for dictacode HID tests."""

import os

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
