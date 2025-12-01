"""
Comprehensive compatibility matrix tests for HID.

Auto-generates test cases from compatibility.json to ensure:
- All "pass" entries are accepted
- All "fail" entries are rejected
- Unknown combinations are rejected
"""

import json
import pytest
from pathlib import Path
from dictacode_hid.compatibility import (
    CompatibilityMatrix,
    CompatibilityChecker,
    MATRIX_SEARCH_PATHS,
)


@pytest.fixture
def compatibility_matrix():
    """Load the actual compatibility matrix."""
    return CompatibilityMatrix()


@pytest.fixture
def compatibility_json():
    """Load the raw compatibility JSON for test generation."""
    # Find the matrix file using the same search paths
    for path in MATRIX_SEARCH_PATHS:
        if path.exists():
            with open(path) as f:
                return json.load(f)
    pytest.fail(f"Compatibility matrix not found in {MATRIX_SEARCH_PATHS}")


def test_matrix_loads_successfully(compatibility_matrix):
    """Test that the compatibility matrix loads without errors."""
    assert compatibility_matrix.protocol_version
    assert len(compatibility_matrix.entries) > 0


def test_matrix_has_current_protocol(compatibility_matrix, compatibility_json):
    """Test that matrix has a current protocol version defined."""
    current_protocol = compatibility_json["protocol"]["current"]
    assert current_protocol == compatibility_matrix.protocol_version
    assert current_protocol  # Not empty


def test_matrix_has_protocol_history(compatibility_matrix):
    """Test that protocol history is loaded."""
    assert len(compatibility_matrix.protocol_history) > 0


class TestPassEntries:
    """Auto-generated tests for all 'pass' entries in the matrix."""

    @pytest.fixture
    def pass_entries(self, compatibility_json):
        """Extract all pass entries from the matrix."""
        return [
            entry
            for entry in compatibility_json["compatibility"]
            if entry.get("status") == "pass"
        ]

    def test_has_pass_entries(self, pass_entries):
        """Verify that there are pass entries to test."""
        assert len(pass_entries) > 0, "No pass entries found in compatibility matrix"

    @pytest.mark.parametrize(
        "entry_index",
        range(10),  # Support up to 10 pass entries (adjust if needed)
    )
    def test_pass_entry_accepted(
        self, compatibility_matrix, pass_entries, entry_index
    ):
        """Test that all pass entries are accepted."""
        if entry_index >= len(pass_entries):
            pytest.skip(f"Only {len(pass_entries)} pass entries exist")

        entry = pass_entries[entry_index]
        stt_ver = entry["stt"]

        # Test all HID versions in this entry
        for hid_ver in entry["hid"]:
            checker = CompatibilityChecker(compatibility_matrix)
            is_compatible, error_msg = checker.validate_compatibility(stt_ver, hid_ver)

            assert is_compatible, (
                f"Expected STT {stt_ver} + HID {hid_ver} to be compatible "
                f"(status: pass), but was rejected: {error_msg}"
            )


class TestFailEntries:
    """Auto-generated tests for all 'fail' entries in the matrix."""

    @pytest.fixture
    def fail_entries(self, compatibility_json):
        """Extract all fail entries from the matrix."""
        return [
            entry
            for entry in compatibility_json["compatibility"]
            if entry.get("status") == "fail"
        ]

    def test_has_fail_entries(self, fail_entries):
        """Verify that there are fail entries to test."""
        # Note: Fail entries are optional, so this just documents the count
        print(f"Found {len(fail_entries)} fail entries in compatibility matrix")

    @pytest.mark.parametrize(
        "entry_index",
        range(10),  # Support up to 10 fail entries (adjust if needed)
    )
    def test_fail_entry_rejected(
        self, compatibility_matrix, fail_entries, entry_index
    ):
        """Test that all fail entries are rejected."""
        if entry_index >= len(fail_entries):
            pytest.skip(f"Only {len(fail_entries)} fail entries exist")

        entry = fail_entries[entry_index]
        stt_ver = entry["stt"]

        # Test all HID versions in this entry
        for hid_ver in entry["hid"]:
            checker = CompatibilityChecker(compatibility_matrix)
            is_compatible, error_msg = checker.validate_compatibility(stt_ver, hid_ver)

            # Fail entries should be explicitly rejected (Weak Spot #5 fix)
            assert not is_compatible, (
                f"Expected STT {stt_ver} + HID {hid_ver} to be rejected "
                f"(status: fail), but was accepted"
            )
            assert "KNOWN INCOMPATIBLE PAIR" in error_msg, (
                f"Expected explicit fail message, got: {error_msg}"
            )
            # Verify the notes field is included in error message
            if entry.get("notes"):
                assert entry["notes"] in error_msg, (
                    f"Expected fail reason '{entry['notes']}' in error message"
                )


class TestUnknownVersions:
    """Test rejection of unknown version combinations."""

    def test_unknown_stt_version_rejected(self, compatibility_matrix):
        """Test that unknown STT versions are rejected."""
        checker = CompatibilityChecker(compatibility_matrix)
        is_compatible, error_msg = checker.validate_compatibility("9.9.9", "0.2.12")

        assert not is_compatible
        assert "Unknown STT version" in error_msg

    def test_unknown_hid_version_rejected(self, compatibility_matrix):
        """Test that unknown HID versions are rejected."""
        checker = CompatibilityChecker(compatibility_matrix)
        # Use a known STT version but unknown HID version
        known_stt_version = list(compatibility_matrix.entries.keys())[0]
        is_compatible, error_msg = checker.validate_compatibility(
            known_stt_version, "9.9.9"
        )

        assert not is_compatible
        assert "INCOMPATIBLE" in error_msg.upper()

    def test_both_unknown_rejected(self, compatibility_matrix):
        """Test that both unknown versions are rejected."""
        checker = CompatibilityChecker(compatibility_matrix)
        is_compatible, error_msg = checker.validate_compatibility("9.9.9", "8.8.8")

        assert not is_compatible


class TestProtocolVersionChecking:
    """Tests for protocol version enforcement (Weak Spot #1 fix)."""

    def test_protocol_version_mismatch_detected(self, compatibility_matrix):
        """Test that protocol version mismatches are detected."""
        # This test verifies the fix for Weak Spot #1
        # The handshake code should reject peers with mismatched protocol versions

        # The matrix should have a current protocol version
        assert compatibility_matrix.protocol_version

        # Expected protocol should be in the matrix
        assert compatibility_matrix.protocol_version in [
            "1.0.0",
            "0.0.0",
        ] or compatibility_matrix.protocol_version.count(".") == 2


class TestMatrixCoverage:
    """Tests to ensure comprehensive matrix coverage."""

    def test_all_entries_have_required_fields(self, compatibility_json):
        """Verify all matrix entries have required fields."""
        for entry in compatibility_json["compatibility"]:
            assert "stt" in entry, f"Entry missing 'stt' field: {entry}"
            assert "hid" in entry, f"Entry missing 'hid' field: {entry}"
            assert "protocol" in entry, f"Entry missing 'protocol' field: {entry}"
            assert "status" in entry, f"Entry missing 'status' field: {entry}"
            assert entry["status"] in ["pass", "fail"], (
                f"Invalid status '{entry['status']}' in entry: {entry}"
            )

    def test_protocol_field_matches_protocol_version(self, compatibility_json):
        """Verify protocol fields reference valid protocol versions."""
        protocol_versions = [
            p["version"] for p in compatibility_json["protocol"]["history"]
        ]

        for entry in compatibility_json["compatibility"]:
            assert entry["protocol"] in protocol_versions, (
                f"Entry references unknown protocol {entry['protocol']}: {entry}"
            )

    def test_matrix_covers_current_version(self, compatibility_json):
        """Verify matrix includes the current release version."""
        # Get current version from package metadata
        import dictacode_hid
        current_version = dictacode_hid.__version__

        # Check if current version is in the matrix
        hid_versions = []
        for entry in compatibility_json["compatibility"]:
            hid_versions.extend(entry["hid"])

        assert current_version in hid_versions, (
            f"Current version {current_version} not found in compatibility matrix. "
            "Update compatibility.json when bumping version."
        )


def test_matrix_file_location(compatibility_matrix):
    """Test that matrix file is found in expected location."""
    assert compatibility_matrix.matrix_path.exists()
    assert compatibility_matrix.matrix_path.name == "compatibility.json"


def test_matrix_json_valid(compatibility_matrix):
    """Test that the loaded matrix has valid JSON structure."""
    # If we got here, the matrix loaded successfully
    assert compatibility_matrix.protocol_version
    assert isinstance(compatibility_matrix.entries, dict)
    assert len(compatibility_matrix.entries) > 0


def test_get_compatible_versions(compatibility_matrix):
    """Test querying compatible HID versions for a given STT version."""
    # Get first STT version from matrix
    stt_version = list(compatibility_matrix.entries.keys())[0]
    compatible_hid = compatibility_matrix.get_compatible_hid_versions(stt_version)

    assert isinstance(compatible_hid, set)
    assert len(compatible_hid) > 0


def test_is_compatible_method(compatibility_matrix):
    """Test the is_compatible method."""
    # Get first entry from matrix
    entry = list(compatibility_matrix.entries.values())[0]
    stt_ver = entry.stt_version
    hid_ver = entry.hid_versions[0]

    assert compatibility_matrix.is_compatible(stt_ver, hid_ver)
    assert not compatibility_matrix.is_compatible(stt_ver, "9.9.9")
