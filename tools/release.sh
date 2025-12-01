#!/usr/bin/env bash
# tools/release.sh - Master release orchestration script
#
# Usage:
#   ./tools/release.sh stt              # Interactive release for STT
#   ./tools/release.sh stt --full       # Full release (PyPI + Deb + Tag + Push)
#   ./tools/release.sh --all --full     # Full release for all components
#   ./tools/release.sh hid --bump patch # Bump version and release

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
Usage: $(basename "$0") <component|--all> [options]

Components:
  stt     Release dictacode-stt
  hid     Release dictacode-hid
  core    Release dictacode-core
  --all   Release all components

Options:
  --full            Full release (PyPI + Deb + Tag + Push)
  --pypi            Release to PyPI only
  --deb             Build Debian package only
  --tag             Create git tag only
  --bump <level>    Bump version first (major|minor|patch)
  --test            Use TestPyPI instead of PyPI
  --remote          Build Debian packages on target devices
  --deploy          Deploy Debian packages after building
  --dry-run         Show what would happen
  --skip-tests      Skip test execution
  --help            Show this help

Examples:
  $(basename "$0") stt --full              # Full STT release
  $(basename "$0") hid --bump patch --full # Bump patch & full release
  $(basename "$0") --all --pypi --tag      # PyPI + tag for all
  $(basename "$0") stt --deb --remote      # Build STT deb on Pi5

Release Workflow:
  1. Bump version (if --bump specified)
  2. Run tests (unless --skip-tests)
  3. Build & upload to PyPI (if --pypi or --full)
  4. Build Debian package (if --deb or --full)
  5. Create git tag (if --tag or --full)
  6. Push tag to remote (if --full)
EOF
    exit 1
}

# Check for uncommitted changes
check_git_clean() {
    if [[ -n "$(git status --porcelain)" ]]; then
        echo -e "${RED}⚠ Working directory has uncommitted changes${NC}"
        echo "Please commit or stash changes before releasing"
        return 1
    fi
    return 0
}

# Run pre-release checks
pre_release_check() {
    local component=$1
    local skip_tests=$2

    echo -e "${BLUE}=== Pre-release Checks: $component ===${NC}"

    # Check git status
    if ! check_git_clean; then
        return 1
    fi

    # Run tests for Python components
    if [[ "$component" != "core" && "$skip_tests" == "false" ]]; then
        echo -e "${YELLOW}Running tests for $component...${NC}"
        local pkg_dir="$REPO_ROOT/apps/$component"

        if [[ -d "$pkg_dir" ]]; then
            cd "$pkg_dir"
            if ! uv run pytest; then
                echo -e "${RED}✗ Tests failed for $component${NC}"
                return 1
            fi
            echo -e "${GREEN}✓ Tests passed${NC}"
            cd "$REPO_ROOT"
        fi
    fi

    return 0
}

# Get component version
get_version() {
    local component=$1

    if [[ "$component" == "core" ]]; then
        grep -Po '(?<=^Version: )[^\s]+' "$REPO_ROOT/ops/packaging/debian/dictacode-core/DEBIAN/control"
    else
        local pkg_dir="$REPO_ROOT/apps/$component"
        grep -Po '(?<=version = ")[^"]+' "$pkg_dir/pyproject.toml"
    fi
}

# Release a single component
release_component() {
    local component=$1
    local do_pypi=$2
    local do_deb=$3
    local do_tag=$4
    local do_push=$5
    local use_test_pypi=$6
    local remote_build=$7
    local deploy=$8
    local dry_run=$9
    local bump_level=${10}
    local skip_tests=${11}

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Releasing: $component${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""

    # Pre-release checks
    if [[ "$dry_run" == "false" ]]; then
        if ! pre_release_check "$component" "$skip_tests"; then
            echo -e "${RED}✗ Pre-release checks failed for $component${NC}"
            return 1
        fi
    fi

    # Version bumping
    if [[ -n "$bump_level" ]]; then
        echo -e "${YELLOW}Step 1: Bumping $bump_level version...${NC}"
        local bump_args="$component --bump $bump_level"
        [[ "$dry_run" == "true" ]] && bump_args="$bump_args --dry-run"

        if [[ "$component" != "core" ]]; then
            "$SCRIPT_DIR/release-pypi.sh" $bump_args --skip-tests
        else
            echo -e "${YELLOW}⚠ Version bumping for core not implemented yet${NC}"
        fi
    fi

    local version=$(get_version "$component")
    echo -e "${BLUE}Version: $version${NC}"

    # PyPI release
    if [[ "$do_pypi" == "true" && "$component" != "core" ]]; then
        echo -e "${YELLOW}Step 2: Releasing to PyPI...${NC}"
        local pypi_args="$component"
        [[ "$use_test_pypi" == "true" ]] && pypi_args="$pypi_args --test"
        [[ "$dry_run" == "true" ]] && pypi_args="$pypi_args --dry-run"
        [[ "$skip_tests" == "true" ]] && pypi_args="$pypi_args --skip-tests"

        "$SCRIPT_DIR/release-pypi.sh" $pypi_args
    fi

    # Debian package
    if [[ "$do_deb" == "true" ]]; then
        echo -e "${YELLOW}Step 3: Building Debian package...${NC}"
        local deb_args="$component"
        [[ "$remote_build" == "true" ]] && deb_args="$deb_args --remote"
        [[ "$deploy" == "true" ]] && deb_args="$deb_args --deploy"
        [[ "$dry_run" == "true" ]] && deb_args="$deb_args --dry-run"

        "$SCRIPT_DIR/release-deb.sh" $deb_args
    fi

    # Git tag
    if [[ "$do_tag" == "true" ]]; then
        echo -e "${YELLOW}Step 4: Creating git tag...${NC}"
        local tag_args="$component"
        [[ "$do_push" == "true" ]] && tag_args="$tag_args --push"
        [[ "$dry_run" == "true" ]] && tag_args="$tag_args --dry-run"

        "$SCRIPT_DIR/release-tag.sh" $tag_args
    fi

    echo -e "${GREEN}✓ Release complete for $component v$version${NC}"
}

# Parse arguments
COMPONENTS=()
DO_PYPI=false
DO_DEB=false
DO_TAG=false
DO_PUSH=false
USE_TEST_PYPI=false
REMOTE_BUILD=false
DEPLOY=false
DRY_RUN=false
BUMP_LEVEL=""
SKIP_TESTS=false
RELEASE_ALL=false

while [[ $# -gt 0 ]]; do
    case $1 in
        stt|hid|core)
            COMPONENTS+=("$1")
            shift
            ;;
        --all)
            RELEASE_ALL=true
            shift
            ;;
        --full)
            DO_PYPI=true
            DO_DEB=true
            DO_TAG=true
            DO_PUSH=true
            shift
            ;;
        --pypi)
            DO_PYPI=true
            shift
            ;;
        --deb)
            DO_DEB=true
            shift
            ;;
        --tag)
            DO_TAG=true
            shift
            ;;
        --test)
            USE_TEST_PYPI=true
            shift
            ;;
        --remote)
            REMOTE_BUILD=true
            shift
            ;;
        --deploy)
            DEPLOY=true
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

# Validate bump level
if [[ -n "$BUMP_LEVEL" && ! "$BUMP_LEVEL" =~ ^(major|minor|patch)$ ]]; then
    echo -e "${RED}Invalid bump level: $BUMP_LEVEL${NC}"
    echo "Must be: major, minor, or patch"
    exit 1
fi

# Set components list
if [[ "$RELEASE_ALL" == "true" ]]; then
    COMPONENTS=(stt hid core)
fi

[[ ${#COMPONENTS[@]} -eq 0 ]] && usage

# Default to --full if no specific action specified
if [[ "$DO_PYPI" == "false" && "$DO_DEB" == "false" && "$DO_TAG" == "false" ]]; then
    echo -e "${YELLOW}No specific action specified, assuming --full${NC}"
    DO_PYPI=true
    DO_DEB=true
    DO_TAG=true
    DO_PUSH=true
fi

# Show release plan
echo -e "${BLUE}=== Release Plan ===${NC}"
echo "Components: ${COMPONENTS[*]}"
echo "Actions:"
[[ -n "$BUMP_LEVEL" ]] && echo "  - Bump $BUMP_LEVEL version"
[[ "$DO_PYPI" == "true" ]] && echo "  - Release to $([ "$USE_TEST_PYPI" == "true" ] && echo "TestPyPI" || echo "PyPI")"
[[ "$DO_DEB" == "true" ]] && echo "  - Build Debian package $([ "$REMOTE_BUILD" == "true" ] && echo "(remote)" || echo "(local)")"
[[ "$DO_TAG" == "true" ]] && echo "  - Create git tag $([ "$DO_PUSH" == "true" ] && echo "and push" || echo "")"
[[ "$DRY_RUN" == "true" ]] && echo -e "${YELLOW}  [DRY RUN MODE]${NC}"
echo ""

# Confirm unless dry-run
if [[ "$DRY_RUN" == "false" ]]; then
    read -p "Continue with release? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Release cancelled"
        exit 0
    fi
fi

# Release each component
for component in "${COMPONENTS[@]}"; do
    release_component "$component" "$DO_PYPI" "$DO_DEB" "$DO_TAG" "$DO_PUSH" \
        "$USE_TEST_PYPI" "$REMOTE_BUILD" "$DEPLOY" "$DRY_RUN" "$BUMP_LEVEL" "$SKIP_TESTS"
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  All releases complete!${NC}"
echo -e "${GREEN}========================================${NC}"
