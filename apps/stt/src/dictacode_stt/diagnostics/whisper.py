"""Whisper diagnostic checks for STT.

Checks whisper binary and model availability.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from .base import DiagnosticResult


# Default paths
DEFAULT_WHISPER_BINARY = Path.home() / "whisper.cpp" / "build" / "bin" / "whisper-cli"
DEFAULT_WHISPER_MODEL = Path.home() / "whisper.cpp" / "models" / "ggml-tiny.bin"

# Minimum model sizes (rough estimates in MB)
MODEL_MIN_SIZES = {
    "tiny": 70,
    "base": 140,
    "small": 460,
    "medium": 1500,
    "large": 2900,
}


def find_whisper_binary(custom_path: Optional[Path] = None) -> Optional[Path]:
    """Find whisper-cli binary."""
    if custom_path and custom_path.exists():
        return custom_path

    # Check default path
    if DEFAULT_WHISPER_BINARY.exists():
        return DEFAULT_WHISPER_BINARY

    # Check PATH
    try:
        result = subprocess.run(
            ["which", "whisper-cli"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass

    return None


def check_whisper_executable(binary_path: Path) -> bool:
    """Check if whisper binary is executable."""
    return os.access(binary_path, os.X_OK)


def get_whisper_version(binary_path: Path) -> Optional[str]:
    """Get whisper version string."""
    try:
        result = subprocess.run(
            [str(binary_path), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        # whisper-cli may not have --version, try --help
        if result.returncode != 0:
            result = subprocess.run(
                [str(binary_path), "--help"],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        if result.returncode == 0:
            return "available"
        return None
    except Exception:
        return None


def find_whisper_model(custom_path: Optional[Path] = None) -> Optional[Path]:
    """Find whisper model file."""
    if custom_path and custom_path.exists():
        return custom_path

    # Check default path
    if DEFAULT_WHISPER_MODEL.exists():
        return DEFAULT_WHISPER_MODEL

    # Check for any model in default directory
    model_dir = Path.home() / "whisper.cpp" / "models"
    if model_dir.exists():
        for model in model_dir.glob("ggml-*.bin"):
            return model

    return None


def check_model_size(model_path: Path) -> bool:
    """Check if model file has reasonable size."""
    try:
        size_mb = model_path.stat().st_size / (1024 * 1024)
        # Minimum size for smallest model (tiny)
        return size_mb >= MODEL_MIN_SIZES.get("tiny", 50)
    except Exception:
        return False


def run_whisper_checks(
    binary_path: Optional[Path] = None,
    model_path: Optional[Path] = None,
) -> DiagnosticResult:
    """Run all whisper diagnostic checks.

    Args:
        binary_path: Custom path to whisper-cli binary.
        model_path: Custom path to whisper model file.
    """
    result = DiagnosticResult(component="stt")

    # Check whisper binary
    found_binary = find_whisper_binary(binary_path)
    if found_binary:
        result.ok("whisper_binary", f"whisper-cli found: {found_binary}")

        if check_whisper_executable(found_binary):
            result.ok("whisper_executable", "whisper-cli is executable")
        else:
            result.fail(
                "whisper_executable",
                "whisper-cli is not executable",
                f"Run: chmod +x {found_binary}",
            )

        version = get_whisper_version(found_binary)
        if version:
            result.ok("whisper_runnable", "whisper-cli runs successfully")
        else:
            result.warn(
                "whisper_runnable",
                "Could not verify whisper-cli runs",
                "Check binary compatibility and dependencies",
            )
    else:
        result.fail(
            "whisper_binary",
            "whisper-cli not found",
            f"Build whisper.cpp or set custom path (default: {DEFAULT_WHISPER_BINARY})",
        )

    # Check whisper model
    found_model = find_whisper_model(model_path)
    if found_model:
        result.ok("whisper_model", f"Model found: {found_model.name}")

        if check_model_size(found_model):
            size_mb = found_model.stat().st_size / (1024 * 1024)
            result.ok("whisper_model_size", f"Model size: {size_mb:.1f} MB")
        else:
            result.warn(
                "whisper_model_size",
                "Model file seems too small (may be corrupted)",
                "Re-download the model file",
            )
    else:
        result.fail(
            "whisper_model",
            "Whisper model not found",
            f"Download model to {DEFAULT_WHISPER_MODEL}",
        )

    return result
