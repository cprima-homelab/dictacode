"""Tests for CLI entry points."""

import sys
from unittest.mock import patch, MagicMock
from pathlib import Path

import pytest

from dictacode_stt.cli import audio_main, whisper_main, send_main


class TestAudioMain:
    """Tests for dictacode-stt-audio CLI."""

    def test_no_args_shows_help(self, capsys):
        """Test that no arguments shows help."""
        result = audio_main([])
        assert result == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "audio" in captured.out.lower()

    def test_list_command_exists(self):
        """Test list subcommand is recognized."""
        # Just test that --help works for list
        with pytest.raises(SystemExit) as exc_info:
            audio_main(["list", "--help"])
        # argparse exits with 0 for --help
        assert exc_info.value.code == 0

    def test_test_subcommand_exists(self):
        """Test test subcommand is recognized."""
        with pytest.raises(SystemExit) as exc_info:
            audio_main(["test", "--help"])
        assert exc_info.value.code == 0

    def test_record_subcommand_exists(self):
        """Test record subcommand is recognized."""
        with pytest.raises(SystemExit) as exc_info:
            audio_main(["record", "--help"])
        assert exc_info.value.code == 0


class TestWhisperMain:
    """Tests for dictacode-stt-whisper CLI."""

    def test_no_args_shows_help(self, capsys):
        """Test that no arguments shows help."""
        result = whisper_main([])
        assert result == 0
        captured = capsys.readouterr()
        assert "usage:" in captured.out.lower() or "whisper" in captured.out.lower()

    def test_check_with_missing_binary(self, capsys):
        """Test check command when binary is missing."""
        with patch("dictacode_stt.cli._find_whisper_binary", return_value=None):
            with patch("dictacode_stt.cli._find_whisper_model", return_value=None):
                result = whisper_main(["check"])

        assert result == 1
        captured = capsys.readouterr()
        assert "FAIL" in captured.err or "not found" in captured.err.lower()

    def test_check_with_valid_paths(self, capsys, tmp_path):
        """Test check command with valid paths."""
        # Create fake binary and model
        binary = tmp_path / "whisper-cli"
        binary.touch()
        binary.chmod(0o755)

        model = tmp_path / "model.bin"
        model.write_bytes(b"fake model data")

        result = whisper_main([
            "--binary", str(binary),
            "--model", str(model),
            "check"
        ])

        assert result == 0
        captured = capsys.readouterr()
        assert "OK" in captured.out

    def test_info_shows_paths(self, capsys, tmp_path):
        """Test info command shows path information."""
        binary = tmp_path / "whisper-cli"
        binary.touch()
        binary.chmod(0o755)

        model = tmp_path / "model.bin"
        model.write_bytes(b"x" * 1024 * 1024)  # 1 MB

        result = whisper_main([
            "--binary", str(binary),
            "--model", str(model),
            "info"
        ])

        assert result == 0
        captured = capsys.readouterr()
        assert str(binary) in captured.out
        assert str(model) in captured.out
        assert "1.0 MB" in captured.out or "1,048,576" in captured.out


class TestSendMain:
    """Tests for dictacode-stt-send CLI."""

    def test_no_args_shows_error(self, capsys):
        """Test that no arguments shows error."""
        result = send_main([])
        assert result == 1
        captured = capsys.readouterr()
        assert "ERROR" in captured.err or "Must specify" in captured.err

    def test_text_and_cmd_conflict(self, capsys):
        """Test that --cmd and text conflict."""
        result = send_main(["hello", "--cmd", "pause"])
        assert result == 1
        captured = capsys.readouterr()
        assert "Cannot specify both" in captured.err

    def test_arg_without_cmd(self, capsys):
        """Test that --arg requires --cmd."""
        result = send_main(["hello", "--arg", "value"])
        assert result == 1
        captured = capsys.readouterr()
        assert "--arg requires --cmd" in captured.err

    def test_dry_run_text_json(self, capsys):
        """Test dry-run with text message using JSON protocol."""
        result = send_main(["hello world", "--dry-run"])

        assert result == 0
        captured = capsys.readouterr()
        assert "hello world" in captured.out
        assert "json" in captured.out.lower()
        assert "dry-run" in captured.out.lower()
        assert '{"t":"text"' in captured.out or "t" in captured.out

    def test_dry_run_command_json(self, capsys):
        """Test dry-run with command message."""
        result = send_main(["--cmd", "pause", "--dry-run"])

        assert result == 0
        captured = capsys.readouterr()
        assert "pause" in captured.out
        assert "dry-run" in captured.out.lower()

    def test_dry_run_command_with_arg(self, capsys):
        """Test dry-run with command and argument."""
        result = send_main(["--cmd", "keymap", "--arg", "de_de", "--dry-run"])

        assert result == 0
        captured = capsys.readouterr()
        assert "keymap" in captured.out
        assert "de_de" in captured.out

    def test_dry_run_msgpack(self, capsys):
        """Test dry-run with msgpack protocol."""
        result = send_main(["hello", "--protocol", "msgpack", "--dry-run"])

        assert result == 0
        captured = capsys.readouterr()
        assert "msgpack" in captured.out.lower()

    def test_send_transport_error(self, capsys):
        """Test error handling when transport fails."""
        from dictacode_stt.transport import TransportError

        with patch("dictacode_stt.cli.UartTransport") as mock_transport:
            mock_instance = MagicMock()
            mock_instance.open.side_effect = TransportError("Device not found")
            mock_transport.return_value = mock_instance

            result = send_main(["hello"])

        assert result == 1
        captured = capsys.readouterr()
        assert "ERROR" in captured.err


class TestEntryPointsExist:
    """Test that entry points are importable."""

    def test_audio_main_callable(self):
        """Test audio_main is callable."""
        assert callable(audio_main)

    def test_whisper_main_callable(self):
        """Test whisper_main is callable."""
        assert callable(whisper_main)

    def test_send_main_callable(self):
        """Test send_main is callable."""
        assert callable(send_main)
