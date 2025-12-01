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
    [stt]="dictacode@dictacode-stt"
    [hid]="dictacode@dictacode-hid"
    [core]="dictacode@dictacode-stt"
)

declare -A ARCHS=(
    [stt]="arm64"
    [hid]="armhf"
    [core]="all"
)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    cat <<EOF
Usage: $(basename "$0") <component> [options]

Components:
  stt     dictacode-stt package (arm64, Pi5)
  hid     dictacode-hid package (armhf, Pi Zero 2W)
  core    dictacode-core package (all architectures)

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
        stt|hid|core)
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
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            ;;
    esac
done

[[ -z "$COMPONENT" ]] && usage

# Get version from pyproject.toml or DEBIAN/control
get_version() {
    if [[ "$COMPONENT" == "core" ]]; then
        grep -Po '(?<=^Version: )[^\s]+' "$REPO_ROOT/ops/packaging/debian/dictacode-core/DEBIAN/control"
    else
        local pkg_dir="$REPO_ROOT/apps/$COMPONENT"
        grep -Po '(?<=version = ")[^"]+' "$pkg_dir/pyproject.toml"
    fi
}

VERSION=$(get_version)
ARCH="${ARCHS[$COMPONENT]}"
TARGET="${TARGETS[$COMPONENT]}"
PKG_NAME="dictacode-${COMPONENT}_${VERSION}_${ARCH}.deb"

echo -e "${GREEN}=== Debian Package Build: $COMPONENT ===${NC}"
echo "Version: $VERSION"
echo "Architecture: $ARCH"
echo "Target: $TARGET"
echo "Output: $OUTPUT_DIR/$PKG_NAME"

if [[ "$REMOTE_BUILD" == "true" ]]; then
    echo -e "${YELLOW}Building on remote device: $TARGET${NC}"

    if [[ "$DRY_RUN" == "false" ]]; then
        # Sync source to device
        echo "Syncing source files..."
        rsync -avz --exclude '__pycache__' --exclude '*.pyc' --exclude '.git' --exclude '.venv' \
            "$REPO_ROOT/" "$TARGET:/tmp/dictacode-build/"

        # Build on device
        echo "Building package on $TARGET..."
        ssh "$TARGET" "cd /tmp/dictacode-build/ops/packaging && ./build-deb.sh $COMPONENT"

        # Retrieve package
        mkdir -p "$OUTPUT_DIR"
        scp "$TARGET:/tmp/dictacode-build/ops/packaging/dist/$PKG_NAME" "$OUTPUT_DIR/"

        if [[ "$DEPLOY" == "true" ]]; then
            echo -e "${YELLOW}Installing package on $TARGET...${NC}"
            ssh "$TARGET" "sudo dpkg -i /tmp/dictacode-build/ops/packaging/dist/$PKG_NAME"
            echo -e "${GREEN}✓ Package installed on $TARGET${NC}"
        fi
    else
        echo "[DRY-RUN] Would sync and build on $TARGET"
    fi
else
    echo -e "${YELLOW}Building locally...${NC}"
    if [[ "$DRY_RUN" == "false" ]]; then
        cd "$REPO_ROOT/ops/packaging"
        ./build-deb.sh "$COMPONENT"
        mkdir -p "$OUTPUT_DIR"
        mv "dist/$PKG_NAME" "$OUTPUT_DIR/" 2>/dev/null || true
    else
        echo "[DRY-RUN] Would run: ./ops/packaging/build-deb.sh $COMPONENT"
    fi
fi

echo -e "${GREEN}✓ Built: $OUTPUT_DIR/$PKG_NAME${NC}"
