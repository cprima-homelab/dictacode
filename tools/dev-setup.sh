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
