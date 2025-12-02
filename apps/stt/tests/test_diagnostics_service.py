"""Tests for DiagnosticsService (v0.3.6).

Tests the central diagnostics service that provides a unified interface
for diagnostics consumed by API and CLI.
"""

import pytest

from dictacode_stt.diagnostics import DiagnosticsService
from dictacode_stt.diagnostics.base import CheckCategory, CheckStatus


class TestDiagnosticsService:
    """Unit tests for DiagnosticsService."""

    def test_instantiation_with_defaults(self):
        """DiagnosticsService can be instantiated with defaults."""
        service = DiagnosticsService()
        assert service.device_index == 0
        assert service.uart_device == "/dev/serial0"
        assert service.whisper_binary is None
        assert service.whisper_model is None

    def test_instantiation_with_custom_values(self):
        """DiagnosticsService accepts custom configuration."""
        from pathlib import Path

        service = DiagnosticsService(
            device_index=2,
            uart_device="/dev/ttyUSB0",
            whisper_binary=Path("/usr/bin/whisper-cli"),
            whisper_model=Path("/models/tiny.bin"),
        )
        assert service.device_index == 2
        assert service.uart_device == "/dev/ttyUSB0"
        assert service.whisper_binary == Path("/usr/bin/whisper-cli")
        assert service.whisper_model == Path("/models/tiny.bin")

    def test_list_categories_returns_all(self):
        """list_categories returns all CheckCategory values."""
        service = DiagnosticsService()
        categories = service.list_categories()

        assert isinstance(categories, list)
        assert len(categories) == len(CheckCategory)

        # Check structure of category dicts
        for cat in categories:
            assert "id" in cat
            assert "name" in cat

    def test_list_categories_ids_match_enum(self):
        """Category IDs match CheckCategory enum values."""
        service = DiagnosticsService()
        categories = service.list_categories()

        category_ids = {cat["id"] for cat in categories}
        expected_ids = {c.value for c in CheckCategory}

        assert category_ids == expected_ids

    def test_list_checks_returns_list(self):
        """list_checks returns a list."""
        service = DiagnosticsService()
        checks = service.list_checks()

        assert isinstance(checks, list)

    def test_list_checks_structure(self):
        """list_checks returns dicts with expected keys."""
        service = DiagnosticsService()
        checks = service.list_checks()

        # Registry may be empty, but structure should be consistent
        for check in checks:
            assert "check_id" in check
            assert "name" in check
            assert "category" in check
            assert "description" in check
            assert "enabled" in check
            assert "severity" in check

    def test_run_all_returns_diagnostic_result(self):
        """run_all returns a DiagnosticResult."""
        from dictacode_stt.diagnostics.base import DiagnosticResult

        service = DiagnosticsService()
        result = service.run_all()

        assert isinstance(result, DiagnosticResult)
        assert result.component == "stt"

    def test_run_all_has_checks(self):
        """run_all returns result with checks."""
        service = DiagnosticsService()
        result = service.run_all()

        # Should have at least some checks
        assert hasattr(result, "checks")
        assert isinstance(result.checks, list)

    def test_quick_status_returns_dict(self):
        """quick_status returns a dict with expected keys."""
        service = DiagnosticsService()
        status = service.quick_status()

        assert isinstance(status, dict)
        assert "overall" in status
        assert "passed" in status
        assert "failed" in status
        assert "warnings" in status
        assert "total" in status

    def test_quick_status_counts_are_integers(self):
        """quick_status counts are integers."""
        service = DiagnosticsService()
        status = service.quick_status()

        assert isinstance(status["passed"], int)
        assert isinstance(status["failed"], int)
        assert isinstance(status["warnings"], int)
        assert isinstance(status["total"], int)

    def test_history_starts_empty(self):
        """get_history returns empty list initially."""
        service = DiagnosticsService()
        history = service.get_history()

        assert isinstance(history, list)
        assert len(history) == 0

    def test_history_populated_after_run(self):
        """get_history returns entry after run_all."""
        service = DiagnosticsService()

        # Run diagnostics
        service.run_all()

        history = service.get_history()
        assert len(history) == 1

        # Check entry structure
        entry = history[0]
        assert "timestamp" in entry
        assert "overall" in entry
        assert "passed" in entry
        assert "failed" in entry

    def test_history_ring_buffer_max_size(self):
        """History maintains max size."""
        service = DiagnosticsService()
        service._history_max = 3

        # Run 5 times
        for _ in range(5):
            service.run_all()

        history = service.get_history()
        assert len(history) == 3

    def test_history_newest_first(self):
        """get_history returns newest entries first."""
        service = DiagnosticsService()
        service._history_max = 5

        # Run twice with different configs (should result in same timestamps but different entries)
        service.run_all()
        service.run_all()

        history = service.get_history()
        assert len(history) == 2

        # Newest should be first (timestamps should be in descending order)
        if history[0]["timestamp"] and history[1]["timestamp"]:
            assert history[0]["timestamp"] >= history[1]["timestamp"]


class TestDiagnosticsServiceIntegration:
    """Integration tests for DiagnosticsService with actual checks."""

    def test_run_all_includes_audio_checks(self):
        """run_all includes audio-related checks."""
        service = DiagnosticsService()
        result = service.run_all()

        # Check for audio-related check names
        check_names = [c.name for c in result.checks]

        # At least one audio-related check should be present
        audio_checks = [n for n in check_names if "audio" in n.lower()]
        assert len(audio_checks) > 0

    def test_run_all_includes_whisper_checks(self):
        """run_all includes whisper-related checks."""
        service = DiagnosticsService()
        result = service.run_all()

        check_names = [c.name for c in result.checks]
        whisper_checks = [n for n in check_names if "whisper" in n.lower()]
        assert len(whisper_checks) > 0

    def test_run_all_exit_code_valid(self):
        """run_all result has valid exit code."""
        service = DiagnosticsService()
        result = service.run_all()

        # Exit code should be 0 (ok), 1 (fail), or 2 (warn)
        assert result.exit_code in [0, 1, 2]

    def test_overall_status_is_valid(self):
        """Overall status is a valid CheckStatus value."""
        service = DiagnosticsService()
        result = service.run_all()

        valid_statuses = [s.value for s in CheckStatus]
        assert result.overall_status.value in valid_statuses
