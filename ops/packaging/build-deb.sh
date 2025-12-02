#!/bin/bash
# build-deb.sh - Build dictacode Debian packages
#
# Usage:
#   ./build-deb.sh                    # build all packages
#   ./build-deb.sh dictacode-hid      # build specific package
#   ./build-deb.sh dictacode-bootstrap

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEBIAN_DIR="$SCRIPT_DIR/debian"
OUT_DIR="$SCRIPT_DIR/dist"

# Source template library for canonical template management
source "$SCRIPT_DIR/lib/templates.sh"

mkdir -p "$OUT_DIR"

# Copy canonical templates to package directories (uses template library)
copy_templates() {
    local pkg_name="$1"
    local pkg_root="$2"

    echo "  Copying templates from canonical source..."

    case "$pkg_name" in
        dictacode-stt)
            mkdir -p "$pkg_root/etc/dictacode"
            copy_template "stt.conf" "$pkg_root/etc/dictacode" "linux"
            # Create empty drop-in directory (postinst ensures it exists)
            mkdir -p "$pkg_root/etc/dictacode/stt.d"
            ;;
        dictacode-hid)
            mkdir -p "$pkg_root/etc/dictacode"
            copy_template "hid.conf" "$pkg_root/etc/dictacode" "linux"
            copy_template "keymap.conf" "$pkg_root/etc/dictacode" "linux"
            # Create empty drop-in directory (postinst ensures it exists)
            mkdir -p "$pkg_root/etc/dictacode/hid.d"
            ;;
    esac
}

build_package() {
    local pkg_name="$1"
    local pkg_root="$DEBIAN_DIR/$pkg_name"

    if [ ! -d "$pkg_root" ]; then
        echo "ERROR: Package not found: $pkg_root"
        return 1
    fi

    echo "Building: $pkg_name"

    # Work around WSL permission issues by building in /tmp
    TEMP_DIR=$(mktemp -d)
    cp -r "$pkg_root" "$TEMP_DIR/"

    # Copy canonical templates (v0.3.2: single source of truth)
    copy_templates "$pkg_name" "$TEMP_DIR/$pkg_name"

    # Validate template checksums against canonical (with optional patches)
    # This ensures templates match canonical source (optionally with platform patches)
    if [ -d "$TEMP_DIR/$pkg_name/etc/dictacode" ]; then
        echo "  Validating templates against canonical source..."
        if ! validate_template_checksums "$TEMP_DIR/$pkg_name/etc/dictacode" "linux"; then
            echo "ERROR: Template checksum mismatch! Templates must match canonical source."
            echo "       Check ops/packaging/templates/ for authoritative versions."
            rm -rf "$TEMP_DIR"
            exit 1
        fi
    fi

    # Fix permissions
    chmod 755 "$TEMP_DIR/$pkg_name/DEBIAN"
    find "$TEMP_DIR/$pkg_name/DEBIAN" -type f -exec chmod 644 {} \;

    # Make scripts executable
    for script in postinst prerm postrm preinst; do
        if [ -f "$TEMP_DIR/$pkg_name/DEBIAN/$script" ]; then
            chmod 755 "$TEMP_DIR/$pkg_name/DEBIAN/$script"
        fi
    done

    # Make any scripts in opt executable
    find "$TEMP_DIR/$pkg_name/opt" -name "*.sh" -exec chmod 755 {} \; 2>/dev/null || true

    # Remove README placeholders from drop-in directories only (*.d/)
    find "$TEMP_DIR/$pkg_name/etc/dictacode" -type d -name "*.d" -exec sh -c 'rm -f "$1"/README' _ {} \; 2>/dev/null || true

    # Build the package
    dpkg-deb --build "$TEMP_DIR/$pkg_name" "$TEMP_DIR/$pkg_name.deb"

    # Copy to output directory
    cp "$TEMP_DIR/$pkg_name.deb" "$OUT_DIR/"

    # Cleanup
    rm -rf "$TEMP_DIR"

    echo "Built: $OUT_DIR/$pkg_name.deb"

    # Validate checksum for packages containing compatibility.json
    if [ -f "$SCRIPT_DIR/validate-artifacts.sh" ]; then
        if dpkg-deb -c "$OUT_DIR/$pkg_name.deb" 2>/dev/null | grep -q "compatibility.json"; then
            echo "Validating compatibility.json checksum..."
            "$SCRIPT_DIR/validate-artifacts.sh" "$pkg_name.deb" || {
                echo "ERROR: Checksum validation failed for $pkg_name.deb"
                exit 1
            }
        fi
    fi
}

# Main
if [ -n "$1" ]; then
    # Build specific package
    build_package "$1"
else
    # Build all packages (only directories with DEBIAN folder)
    for pkg_dir in "$DEBIAN_DIR"/*/; do
        pkg_name=$(basename "$pkg_dir")
        # Skip non-package directories (like patches/)
        if [ -d "$pkg_dir/DEBIAN" ]; then
            build_package "$pkg_name"
        fi
    done
fi
