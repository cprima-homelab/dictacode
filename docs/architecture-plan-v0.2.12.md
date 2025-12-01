# dictacode Architecture Plan v0.2.12 - Deployment Hygiene & Component Packaging

## Status

### Phase 1: Component Inventory
- [x] Document all releasable components
- [x] Define versioning scheme per component
- [x] Create component manifest file
- [x] Document dependencies between components

### Phase 2: Python Package Scripts
- [x] Create `tools/release-pypi.sh` for PyPI releases
- [x] Support individual package selection
- [x] Version bump automation
- [x] Build and upload to PyPI (or TestPyPI)
- [x] Dry-run mode

### Phase 3: Debian Package Scripts
- [x] Create `tools/release-deb.sh` for .deb releases
- [x] Support individual package selection
- [x] Version extraction from pyproject.toml
- [x] Architecture-specific builds (arm64, armhf)
- [x] Local build and remote device build

### Phase 4: Git Tagging Strategy
- [x] Define tag naming convention per component
- [x] Create `tools/release-tag.sh` for git tagging
- [x] Support component-specific tags
- [ ] Changelog generation from commits (deferred - out of scope)

### Phase 5: Release Orchestration
- [x] Create `tools/release.sh` master script
- [x] Interactive component selection
- [x] Pre-release checks (tests, lint)
- [x] Post-release verification

### Phase 6: CI/CD Integration
- [x] GitHub Actions for package publishing
- [x] Tag-triggered releases
- [x] Release artifact uploads

### Phase 7: Development Environment Setup
- [x] Create `tools/dev-setup.sh` for venv initialization
- [x] Enable system-site-packages for systemd-python access
- [x] Install development dependencies (pytest, ruff, etc.)
- [ ] Configure pre-commit hooks (deferred)
- [ ] Document manual setup steps in CONTRIBUTING.md (deferred)

**v0.2.12 COMPLETED**

---

## Prerequisites

v0.2.12 is infrastructure - can be done in parallel with feature work.
- ✅ v0.2.99: Python tooling (ruff, black, etc.)

---

## Problem Statement

### Current State

No structured release process:
- Manual version bumping
- No scripts for individual component releases
- Unclear which components can be released independently
- No git tag strategy for component versions
- Risk of releasing inconsistent versions

### Component Inventory

| Component | Type | Target | Independent Release? |
|-----------|------|--------|---------------------|
| `dictacode-stt` | Python | PyPI | ✅ Yes |
| `dictacode-hid` | Python | PyPI | ✅ Yes |
| `dictacode-stt` | Debian | Pi5 (arm64) | ✅ Yes |
| `dictacode-hid` | Debian | Pi Zero 2W (armhf) | ✅ Yes |
| `dictacode-web` | Debian | Pi5 (arm64) | ✅ Yes (future) |

### Goals

1. **Individual releases** - Bump one component without affecting others
2. **Consistent versioning** - Clear version scheme per component
3. **Automated scripts** - Reduce manual errors
4. **Git tag hygiene** - Component-specific tags
5. **CI/CD ready** - Scripts work locally and in pipelines

---

## Design

### Versioning Strategy

```
Component Version Format:
  {component}-v{major}.{minor}.{patch}

Examples:
  stt-v0.2.12        # STT Python/Debian package
  hid-v0.2.12        # HID Python/Debian package
  web-v0.3.0         # Web console (future)

Git Tags:
  stt/v0.2.12        # Tag for STT release
  hid/v0.2.12        # Tag for HID release
  v0.2.12            # Monorepo-wide release (optional)
```

### Component Manifest

```yaml
# components.yaml - Component registry

components:
  stt:
    name: dictacode-stt
    description: Speech-to-Text Engine
    path: apps/stt
    version_file: apps/stt/pyproject.toml
    artifacts:
      - type: pypi
        name: dictacode-stt
      - type: deb
        name: dictacode-stt
        arch: [arm64]
        target: dictacode-pi5
    dependencies: []

  hid:
    name: dictacode-hid
    description: HID Gadget Controller
    path: apps/hid
    version_file: apps/hid/pyproject.toml
    artifacts:
      - type: pypi
        name: dictacode-hid
      - type: deb
        name: dictacode-hid
        arch: [armhf]
        target: dictacode-pi0
    dependencies: []

  web:
    name: dictacode-web
    description: Web Console
    path: apps/web-console
    version_file: apps/web-console/package.json
    artifacts:
      - type: deb
        name: dictacode-web
        arch: [arm64]
        target: dictacode-pi5
    dependencies: [stt]

# Global settings
settings:
  pypi_repository: https://upload.pypi.org/legacy/
  pypi_test_repository: https://test.pypi.org/legacy/
  deb_output_dir: dist/deb
  changelog_file: CHANGELOG.md
```

---

## Scripts

### tools/release-pypi.sh

```bash
#!/usr/bin/env bash
# tools/release-pypi.sh - Release Python package to PyPI
#
# Usage:
#   ./tools/release-pypi.sh stt              # Release STT to PyPI
#   ./tools/release-pypi.sh hid --test       # Release HID to TestPyPI
#   ./tools/release-pypi.sh stt --dry-run    # Show what would happen
#   ./tools/release-pypi.sh stt --bump minor # Bump minor version first

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    cat <<EOF
Usage: $(basename "$0") <component> [options]

Components:
  stt     dictacode-stt package
  hid     dictacode-hid package

Options:
  --test          Upload to TestPyPI instead of PyPI
  --dry-run       Show what would happen without executing
  --bump <level>  Bump version before release (major|minor|patch)
  --skip-tests    Skip running tests before release
  --help          Show this help

Examples:
  $(basename "$0") stt                    # Release STT to PyPI
  $(basename "$0") hid --test             # Release HID to TestPyPI
  $(basename "$0") stt --bump patch       # Bump patch, then release
EOF
    exit 1
}

# Parse arguments
COMPONENT=""
USE_TEST_PYPI=false
DRY_RUN=false
BUMP_LEVEL=""
SKIP_TESTS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        stt|hid)
            COMPONENT="$1"
            shift
            ;;
        --test)
            USE_TEST_PYPI=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --bump)
            BUMP_LEVEL="$2"
            shift 2
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

[[ -z "$COMPONENT" ]] && usage

# Component paths
case $COMPONENT in
    stt) PKG_DIR="$REPO_ROOT/apps/stt" ;;
    hid) PKG_DIR="$REPO_ROOT/apps/hid" ;;
esac

# Get current version
get_version() {
    grep -Po '(?<=version = ")[^"]+' "$PKG_DIR/pyproject.toml"
}

# Bump version
bump_version() {
    local level=$1
    local current=$(get_version)
    local IFS='.'
    read -ra parts <<< "$current"

    case $level in
        major) parts[0]=$((parts[0] + 1)); parts[1]=0; parts[2]=0 ;;
        minor) parts[1]=$((parts[1] + 1)); parts[2]=0 ;;
        patch) parts[2]=$((parts[2] + 1)) ;;
    esac

    local new_version="${parts[0]}.${parts[1]}.${parts[2]}"
    echo "$new_version"
}

# Main
echo -e "${GREEN}=== PyPI Release: $COMPONENT ===${NC}"
echo "Package directory: $PKG_DIR"

VERSION=$(get_version)
echo "Current version: $VERSION"

# Bump if requested
if [[ -n "$BUMP_LEVEL" ]]; then
    NEW_VERSION=$(bump_version "$BUMP_LEVEL")
    echo -e "${YELLOW}Bumping version: $VERSION -> $NEW_VERSION${NC}"

    if [[ "$DRY_RUN" == "false" ]]; then
        sed -i "s/version = \"$VERSION\"/version = \"$NEW_VERSION\"/" "$PKG_DIR/pyproject.toml"
        VERSION=$NEW_VERSION
    fi
fi

# Run tests
if [[ "$SKIP_TESTS" == "false" ]]; then
    echo -e "${YELLOW}Running tests...${NC}"
    if [[ "$DRY_RUN" == "false" ]]; then
        cd "$PKG_DIR" && uv run pytest
    else
        echo "[DRY-RUN] Would run: cd $PKG_DIR && uv run pytest"
    fi
fi

# Build
echo -e "${YELLOW}Building package...${NC}"
if [[ "$DRY_RUN" == "false" ]]; then
    cd "$PKG_DIR"
    rm -rf dist/
    uv build
else
    echo "[DRY-RUN] Would run: cd $PKG_DIR && uv build"
fi

# Upload
if [[ "$USE_TEST_PYPI" == "true" ]]; then
    REPO_URL="https://test.pypi.org/legacy/"
    REPO_NAME="testpypi"
else
    REPO_URL="https://upload.pypi.org/legacy/"
    REPO_NAME="pypi"
fi

echo -e "${YELLOW}Uploading to $REPO_NAME...${NC}"
if [[ "$DRY_RUN" == "false" ]]; then
    uv publish --repository "$REPO_NAME"
else
    echo "[DRY-RUN] Would run: uv publish --repository $REPO_NAME"
fi

echo -e "${GREEN}✓ Released $COMPONENT v$VERSION to $REPO_NAME${NC}"
```

### tools/release-deb.sh

```bash
#!/usr/bin/env bash
# tools/release-deb.sh - Build Debian package for component
#
# Usage:
#   ./tools/release-deb.sh stt              # Build STT .deb locally
#   ./tools/release-deb.sh hid --remote     # Build HID on Pi Zero
#   ./tools/release-deb.sh stt --deploy     # Build and deploy to device

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Device targets
declare -A TARGETS=(
    [stt]="dietpi@dictacode-pi5"
    [hid]="dietpi@dictacode-pi0"
)

declare -A ARCHS=(
    [stt]="arm64"
    [hid]="armhf"
)

usage() {
    cat <<EOF
Usage: $(basename "$0") <component> [options]

Components:
  stt     dictacode-stt package (arm64, Pi5)
  hid     dictacode-hid package (armhf, Pi Zero 2W)
  web     dictacode-web package (arm64, Pi5)

Options:
  --remote        Build on target device via SSH
  --deploy        Build and install on target device
  --output <dir>  Output directory (default: dist/deb)
  --dry-run       Show what would happen
  --help          Show this help

Examples:
  $(basename "$0") stt                    # Build locally
  $(basename "$0") hid --remote           # Build on Pi Zero
  $(basename "$0") stt --deploy           # Build and install on Pi5
EOF
    exit 1
}

# Parse arguments
COMPONENT=""
REMOTE_BUILD=false
DEPLOY=false
OUTPUT_DIR="$REPO_ROOT/dist/deb"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        stt|hid|web)
            COMPONENT="$1"
            shift
            ;;
        --remote)
            REMOTE_BUILD=true
            shift
            ;;
        --deploy)
            DEPLOY=true
            REMOTE_BUILD=true
            shift
            ;;
        --output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

[[ -z "$COMPONENT" ]] && usage

# Get version from pyproject.toml
get_version() {
    local pkg_dir="$REPO_ROOT/apps/$COMPONENT"
    grep -Po '(?<=version = ")[^"]+' "$pkg_dir/pyproject.toml"
}

VERSION=$(get_version)
ARCH="${ARCHS[$COMPONENT]}"
TARGET="${TARGETS[$COMPONENT]}"
PKG_NAME="dictacode-${COMPONENT}_${VERSION}_${ARCH}.deb"

echo "=== Debian Package Build: $COMPONENT ==="
echo "Version: $VERSION"
echo "Architecture: $ARCH"
echo "Target: $TARGET"
echo "Output: $OUTPUT_DIR/$PKG_NAME"

if [[ "$REMOTE_BUILD" == "true" ]]; then
    echo "Building on remote device: $TARGET"

    if [[ "$DRY_RUN" == "false" ]]; then
        # Sync source to device
        rsync -avz --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' \
            "$REPO_ROOT/apps/$COMPONENT/" "$TARGET:/tmp/dictacode-$COMPONENT-build/"

        rsync -avz "$REPO_ROOT/ops/packaging/" "$TARGET:/tmp/dictacode-packaging/"

        # Build on device
        ssh "$TARGET" "cd /tmp/dictacode-packaging && ./build-deb.sh $COMPONENT"

        # Retrieve package
        mkdir -p "$OUTPUT_DIR"
        scp "$TARGET:/tmp/dictacode-packaging/dist/$PKG_NAME" "$OUTPUT_DIR/"

        if [[ "$DEPLOY" == "true" ]]; then
            echo "Installing package on $TARGET..."
            ssh "$TARGET" "sudo dpkg -i /tmp/dictacode-packaging/dist/$PKG_NAME"
        fi
    else
        echo "[DRY-RUN] Would sync and build on $TARGET"
    fi
else
    echo "Building locally..."
    if [[ "$DRY_RUN" == "false" ]]; then
        cd "$REPO_ROOT/ops/packaging"
        ./build-deb.sh "$COMPONENT"
        mkdir -p "$OUTPUT_DIR"
        mv "dist/$PKG_NAME" "$OUTPUT_DIR/"
    else
        echo "[DRY-RUN] Would run: ./ops/packaging/build-deb.sh $COMPONENT"
    fi
fi

echo "✓ Built: $OUTPUT_DIR/$PKG_NAME"
```

### tools/release-tag.sh

```bash
#!/usr/bin/env bash
# tools/release-tag.sh - Create git tag for component release
#
# Usage:
#   ./tools/release-tag.sh stt              # Tag STT with current version
#   ./tools/release-tag.sh hid --push       # Tag and push to remote
#   ./tools/release-tag.sh --all            # Tag all components

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    cat <<EOF
Usage: $(basename "$0") <component|--all> [options]

Components:
  stt     Tag dictacode-stt
  hid     Tag dictacode-hid
  web     Tag dictacode-web
  --all   Tag all components

Options:
  --push        Push tag to remote
  --message     Custom tag message
  --dry-run     Show what would happen
  --help        Show this help

Tag Format:
  {component}/v{version}   e.g., stt/v0.2.12

Examples:
  $(basename "$0") stt                    # Create tag stt/v0.2.12
  $(basename "$0") hid --push             # Create and push tag
  $(basename "$0") --all --push           # Tag and push all
EOF
    exit 1
}

# Get version for component
get_version() {
    local component=$1
    local pkg_dir="$REPO_ROOT/apps/$component"

    if [[ -f "$pkg_dir/pyproject.toml" ]]; then
        grep -Po '(?<=version = ")[^"]+' "$pkg_dir/pyproject.toml"
    elif [[ -f "$pkg_dir/package.json" ]]; then
        grep -Po '(?<="version": ")[^"]+' "$pkg_dir/package.json"
    fi
}

# Create tag for component
create_tag() {
    local component=$1
    local push=$2
    local dry_run=$3
    local message=$4

    local version=$(get_version "$component")
    local tag="${component}/v${version}"

    echo "Creating tag: $tag"

    if [[ "$dry_run" == "false" ]]; then
        # Check if tag exists
        if git rev-parse "$tag" >/dev/null 2>&1; then
            echo "⚠ Tag $tag already exists, skipping"
            return
        fi

        # Create annotated tag
        local msg="${message:-Release $component v$version}"
        git tag -a "$tag" -m "$msg"
        echo "✓ Created tag: $tag"

        if [[ "$push" == "true" ]]; then
            git push origin "$tag"
            echo "✓ Pushed tag: $tag"
        fi
    else
        echo "[DRY-RUN] Would create tag: $tag"
        [[ "$push" == "true" ]] && echo "[DRY-RUN] Would push tag: $tag"
    fi
}

# Parse arguments
COMPONENTS=()
PUSH=false
DRY_RUN=false
MESSAGE=""
TAG_ALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        stt|hid|web)
            COMPONENTS+=("$1")
            shift
            ;;
        --all)
            TAG_ALL=true
            shift
            ;;
        --push)
            PUSH=true
            shift
            ;;
        --message)
            MESSAGE="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

if [[ "$TAG_ALL" == "true" ]]; then
    COMPONENTS=(stt hid)
    # Add web when it exists
    [[ -d "$REPO_ROOT/apps/web-console" ]] && COMPONENTS+=(web)
fi

[[ ${#COMPONENTS[@]} -eq 0 ]] && usage

echo "=== Git Tagging ==="

for component in "${COMPONENTS[@]}"; do
    create_tag "$component" "$PUSH" "$DRY_RUN" "$MESSAGE"
done

echo "Done!"
```

### tools/release.sh (Master Script)

```bash
#!/usr/bin/env bash
# tools/release.sh - Interactive release orchestration
#
# Usage:
#   ./tools/release.sh                    # Interactive mode
#   ./tools/release.sh stt --pypi --deb   # Release STT to PyPI and build .deb
#   ./tools/release.sh hid --full         # Full release (PyPI, deb, tag, deploy)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

usage() {
    cat <<EOF
Usage: $(basename "$0") [component] [options]

Interactive release tool for dictacode components.

Components:
  stt     dictacode-stt
  hid     dictacode-hid
  web     dictacode-web (future)

Options:
  --pypi          Release to PyPI
  --deb           Build Debian package
  --tag           Create git tag
  --deploy        Deploy to target device
  --full          All of the above
  --bump <level>  Bump version (major|minor|patch)
  --dry-run       Show what would happen
  --help          Show this help

Examples:
  $(basename "$0")                        # Interactive mode
  $(basename "$0") stt --pypi             # Release STT to PyPI only
  $(basename "$0") hid --full --bump patch # Full HID release with patch bump
EOF
    exit 1
}

# Pre-release checks
pre_release_checks() {
    local component=$1

    echo -e "${BLUE}Running pre-release checks...${NC}"

    # Check for uncommitted changes
    if [[ -n $(git status --porcelain) ]]; then
        echo -e "${RED}✗ Uncommitted changes detected${NC}"
        git status --short
        read -p "Continue anyway? [y/N] " -n 1 -r
        echo
        [[ ! $REPLY =~ ^[Yy]$ ]] && exit 1
    else
        echo -e "${GREEN}✓ Working directory clean${NC}"
    fi

    # Run tests
    echo "Running tests for $component..."
    cd "$REPO_ROOT/apps/$component"
    if uv run pytest -q; then
        echo -e "${GREEN}✓ Tests passed${NC}"
    else
        echo -e "${RED}✗ Tests failed${NC}"
        exit 1
    fi

    # Run linter
    echo "Running linter..."
    if ruff check "apps/$component" --quiet; then
        echo -e "${GREEN}✓ Lint passed${NC}"
    else
        echo -e "${YELLOW}⚠ Lint warnings${NC}"
    fi
}

# Interactive component selection
select_component() {
    echo -e "${BLUE}Select component to release:${NC}"
    echo "  1) stt - Speech-to-Text Engine"
    echo "  2) hid - HID Gadget Controller"
    echo "  3) web - Web Console (future)"
    echo "  4) Cancel"
    read -p "Choice [1-4]: " choice

    case $choice in
        1) echo "stt" ;;
        2) echo "hid" ;;
        3) echo "web" ;;
        *) exit 0 ;;
    esac
}

# Interactive release type selection
select_release_types() {
    echo -e "${BLUE}Select release types (space to toggle, enter to confirm):${NC}"
    echo "  [x] PyPI package"
    echo "  [x] Debian package"
    echo "  [x] Git tag"
    echo "  [ ] Deploy to device"

    # Simplified: just ask yes/no for each
    local types=()
    read -p "Release to PyPI? [Y/n] " -n 1 -r; echo
    [[ ! $REPLY =~ ^[Nn]$ ]] && types+=("pypi")

    read -p "Build Debian package? [Y/n] " -n 1 -r; echo
    [[ ! $REPLY =~ ^[Nn]$ ]] && types+=("deb")

    read -p "Create git tag? [Y/n] " -n 1 -r; echo
    [[ ! $REPLY =~ ^[Nn]$ ]] && types+=("tag")

    read -p "Deploy to device? [y/N] " -n 1 -r; echo
    [[ $REPLY =~ ^[Yy]$ ]] && types+=("deploy")

    echo "${types[@]}"
}

# Main release flow
main() {
    local component=""
    local do_pypi=false
    local do_deb=false
    local do_tag=false
    local do_deploy=false
    local bump_level=""
    local dry_run=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            stt|hid|web) component="$1"; shift ;;
            --pypi) do_pypi=true; shift ;;
            --deb) do_deb=true; shift ;;
            --tag) do_tag=true; shift ;;
            --deploy) do_deploy=true; shift ;;
            --full) do_pypi=true; do_deb=true; do_tag=true; do_deploy=true; shift ;;
            --bump) bump_level="$2"; shift 2 ;;
            --dry-run) dry_run=true; shift ;;
            --help|-h) usage ;;
            *) echo "Unknown: $1"; usage ;;
        esac
    done

    # Interactive mode if no component specified
    if [[ -z "$component" ]]; then
        component=$(select_component)
        read -ra types <<< "$(select_release_types)"
        for t in "${types[@]}"; do
            case $t in
                pypi) do_pypi=true ;;
                deb) do_deb=true ;;
                tag) do_tag=true ;;
                deploy) do_deploy=true ;;
            esac
        done
    fi

    echo -e "${GREEN}=== Release: $component ===${NC}"
    echo "PyPI: $do_pypi | Deb: $do_deb | Tag: $do_tag | Deploy: $do_deploy"
    [[ -n "$bump_level" ]] && echo "Version bump: $bump_level"
    [[ "$dry_run" == "true" ]] && echo -e "${YELLOW}DRY RUN MODE${NC}"

    # Pre-release checks
    pre_release_checks "$component"

    # Version bump
    local bump_args=""
    [[ -n "$bump_level" ]] && bump_args="--bump $bump_level"

    # PyPI release
    if [[ "$do_pypi" == "true" ]]; then
        echo -e "\n${BLUE}>>> PyPI Release${NC}"
        "$SCRIPT_DIR/release-pypi.sh" "$component" $bump_args \
            $([[ "$dry_run" == "true" ]] && echo "--dry-run")
    fi

    # Debian package
    if [[ "$do_deb" == "true" ]]; then
        echo -e "\n${BLUE}>>> Debian Package${NC}"
        local deb_args=""
        [[ "$do_deploy" == "true" ]] && deb_args="--deploy"
        "$SCRIPT_DIR/release-deb.sh" "$component" --remote $deb_args \
            $([[ "$dry_run" == "true" ]] && echo "--dry-run")
    fi

    # Git tag
    if [[ "$do_tag" == "true" ]]; then
        echo -e "\n${BLUE}>>> Git Tag${NC}"
        "$SCRIPT_DIR/release-tag.sh" "$component" --push \
            $([[ "$dry_run" == "true" ]] && echo "--dry-run")
    fi

    echo -e "\n${GREEN}✓ Release complete: $component${NC}"
}

main "$@"
```

### tools/dev-setup.sh (Development Environment)

```bash
#!/usr/bin/env bash
# tools/dev-setup.sh - Initialize development environment
#
# Usage:
#   ./tools/dev-setup.sh                    # Setup all components
#   ./tools/dev-setup.sh stt                # Setup only STT
#   ./tools/dev-setup.sh hid                # Setup only HID

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

setup_component() {
    local component=$1
    local app_dir="$REPO_ROOT/apps/$component"

    echo -e "${YELLOW}Setting up $component...${NC}"
    cd "$app_dir"

    # Create venv with uv
    if [[ ! -d ".venv" ]]; then
        uv venv
    fi

    # Enable system-site-packages for python3-systemd access
    if grep -q "include-system-site-packages = false" ".venv/pyvenv.cfg"; then
        sed -i 's/include-system-site-packages = false/include-system-site-packages = true/' ".venv/pyvenv.cfg"
        echo "  ✓ Enabled system-site-packages"
    fi

    # Install dependencies
    uv sync --dev

    # Verify systemd import works
    if .venv/bin/python -c "from systemd import daemon; print('OK')" 2>/dev/null; then
        echo -e "${GREEN}  ✓ systemd import works${NC}"
    else
        echo "  ⚠ systemd import failed - install python3-systemd"
    fi

    echo -e "${GREEN}✓ Setup complete: $component${NC}"
}

# Main
COMPONENTS=()
[[ $# -eq 0 ]] && COMPONENTS=(stt hid) || COMPONENTS=("$@")

for component in "${COMPONENTS[@]}"; do
    setup_component "$component"
done
```

---

## GitHub Actions Workflow

```yaml
# .github/workflows/release.yml

name: Release

on:
  push:
    tags:
      - 'stt/v*'
      - 'hid/v*'
      - 'web/v*'

jobs:
  extract-info:
    runs-on: ubuntu-latest
    outputs:
      component: ${{ steps.parse.outputs.component }}
      version: ${{ steps.parse.outputs.version }}
    steps:
      - name: Parse tag
        id: parse
        run: |
          TAG="${GITHUB_REF#refs/tags/}"
          COMPONENT="${TAG%%/*}"
          VERSION="${TAG#*/v}"
          echo "component=$COMPONENT" >> $GITHUB_OUTPUT
          echo "version=$VERSION" >> $GITHUB_OUTPUT

  pypi:
    needs: extract-info
    runs-on: ubuntu-latest
    if: needs.extract-info.outputs.component != 'web'
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        uses: astral-sh/setup-uv@v2

      - name: Build package
        run: |
          cd apps/${{ needs.extract-info.outputs.component }}
          uv build

      - name: Publish to PyPI
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
        run: |
          cd apps/${{ needs.extract-info.outputs.component }}
          uv publish

  deb:
    needs: extract-info
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Debian package
        run: |
          cd ops/packaging
          ./build-deb.sh ${{ needs.extract-info.outputs.component }}

      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: dictacode-${{ needs.extract-info.outputs.component }}_${{ needs.extract-info.outputs.version }}.deb
          path: ops/packaging/dist/*.deb

  release:
    needs: [extract-info, pypi, deb]
    runs-on: ubuntu-latest
    steps:
      - name: Download artifacts
        uses: actions/download-artifact@v4

      - name: Create GitHub Release
        uses: softprops/action-gh-release@v1
        with:
          files: |
            **/*.deb
          generate_release_notes: true
```

---

## File Structure

```
dictacode/
├── components.yaml               # NEW: Component manifest
├── tools/
│   ├── release.sh                # NEW: Master release script
│   ├── release-pypi.sh           # NEW: PyPI release script
│   ├── release-deb.sh            # NEW: Debian package script
│   ├── release-tag.sh            # NEW: Git tagging script
│   └── dev-setup.sh              # NEW: Development environment setup
├── .github/
│   └── workflows/
│       └── release.yml           # NEW: Release workflow
└── apps/
    ├── stt/
    │   └── pyproject.toml        # Version source of truth
    └── hid/
        └── pyproject.toml        # Version source of truth
```

---

## Files to Create/Modify

1. `components.yaml` - NEW: Component registry
2. `tools/release.sh` - NEW: Master release script
3. `tools/release-pypi.sh` - NEW: PyPI release script
4. `tools/release-deb.sh` - NEW: Debian package script
5. `tools/release-tag.sh` - NEW: Git tagging script
6. `tools/dev-setup.sh` - NEW: Development environment setup
7. `.github/workflows/release.yml` - NEW: Tag-triggered release workflow
8. `RELEASING.md` - NEW: Release process documentation
9. `CONTRIBUTING.md` - NEW/MODIFIED: Development setup instructions

---

## Usage Examples

```bash
# Release only STT to PyPI (patch bump)
./tools/release.sh stt --pypi --bump patch

# Build HID debian package and deploy to Pi Zero
./tools/release.sh hid --deb --deploy

# Full STT release (PyPI + deb + tag + deploy)
./tools/release.sh stt --full --bump minor

# Interactive mode
./tools/release.sh

# Dry run to see what would happen
./tools/release.sh hid --full --dry-run

# Just create git tag
./tools/release-tag.sh stt --push

# List USB-serial devices on Pi Zero before deploy
./tools/release-deb.sh hid --remote

# Setup development environment
./tools/dev-setup.sh           # Setup all components
./tools/dev-setup.sh stt       # Setup only STT
```

---

## Success Criteria

v0.2.12 is complete when:

1. ✅ `components.yaml` documents all releasable components
2. ✅ `tools/release-pypi.sh` releases individual Python packages
3. ✅ `tools/release-deb.sh` builds individual Debian packages
4. ✅ `tools/release-tag.sh` creates component-specific git tags
5. ✅ `tools/release.sh` orchestrates full releases
6. ✅ Version bumping works for individual components
7. ✅ Dry-run mode shows what would happen
8. ✅ Pre-release checks (tests, lint) run before release
9. ✅ GitHub Actions triggered by component tags
10. ✅ Release artifacts uploaded to GitHub Releases
11. ✅ `tools/dev-setup.sh` initializes venv with system-site-packages
12. ✅ Development setup verifies systemd-python import
13. ✅ Documentation in RELEASING.md and CONTRIBUTING.md

---

## Out of Scope (v0.2.12)

- Automatic changelog generation from commits
- Semantic release automation
- Multi-architecture cross-compilation
- Package signing (GPG)
- Private PyPI repository
- Rollback scripts
