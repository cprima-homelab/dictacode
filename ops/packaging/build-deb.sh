#!/bin/sh
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

mkdir -p "$OUT_DIR"

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

    # Build the package
    dpkg-deb --build "$TEMP_DIR/$pkg_name" "$TEMP_DIR/$pkg_name.deb"

    # Copy to output directory
    cp "$TEMP_DIR/$pkg_name.deb" "$OUT_DIR/"

    # Cleanup
    rm -rf "$TEMP_DIR"

    echo "Built: $OUT_DIR/$pkg_name.deb"
}

# Main
if [ -n "$1" ]; then
    # Build specific package
    build_package "$1"
else
    # Build all packages
    for pkg_dir in "$DEBIAN_DIR"/*/; do
        pkg_name=$(basename "$pkg_dir")
        build_package "$pkg_name"
    done
fi
