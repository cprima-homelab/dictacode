"""Compatibility checking for dictacode HID."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass

# Search paths for matrix file (in priority order)
MATRIX_SEARCH_PATHS = [
    Path("/opt/dictacode/shared/compatibility.json"),  # Production
    Path(__file__).parent.parent.parent.parent / "compatibility.json",  # Dev (repo root)
    Path("/etc/dictacode/compatibility.json"),  # Alternative system location
]

# Try to add PyPI installation path if importlib.resources available
try:
    from importlib import resources
    import sys

    # For Python 3.9+
    if sys.version_info >= (3, 9):
        # shared-data installs to sys.prefix / share/dictacode/compatibility.json
        # importlib.resources can access it via package name
        pkg_files = resources.files("dictacode_hid")
        # Path depends on shared-data configuration
        pkg_matrix = pkg_files.parent.parent / "share" / "dictacode" / "compatibility.json"
        if pkg_matrix.exists():
            MATRIX_SEARCH_PATHS.insert(1, Path(str(pkg_matrix)))
except (ImportError, AttributeError, TypeError):
    pass  # Fall back to other paths

@dataclass
class CompatibilityEntry:
    """Single compatibility entry from matrix."""
    stt_version: str
    hid_versions: List[str]
    protocol: str
    status: str  # "pass" or "fail"
    notes: str

class CompatibilityMatrix:
    """Loads and queries compatibility matrix from external JSON file."""

    def __init__(self, matrix_path: Optional[Path] = None):
        self.logger = logging.getLogger("dictacode.compatibility")
        self.matrix_path = matrix_path or self._find_matrix_file()
        self.protocol_version: str = ""
        self.protocol_history: List[Dict] = []
        self.entries: Dict[str, CompatibilityEntry] = {}
        self._load_matrix()

    def _find_matrix_file(self) -> Path:
        """Find matrix file in search paths. HARD-FAIL if not found."""
        for path in MATRIX_SEARCH_PATHS:
            if path.exists():
                self.logger.info(f"Found compatibility matrix: {path}")
                return path

        # HARD FAIL - no fallback
        error_msg = (
            "FATAL: Compatibility matrix file not found!\n"
            f"Searched paths:\n" +
            "\n".join(f"  - {p}" for p in MATRIX_SEARCH_PATHS) +
            "\n\nThis file is REQUIRED for operation. Cannot continue."
        )
        self.logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    def _load_matrix(self):
        """Load matrix from JSON file."""
        try:
            with open(self.matrix_path) as f:
                data = json.load(f)

            # Load protocol info
            protocol_data = data.get("protocol", {})
            self.protocol_version = protocol_data.get("current", "1.0.0")
            self.protocol_history = protocol_data.get("history", [])

            # Load compatibility entries (only "pass" status entries)
            for entry in data.get("compatibility", []):
                if entry.get("status") == "pass":
                    stt_ver = entry["stt"]
                    self.entries[stt_ver] = CompatibilityEntry(
                        stt_version=stt_ver,
                        hid_versions=entry["hid"],
                        protocol=entry["protocol"],
                        status=entry["status"],
                        notes=entry.get("notes", "")
                    )

            self.logger.info(
                f"Loaded compatibility matrix: {len(self.entries)} passing STT versions"
            )
        except Exception as e:
            self.logger.error(f"Failed to load compatibility matrix: {e}")
            raise

    def get_compatible_hid_versions(self, stt_version: str) -> Set[str]:
        """Get set of HID versions compatible with given STT version."""
        entry = self.entries.get(stt_version)
        return set(entry.hid_versions) if entry else set()

    def is_compatible(self, stt_version: str, hid_version: str) -> bool:
        """Check if STT and HID versions are compatible."""
        return hid_version in self.get_compatible_hid_versions(stt_version)

    def log_active_matrix(self):
        """Log active matrix for debugging."""
        self.logger.info("=" * 50)
        self.logger.info("ACTIVE COMPATIBILITY MATRIX")
        self.logger.info(f"Source: {self.matrix_path}")
        self.logger.info(f"Protocol: {self.protocol_version}")
        self.logger.info("=" * 50)
        for entry in self.entries.values():
            hid_str = ", ".join(sorted(entry.hid_versions))
            self.logger.info(f"STT {entry.stt_version} → HID [{hid_str}]")
        self.logger.info("=" * 50)

class CompatibilityChecker:
    """Runtime compatibility validation."""

    def __init__(self, matrix: Optional[CompatibilityMatrix] = None):
        self.matrix = matrix or CompatibilityMatrix()
        self.logger = logging.getLogger("dictacode.compatibility")
        self.matrix.log_active_matrix()

    def validate_compatibility(
        self,
        stt_version: str,
        hid_version: str
    ) -> Tuple[bool, str]:
        """
        Validate version compatibility.

        Returns:
            (is_compatible, error_message)
        """
        # Check if versions exist in matrix
        if stt_version not in self.matrix.entries:
            error = f"Unknown STT version: {stt_version}"
            self.logger.warning(error)
            return False, error

        if self.matrix.is_compatible(stt_version, hid_version):
            self.logger.info(
                f"Version compatibility OK: STT {stt_version} ↔ HID {hid_version}"
            )
            return True, ""

        # Get compatible versions for error message
        compatible = self.matrix.get_compatible_hid_versions(stt_version)
        compatible_str = ", ".join(sorted(compatible)) if compatible else "none"

        error = (
            f"INCOMPATIBLE VERSIONS: STT {stt_version} requires HID [{compatible_str}], "
            f"found HID {hid_version}. See COMPATIBILITY.md for upgrade instructions."
        )
        self.logger.error(error)
        return False, error
