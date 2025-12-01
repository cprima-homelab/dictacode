#!/bin/sh
# validate-artifacts.sh - Validate built artifacts contain correct compatibility.json
#
# Usage:
#   ./validate-artifacts.sh                    # validate all built packages
#   ./validate-artifacts.sh dictacode-core     # validate specific package

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="$SCRIPT_DIR/dist"
SOURCE_MATRIX="$REPO_ROOT/compatibility.json"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

fatal() {
    echo "${RED}ERROR: $*${NC}" >&2
    exit 1
}

info() {
    echo "${GREEN}$*${NC}"
}

warn() {
    echo "${YELLOW}WARNING: $*${NC}"
}

validate_deb_package() {
    local deb_file="$1"
    local pkg_name=$(basename "$deb_file" .deb)

    echo ""
    info "=== Validating: $pkg_name ==="

    if [ ! -f "$deb_file" ]; then
        fatal "Package not found: $deb_file"
    fi

    # Check if this package should contain compatibility.json
    if ! dpkg-deb -c "$deb_file" | grep -q "compatibility.json"; then
        warn "Package does not contain compatibility.json (skipping)"
        return 0
    fi

    # Extract to temp directory
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf '$TEMP_DIR'" EXIT

    dpkg-deb -x "$deb_file" "$TEMP_DIR"

    # Find compatibility.json in extracted package
    EXTRACTED_MATRIX=$(find "$TEMP_DIR" -name "compatibility.json" -type f)

    if [ -z "$EXTRACTED_MATRIX" ]; then
        fatal "compatibility.json not found in extracted package"
    fi

    if [ $(echo "$EXTRACTED_MATRIX" | wc -l) -gt 1 ]; then
        fatal "Multiple compatibility.json files found in package:\n$EXTRACTED_MATRIX"
    fi

    info "Found matrix in package: $(echo "$EXTRACTED_MATRIX" | sed "s|$TEMP_DIR||")"

    # Compute checksums
    SOURCE_SHA=$(sha256sum "$SOURCE_MATRIX" | awk '{print $1}')
    EXTRACTED_SHA=$(sha256sum "$EXTRACTED_MATRIX" | awk '{print $1}')

    echo "Source checksum:    $SOURCE_SHA"
    echo "Extracted checksum: $EXTRACTED_SHA"

    if [ "$SOURCE_SHA" != "$EXTRACTED_SHA" ]; then
        fatal "Checksum mismatch! Package contains different compatibility.json"
    fi

    info "✓ Checksum validated successfully"

    # Cleanup (trap will handle it, but explicit is better)
    rm -rf "$TEMP_DIR"
    trap - EXIT
}

validate_wheel() {
    local wheel_file="$1"
    local pkg_name=$(basename "$wheel_file" .whl)

    echo ""
    info "=== Validating wheel: $pkg_name ==="

    if [ ! -f "$wheel_file" ]; then
        fatal "Wheel not found: $wheel_file"
    fi

    # Check if wheel contains compatibility.json
    if ! unzip -l "$wheel_file" | grep -q "compatibility.json"; then
        warn "Wheel does not contain compatibility.json (skipping)"
        return 0
    fi

    # Extract to temp directory
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf '$TEMP_DIR'" EXIT

    unzip -q "$wheel_file" -d "$TEMP_DIR"

    # Find compatibility.json in extracted wheel
    EXTRACTED_MATRIX=$(find "$TEMP_DIR" -name "compatibility.json" -type f)

    if [ -z "$EXTRACTED_MATRIX" ]; then
        fatal "compatibility.json not found in extracted wheel"
    fi

    if [ $(echo "$EXTRACTED_MATRIX" | wc -l) -gt 1 ]; then
        fatal "Multiple compatibility.json files found in wheel:\n$EXTRACTED_MATRIX"
    fi

    info "Found matrix in wheel: $(echo "$EXTRACTED_MATRIX" | sed "s|$TEMP_DIR||")"

    # Compute checksums
    SOURCE_SHA=$(sha256sum "$SOURCE_MATRIX" | awk '{print $1}')
    EXTRACTED_SHA=$(sha256sum "$EXTRACTED_MATRIX" | awk '{print $1}')

    echo "Source checksum:    $SOURCE_SHA"
    echo "Extracted checksum: $EXTRACTED_SHA"

    if [ "$SOURCE_SHA" != "$EXTRACTED_SHA" ]; then
        fatal "Checksum mismatch! Wheel contains different compatibility.json"
    fi

    info "✓ Checksum validated successfully"

    # Cleanup
    rm -rf "$TEMP_DIR"
    trap - EXIT
}

validate_systemd_units() {
    local deb_file="$1"

    echo ""
    info "=== Validating systemd units ==="

    if ! dpkg-deb -c "$deb_file" | grep -q "dictacode-stt.service"; then
        warn "Main systemd unit not found (may be OK for non-stt packages)"
    else
        info "✓ Main systemd unit present"
    fi

    if dpkg-deb -c "$deb_file" | grep -q "dictacode-stt"; then
        if ! dpkg-deb -c "$deb_file" | grep -q "dictacode-stt-api.service"; then
            warn "API systemd unit not found in dictacode-stt package"
        else
            info "✓ API systemd unit present"
        fi
    fi
}

validate_config_structure() {
    local deb_file="$1"
    local temp_dir=$(mktemp -d)
    trap "rm -rf '$temp_dir'" EXIT

    echo ""
    info "=== Validating config file structure ==="

    dpkg-deb -x "$deb_file" "$temp_dir"

    local config="$temp_dir/etc/dictacode/stt.conf"
    if [ -f "$config" ]; then
        # Check for required keys (as comments or actual values)
        local missing_keys=0
        for key in metrics_enabled metrics_port api_host api_port api_metrics_enabled api_metrics_port; do
            if ! grep -Eq "^(#.*)?${key}=" "$config"; then
                warn "Config key not documented: $key"
                missing_keys=$((missing_keys + 1))
            fi
        done

        if [ $missing_keys -eq 0 ]; then
            info "✓ All config keys present"
        else
            warn "Missing $missing_keys config keys"
        fi
    else
        warn "Config file not found (may be OK for non-stt packages)"
    fi

    rm -rf "$temp_dir"
    trap - EXIT
}

# Main
if [ ! -f "$SOURCE_MATRIX" ]; then
    fatal "Source compatibility.json not found: $SOURCE_MATRIX"
fi

info "Source matrix: $SOURCE_MATRIX"
info "Source SHA256: $(sha256sum "$SOURCE_MATRIX" | awk '{print $1}')"

if [ -n "$1" ]; then
    # Validate specific package
    if [ -f "$OUT_DIR/$1.deb" ]; then
        validate_deb_package "$OUT_DIR/$1.deb"
        validate_systemd_units "$OUT_DIR/$1.deb"
        validate_config_structure "$OUT_DIR/$1.deb"
    elif [ -f "$OUT_DIR/$1" ]; then
        if echo "$1" | grep -q '\.whl$'; then
            validate_wheel "$OUT_DIR/$1"
        else
            validate_deb_package "$OUT_DIR/$1"
            validate_systemd_units "$OUT_DIR/$1"
            validate_config_structure "$OUT_DIR/$1"
        fi
    else
        fatal "Package not found: $OUT_DIR/$1 or $OUT_DIR/$1.deb"
    fi
else
    # Validate all packages
    VALIDATED=0
    SKIPPED=0

    # Check for .deb files
    if ls "$OUT_DIR"/*.deb >/dev/null 2>&1; then
        for deb_file in "$OUT_DIR"/*.deb; do
            if validate_deb_package "$deb_file" 2>&1 | grep -q "skipping"; then
                SKIPPED=$((SKIPPED + 1))
            else
                VALIDATED=$((VALIDATED + 1))
            fi
        done
    fi

    # Check for .whl files in app directories
    for app_dir in "$REPO_ROOT/apps/"*/; do
        if [ -d "$app_dir/dist" ]; then
            for whl_file in "$app_dir/dist"/*.whl; do
                if [ -f "$whl_file" ]; then
                    if validate_wheel "$whl_file" 2>&1 | grep -q "skipping"; then
                        SKIPPED=$((SKIPPED + 1))
                    else
                        VALIDATED=$((VALIDATED + 1))
                    fi
                fi
            done
        fi
    done

    echo ""
    info "==================================="
    info "Validation complete!"
    echo "Validated: $VALIDATED packages"
    echo "Skipped: $SKIPPED packages (no compatibility.json)"
    info "==================================="
fi
