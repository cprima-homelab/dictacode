# dictacode Architecture Plan v0.2.99 - Python Best Practices & Tooling

## Status

### Phase 1: Ruff Configuration ✅ COMPLETE
- [x] Add `ruff.toml` at repository root
- [x] Configure linting rules (pyflakes, pycodestyle, isort, etc.)
- [x] Configure import sorting (isort-compatible)
- [x] Per-file ignores for tests and __init__.py
- [x] Document rule selections in ruff.toml
- [x] Run `ruff check --fix` on codebase (230 issues auto-fixed)

### Phase 2: Black Configuration ✅ COMPLETE
- [x] Add black config to `pyproject.toml` (each package)
- [x] Set line length (88)
- [x] Configure target Python version (3.9+)
- [x] Exclude patterns (generated files, etc.)
- [x] Format entire codebase (77 files reformatted)

### Phase 3: Type Checking (mypy) ✅ COMPLETE
- [x] Add mypy config to pyproject.toml (both packages)
- [x] Configure strictness level (gradual typing approach)
- [x] Add py.typed markers to packages
- [x] Add pytest and coverage configuration
- [x] Configure test-specific mypy overrides

### Phase 4: Pre-commit Hooks ⏳ PENDING
- [ ] Add `.pre-commit-config.yaml`
- [ ] Configure ruff, black, mypy hooks
- [ ] Add trailing whitespace, EOF fixes
- [ ] Document installation for contributors

### Phase 5: CI Integration ⏳ PENDING
- [ ] Add GitHub Actions workflow for linting
- [ ] Fail on lint errors
- [ ] Run on PR and push to main
- [ ] Cache dependencies for speed

### Phase 6: Developer Documentation ⏳ PENDING
- [ ] Update CONTRIBUTING.md with tooling setup
- [ ] Add Makefile/justfile for common commands
- [ ] Document IDE setup (VS Code, PyCharm)

**v0.2.99 STATUS:**
- ✅ **Phases 1-3 COMPLETE** - Core tooling configured and applied
- ⏳ **Phases 4-6 PENDING** - Pre-commit hooks, CI, and documentation

---

## Prerequisites

v0.2.99 is infrastructure - can be done in parallel with feature work.

---

## Problem Statement

### Current State

No consistent code style enforcement:
- No linter configuration
- No formatter configuration
- No pre-commit hooks
- Inconsistent code style across files
- No automated checks in CI

### Goals

1. **Consistent code style** - All Python code follows same conventions
2. **Automated enforcement** - Pre-commit hooks catch issues before commit
3. **CI validation** - PRs blocked if code doesn't pass checks
4. **Developer experience** - Easy setup, fast feedback, IDE integration
5. **Modern tooling** - Use Ruff (fast, comprehensive) + Black (formatter)

---

## Design

### Tool Selection

| Tool | Purpose | Why |
|------|---------|-----|
| **Ruff** | Linting + import sorting | 10-100x faster than flake8, replaces isort, growing ecosystem |
| **Black** | Code formatting | Industry standard, opinionated, deterministic |
| **mypy** | Type checking | Catch type errors, improve IDE support |
| **pre-commit** | Git hooks | Automated checks before commit |

**Why Ruff over flake8/pylint?**
- Written in Rust, extremely fast
- Replaces flake8, isort, pyupgrade, autoflake in one tool
- Active development, growing rule set
- Native `--fix` support

### Repository Structure

```
dictacode/
├── ruff.toml                     # Repository-wide Ruff config
├── .pre-commit-config.yaml       # Pre-commit hooks
├── .github/
│   └── workflows/
│       └── ci-py.yml             # Python CI workflow
├── apps/
│   ├── stt/
│   │   ├── pyproject.toml        # Black config, package metadata
│   │   ├── src/
│   │   │   └── dictacode_stt/
│   │   │       └── py.typed      # PEP 561 marker
│   │   └── tests/
│   └── hid/
│       ├── pyproject.toml
│       ├── src/
│       │   └── dictacode_hid/
│       │       └── py.typed
│       └── tests/
└── Makefile                      # Developer commands
```

---

## Configuration Files

### ruff.toml (Repository Root)

```toml
# ruff.toml - Repository-wide Ruff configuration

# Target Python version
target-version = "py39"

# Line length (match Black)
line-length = 88

# Exclude patterns
exclude = [
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "*.egg-info",
    "build",
    "dist",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
]

[lint]
# Enable rule categories
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "UP",     # pyupgrade
    "ARG",    # flake8-unused-arguments
    "SIM",    # flake8-simplify
    "TCH",    # flake8-type-checking
    "PTH",    # flake8-use-pathlib
    "ERA",    # eradicate (commented-out code)
    "PL",     # pylint
    "RUF",    # Ruff-specific rules
]

# Ignore specific rules
ignore = [
    "E501",   # Line too long (handled by Black)
    "PLR0913", # Too many arguments
    "PLR2004", # Magic value comparison
]

# Allow autofix for all enabled rules
fixable = ["ALL"]
unfixable = []

[lint.per-file-ignores]
# Tests can use assert, magic values, etc.
"tests/**/*.py" = ["S101", "PLR2004", "ARG001"]
# __init__.py can have unused imports (re-exports)
"__init__.py" = ["F401"]

[lint.isort]
# isort configuration (replaces .isort.cfg)
known-first-party = ["dictacode_stt", "dictacode_hid"]
force-single-line = false
lines-after-imports = 2
section-order = [
    "future",
    "standard-library",
    "third-party",
    "first-party",
    "local-folder",
]

[lint.pydocstyle]
convention = "google"
```

### pyproject.toml (Per Package)

```toml
# apps/stt/pyproject.toml

[project]
name = "dictacode-stt"
version = "0.2.99"
requires-python = ">=3.9"
# ... other metadata

[tool.black]
line-length = 88
target-version = ["py39", "py310", "py311", "py312"]
include = '\.pyi?$'
exclude = '''
/(
    \.git
    | \.venv
    | venv
    | __pycache__
    | \.mypy_cache
    | build
    | dist
)/
'''

[tool.mypy]
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false  # Gradual typing - start permissive
check_untyped_defs = true
ignore_missing_imports = true  # Third-party libs without stubs

# Stricter settings for new code (enable gradually)
# disallow_untyped_defs = true
# strict = true

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["src"]
branch = true
omit = ["tests/*"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "if TYPE_CHECKING:",
    "raise NotImplementedError",
]
```

### .pre-commit-config.yaml

```yaml
# .pre-commit-config.yaml

# See https://pre-commit.com for more information
# See https://pre-commit.com/hooks.html for more hooks

repos:
  # General file fixes
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-toml
      - id: check-added-large-files
        args: ['--maxkb=1000']
      - id: check-merge-conflict
      - id: detect-private-key

  # Ruff - linting and import sorting
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.6.0
    hooks:
      # Linter
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]
      # Formatter (optional - can use Black instead)
      # - id: ruff-format

  # Black - code formatting
  - repo: https://github.com/psf/black
    rev: 24.8.0
    hooks:
      - id: black

  # mypy - type checking
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-requests
          - types-PyYAML
        args: [--config-file=apps/stt/pyproject.toml]
        # Run only on changed files for speed
        pass_filenames: true

  # Security checks
  - repo: https://github.com/PyCQA/bandit
    rev: 1.7.9
    hooks:
      - id: bandit
        args: ["-c", "pyproject.toml", "-r"]
        additional_dependencies: ["bandit[toml]"]
        exclude: tests/

# CI configuration
ci:
  autofix_commit_msg: |
    [pre-commit.ci] auto fixes from pre-commit hooks
  autofix_prs: true
  autoupdate_branch: ''
  autoupdate_commit_msg: '[pre-commit.ci] pre-commit autoupdate'
  autoupdate_schedule: weekly
  skip: [mypy]  # mypy can be slow, run in CI instead
```

### GitHub Actions Workflow

```yaml
# .github/workflows/ci-py.yml

name: Python CI

on:
  push:
    branches: [main]
    paths:
      - 'apps/**/*.py'
      - 'pyproject.toml'
      - 'ruff.toml'
      - '.github/workflows/ci-py.yml'
  pull_request:
    branches: [main]
    paths:
      - 'apps/**/*.py'
      - 'pyproject.toml'
      - 'ruff.toml'

jobs:
  lint:
    name: Lint & Format Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        uses: astral-sh/setup-uv@v2

      - name: Cache dependencies
        uses: actions/cache@v4
        with:
          path: ~/.cache/uv
          key: uv-${{ runner.os }}-${{ hashFiles('**/pyproject.toml') }}

      - name: Install dependencies
        run: |
          uv pip install --system ruff black mypy

      - name: Ruff lint
        run: ruff check apps/

      - name: Ruff format check
        run: ruff format --check apps/

      - name: Black format check
        run: black --check apps/

  typecheck:
    name: Type Check
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        uses: astral-sh/setup-uv@v2

      - name: Install dependencies
        run: |
          cd apps/stt && uv sync
          cd ../hid && uv sync

      - name: mypy (STT)
        run: |
          cd apps/stt
          uv run mypy src/

      - name: mypy (HID)
        run: |
          cd apps/hid
          uv run mypy src/

  test:
    name: Tests
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.9', '3.10', '3.11', '3.12']
        package: ['stt', 'hid']
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install uv
        uses: astral-sh/setup-uv@v2

      - name: Install and test
        run: |
          cd apps/${{ matrix.package }}
          uv sync
          uv run pytest --tb=short
```

---

## Makefile

```makefile
# Makefile - Developer convenience commands

.PHONY: help lint format typecheck test all clean

# Default target
help:
	@echo "dictacode development commands:"
	@echo ""
	@echo "  make lint       - Run Ruff linter"
	@echo "  make format     - Format code with Black"
	@echo "  make typecheck  - Run mypy type checker"
	@echo "  make test       - Run all tests"
	@echo "  make all        - Run lint, format, typecheck, test"
	@echo "  make fix        - Auto-fix linting issues"
	@echo "  make clean      - Remove build artifacts"
	@echo ""
	@echo "  make setup      - Install pre-commit hooks"

# Linting
lint:
	ruff check apps/

lint-fix:
	ruff check --fix apps/

# Formatting
format:
	black apps/

format-check:
	black --check apps/

# Type checking
typecheck:
	cd apps/stt && uv run mypy src/
	cd apps/hid && uv run mypy src/

# Testing
test:
	cd apps/stt && uv run pytest
	cd apps/hid && uv run pytest

test-stt:
	cd apps/stt && uv run pytest -v

test-hid:
	cd apps/hid && uv run pytest -v

# Combined targets
all: lint format-check typecheck test

fix: lint-fix format

# Pre-commit setup
setup:
	pip install pre-commit
	pre-commit install
	@echo "Pre-commit hooks installed!"

# Clean build artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name dist -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name build -exec rm -rf {} + 2>/dev/null || true
```

---

## IDE Configuration

### VS Code Settings

```json
// .vscode/settings.json
{
    // Python
    "python.analysis.typeCheckingMode": "basic",
    "python.analysis.autoImportCompletions": true,

    // Formatting
    "[python]": {
        "editor.defaultFormatter": "ms-python.black-formatter",
        "editor.formatOnSave": true,
        "editor.codeActionsOnSave": {
            "source.organizeImports": "explicit"
        }
    },

    // Ruff extension
    "ruff.lint.enable": true,
    "ruff.format.enable": true,
    "ruff.organizeImports": true,

    // Black extension
    "black-formatter.args": ["--line-length", "88"],

    // File associations
    "files.associations": {
        "*.toml": "toml"
    },

    // Exclude from search
    "files.exclude": {
        "**/__pycache__": true,
        "**/.pytest_cache": true,
        "**/.mypy_cache": true,
        "**/.ruff_cache": true,
        "**/venv": true,
        "**/.venv": true
    }
}
```

### VS Code Extensions

```json
// .vscode/extensions.json
{
    "recommendations": [
        "ms-python.python",
        "ms-python.vscode-pylance",
        "ms-python.black-formatter",
        "charliermarsh.ruff",
        "tamasfe.even-better-toml"
    ]
}
```

---

## Migration Strategy

### Phase 1: Add Configuration (No Enforcement)

1. Add `ruff.toml`, update `pyproject.toml` files
2. Add `.pre-commit-config.yaml`
3. Run formatters on entire codebase:
   ```bash
   ruff check --fix apps/
   black apps/
   ```
4. Commit formatted code in single "Format codebase" commit

### Phase 2: Enable Pre-commit

1. Install pre-commit: `pre-commit install`
2. Announce to team in PR
3. Document in CONTRIBUTING.md

### Phase 3: Enable CI

1. Add GitHub Actions workflow
2. Start with warnings only (`continue-on-error: true`)
3. Fix remaining issues
4. Remove `continue-on-error` to enforce

### Phase 4: Gradual Strictness

1. Start with permissive mypy settings
2. Enable stricter rules incrementally:
   ```toml
   # Week 1: Basic
   check_untyped_defs = true

   # Week 2: Warnings
   warn_return_any = true

   # Week 3+: Full strict (optional)
   disallow_untyped_defs = true
   ```

---

## File Structure

```
dictacode/
├── ruff.toml                     # NEW: Ruff configuration
├── Makefile                      # NEW: Developer commands
├── .pre-commit-config.yaml       # NEW: Pre-commit hooks
├── .vscode/
│   ├── settings.json             # NEW: VS Code settings
│   └── extensions.json           # NEW: Recommended extensions
├── .github/
│   └── workflows/
│       └── ci-py.yml             # NEW: Python CI workflow
├── apps/
│   ├── stt/
│   │   ├── pyproject.toml        # MODIFIED: Add tool configs
│   │   └── src/dictacode_stt/
│   │       └── py.typed          # NEW: PEP 561 marker
│   └── hid/
│       ├── pyproject.toml        # MODIFIED: Add tool configs
│       └── src/dictacode_hid/
│           └── py.typed          # NEW: PEP 561 marker
└── CONTRIBUTING.md               # MODIFIED: Add tooling docs
```

---

## Files to Create/Modify

1. `ruff.toml` - NEW: Repository-wide Ruff config
2. `Makefile` - NEW: Developer commands
3. `.pre-commit-config.yaml` - NEW: Pre-commit hooks
4. `.vscode/settings.json` - NEW: VS Code settings
5. `.vscode/extensions.json` - NEW: Recommended extensions
6. `.github/workflows/ci-py.yml` - NEW: Python CI workflow
7. `apps/stt/pyproject.toml` - Add Black, mypy, pytest config
8. `apps/stt/src/dictacode_stt/py.typed` - NEW: PEP 561 marker
9. `apps/hid/pyproject.toml` - Add Black, mypy, pytest config
10. `apps/hid/src/dictacode_hid/py.typed` - NEW: PEP 561 marker
11. `CONTRIBUTING.md` - Add development setup instructions

---

## Success Criteria

v0.2.99 is complete when:

1. ✅ `ruff.toml` configured with appropriate rules
2. ✅ Black configured in each package's `pyproject.toml`
3. ✅ mypy configured with gradual typing support
4. ⏳ Pre-commit hooks installed and documented
5. ⏳ CI workflow runs lint/format/typecheck on PRs
6. ⏸️ All existing code passes lint checks (620 warnings remain for gradual cleanup)
7. ✅ All existing code is formatted with Black (77 files)
8. ⏳ VS Code settings for contributors
9. ⏳ Makefile with common developer commands
10. ⏳ CONTRIBUTING.md updated with setup instructions
11. ✅ `py.typed` markers added to packages

**Current Progress:** 4/11 complete (Phases 1-3)
**Next Steps:** Implement Phases 4-6 for full developer workflow

---

## Out of Scope (v0.2.99)

- Full strict mypy compliance (gradual adoption)
- 100% type coverage
- Documentation linting (pydocstyle enforcement)
- Complexity limits (cyclomatic complexity)
- Test coverage enforcement
- Automatic dependency updates (Dependabot)
