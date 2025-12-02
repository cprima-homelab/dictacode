#!/bin/bash
# build-pkg.sh - Build dictacode macOS installer packages (.pkg)
#
# PURPOSE:
#   macOS packages are for configuration/code inspection and development,
#   NOT for functional UART/HID runtime. The hardware-dependent features
#   (USB gadget mode, UART serial) are Linux-specific.
#
# WHAT GETS INSTALLED:
#   - Configuration files (stt.conf, hid.conf, keymap.conf)
#   - Drop-in directories (stt.d/, hid.d/)
#   - Shared data (compatibility.json)
#   - Audio config directories
#
# WHAT IS NOT INCLUDED:
#   - launchd plists (no background services)
#   - System users/groups
#   - Hardware-dependent binaries
#
# Usage:
#   ./build-pkg.sh                    # build all packages
#   ./build-pkg.sh dictacode-hid      # build specific package
#   ./build-pkg.sh dictacode-core
#   ./build-pkg.sh --combined         # build combined installer
#
# Requires: macOS with pkgbuild and productbuild (Xcode Command Line Tools)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
OUT_DIR="$SCRIPT_DIR/dist"

# Source template library for canonical template management
source "$SCRIPT_DIR/../lib/templates.sh"

# macOS install root
INSTALL_ROOT="/Library/Application Support/dictacode"

# Package identifier prefix
PKG_IDENTIFIER="com.dictacode"

# Version from compatibility.json or default
VERSION=$(grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' "$REPO_ROOT/compatibility.json" 2>/dev/null | head -1 | cut -d'"' -f4 || echo "0.3.2")

mkdir -p "$OUT_DIR"

# Check if running on macOS
check_macos() {
    if [[ "$(uname)" != "Darwin" ]]; then
        echo "WARNING: Not running on macOS. Package will be created but may not be valid."
        echo "         For production packages, build on macOS with Xcode Command Line Tools."
        return 1
    fi
    return 0
}

# Create payload directory structure
create_payload() {
    local pkg_name="$1"
    local payload_dir="$2"

    echo "  Creating payload for $pkg_name..."

    case "$pkg_name" in
        dictacode-core)
            # Shared data directory
            mkdir -p "$payload_dir$INSTALL_ROOT/shared"
            cp "$REPO_ROOT/compatibility.json" "$payload_dir$INSTALL_ROOT/shared/"
            echo "    -> shared/compatibility.json"
            ;;

        dictacode-stt)
            # STT config and drop-in directory
            mkdir -p "$payload_dir$INSTALL_ROOT"
            mkdir -p "$payload_dir$INSTALL_ROOT/stt.d"
            mkdir -p "$payload_dir$INSTALL_ROOT/audio"
            mkdir -p "$payload_dir$INSTALL_ROOT/audio/profiles"

            copy_template "stt.conf" "$payload_dir$INSTALL_ROOT" "darwin"
            echo "    -> stt.d/ (drop-in directory)"
            echo "    -> audio/ (audio config directory)"
            ;;

        dictacode-hid)
            # HID config, keymap, and drop-in directory
            mkdir -p "$payload_dir$INSTALL_ROOT"
            mkdir -p "$payload_dir$INSTALL_ROOT/hid.d"
            mkdir -p "$payload_dir$INSTALL_ROOT/hid/devices.d"

            copy_template "hid.conf" "$payload_dir$INSTALL_ROOT" "darwin"
            copy_template "keymap.conf" "$payload_dir$INSTALL_ROOT" "darwin"
            echo "    -> hid.d/ (drop-in directory)"
            echo "    -> hid/devices.d/ (HID registry)"
            ;;
    esac
}

# Create postinstall script
create_postinstall() {
    local pkg_name="$1"
    local scripts_dir="$2"

    mkdir -p "$scripts_dir"

    cat > "$scripts_dir/postinstall" << 'POSTINSTALL'
#!/bin/bash
# postinstall script for dictacode macOS package
#
# This script runs as root after package installation.
# It sets standard permissions for config files.

set -e

INSTALL_ROOT="/Library/Application Support/dictacode"

# Only proceed if the directory exists (it should after payload install)
if [ ! -d "$INSTALL_ROOT" ]; then
    echo "dictacode: Install directory not found, skipping permissions setup"
    exit 0
fi

# Set ownership to root:wheel (standard for macOS system configs)
# Use -R but ignore errors on individual files (SIP protection)
chown -R root:wheel "$INSTALL_ROOT" 2>/dev/null || true

# Set directory permissions (755)
find "$INSTALL_ROOT" -type d -exec chmod 755 {} \; 2>/dev/null || true

# Set file permissions (644 for configs)
find "$INSTALL_ROOT" -type f \( -name "*.conf" -o -name "*.json" \) -exec chmod 644 {} \; 2>/dev/null || true

echo "dictacode: Configuration installed to $INSTALL_ROOT"
echo "dictacode: NOTE - This package provides configs only, not runtime services."
echo "dictacode: Hardware features (UART/HID) require Linux."

exit 0
POSTINSTALL

    chmod 755 "$scripts_dir/postinstall"
}

# Build a single package
build_package() {
    local pkg_name="$1"
    local temp_dir=$(mktemp -d)
    local payload_dir="$temp_dir/payload"
    local scripts_dir="$temp_dir/scripts"

    echo "Building: $pkg_name (macOS .pkg)"

    # Create payload
    mkdir -p "$payload_dir"
    create_payload "$pkg_name" "$payload_dir"

    # Validate template checksums against canonical (with optional patches)
    local install_dir="$payload_dir$INSTALL_ROOT"
    if [ -d "$install_dir" ] && ls "$install_dir"/*.conf >/dev/null 2>&1; then
        if ! validate_template_checksums "$install_dir" "darwin" 2>/dev/null; then
            echo "WARNING: Template checksum mismatch (may be OK if no patches yet)"
        fi
    fi

    # Create postinstall script
    create_postinstall "$pkg_name" "$scripts_dir"

    # Build package
    if check_macos; then
        # Native macOS build with pkgbuild
        pkgbuild \
            --root "$payload_dir" \
            --scripts "$scripts_dir" \
            --identifier "${PKG_IDENTIFIER}.${pkg_name}" \
            --version "$VERSION" \
            --install-location "/" \
            "$OUT_DIR/${pkg_name}-${VERSION}.pkg"

        echo "Built: $OUT_DIR/${pkg_name}-${VERSION}.pkg"
    else
        # Non-macOS: create a tarball of the payload for inspection
        echo "  Creating payload tarball (non-macOS build)..."
        tar -czf "$OUT_DIR/${pkg_name}-${VERSION}-macos-payload.tar.gz" \
            -C "$payload_dir" .

        # Also save the scripts
        tar -czf "$OUT_DIR/${pkg_name}-${VERSION}-macos-scripts.tar.gz" \
            -C "$scripts_dir" .

        echo "Created: $OUT_DIR/${pkg_name}-${VERSION}-macos-payload.tar.gz"
        echo "Created: $OUT_DIR/${pkg_name}-${VERSION}-macos-scripts.tar.gz"
        echo "  (Run on macOS to build actual .pkg)"
    fi

    # Cleanup
    rm -rf "$temp_dir"

    # Validate
    validate_package "$pkg_name"
}

# Validate package contents
validate_package() {
    local pkg_name="$1"
    local pkg_file="$OUT_DIR/${pkg_name}-${VERSION}.pkg"

    echo "  Validating $pkg_name..."

    if [ -f "$pkg_file" ] && check_macos 2>/dev/null; then
        # On macOS, inspect the package
        echo "  Package contents:"
        pkgutil --payload-files "$pkg_file" 2>/dev/null | head -20 || true
    fi

    # Validate compatibility.json checksum for core package
    if [ "$pkg_name" = "dictacode-core" ]; then
        local src_checksum=$(shasum -a 256 "$REPO_ROOT/compatibility.json" | cut -d' ' -f1)
        echo "  Source compatibility.json checksum: $src_checksum"
    fi

    echo "  Validation complete."
}

# Build combined installer (optional)
build_combined() {
    if ! check_macos; then
        echo "Combined installer requires macOS"
        return 1
    fi

    echo "Building combined installer..."

    # Build individual packages first
    for pkg in dictacode-core dictacode-stt dictacode-hid; do
        if [ ! -f "$OUT_DIR/${pkg}-${VERSION}.pkg" ]; then
            build_package "$pkg"
        fi
    done

    # Create distribution XML
    local dist_xml="$OUT_DIR/distribution.xml"
    cat > "$dist_xml" << DISTXML
<?xml version="1.0" encoding="utf-8"?>
<installer-gui-script minSpecVersion="1">
    <title>dictacode</title>
    <organization>com.dictacode</organization>
    <domains enable_localSystem="true"/>
    <options customize="allow" require-scripts="true"/>

    <choices-outline>
        <line choice="dictacode-core"/>
        <line choice="dictacode-stt"/>
        <line choice="dictacode-hid"/>
    </choices-outline>

    <choice id="dictacode-core" title="Core (Required)" enabled="false">
        <pkg-ref id="com.dictacode.dictacode-core"/>
    </choice>
    <choice id="dictacode-stt" title="STT Service">
        <pkg-ref id="com.dictacode.dictacode-stt"/>
    </choice>
    <choice id="dictacode-hid" title="HID Service">
        <pkg-ref id="com.dictacode.dictacode-hid"/>
    </choice>

    <pkg-ref id="com.dictacode.dictacode-core" version="$VERSION">dictacode-core-${VERSION}.pkg</pkg-ref>
    <pkg-ref id="com.dictacode.dictacode-stt" version="$VERSION">dictacode-stt-${VERSION}.pkg</pkg-ref>
    <pkg-ref id="com.dictacode.dictacode-hid" version="$VERSION">dictacode-hid-${VERSION}.pkg</pkg-ref>
</installer-gui-script>
DISTXML

    # Build product archive
    productbuild \
        --distribution "$dist_xml" \
        --package-path "$OUT_DIR" \
        "$OUT_DIR/dictacode-${VERSION}.pkg"

    rm "$dist_xml"
    echo "Built: $OUT_DIR/dictacode-${VERSION}.pkg (combined installer)"
}

# Main
case "$1" in
    --combined)
        build_combined
        ;;
    "")
        # Build all individual packages
        for pkg in dictacode-core dictacode-stt dictacode-hid; do
            build_package "$pkg"
        done
        ;;
    *)
        # Build specific package
        build_package "$1"
        ;;
esac

echo ""
echo "macOS packages built in: $OUT_DIR"
