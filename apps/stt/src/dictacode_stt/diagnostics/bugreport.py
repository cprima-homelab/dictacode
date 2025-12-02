"""Bug report generation for dictacode STT (v0.2.9 Phase 5)."""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dictacode_stt.diagnostics.base import CheckStatus, DiagnosticResult
from dictacode_stt.diagnostics.registry import DiagnosticRegistry


logger = logging.getLogger(__name__)


@dataclass
class SystemReport:
    """Comprehensive system status report."""

    report_id: str
    generated_at: datetime
    version: str
    platform: Dict[str, Any]
    diagnostics: List[DiagnosticResult]
    logs: Dict[str, str]
    config: Dict[str, str]
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at.isoformat(),
            "version": self.version,
            "platform": self.platform,
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "logs": self.logs,
            "config": self.config,
            "summary": self.summary,
        }


class BugReportGenerator:
    """Generate comprehensive bug reports for issue submission."""

    SENSITIVE_KEYS = ["api_key", "password", "secret", "token", "credential", "auth"]
    LOG_LINES = 500  # Last N lines of logs

    def __init__(
        self,
        registry: Optional[DiagnosticRegistry] = None,
        log_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None,
    ):
        """Initialize bug report generator.

        Args:
            registry: Diagnostic registry (creates default if None)
            log_dir: Log directory (default: /var/log/dictacode)
            config_dir: Config directory (default: /etc/dictacode)
        """
        from dictacode_stt.diagnostics.registry import get_registry

        self.registry = registry or get_registry()
        self.log_dir = log_dir or Path("/var/log/dictacode")
        self.config_dir = config_dir or Path("/etc/dictacode")

    def generate(
        self,
        device_index: int = 0,
        uart_device: str = "/dev/serial0",
        whisper_binary: Optional[str] = None,
        whisper_model: Optional[str] = None,
    ) -> SystemReport:
        """Generate a complete bug report.

        Args:
            device_index: Audio device index for diagnostics
            uart_device: UART device path for diagnostics
            whisper_binary: Path to whisper binary
            whisper_model: Path to whisper model

        Returns:
            SystemReport with comprehensive diagnostic information
        """
        report_id = str(uuid.uuid4())[:8]
        logger.info(f"Generating bug report {report_id}")

        # Run all diagnostics
        from dictacode_stt.diagnostics import run_all_checks

        diagnostics_result = run_all_checks(
            device_index=device_index,
            uart_device=uart_device,
            whisper_binary=whisper_binary,
            whisper_model=whisper_model,
        )

        # Collect system info
        platform_info = self._collect_platform_info()

        # Collect logs (redacted)
        logs = self._collect_logs()

        # Collect config (redacted)
        config = self._collect_config()

        # Generate summary
        summary = self._generate_summary(diagnostics_result.checks)

        return SystemReport(
            report_id=report_id,
            generated_at=datetime.now(),
            version=self._get_version(),
            platform=platform_info,
            diagnostics=diagnostics_result.checks,
            logs=logs,
            config=config,
            summary=summary,
        )

    def _collect_platform_info(self) -> Dict[str, Any]:
        """Collect system/platform information."""
        logger.debug("Collecting platform information")

        info = {
            "os": platform.system(),
            "os_version": platform.version(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "hostname": platform.node(),
        }

        # Linux-specific info
        if platform.system() == "Linux":
            info["kernel"] = self._run_cmd("uname -r")
            info["uptime"] = self._run_cmd("uptime -p")
            info["memory"] = self._get_memory_info()
            info["disk"] = self._get_disk_info()

        return info

    def _collect_logs(self) -> Dict[str, str]:
        """Collect recent logs (redacted)."""
        logger.debug("Collecting logs")
        logs = {}

        # Try journalctl logs (systemd)
        for service in ["dictacode-stt", "dictacode-hid"]:
            output = self._run_cmd(
                f"journalctl -u {service} --no-pager -n {self.LOG_LINES} 2>/dev/null"
            )
            if output:
                logs[f"{service}.log"] = self._redact(output)

        # File-based logs
        if self.log_dir.exists():
            for log_file in self.log_dir.glob("*.log"):
                try:
                    content = self._read_tail(log_file, self.LOG_LINES)
                    if content:
                        logs[log_file.name] = self._redact(content)
                except Exception as e:
                    logger.warning(f"Failed to read {log_file}: {e}")

        return logs

    def _collect_config(self) -> Dict[str, str]:
        """Collect configuration (redacted)."""
        logger.debug("Collecting configuration")
        config = {}

        if self.config_dir.exists():
            for conf_file in self.config_dir.rglob("*.conf"):
                try:
                    rel_path = conf_file.relative_to(self.config_dir)
                    content = conf_file.read_text()
                    config[str(rel_path)] = self._redact(content)
                except Exception as e:
                    logger.warning(f"Failed to read {conf_file}: {e}")

        return config

    def _redact(self, text: str) -> str:
        """Redact sensitive information.

        Args:
            text: Text to redact

        Returns:
            Redacted text with sensitive values replaced
        """
        if not text:
            return text

        lines = text.split("\n")
        redacted_lines = []

        for line in lines:
            lower = line.lower()
            # Check if line contains sensitive key
            if any(key in lower for key in self.SENSITIVE_KEYS):
                # Redact value after = or :
                if "=" in line:
                    parts = line.split("=", 1)
                    line = f"{parts[0]}=[REDACTED]"
                elif ":" in line:
                    parts = line.split(":", 1)
                    line = f"{parts[0]}: [REDACTED]"
            redacted_lines.append(line)

        return "\n".join(redacted_lines)

    def _generate_summary(self, diagnostics: List[DiagnosticResult]) -> Dict[str, Any]:
        """Generate human-readable summary.

        Args:
            diagnostics: List of diagnostic results

        Returns:
            Summary dictionary with counts and critical issues
        """
        failed = [d for d in diagnostics if d.status == CheckStatus.FAIL]
        warnings = [d for d in diagnostics if d.status == CheckStatus.WARNING]

        summary = {
            "status": "healthy" if not failed else "unhealthy",
            "checks_passed": len(
                [d for d in diagnostics if d.status == CheckStatus.OK]
            ),
            "checks_failed": len(failed),
            "checks_warning": len(warnings),
            "critical_issues": [
                f"{d.name}: {d.message}"
                for d in diagnostics
                if d.severity == "critical" and d.status == CheckStatus.FAIL
            ],
            "warnings": [f"{d.name}: {d.message}" for d in warnings],
        }

        return summary

    def to_markdown(self, report: SystemReport) -> str:
        """Generate markdown for GitHub issue.

        Args:
            report: System report to convert

        Returns:
            Markdown-formatted bug report
        """
        md = []
        md.append(f"# Bug Report {report.report_id}")
        md.append(f"\n**Generated:** {report.generated_at.isoformat()}")
        md.append(f"**Version:** {report.version}")

        # Summary
        md.append("\n## Summary")
        md.append(f"- Status: **{report.summary['status']}**")
        md.append(f"- Checks Passed: {report.summary['checks_passed']}")
        md.append(f"- Checks Failed: {report.summary['checks_failed']}")
        md.append(f"- Checks Warning: {report.summary['checks_warning']}")

        if report.summary["critical_issues"]:
            md.append("\n### Critical Issues")
            for issue in report.summary["critical_issues"]:
                md.append(f"- {issue}")

        if report.summary["warnings"]:
            md.append("\n### Warnings")
            for warning in report.summary["warnings"]:
                md.append(f"- {warning}")

        # Platform
        md.append("\n## System Information")
        md.append("```")
        md.append(
            f"OS: {report.platform['os']} {report.platform.get('os_release', 'N/A')}"
        )
        md.append(f"Kernel: {report.platform.get('kernel', 'N/A')}")
        md.append(f"Machine: {report.platform['machine']}")
        md.append(f"Python: {report.platform['python_version']}")
        if "memory" in report.platform:
            mem = report.platform["memory"]
            if mem:
                md.append(f"Memory: {mem.get('MemTotal', 'N/A')}")
        if "disk" in report.platform:
            disk = report.platform["disk"]
            if disk:
                md.append(
                    f"Disk: {disk.get('free_gb', 'N/A')} GB free / {disk.get('total_gb', 'N/A')} GB total"
                )
        md.append("```")

        # Diagnostic Results
        md.append("\n## Diagnostic Results")
        md.append("\n| Check | Status | Message |")
        md.append("|-------|--------|---------|")
        for diag in report.diagnostics:
            status_icon = {
                "ok": "OK",
                "warning": "WARNING",
                "fail": "FAIL",
                "error": "ERROR",
                "skip": "SKIP",
            }.get(diag.status.value, "?")
            md.append(f"| {diag.name} | {status_icon} | {diag.message} |")

        # Logs (collapsible)
        if report.logs:
            md.append("\n## Logs")
            md.append("\n<details>")
            md.append("<summary>Click to expand logs</summary>\n")
            for name, content in report.logs.items():
                md.append(f"### {name}")
                md.append("```")
                # Truncate very long logs
                lines = content.split("\n")
                if len(lines) > 100:
                    md.append("\n".join(lines[:50]))
                    md.append(f"\n... ({len(lines) - 100} lines omitted) ...\n")
                    md.append("\n".join(lines[-50:]))
                else:
                    md.append(content)
                md.append("```\n")
            md.append("</details>")

        # Config (collapsible)
        if report.config:
            md.append("\n## Configuration")
            md.append("\n<details>")
            md.append("<summary>Click to expand configuration</summary>\n")
            for name, content in report.config.items():
                md.append(f"### {name}")
                md.append("```")
                md.append(content)
                md.append("```\n")
            md.append("</details>")

        return "\n".join(md)

    def _run_cmd(self, cmd: str) -> str:
        """Run shell command and return output.

        Args:
            cmd: Command to run

        Returns:
            Command output (stdout)
        """
        try:
            result = subprocess.run(
                cmd, check=False, shell=True, capture_output=True, text=True, timeout=10
            )
            return result.stdout.strip()
        except Exception as e:
            logger.debug(f"Command failed: {cmd}: {e}")
            return ""

    def _read_tail(self, path: Path, lines: int) -> str:
        """Read last N lines of a file.

        Args:
            path: File path
            lines: Number of lines to read

        Returns:
            Last N lines of file
        """
        try:
            with open(path) as f:
                all_lines = f.readlines()
                return "".join(all_lines[-lines:])
        except Exception as e:
            logger.debug(f"Failed to read {path}: {e}")
            return ""

    def _get_version(self) -> str:
        """Get dictacode version."""
        try:
            from dictacode_stt import __version__

            return __version__
        except Exception:
            return "unknown"

    def _get_memory_info(self) -> Dict[str, str]:
        """Get memory information from /proc/meminfo."""
        try:
            with open("/proc/meminfo") as f:
                lines = f.readlines()
            info = {}
            for line in lines[:5]:
                if ":" in line:
                    key, val = line.split(":", 1)
                    info[key.strip()] = val.strip()
            return info
        except Exception as e:
            logger.debug(f"Failed to read memory info: {e}")
            return {}

    def _get_disk_info(self) -> Dict[str, float]:
        """Get disk usage information."""
        try:
            usage = shutil.disk_usage("/")
            return {
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
            }
        except Exception as e:
            logger.debug(f"Failed to get disk info: {e}")
            return {}
