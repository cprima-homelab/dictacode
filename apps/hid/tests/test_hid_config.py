"""Unit tests for HID configuration loader."""

from pathlib import Path

import pytest

from dictacode_hid.hid_config import HidConfig, load_hid_config


def test_default_config():
    """Test default configuration values."""
    config = HidConfig()

    # Transport defaults
    assert config.uart_device == "/dev/serial0"
    assert config.uart_baud == 115200
    assert config.hid_device == "/dev/hidg0"
    assert config.protocol == "json"

    # Mode defaults
    assert config.initial_mode == "normal"
    assert config.initial_keymap == "en_us"

    # Supervisor defaults
    assert config.supervisor_enabled is True
    assert config.supervisor_timeout == 30.0
    assert config.supervisor_ping_interval == 5.0


def test_baud_rate_validation():
    """Test UART baud rate validation."""
    # Valid baud rates
    HidConfig(uart_baud=9600)
    HidConfig(uart_baud=115200)
    HidConfig(uart_baud=230400)

    # Invalid baud rate uses default with WARN policy
    config = HidConfig(uart_baud=12345)
    assert config.uart_baud == 115200  # Falls back to default


def test_protocol_validation():
    """Test protocol validation."""
    # Valid protocols
    HidConfig(protocol="json")
    HidConfig(protocol="msgpack")

    # Invalid protocol uses default with WARN policy
    config = HidConfig(protocol="invalid")
    assert config.protocol == "json"


def test_mode_validation():
    """Test initial mode validation."""
    # Valid modes
    HidConfig(initial_mode="normal")
    HidConfig(initial_mode="maintenance")
    HidConfig(initial_mode="paused")

    # Invalid mode uses default with WARN policy
    config = HidConfig(initial_mode="invalid")
    assert config.initial_mode == "normal"


def test_log_level_validation():
    """Test log level validation."""
    # Valid levels
    HidConfig(log_level="DEBUG")
    HidConfig(log_level="INFO")
    HidConfig(log_level="WARNING")

    # Invalid level uses default
    config = HidConfig(log_level="INVALID")
    assert config.log_level == "INFO"


def test_supervisor_timeout_validation():
    """Test supervisor timeout validation."""
    # Valid timeouts
    HidConfig(supervisor_timeout=1.0)
    HidConfig(supervisor_timeout=60.0)

    # Invalid timeout uses default
    config = HidConfig(supervisor_timeout=-5.0)
    assert config.supervisor_timeout == 30.0


def test_config_file_missing():
    """Test graceful fallback when config missing."""
    config = load_hid_config(Path("/nonexistent/hid.conf"))
    assert isinstance(config, HidConfig)
    assert config.uart_device == "/dev/serial0"  # Defaults


def test_config_file_with_flat_structure(tmp_path):
    """Test parsing config with flat (DEFAULT section) structure."""
    config_file = tmp_path / "hid.conf"
    config_file.write_text(
        """
# Flat config (no sections)
uart_device=/dev/ttyUSB0
uart_baud=9600
protocol=msgpack
"""
    )

    config = load_hid_config(config_file)
    assert config.uart_device == "/dev/ttyUSB0"
    assert config.uart_baud == 9600
    assert config.protocol == "msgpack"


def test_config_file_with_sections(tmp_path):
    """Test parsing config with [hid] section."""
    config_file = tmp_path / "hid.conf"
    config_file.write_text(
        """
[hid]
uart_device=/dev/ttyAMA0
initial_mode=maintenance
log_level=DEBUG
"""
    )

    config = load_hid_config(config_file)
    assert config.uart_device == "/dev/ttyAMA0"
    assert config.initial_mode == "maintenance"
    assert config.log_level == "DEBUG"


def test_invalid_boolean_fallback(tmp_path):
    """Test fallback to defaults on invalid boolean values."""
    config_file = tmp_path / "hid.conf"
    config_file.write_text(
        """
supervisor_enabled=maybe
dry_run=yesno
"""
    )

    config = load_hid_config(config_file)
    # Should fall back to defaults
    assert config.supervisor_enabled is True
    assert config.dry_run is False


def test_invalid_integer_fallback(tmp_path):
    """Test fallback to defaults on invalid integer values."""
    config_file = tmp_path / "hid.conf"
    config_file.write_text(
        """
uart_baud=not_a_number
"""
    )

    config = load_hid_config(config_file)
    # Should fall back to defaults
    assert config.uart_baud == 115200


def test_invalid_float_fallback(tmp_path):
    """Test fallback to defaults on invalid float values."""
    config_file = tmp_path / "hid.conf"
    config_file.write_text(
        """
supervisor_timeout=invalid
"""
    )

    config = load_hid_config(config_file)
    # Should fall back to default
    assert config.supervisor_timeout == 30.0


def test_partial_config(tmp_path):
    """Test config with only some keys set."""
    config_file = tmp_path / "hid.conf"
    config_file.write_text(
        """
uart_device=/dev/ttyUSB1
initial_keymap=de_de
"""
    )

    config = load_hid_config(config_file)
    # Set values
    assert config.uart_device == "/dev/ttyUSB1"
    assert config.initial_keymap == "de_de"
    # Defaults for unset
    assert config.uart_baud == 115200
    assert config.protocol == "json"


def test_all_config_keys(tmp_path):
    """Test loading all configuration keys."""
    config_file = tmp_path / "hid.conf"
    config_file.write_text(
        """
uart_device=/dev/ttyUSB0
uart_baud=230400
hid_device=/dev/hidg1
protocol=msgpack
initial_mode=maintenance
initial_keymap=de_de
supervisor_enabled=false
supervisor_timeout=60.0
supervisor_ping_interval=10.0
log_level=DEBUG
dry_run=true
"""
    )

    config = load_hid_config(config_file)
    assert config.uart_device == "/dev/ttyUSB0"
    assert config.uart_baud == 230400
    assert config.hid_device == "/dev/hidg1"
    assert config.protocol == "msgpack"
    assert config.initial_mode == "maintenance"
    assert config.initial_keymap == "de_de"
    assert config.supervisor_enabled is False
    assert config.supervisor_timeout == 60.0
    assert config.supervisor_ping_interval == 10.0
    assert config.log_level == "DEBUG"
    assert config.dry_run is True


def test_comments_ignored(tmp_path):
    """Test that comments are properly ignored.

    Note: ConfigParser doesn't strip inline comments, so we test full-line
    comments which are properly ignored.
    """
    config_file = tmp_path / "hid.conf"
    config_file.write_text(
        """
# This is a comment
uart_baud=9600
# protocol=msgpack (commented out)
protocol=json
"""
    )

    config = load_hid_config(config_file)
    assert config.uart_baud == 9600
    assert config.protocol == "json"


# === Drop-in config tests (v0.3.2) ===


def test_drop_in_overrides_base_config(tmp_path):
    """Test drop-in config overrides base config values."""
    # Create base config
    base_config = tmp_path / "hid.conf"
    base_config.write_text(
        """
uart_baud=115200
protocol=json
initial_keymap=en_us
"""
    )

    # Create drop-in directory
    drop_in_dir = tmp_path / "hid.d"
    drop_in_dir.mkdir()

    # Create drop-in that overrides some values
    (drop_in_dir / "10-custom.conf").write_text(
        """
uart_baud=230400
protocol=msgpack
"""
    )

    config = load_hid_config(base_config, drop_in_dir)

    # Drop-in values should override base
    assert config.uart_baud == 230400
    assert config.protocol == "msgpack"
    # Base value not overridden should remain
    assert config.initial_keymap == "en_us"


def test_drop_in_sorted_order(tmp_path):
    """Test drop-ins are merged in sorted filename order."""
    base_config = tmp_path / "hid.conf"
    base_config.write_text("uart_baud=115200\n")

    drop_in_dir = tmp_path / "hid.d"
    drop_in_dir.mkdir()

    # Create drop-ins - later in sort order should win
    (drop_in_dir / "10-first.conf").write_text("uart_baud=9600\n")
    (drop_in_dir / "20-second.conf").write_text("uart_baud=230400\n")

    config = load_hid_config(base_config, drop_in_dir)

    # 20-second.conf should override 10-first.conf
    assert config.uart_baud == 230400


def test_drop_in_only_conf_files(tmp_path):
    """Test only *.conf files in drop-in dir are loaded."""
    base_config = tmp_path / "hid.conf"
    base_config.write_text("uart_baud=115200\n")

    drop_in_dir = tmp_path / "hid.d"
    drop_in_dir.mkdir()

    # Create a .conf file and non-.conf files
    (drop_in_dir / "10-valid.conf").write_text("uart_baud=9600\n")
    (drop_in_dir / "20-invalid.txt").write_text("uart_baud=230400\n")
    (drop_in_dir / "README").write_text("uart_baud=38400\n")

    config = load_hid_config(base_config, drop_in_dir)

    # Only .conf file should be loaded
    assert config.uart_baud == 9600


def test_drop_in_missing_dir(tmp_path):
    """Test graceful handling when drop-in directory doesn't exist."""
    base_config = tmp_path / "hid.conf"
    base_config.write_text("uart_baud=230400\n")

    # Non-existent drop-in dir
    drop_in_dir = tmp_path / "hid.d"

    config = load_hid_config(base_config, drop_in_dir)

    # Should still load base config
    assert config.uart_baud == 230400


def test_drop_in_empty_dir(tmp_path):
    """Test handling of empty drop-in directory."""
    base_config = tmp_path / "hid.conf"
    base_config.write_text("uart_baud=230400\n")

    drop_in_dir = tmp_path / "hid.d"
    drop_in_dir.mkdir()

    config = load_hid_config(base_config, drop_in_dir)

    assert config.uart_baud == 230400


def test_drop_in_invalid_file_skipped(tmp_path, caplog):
    """Test invalid drop-in files are skipped with warning."""
    import logging

    caplog.set_level(logging.WARNING)

    base_config = tmp_path / "hid.conf"
    base_config.write_text("uart_baud=115200\n")

    drop_in_dir = tmp_path / "hid.d"
    drop_in_dir.mkdir()

    # Create valid and invalid drop-ins
    (drop_in_dir / "10-valid.conf").write_text("uart_baud=9600\n")
    # Write binary garbage that can't be parsed
    (drop_in_dir / "20-invalid.conf").write_bytes(b"\x00\x01\x02\x03")

    config = load_hid_config(base_config, drop_in_dir)

    # Valid config should be loaded
    assert config.uart_baud == 9600
    # Warning should be logged for invalid file
    assert "20-invalid.conf" in caplog.text


def test_base_only_no_drop_in(tmp_path):
    """Test loading base config without any drop-ins."""
    base_config = tmp_path / "hid.conf"
    base_config.write_text(
        """
uart_baud=230400
protocol=msgpack
initial_mode=maintenance
"""
    )

    config = load_hid_config(base_config, tmp_path / "nonexistent_hid.d")

    assert config.uart_baud == 230400
    assert config.protocol == "msgpack"
    assert config.initial_mode == "maintenance"


def test_multiple_drop_ins_accumulate(tmp_path):
    """Test multiple drop-ins accumulate values from different keys."""
    base_config = tmp_path / "hid.conf"
    base_config.write_text(
        """
uart_device=/dev/serial0
"""
    )

    drop_in_dir = tmp_path / "hid.d"
    drop_in_dir.mkdir()

    # Each drop-in adds different settings
    (drop_in_dir / "10-baud.conf").write_text("uart_baud=9600\n")
    (drop_in_dir / "20-mode.conf").write_text("initial_mode=maintenance\n")
    (drop_in_dir / "30-supervisor.conf").write_text("supervisor_enabled=false\n")

    config = load_hid_config(base_config, drop_in_dir)

    # All values should be accumulated
    assert config.uart_device == "/dev/serial0"  # Base
    assert config.uart_baud == 9600  # From 10-baud.conf
    assert config.initial_mode == "maintenance"  # From 20-mode.conf
    assert config.supervisor_enabled is False  # From 30-supervisor.conf
