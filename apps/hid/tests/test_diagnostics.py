"""Tests for diagnostic classes."""

import json

import pytest

from dictacode_hid.diagnostics.base import CheckStatus, CheckResult, DiagnosticResult


class TestCheckStatus:
    """Test CheckStatus enum."""

    def test_values_exist(self):
        """Test all expected values exist."""
        assert CheckStatus.OK.value == "ok"
        assert CheckStatus.WARN.value == "warn"
        assert CheckStatus.FAIL.value == "fail"


class TestCheckResult:
    """Test CheckResult dataclass."""

    def test_create_simple(self):
        """Test creating simple check result."""
        result = CheckResult(
            name="test_check",
            status=CheckStatus.OK,
            message="Test passed",
        )
        assert result.name == "test_check"
        assert result.status == CheckStatus.OK
        assert result.message == "Test passed"
        assert result.next_step is None

    def test_create_with_next_step(self):
        """Test creating check result with next step."""
        result = CheckResult(
            name="test_check",
            status=CheckStatus.FAIL,
            message="Test failed",
            next_step="Fix the issue",
        )
        assert result.next_step == "Fix the issue"

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = CheckResult(
            name="test_check",
            status=CheckStatus.OK,
            message="Test passed",
        )
        d = result.to_dict()
        assert d["name"] == "test_check"
        assert d["status"] == "ok"
        assert d["message"] == "Test passed"
        assert "next_step" not in d

    def test_to_dict_with_next_step(self):
        """Test dictionary conversion with next step."""
        result = CheckResult(
            name="test_check",
            status=CheckStatus.FAIL,
            message="Test failed",
            next_step="Fix it",
        )
        d = result.to_dict()
        assert d["next_step"] == "Fix it"


class TestDiagnosticResult:
    """Test DiagnosticResult class."""

    def test_create_empty(self):
        """Test creating empty result."""
        result = DiagnosticResult(component="hid")
        assert result.component == "hid"
        assert result.checks == []

    def test_add_check(self):
        """Test adding check result."""
        result = DiagnosticResult(component="hid")
        check = CheckResult(name="test", status=CheckStatus.OK, message="OK")
        result.add(check)
        assert len(result.checks) == 1
        assert result.checks[0] == check

    def test_ok_helper(self):
        """Test ok() helper method."""
        result = DiagnosticResult(component="hid")
        result.ok("test", "Test passed")
        assert len(result.checks) == 1
        assert result.checks[0].status == CheckStatus.OK

    def test_warn_helper(self):
        """Test warn() helper method."""
        result = DiagnosticResult(component="hid")
        result.warn("test", "Warning", next_step="Fix it")
        assert len(result.checks) == 1
        assert result.checks[0].status == CheckStatus.WARN
        assert result.checks[0].next_step == "Fix it"

    def test_fail_helper(self):
        """Test fail() helper method."""
        result = DiagnosticResult(component="hid")
        result.fail("test", "Failed", next_step="Fix it")
        assert len(result.checks) == 1
        assert result.checks[0].status == CheckStatus.FAIL

    def test_counts(self):
        """Test count properties."""
        result = DiagnosticResult(component="hid")
        result.ok("ok1", "OK 1")
        result.ok("ok2", "OK 2")
        result.warn("warn1", "Warn 1")
        result.fail("fail1", "Fail 1")

        assert result.passed == 2
        assert result.warnings == 1
        assert result.failures == 1

    def test_overall_status_ok(self):
        """Test overall status when all OK."""
        result = DiagnosticResult(component="hid")
        result.ok("test", "OK")
        assert result.overall_status == CheckStatus.OK

    def test_overall_status_warn(self):
        """Test overall status with warnings only."""
        result = DiagnosticResult(component="hid")
        result.ok("test", "OK")
        result.warn("test2", "Warn")
        assert result.overall_status == CheckStatus.WARN

    def test_overall_status_fail(self):
        """Test overall status with failures."""
        result = DiagnosticResult(component="hid")
        result.ok("test", "OK")
        result.warn("test2", "Warn")
        result.fail("test3", "Fail")
        assert result.overall_status == CheckStatus.FAIL

    def test_exit_code_ok(self):
        """Test exit code when all OK."""
        result = DiagnosticResult(component="hid")
        result.ok("test", "OK")
        assert result.exit_code == 0

    def test_exit_code_warn(self):
        """Test exit code with warnings."""
        result = DiagnosticResult(component="hid")
        result.warn("test", "Warn")
        assert result.exit_code == 2

    def test_exit_code_fail(self):
        """Test exit code with failures."""
        result = DiagnosticResult(component="hid")
        result.fail("test", "Fail")
        assert result.exit_code == 1

    def test_to_dict(self):
        """Test dictionary conversion."""
        result = DiagnosticResult(component="hid")
        result.ok("test", "OK")
        result.fail("test2", "Fail")

        d = result.to_dict()
        assert d["status"] == "fail"
        assert d["component"] == "hid"
        assert len(d["checks"]) == 2
        assert d["summary"]["passed"] == 1
        assert d["summary"]["failed"] == 1
        assert d["summary"]["warnings"] == 0

    def test_to_json(self):
        """Test JSON conversion."""
        result = DiagnosticResult(component="hid")
        result.ok("test", "OK")

        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert parsed["status"] == "ok"
        assert parsed["component"] == "hid"

    def test_to_human_basic(self):
        """Test human-readable output."""
        result = DiagnosticResult(component="hid")
        result.ok("boot_config", "dtoverlay configured")
        result.fail("kernel_module", "Module not loaded")

        output = result.to_human()
        assert "=== dictacode HID Hardware Check ===" in output
        assert "[OK]" in output
        assert "[FAIL]" in output
        assert "Status:" in output

    def test_to_human_quiet(self):
        """Test quiet human-readable output."""
        result = DiagnosticResult(component="hid")
        result.ok("boot_config", "OK")
        result.fail("kernel_module", "Failed", next_step="Fix it")

        output = result.to_human(quiet=True)
        assert "[OK]" not in output
        assert "[FAIL]" in output
        assert "kernel_module" in output
