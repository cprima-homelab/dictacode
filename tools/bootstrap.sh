#!/usr/bin/env sh
# dictacode bootstrap - fetches and installs .deb packages from GitHub releases
#
# POSIX sh compatible
#
# Options:
#   -t <pi5|pi0>    Target device type (required)
#   -U              Fully upgrade system before bootstrap
#   -v <version>    Package version (default: 0.1.0)
#   -h              Show help

set -eu

REPO="cprima-homelab/dictacode"
VERSION="${DICTACODE_VERSION:-0.1.0}"
UPGRADE=0
TARGET=""

__usage() {
    cat <<'EOF'
Usage: bootstrap.sh [OPTIONS]

Options:
  -t <pi5|pi0>    Target device type (required)
                    pi5 = STT engine (installs dictacode-core + dictacode-stt)
                    pi0 = HID gadget (installs dictacode-core + dictacode-hid)
  -U              Fully upgrade the system (apt-get dist-upgrade) first
  -v <version>    Package version (default: 0.1.0)
  -h              Show this help and exit

Examples:
  # Pi5 (STT engine)
  curl -sSL https://raw.githubusercontent.com/cprima-homelab/dictacode/exploration/tools/bootstrap.sh | sudo sh -s -- -t pi5

  # Pi Zero (HID gadget)
  curl -sSL https://raw.githubusercontent.com/cprima-homelab/dictacode/exploration/tools/bootstrap.sh | sudo sh -s -- -t pi0

  # With system upgrade first
  curl -sSL ... | sudo sh -s -- -t pi5 -U

  # Specific version
  curl -sSL ... | sudo sh -s -- -t pi5 -v 0.2.0

Environment:
  DICTACODE_VERSION    Override default version (e.g., export DICTACODE_VERSION=0.2.0)
EOF
}

cleanup() {
    rm -f /tmp/dictacode-*.deb 2>/dev/null || true
}
trap cleanup EXIT INT TERM

download_deb() {
    pkg_name="$1"
    pkg_version="$2"
    url="https://github.com/${REPO}/releases/download/${pkg_name}-v${pkg_version}/${pkg_name}.deb"
    dest="/tmp/${pkg_name}.deb"

    echo "Downloading: ${pkg_name} v${pkg_version}"
    echo "  URL: ${url}"

    if ! curl -fsSL -o "$dest" "$url"; then
        echo "ERROR: Failed to download ${pkg_name}" >&2
        echo "  Check if release exists: https://github.com/${REPO}/releases/tag/${pkg_name}-v${pkg_version}" >&2
        exit 1
    fi

    echo "  Saved: ${dest}"
}

# Parse options
while getopts "Uht:v:" opt; do
    case "$opt" in
        U)
            UPGRADE=1
            ;;
        t)
            TARGET="$OPTARG"
            ;;
        v)
            VERSION="$OPTARG"
            ;;
        h)
            __usage
            exit 0
            ;;
        *)
            __usage
            exit 1
            ;;
    esac
done
shift $((OPTIND - 1))

# Validate target
if [ -z "$TARGET" ]; then
    echo "ERROR: -t <pi5|pi0> is required" >&2
    __usage
    exit 1
fi

case "$TARGET" in
    pi5|pi0)
        ;;
    *)
        echo "ERROR: invalid target '$TARGET' (must be pi5 or pi0)" >&2
        __usage
        exit 1
        ;;
esac

# Check root
if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: must run as root (use sudo)" >&2
    exit 1
fi

echo "========================================"
echo "  dictacode bootstrap"
echo "========================================"
echo "Target:  ${TARGET}"
echo "Version: ${VERSION}"
echo "Upgrade: ${UPGRADE}"
echo ""

# Update package lists
echo "=== Updating package lists ==="
apt-get update

# Optional full upgrade
if [ "$UPGRADE" -eq 1 ]; then
    echo "=== Performing system upgrade ==="
    apt-get dist-upgrade -y
fi

# Download packages
echo ""
echo "=== Downloading packages ==="

download_deb "dictacode-core" "$VERSION"

if [ "$TARGET" = "pi5" ]; then
    download_deb "dictacode-stt" "$VERSION"
elif [ "$TARGET" = "pi0" ]; then
    download_deb "dictacode-hid" "$VERSION"
fi

# Install packages
echo ""
echo "=== Installing packages ==="

dpkg -i /tmp/dictacode-core.deb || true

if [ "$TARGET" = "pi5" ]; then
    dpkg -i /tmp/dictacode-stt.deb || true
elif [ "$TARGET" = "pi0" ]; then
    dpkg -i /tmp/dictacode-hid.deb || true
fi

# Fix dependencies
echo ""
echo "=== Installing dependencies ==="
apt-get install -f -y

# Summary
echo ""
echo "========================================"
echo "  Bootstrap complete!"
echo "========================================"

if [ "$TARGET" = "pi5" ]; then
    echo ""
    echo "Next steps for Pi5 (STT):"
    echo "  1. Edit config (optional): sudo nano /etc/dictacode/stt.conf"
    echo "  2. Build whisper.cpp:      sudo /opt/dictacode/stt/install-whisper.sh"
    echo "  3. Start service:          sudo systemctl enable --now dictacode-stt"
elif [ "$TARGET" = "pi0" ]; then
    echo ""
    echo "Next steps for Pi Zero (HID):"
    echo "  1. Reboot:                 sudo reboot"
    echo "  2. Verify HID device:      ls -la /dev/hidg0"
    echo "  3. Set keymap (optional):  sudo dictacode-keymap set de_de"
fi

echo ""
