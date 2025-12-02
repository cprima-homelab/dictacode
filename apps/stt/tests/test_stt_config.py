"""Unit tests for STT configuration loader."""

from pathlib import Path

import pytest

from dictacode_stt.stt_config import SttConfig, load_stt_config


def test_default_config():
    """Test default configuration values."""
    config = SttConfig()

    # Security: localhost by default
    assert config.api_host == "127.0.0.1"

    # No port collisions
    assert config.metrics_port == 9100
    assert config.api_port == 8000
    assert config.api_metrics_port == 9101

    # Metrics disabled by default
    assert config.metrics_enabled is False
    assert config.api_metrics_enabled is False


def test_port_validation_out_of_range():
    """Test port range validation."""
    with pytest.raises(ValueError, match="Invalid.*port"):
        SttConfig(api_port=65536)  # Out of range

    with pytest.raises(ValueError, match="Invalid.*port"):
        SttConfig(metrics_port=0)  # Too low

    with pytest.raises(ValueError, match="Invalid.*port"):
        SttConfig(api_metrics_port=99999)  # Too high


def test_port_validation_non_integer():
    """Test port type validation."""
    with pytest.raises((ValueError, TypeError)):
        SttConfig(api_port="not_a_number")


def test_baud_rate_validation():
    """Test UART baud rate validation."""
    # Valid baud rates
    SttConfig(uart_baud=9600)
    SttConfig(uart_baud=115200)

    # Invalid baud rate
    with pytest.raises(ValueError, match="Invalid uart_baud"):
        SttConfig(uart_baud=12345)


def test_chunk_duration_validation():
    """Test chunk duration validation."""
    # Valid durations
    SttConfig(chunk_duration=0.1)
    SttConfig(chunk_duration=5.0)
    SttConfig(chunk_duration=60.0)

    # Too small
    with pytest.raises(ValueError, match="Invalid chunk_duration"):
        SttConfig(chunk_duration=0.01)

    # Too large
    with pytest.raises(ValueError, match="Invalid chunk_duration"):
        SttConfig(chunk_duration=120.0)


def test_config_file_missing():
    """Test graceful fallback when config missing."""
    config = load_stt_config(Path("/nonexistent/stt.conf"))
    assert isinstance(config, SttConfig)
    assert config.api_host == "127.0.0.1"  # Defaults


def test_config_file_with_flat_structure(tmp_path):
    """Test parsing config with flat (DEFAULT section) structure."""
    config_file = tmp_path / "stt.conf"
    config_file.write_text(
        """
# Flat config (no sections)
api_port=9000
metrics_enabled=true
api_host=192.168.1.100
"""
    )

    config = load_stt_config(config_file)
    assert config.api_port == 9000
    assert config.metrics_enabled is True
    assert config.api_host == "192.168.1.100"


def test_config_file_with_sections(tmp_path):
    """Test parsing config with [stt] section."""
    config_file = tmp_path / "stt.conf"
    config_file.write_text(
        """
[stt]
api_port=9000
metrics_enabled=true
api_metrics_port=9102
"""
    )

    config = load_stt_config(config_file)
    assert config.api_port == 9000
    assert config.metrics_enabled is True
    assert config.api_metrics_port == 9102


def test_invalid_boolean_fallback(tmp_path):
    """Test fallback to defaults on invalid boolean values."""
    config_file = tmp_path / "stt.conf"
    config_file.write_text(
        """
metrics_enabled=maybe
api_metrics_enabled=yesno
"""
    )

    config = load_stt_config(config_file)
    # Should fall back to defaults
    assert config.metrics_enabled is False
    assert config.api_metrics_enabled is False


def test_invalid_integer_fallback(tmp_path):
    """Test fallback to defaults on invalid integer values."""
    config_file = tmp_path / "stt.conf"
    config_file.write_text(
        """
api_port=not_a_number
metrics_port=abc
"""
    )

    config = load_stt_config(config_file)
    # Should fall back to defaults
    assert config.api_port == 8000
    assert config.metrics_port == 9100


def test_invalid_float_fallback(tmp_path):
    """Test fallback to defaults on invalid float values."""
    config_file = tmp_path / "stt.conf"
    config_file.write_text(
        """
chunk_duration=invalid
"""
    )

    config = load_stt_config(config_file)
    # Should fall back to default
    assert config.chunk_duration == 5.0


def test_partial_config(tmp_path):
    """Test config with only some keys set."""
    config_file = tmp_path / "stt.conf"
    config_file.write_text(
        """
api_port=9500
model=base
"""
    )

    config = load_stt_config(config_file)
    # Set values
    assert config.api_port == 9500
    assert config.model == "base"
    # Defaults for unset
    assert config.metrics_enabled is False
    assert config.api_host == "127.0.0.1"


def test_all_config_keys(tmp_path):
    """Test loading all configuration keys."""
    config_file = tmp_path / "stt.conf"
    config_file.write_text(
        """
metrics_enabled=true
metrics_port=9200
api_host=0.0.0.0
api_port=9300
api_config_dir=/custom/path
api_metrics_enabled=true
api_metrics_port=9301
model=small
language=de
uart_device=/dev/ttyUSB0
uart_baud=230400
chunk_duration=10.5
"""
    )

    config = load_stt_config(config_file)
    assert config.metrics_enabled is True
    assert config.metrics_port == 9200
    assert config.api_host == "0.0.0.0"
    assert config.api_port == 9300
    assert config.api_config_dir == "/custom/path"
    assert config.api_metrics_enabled is True
    assert config.api_metrics_port == 9301
    assert config.model == "small"
    assert config.language == "de"
    assert config.uart_device == "/dev/ttyUSB0"
    assert config.uart_baud == 230400
    assert config.chunk_duration == 10.5


def test_validation_fails_with_bad_config_file(tmp_path):
    """Test that validation errors in config cause fallback to defaults."""
    config_file = tmp_path / "stt.conf"
    config_file.write_text(
        """
api_port=65536
uart_baud=12345
chunk_duration=150
"""
    )

    # Should fall back to safe defaults due to validation errors
    config = load_stt_config(config_file)
    assert isinstance(config, SttConfig)
    # Should be defaults since validation failed
    assert config.api_port == 8000
    assert config.uart_baud == 115200
    assert config.chunk_duration == 5.0


def test_comments_ignored(tmp_path):
    """Test that comments are properly ignored."""
    config_file = tmp_path / "stt.conf"
    config_file.write_text(
        """
# This is a comment
api_port=9000  # inline comment
# metrics_enabled=true (commented out)
metrics_enabled=false
"""
    )

    config = load_stt_config(config_file)
    assert config.api_port == 9000
    assert config.metrics_enabled is False


def test_security_warning_on_non_localhost(tmp_path, caplog):
    """Test that warning is logged when API bound to non-localhost."""
    import logging

    caplog.set_level(logging.WARNING)

    # Should warn on 0.0.0.0
    config = SttConfig(api_host="0.0.0.0")
    assert "not localhost" in caplog.text.lower()

    # Should not warn on localhost variants
    caplog.clear()
    SttConfig(api_host="127.0.0.1")
    assert "not localhost" not in caplog.text.lower()

    SttConfig(api_host="localhost")
    assert "not localhost" not in caplog.text.lower()

    SttConfig(api_host="::1")
    assert "not localhost" not in caplog.text.lower()


def test_no_port_collision():
    """Test that default ports don't collide."""
    config = SttConfig()

    # All ports should be unique
    ports = [config.metrics_port, config.api_port, config.api_metrics_port]
    assert len(ports) == len(set(ports)), "Default ports must not collide"

    # Verify expected defaults
    assert config.metrics_port == 9100
    assert config.api_port == 8000
    assert config.api_metrics_port == 9101


# === Drop-in config tests (v0.3.2) ===


def test_drop_in_overrides_base_config(tmp_path):
    """Test drop-in config overrides base config values."""
    # Create base config
    base_config = tmp_path / "stt.conf"
    base_config.write_text(
        """
api_port=8000
model=tiny
language=en
"""
    )

    # Create drop-in directory
    drop_in_dir = tmp_path / "stt.d"
    drop_in_dir.mkdir()

    # Create drop-in that overrides some values
    (drop_in_dir / "10-custom.conf").write_text(
        """
api_port=9000
model=base
"""
    )

    config = load_stt_config(base_config, drop_in_dir)

    # Drop-in values should override base
    assert config.api_port == 9000
    assert config.model == "base"
    # Base value not overridden should remain
    assert config.language == "en"


def test_drop_in_sorted_order(tmp_path):
    """Test drop-ins are merged in sorted filename order."""
    base_config = tmp_path / "stt.conf"
    base_config.write_text("api_port=8000\n")

    drop_in_dir = tmp_path / "stt.d"
    drop_in_dir.mkdir()

    # Create drop-ins in reverse order (20 before 10)
    # Later in sort order should win
    (drop_in_dir / "10-first.conf").write_text("api_port=9000\n")
    (drop_in_dir / "20-second.conf").write_text("api_port=9500\n")

    config = load_stt_config(base_config, drop_in_dir)

    # 20-second.conf should override 10-first.conf
    assert config.api_port == 9500


def test_drop_in_only_conf_files(tmp_path):
    """Test only *.conf files in drop-in dir are loaded."""
    base_config = tmp_path / "stt.conf"
    base_config.write_text("api_port=8000\n")

    drop_in_dir = tmp_path / "stt.d"
    drop_in_dir.mkdir()

    # Create a .conf file and non-.conf files
    (drop_in_dir / "10-valid.conf").write_text("api_port=9000\n")
    (drop_in_dir / "20-invalid.txt").write_text("api_port=9999\n")
    (drop_in_dir / "README").write_text("api_port=8888\n")

    config = load_stt_config(base_config, drop_in_dir)

    # Only .conf file should be loaded
    assert config.api_port == 9000


def test_drop_in_missing_dir(tmp_path):
    """Test graceful handling when drop-in directory doesn't exist."""
    base_config = tmp_path / "stt.conf"
    base_config.write_text("api_port=9000\n")

    # Non-existent drop-in dir
    drop_in_dir = tmp_path / "stt.d"

    config = load_stt_config(base_config, drop_in_dir)

    # Should still load base config
    assert config.api_port == 9000


def test_drop_in_empty_dir(tmp_path):
    """Test handling of empty drop-in directory."""
    base_config = tmp_path / "stt.conf"
    base_config.write_text("api_port=9000\n")

    drop_in_dir = tmp_path / "stt.d"
    drop_in_dir.mkdir()

    config = load_stt_config(base_config, drop_in_dir)

    assert config.api_port == 9000


def test_drop_in_invalid_file_skipped(tmp_path, caplog):
    """Test invalid drop-in files are skipped with warning."""
    import logging

    caplog.set_level(logging.WARNING)

    base_config = tmp_path / "stt.conf"
    base_config.write_text("api_port=8000\n")

    drop_in_dir = tmp_path / "stt.d"
    drop_in_dir.mkdir()

    # Create valid and invalid drop-ins
    (drop_in_dir / "10-valid.conf").write_text("api_port=9000\n")
    # Write binary garbage that can't be parsed
    (drop_in_dir / "20-invalid.conf").write_bytes(b"\x00\x01\x02\x03")

    config = load_stt_config(base_config, drop_in_dir)

    # Valid config should be loaded
    assert config.api_port == 9000
    # Warning should be logged for invalid file
    assert "20-invalid.conf" in caplog.text


def test_base_only_no_drop_in(tmp_path):
    """Test loading base config without any drop-ins."""
    base_config = tmp_path / "stt.conf"
    base_config.write_text(
        """
api_port=9000
model=small
metrics_enabled=true
"""
    )

    config = load_stt_config(base_config, tmp_path / "nonexistent_stt.d")

    assert config.api_port == 9000
    assert config.model == "small"
    assert config.metrics_enabled is True
