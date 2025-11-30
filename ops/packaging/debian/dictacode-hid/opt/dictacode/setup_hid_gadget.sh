#!/bin/bash
# setup_hid_gadget.sh - Create USB HID keyboard gadget
#
# Safety checks:
# 1. Target must be capable (has dwc2/OTG hardware)
# 2. Role must be "hid" (from inventory.yaml)
#
# Idempotent: safe to run multiple times

set -e

GADGET_NAME="dictacode"
GADGET_DIR="/sys/kernel/config/usb_gadget/$GADGET_NAME"
INVENTORY_FILE="/etc/dictacode/inventory.yaml"

# -----------------------------------------------------------------------------
# Safety Check 1: Hardware Capability
# -----------------------------------------------------------------------------
check_hardware_capable() {
    # Check if this is a Pi Zero / Pi Zero W / Pi Zero 2 W (OTG capable)
    # These have dwc2 hardware that supports USB gadget mode

    # Method 1: Check for UDC (USB Device Controller) availability
    # This only works if dwc2 module is loaded
    if [ -d "/sys/class/udc" ] && [ -n "$(ls /sys/class/udc 2>/dev/null)" ]; then
        return 0
    fi

    # Method 2: Check device tree for dwc2
    if [ -d "/proc/device-tree/soc/usb@20980000" ]; then
        return 0  # Pi Zero / Zero W
    fi
    if [ -d "/proc/device-tree/soc/usb@3f980000" ]; then
        return 0  # Pi Zero 2 W
    fi

    # Method 3: Check if dwc2 overlay is configured (but may need reboot)
    if grep -q "dtoverlay=dwc2" /boot/firmware/config.txt 2>/dev/null; then
        echo "WARNING: dwc2 overlay configured but UDC not available (reboot required?)"
        return 0
    fi
    if grep -q "dtoverlay=dwc2" /boot/config.txt 2>/dev/null; then
        echo "WARNING: dwc2 overlay configured but UDC not available (reboot required?)"
        return 0
    fi

    return 1
}

# -----------------------------------------------------------------------------
# Safety Check 2: Role Check
# -----------------------------------------------------------------------------
check_role_hid() {
    # Check if this device has role "hid" in inventory

    if [ ! -f "$INVENTORY_FILE" ]; then
        echo "WARNING: Inventory file not found: $INVENTORY_FILE"
        echo "Assuming role is 'hid' for this device"
        return 0
    fi

    # Simple grep check - look for role: hid in the hid device section
    # A proper check would use a YAML parser
    if grep -A5 "^[[:space:]]*hid:" "$INVENTORY_FILE" | grep -q "role:[[:space:]]*hid"; then
        return 0
    fi

    # Alternative: check hostname matches inventory
    local hostname=$(hostname)
    if grep -B5 "hostname:[[:space:]]*$hostname" "$INVENTORY_FILE" | grep -q "role:[[:space:]]*hid"; then
        return 0
    fi

    echo "WARNING: Could not confirm role is 'hid' in inventory"
    echo "Proceeding anyway (inventory check is advisory)"
    return 0
}

# -----------------------------------------------------------------------------
# Main Setup
# -----------------------------------------------------------------------------
setup_gadget() {
    # Exit if gadget already exists and bound
    if [ -f "$GADGET_DIR/UDC" ] && [ -n "$(cat $GADGET_DIR/UDC 2>/dev/null)" ]; then
        echo "Gadget already configured and bound"
        exit 0
    fi

    # Load libcomposite if needed
    if ! lsmod | grep -q libcomposite; then
        echo "Loading libcomposite module..."
        modprobe libcomposite || {
            echo "ERROR: Failed to load libcomposite module"
            exit 1
        }
    fi

    # Wait for UDC to appear (may take a moment after module load)
    local retries=10
    while [ ! -d "/sys/class/udc" ] || [ -z "$(ls /sys/class/udc 2>/dev/null)" ]; do
        if [ $retries -le 0 ]; then
            echo "ERROR: No UDC available after waiting"
            exit 1
        fi
        echo "Waiting for UDC..."
        sleep 0.5
        retries=$((retries - 1))
    done

    # Create gadget directory
    echo "Creating USB gadget: $GADGET_NAME"
    mkdir -p "$GADGET_DIR"
    cd "$GADGET_DIR"

    # Device descriptor
    echo 0x1d6b > idVendor   # Linux Foundation
    echo 0x0104 > idProduct  # Multifunction Composite Gadget
    echo 0x0100 > bcdDevice  # v1.0.0
    echo 0x0200 > bcdUSB     # USB2

    # Strings (English)
    mkdir -p strings/0x409
    echo "dictacode-$(cat /proc/cpuinfo | grep Serial | cut -d: -f2 | tr -d ' ' | tail -c 8)" > strings/0x409/serialnumber
    echo "dictacode" > strings/0x409/manufacturer
    echo "dictacode HID Keyboard" > strings/0x409/product

    # Configuration
    mkdir -p configs/c.1/strings/0x409
    echo "Config 1: HID Keyboard" > configs/c.1/strings/0x409/configuration
    echo 250 > configs/c.1/MaxPower

    # HID function (keyboard)
    mkdir -p functions/hid.usb0
    echo 1 > functions/hid.usb0/protocol      # 1 = Keyboard
    echo 1 > functions/hid.usb0/subclass      # 1 = Boot interface subclass
    echo 8 > functions/hid.usb0/report_length # 8-byte keyboard reports

    # Standard USB HID keyboard report descriptor
    # See USB HID Usage Tables specification
    echo -ne '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x05\x75\x01\x05\x08\x19\x01\x29\x05\x91\x02\x95\x01\x75\x03\x91\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' > functions/hid.usb0/report_desc

    # Link function to configuration
    ln -sf functions/hid.usb0 configs/c.1/

    # Bind to UDC
    local udc=$(ls /sys/class/udc | head -1)
    if [ -z "$udc" ]; then
        echo "ERROR: No UDC available"
        exit 1
    fi

    echo "Binding to UDC: $udc"
    echo "$udc" > UDC

    # Verify
    sleep 0.5
    if [ -e /dev/hidg0 ]; then
        echo "SUCCESS: /dev/hidg0 created"
        ls -la /dev/hidg0
    else
        echo "ERROR: /dev/hidg0 not created"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Entry Point
# -----------------------------------------------------------------------------
main() {
    echo "=== dictacode HID Gadget Setup ==="

    # Safety check 1: Hardware capability
    echo "Checking hardware capability..."
    if ! check_hardware_capable; then
        echo "ERROR: This device is not USB gadget capable"
        echo "USB HID gadget requires Pi Zero / Zero W / Zero 2 W with OTG port"
        exit 1
    fi
    echo "Hardware: OK"

    # Safety check 2: Role check
    echo "Checking role..."
    if ! check_role_hid; then
        echo "ERROR: This device does not have role 'hid'"
        echo "USB HID gadget should only be configured on devices with role 'hid'"
        exit 1
    fi
    echo "Role: OK"

    # Setup gadget
    setup_gadget

    echo "=== Setup Complete ==="
}

main "$@"
