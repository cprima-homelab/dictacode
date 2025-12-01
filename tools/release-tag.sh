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

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    cat <<EOF
Usage: $(basename "$0") <component|--all> [options]

Components:
  stt     Tag dictacode-stt
  hid     Tag dictacode-hid
  core    Tag dictacode-core
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

    if [[ "$component" == "core" ]]; then
        grep -Po '(?<=^Version: )[^\s]+' "$REPO_ROOT/ops/packaging/debian/dictacode-core/DEBIAN/control"
    else
        local pkg_dir="$REPO_ROOT/apps/$component"
        if [[ -f "$pkg_dir/pyproject.toml" ]]; then
            grep -Po '(?<=version = ")[^"]+' "$pkg_dir/pyproject.toml"
        elif [[ -f "$pkg_dir/package.json" ]]; then
            grep -Po '(?<="version": ")[^"]+' "$pkg_dir/package.json"
        fi
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

    echo -e "${YELLOW}Creating tag: $tag${NC}"

    if [[ "$dry_run" == "false" ]]; then
        # Check if tag exists
        if git rev-parse "$tag" >/dev/null 2>&1; then
            echo -e "${RED}⚠ Tag $tag already exists, skipping${NC}"
            return
        fi

        # Create annotated tag
        local msg="${message:-Release $component v$version}"
        git tag -a "$tag" -m "$msg"
        echo -e "${GREEN}✓ Created tag: $tag${NC}"

        if [[ "$push" == "true" ]]; then
            git push origin "$tag"
            echo -e "${GREEN}✓ Pushed tag: $tag${NC}"
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
        stt|hid|core)
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
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

if [[ "$TAG_ALL" == "true" ]]; then
    COMPONENTS=(stt hid core)
fi

[[ ${#COMPONENTS[@]} -eq 0 ]] && usage

echo -e "${GREEN}=== Git Tagging ===${NC}"

for component in "${COMPONENTS[@]}"; do
    create_tag "$component" "$PUSH" "$DRY_RUN" "$MESSAGE"
done

echo -e "${GREEN}Done!${NC}"
