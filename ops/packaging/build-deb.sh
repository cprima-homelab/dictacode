#!/bin/sh
set -e

PKG_ROOT="ops/packaging/debian/dictacode-bootstrap"
OUT_DIR="ops/packaging/dist"

mkdir -p "$OUT_DIR"

# Work around WSL permission issues by building in /tmp
TEMP_DIR=$(mktemp -d)
cp -r "$PKG_ROOT" "$TEMP_DIR/"
PKG_NAME=$(basename "$PKG_ROOT")

# Fix permissions
chmod 755 "$TEMP_DIR/$PKG_NAME/DEBIAN"
find "$TEMP_DIR/$PKG_NAME/DEBIAN" -type f -exec chmod 644 {} \;
chmod 755 "$TEMP_DIR/$PKG_NAME/DEBIAN/postinst"

# Build the package
dpkg-deb --build "$TEMP_DIR/$PKG_NAME" "$TEMP_DIR/dictacode-bootstrap.deb"

# Copy to output directory
cp "$TEMP_DIR/dictacode-bootstrap.deb" "$OUT_DIR/"

# Cleanup
rm -rf "$TEMP_DIR"

echo "Built: $OUT_DIR/dictacode-bootstrap.deb"
