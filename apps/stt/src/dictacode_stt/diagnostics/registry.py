"""Diagnostic Check Registry (v0.2.9 Phase 2).

Provides dynamic check registration, dependency management, and async execution.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

from .base import (
    CheckCategory,
    CheckResult,
    CheckSeverity,
    CheckStatus,
    DiagnosticResult,
)


logger = logging.getLogger(__name__)


@dataclass
class DiagnosticCheck:
    """A registered diagnostic check (v0.2.9)."""

    check_id: str
    name: str
    category: CheckCategory
    func: Callable[..., CheckResult]
    description: str = ""
    depends_on: List[str] = field(default_factory=list)
    timeout: float = 30.0  # Timeout in seconds
    severity: CheckSeverity = CheckSeverity.INFO
    enabled: bool = True

    def __hash__(self):
        """Allow DiagnosticCheck to be used in sets."""
        return hash(self.check_id)


class DiagnosticRegistry:
    """Registry for diagnostic checks (v0.2.9 Phase 2).

    Allows checks to be dynamically registered, manages dependencies,
    and provides async execution with timeouts.

    Usage:
        registry = DiagnosticRegistry()

        # Register a check
        @registry.register(
            check_id="audio_device",
            name="Audio Device Available",
            category=CheckCategory.AUDIO,
        )
        def check_audio_device() -> CheckResult:
            # ... check logic ...
            return CheckResult(...)

        # Run all checks
        result = await registry.run_all()
    """

    def __init__(self):
        """Initialize empty registry."""
        self._checks: Dict[str, DiagnosticCheck] = {}
        self._categories: Dict[CheckCategory, List[DiagnosticCheck]] = {}

    def register(
        self,
        check_id: str,
        name: str,
        category: CheckCategory,
        description: str = "",
        depends_on: Optional[List[str]] = None,
        timeout: float = 30.0,
        severity: CheckSeverity = CheckSeverity.INFO,
        enabled: bool = True,
    ) -> Callable:
        """Decorator to register a diagnostic check.

        Args:
            check_id: Unique check identifier
            name: Human-readable check name
            category: Check category
            description: Check description
            depends_on: List of check_ids this check depends on
            timeout: Execution timeout in seconds
            severity: Default severity level
            enabled: Whether check is enabled

        Returns:
            Decorator function

        Example:
            @registry.register(
                check_id="whisper_binary",
                name="Whisper Binary",
                category=CheckCategory.TRANSCRIPTION,
                depends_on=["python_version"],
            )
            def check_whisper_binary() -> CheckResult:
                # ... check logic ...
                return CheckResult(...)
        """

        def decorator(func: Callable[..., CheckResult]) -> Callable:
            check = DiagnosticCheck(
                check_id=check_id,
                name=name,
                category=category,
                func=func,
                description=description,
                depends_on=depends_on or [],
                timeout=timeout,
                severity=severity,
                enabled=enabled,
            )

            self._checks[check_id] = check

            # Add to category index
            if category not in self._categories:
                self._categories[category] = []
            self._categories[category].append(check)

            logger.debug(f"Registered check: {check_id} ({category.value})")
            return func

        return decorator

    def unregister(self, check_id: str) -> bool:
        """Unregister a check.

        Args:
            check_id: Check identifier to remove

        Returns:
            True if check was unregistered, False if not found
        """
        if check_id not in self._checks:
            return False

        check = self._checks[check_id]

        # Remove from category index
        if check.category in self._categories:
            self._categories[check.category].remove(check)

        # Remove from main registry
        del self._checks[check_id]

        logger.debug(f"Unregistered check: {check_id}")
        return True

    def get_check(self, check_id: str) -> Optional[DiagnosticCheck]:
        """Get a registered check by ID."""
        return self._checks.get(check_id)

    def list_checks(
        self,
        category: Optional[CheckCategory] = None,
        enabled_only: bool = False,
    ) -> List[DiagnosticCheck]:
        """List registered checks.

        Args:
            category: Filter by category (None = all)
            enabled_only: Only include enabled checks

        Returns:
            List of diagnostic checks
        """
        if category:
            checks = self._categories.get(category, [])
        else:
            checks = list(self._checks.values())

        if enabled_only:
            checks = [c for c in checks if c.enabled]

        return checks

    def _resolve_dependencies(
        self, checks: List[DiagnosticCheck]
    ) -> List[DiagnosticCheck]:
        """Resolve check dependencies using topological sort.

        Args:
            checks: List of checks to sort

        Returns:
            Checks sorted by dependencies (dependencies first)

        Raises:
            ValueError: If circular dependency detected
        """
        # Build dependency graph
        graph: Dict[str, Set[str]] = {}
        in_degree: Dict[str, int] = {}

        check_map = {c.check_id: c for c in checks}

        for check in checks:
            graph[check.check_id] = set(check.depends_on)
            in_degree[check.check_id] = len(check.depends_on)

        # Topological sort (Kahn's algorithm)
        queue = [cid for cid, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            check_id = queue.pop(0)
            result.append(check_map[check_id])

            # Update dependents
            for other_id, deps in graph.items():
                if check_id in deps:
                    deps.remove(check_id)
                    in_degree[other_id] -= 1
                    if in_degree[other_id] == 0:
                        queue.append(other_id)

        # Check for circular dependencies
        if len(result) != len(checks):
            remaining = [c.check_id for c in checks if c not in result]
            raise ValueError(f"Circular dependency detected: {remaining}")

        return result

    async def run_check(self, check: DiagnosticCheck, **kwargs) -> CheckResult:
        """Run a single check with timeout.

        Args:
            check: The check to run
            **kwargs: Arguments to pass to check function

        Returns:
            CheckResult from the check

        Raises:
            asyncio.TimeoutError: If check exceeds timeout
        """
        start_time = time.perf_counter()

        try:
            # Run check with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(check.func, **kwargs),
                timeout=check.timeout,
            )

            # Add timing and metadata
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            result.duration_ms = duration_ms
            result.check_id = check.check_id
            result.category = check.category

            # Use check's default severity if not set
            if result.severity == CheckSeverity.INFO:
                result.severity = check.severity

            logger.debug(
                f"Check {check.check_id} completed in {duration_ms}ms: {result.status.value}"
            )

            return result

        except asyncio.TimeoutError:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Check {check.check_id} timed out after {duration_ms}ms")

            return CheckResult(
                check_id=check.check_id,
                name=check.name,
                status=CheckStatus.ERROR,
                message=f"Check timed out after {check.timeout}s",
                category=check.category,
                severity=CheckSeverity.CRITICAL,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Check {check.check_id} raised exception: {e}", exc_info=True)

            return CheckResult(
                check_id=check.check_id,
                name=check.name,
                status=CheckStatus.ERROR,
                message=f"Check failed with error: {e!s}",
                category=check.category,
                severity=CheckSeverity.CRITICAL,
                duration_ms=duration_ms,
            )

    async def run_all(
        self,
        category: Optional[CheckCategory] = None,
        enabled_only: bool = True,
        **kwargs,
    ) -> DiagnosticResult:
        """Run all registered checks (with dependency resolution).

        Args:
            category: Run checks from specific category only (None = all)
            enabled_only: Only run enabled checks
            **kwargs: Arguments to pass to check functions

        Returns:
            DiagnosticResult containing all check results
        """
        # Get checks to run
        checks = self.list_checks(category=category, enabled_only=enabled_only)

        if not checks:
            logger.warning("No checks to run")
            return DiagnosticResult(component="stt")

        # Resolve dependencies
        try:
            ordered_checks = self._resolve_dependencies(checks)
        except ValueError as e:
            logger.error(f"Dependency resolution failed: {e}")
            # Return error result
            result = DiagnosticResult(component="stt")
            result.fail(
                name="dependency_error",
                message=str(e),
                next_step="Fix circular dependencies in check registration",
            )
            return result

        logger.info(f"Running {len(ordered_checks)} diagnostic checks...")

        # Run checks in order
        result = DiagnosticResult(component="stt")
        completed_checks: Set[str] = set()

        for check in ordered_checks:
            # Check if dependencies completed successfully
            failed_deps = []
            for dep_id in check.depends_on:
                if dep_id not in completed_checks:
                    failed_deps.append(dep_id)

            if failed_deps:
                # Skip check if dependencies failed
                logger.warning(
                    f"Skipping {check.check_id}: dependencies failed: {failed_deps}"
                )
                result.add(
                    CheckResult(
                        check_id=check.check_id,
                        name=check.name,
                        status=CheckStatus.SKIPPED,
                        message=f"Skipped due to failed dependencies: {', '.join(failed_deps)}",
                        category=check.category,
                        severity=check.severity,
                    )
                )
                continue

            # Run the check
            check_result = await self.run_check(check, **kwargs)
            result.add(check_result)

            # Track completion (even if failed)
            completed_checks.add(check.check_id)

        logger.info(
            f"Diagnostics complete: {result.passed} passed, "
            f"{result.failures} failed, {result.warnings} warnings"
        )

        return result

    def count_checks(self, category: Optional[CheckCategory] = None) -> int:
        """Count registered checks.

        Args:
            category: Count checks in specific category (None = all)

        Returns:
            Number of checks
        """
        if category:
            return len(self._categories.get(category, []))
        return len(self._checks)


# Global registry instance
_global_registry: Optional[DiagnosticRegistry] = None


def get_registry() -> DiagnosticRegistry:
    """Get the global diagnostic registry.

    Returns:
        Global DiagnosticRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = DiagnosticRegistry()
    return _global_registry
