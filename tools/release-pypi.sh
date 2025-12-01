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
        # Also update __init__.py
        sed -i "s/__version__ = \"$VERSION\"/__version__ = \"$NEW_VERSION\"/" "$PKG_DIR/src/dictacode_${COMPONENT}/__init__.py"
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

    # Validate checksum for wheels containing compatibility.json
    VALIDATE_SCRIPT="$PROJECT_ROOT/ops/packaging/validate-artifacts.sh"
    if [[ -f "$VALIDATE_SCRIPT" ]]; then
        for wheel in dist/*.whl; do
            if unzip -l "$wheel" 2>/dev/null | grep -q "compatibility.json"; then
                echo -e "${YELLOW}Validating compatibility.json checksum in wheel...${NC}"
                "$VALIDATE_SCRIPT" "$wheel" || {
                    echo -e "${RED}ERROR: Checksum validation failed for $wheel${NC}"
                    exit 1
                }
            fi
        done
    fi
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
