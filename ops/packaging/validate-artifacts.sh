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

validate_template_checksums() {
    local deb_file="$1"
    local temp_dir=$(mktemp -d)
    trap "rm -rf '$temp_dir'" EXIT

    echo ""
    info "=== Validating template checksums ==="

    dpkg-deb -x "$deb_file" "$temp_dir"

    local config_dir="$temp_dir/etc/dictacode"
    if [ ! -d "$config_dir" ]; then
        warn "No config directory in package (may be OK for core package)"
        rm -rf "$temp_dir"
        trap - EXIT
        return 0
    fi

    templates_dir="$REPO_ROOT/ops/packaging/templates"
    failed=0

    # Check each .conf file against canonical template
    for installed_conf in "$config_dir"/*.conf; do
        # Skip if glob didn't match (literal *.conf)
        [ -f "$installed_conf" ] || continue

        template_name=$(basename "$installed_conf")
        canonical="$templates_dir/$template_name"

        if [ -f "$canonical" ]; then
            installed_sha=$(sha256sum "$installed_conf" | awk '{print $1}')
            canonical_sha=$(sha256sum "$canonical" | awk '{print $1}')

            if [ "$installed_sha" = "$canonical_sha" ]; then
                info "✓ $template_name matches canonical"
            else
                warn "✗ $template_name differs from canonical"
                echo "  Canonical: $canonical_sha"
                echo "  Installed: $installed_sha"
                failed=$((failed + 1))
            fi
        else
            warn "No canonical template found for $template_name"
        fi
    done

    rm -rf "$temp_dir"
    trap - EXIT

    if [ $failed -gt 0 ]; then
        warn "$failed template(s) differ from canonical source"
    else
        info "✓ All templates match canonical source"
    fi
}

# === macOS Package Validation ===

validate_macos_pkg() {
    local pkg_file="$1"
    local pkg_name=$(basename "$pkg_file" .pkg)

    echo ""
    info "=== Validating macOS package: $pkg_name ==="

    if [ ! -f "$pkg_file" ]; then
        fatal "Package not found: $pkg_file"
    fi

    # Only works on macOS
    if [ "$(uname)" != "Darwin" ]; then
        warn "macOS .pkg validation requires macOS (skipping detailed check)"
        return 0
    fi

    # Extract to temp directory
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf '$TEMP_DIR'" EXIT

    # Expand the package
    pkgutil --expand "$pkg_file" "$TEMP_DIR/expanded"

    # Find and extract payload
    if [ -f "$TEMP_DIR/expanded/Payload" ]; then
        mkdir -p "$TEMP_DIR/payload"
        cd "$TEMP_DIR/payload"
        cpio -idm < "$TEMP_DIR/expanded/Payload" 2>/dev/null
        cd - > /dev/null
    fi

    # Check for compatibility.json
    EXTRACTED_MATRIX=$(find "$TEMP_DIR/payload" -name "compatibility.json" -type f 2>/dev/null)

    if [ -n "$EXTRACTED_MATRIX" ]; then
        info "Found matrix in package: $(echo "$EXTRACTED_MATRIX" | sed "s|$TEMP_DIR/payload||")"

        SOURCE_SHA=$(shasum -a 256 "$SOURCE_MATRIX" | cut -d' ' -f1)
        EXTRACTED_SHA=$(shasum -a 256 "$EXTRACTED_MATRIX" | cut -d' ' -f1)

        echo "Source checksum:    $SOURCE_SHA"
        echo "Extracted checksum: $EXTRACTED_SHA"

        if [ "$SOURCE_SHA" != "$EXTRACTED_SHA" ]; then
            fatal "Checksum mismatch! Package contains different compatibility.json"
        fi

        info "✓ Checksum validated successfully"
    else
        warn "Package does not contain compatibility.json (may be OK for non-core packages)"
    fi

    rm -rf "$TEMP_DIR"
    trap - EXIT
}

validate_macos_payload_tarball() {
    local tarball="$1"
    local pkg_name=$(basename "$tarball" | sed 's/-macos-payload.tar.gz$//')

    echo ""
    info "=== Validating macOS payload: $pkg_name ==="

    if [ ! -f "$tarball" ]; then
        fatal "Payload tarball not found: $tarball"
    fi

    # Extract to temp directory
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf '$TEMP_DIR'" EXIT

    tar -xzf "$tarball" -C "$TEMP_DIR"

    # macOS install root
    local macos_root="Library/Application Support/dictacode"

    # Validate expected paths based on package
    case "$pkg_name" in
        dictacode-core*)
            if [ -f "$TEMP_DIR/$macos_root/shared/compatibility.json" ]; then
                info "✓ Found shared/compatibility.json"

                SOURCE_SHA=$(sha256sum "$SOURCE_MATRIX" | awk '{print $1}')
                EXTRACTED_SHA=$(sha256sum "$TEMP_DIR/$macos_root/shared/compatibility.json" | awk '{print $1}')

                if [ "$SOURCE_SHA" = "$EXTRACTED_SHA" ]; then
                    info "✓ Checksum validated successfully"
                else
                    fatal "Checksum mismatch!"
                fi
            else
                fatal "Missing shared/compatibility.json"
            fi
            ;;

        dictacode-stt*)
            if [ -f "$TEMP_DIR/$macos_root/stt.conf" ]; then
                info "✓ Found stt.conf"
            else
                fatal "Missing stt.conf"
            fi
            if [ -d "$TEMP_DIR/$macos_root/stt.d" ]; then
                info "✓ Found stt.d/ drop-in directory"
            else
                fatal "Missing stt.d/ drop-in directory"
            fi
            ;;

        dictacode-hid*)
            if [ -f "$TEMP_DIR/$macos_root/hid.conf" ]; then
                info "✓ Found hid.conf"
            else
                fatal "Missing hid.conf"
            fi
            if [ -f "$TEMP_DIR/$macos_root/keymap.conf" ]; then
                info "✓ Found keymap.conf"
            else
                fatal "Missing keymap.conf"
            fi
            if [ -d "$TEMP_DIR/$macos_root/hid.d" ]; then
                info "✓ Found hid.d/ drop-in directory"
            else
                fatal "Missing hid.d/ drop-in directory"
            fi
            ;;
    esac

    rm -rf "$TEMP_DIR"
    trap - EXIT

    info "✓ macOS payload validation complete"
}

validate_paths_alignment() {
    echo ""
    info "=== Validating paths.py alignment with packaging ==="

    local stt_paths="$REPO_ROOT/apps/stt/src/dictacode_stt/paths.py"
    local hid_paths="$REPO_ROOT/apps/hid/src/dictacode_hid/paths.py"

    # Check macOS paths in paths.py
    for paths_file in "$stt_paths" "$hid_paths"; do
        if [ -f "$paths_file" ]; then
            local app_name=$(basename "$(dirname "$(dirname "$paths_file")")")

            # Check for darwin paths
            if grep -q '"/Library/Application Support/dictacode"' "$paths_file"; then
                info "✓ $app_name paths.py has macOS paths"
            else
                warn "$app_name paths.py missing macOS paths"
            fi

            # Check for linux paths
            if grep -q '"/etc/dictacode"' "$paths_file"; then
                info "✓ $app_name paths.py has Linux paths"
            else
                warn "$app_name paths.py missing Linux paths"
            fi
        fi
    done
}

# Main
if [ ! -f "$SOURCE_MATRIX" ]; then
    fatal "Source compatibility.json not found: $SOURCE_MATRIX"
fi

info "Source matrix: $SOURCE_MATRIX"
info "Source SHA256: $(sha256sum "$SOURCE_MATRIX" | awk '{print $1}')"

MACOS_OUT_DIR="$SCRIPT_DIR/macos/dist"

if [ -n "$1" ]; then
    # Validate specific package
    if [ -f "$OUT_DIR/$1.deb" ]; then
        validate_deb_package "$OUT_DIR/$1.deb"
        validate_systemd_units "$OUT_DIR/$1.deb"
        validate_config_structure "$OUT_DIR/$1.deb"
        validate_template_checksums "$OUT_DIR/$1.deb"
    elif [ -f "$OUT_DIR/$1" ]; then
        if echo "$1" | grep -q '\.whl$'; then
            validate_wheel "$OUT_DIR/$1"
        elif echo "$1" | grep -q '\.pkg$'; then
            validate_macos_pkg "$OUT_DIR/$1"
        elif echo "$1" | grep -q 'macos-payload.tar.gz$'; then
            validate_macos_payload_tarball "$OUT_DIR/$1"
        else
            validate_deb_package "$OUT_DIR/$1"
            validate_systemd_units "$OUT_DIR/$1"
            validate_config_structure "$OUT_DIR/$1"
            validate_template_checksums "$OUT_DIR/$1"
        fi
    elif [ -f "$MACOS_OUT_DIR/$1" ]; then
        if echo "$1" | grep -q '\.pkg$'; then
            validate_macos_pkg "$MACOS_OUT_DIR/$1"
        elif echo "$1" | grep -q 'macos-payload.tar.gz$'; then
            validate_macos_payload_tarball "$MACOS_OUT_DIR/$1"
        fi
    else
        fatal "Package not found: $OUT_DIR/$1 or $OUT_DIR/$1.deb"
    fi
else
    # Validate all packages
    VALIDATED=0
    SKIPPED=0

    # Check for .deb files (Linux)
    if ls "$OUT_DIR"/*.deb >/dev/null 2>&1; then
        info "=== Linux Packages (.deb) ==="
        for deb_file in "$OUT_DIR"/*.deb; do
            if validate_deb_package "$deb_file" 2>&1 | grep -q "skipping"; then
                SKIPPED=$((SKIPPED + 1))
            else
                validate_template_checksums "$deb_file"
                VALIDATED=$((VALIDATED + 1))
            fi
        done
    fi

    # Check for .pkg files (macOS)
    if ls "$MACOS_OUT_DIR"/*.pkg >/dev/null 2>&1; then
        info "=== macOS Packages (.pkg) ==="
        for pkg_file in "$MACOS_OUT_DIR"/*.pkg; do
            validate_macos_pkg "$pkg_file"
            VALIDATED=$((VALIDATED + 1))
        done
    fi

    # Check for macOS payload tarballs (built on non-macOS)
    if ls "$MACOS_OUT_DIR"/*-macos-payload.tar.gz >/dev/null 2>&1; then
        info "=== macOS Payload Tarballs ==="
        for tarball in "$MACOS_OUT_DIR"/*-macos-payload.tar.gz; do
            validate_macos_payload_tarball "$tarball"
            VALIDATED=$((VALIDATED + 1))
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

    # Validate paths.py alignment
    validate_paths_alignment

    echo ""
    info "==================================="
    info "Validation complete!"
    echo "Validated: $VALIDATED packages"
    echo "Skipped: $SKIPPED packages (no compatibility.json)"
    info "==================================="
fi
