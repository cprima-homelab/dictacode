#!/usr/bin/env python3
"""
check_hardware.py - Verify Pi Zero USB HID gadget prerequisites.

Sandbox script for dictacode HID.
Checks: boot config, kernel modules, configfs, gadget setup, /dev/hidg0.

Usage:
    python check_hardware.py

Exit code: 0 if READY, 1 if NOT READY
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


# Status indicators
OK = "[OK]"
WARN = "[WARN]"
FAIL = "[FAIL]"
INFO = "[INFO]"


class CheckResult:
    def __init__(self):
        self.issues = 0
        self.warnings = 0
        self.next_steps: List[str] = []

    def ok(self, msg: str) -> None:
        print(f"  {OK} {msg}")

    def warn(self, msg: str) -> None:
        print(f"  {WARN} {msg}")
        self.warnings += 1

    def fail(self, msg: str, next_step: str = None) -> None:
        print(f"  {FAIL} {msg}")
        self.issues += 1
        if next_step:
            self.next_steps.append(next_step)

    def info(self, msg: str) -> None:
        print(f"  {INFO} {msg}")


def find_config_txt() -> Tuple[Path | None, str]:
    """Find config.txt location (varies by distro)."""
    paths = [
        Path("/boot/firmware/config.txt"),  # Modern Pi OS (Bookworm+)
        Path("/boot/config.txt"),  # Legacy Pi OS
    ]
    for p in paths:
        if p.exists():
            return p, "modern" if "firmware" in str(p) else "legacy"
    return None, "unknown"


def check_file_contains(path: Path, pattern: str) -> bool:
    """Check if file contains pattern (handles comments)."""
    if not path.exists():
        return False
    try:
        content = path.read_text()
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("#"):
                continue
            if pattern in line:
                return True
        return False
    except Exception:
        return False


def check_modules_configured(module: str) -> Tuple[bool, str]:
    """Check if module is configured to load at boot."""
    # Check /etc/modules
    etc_modules = Path("/etc/modules")
    if etc_modules.exists():
        if check_file_contains(etc_modules, module):
            return True, "/etc/modules"

    # Check /etc/modules-load.d/
    modules_load_d = Path("/etc/modules-load.d")
    if modules_load_d.exists():
        for conf in modules_load_d.glob("*.conf"):
            if check_file_contains(conf, module):
                return True, str(conf)

    return False, ""


def check_module_loaded(module: str) -> bool:
    """Check if kernel module is currently loaded."""
    try:
        result = subprocess.run(
            ["lsmod"], check=False, capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if line.startswith(module) or f" {module} " in line:
                return True
        return False
    except Exception:
        return False


def check_dwc2_active() -> bool:
    """Check if dwc2 is active (may be loaded via device tree, not lsmod)."""
    # If UDC is available, dwc2 is working regardless of lsmod
    udc_path = Path("/sys/class/udc")
    if udc_path.exists() and list(udc_path.iterdir()):
        return True
    # Fallback to lsmod check
    return check_module_loaded("dwc2")


def get_udc_name() -> str | None:
    """Get the name of the USB Device Controller."""
    udc_path = Path("/sys/class/udc")
    if not udc_path.exists():
        return None
    udcs = list(udc_path.iterdir())
    if udcs:
        return udcs[0].name
    return None


def check_configfs_mounted() -> bool:
    """Check if configfs is mounted."""
    try:
        with open("/proc/mounts") as f:
            for line in f:
                if "configfs" in line and "/sys/kernel/config" in line:
                    return True
        return False
    except Exception:
        return False


def check_gadget_configured() -> Tuple[bool, str | None]:
    """Check if USB gadget is configured in configfs."""
    gadget_base = Path("/sys/kernel/config/usb_gadget")
    if not gadget_base.exists():
        return False, None

    gadgets = [d for d in gadget_base.iterdir() if d.is_dir()]
    if not gadgets:
        return False, None

    return True, gadgets[0].name


def check_hid_function(gadget_name: str) -> bool:
    """Check if HID function exists in gadget."""
    hid_path = Path(f"/sys/kernel/config/usb_gadget/{gadget_name}/functions/hid.usb0")
    return hid_path.exists()


def check_gadget_bound(gadget_name: str) -> Tuple[bool, str | None]:
    """Check if gadget is bound to UDC."""
    udc_file = Path(f"/sys/kernel/config/usb_gadget/{gadget_name}/UDC")
    if not udc_file.exists():
        return False, None
    try:
        content = udc_file.read_text().strip()
        if content:
            return True, content
        return False, None
    except Exception:
        return False, None


def main() -> int:
    result = CheckResult()

    print("=== dictacode HID Hardware Check ===")
    print()

    # 1. Boot Configuration
    print("Boot Configuration:")
    config_txt, distro_type = find_config_txt()

    if config_txt:
        result.ok(f"{config_txt} exists ({distro_type} layout)")

        if check_file_contains(config_txt, "dtoverlay=dwc2"):
            result.ok("dtoverlay=dwc2 configured")
        else:
            result.fail(
                "dtoverlay=dwc2 not found in config.txt",
                f"Add 'dtoverlay=dwc2' to {config_txt}",
            )
    else:
        result.fail("config.txt not found", "Check Pi boot partition mount")
    print()

    # 2. Module Configuration
    print("Module Configuration:")

    dwc2_configured, dwc2_location = check_modules_configured("dwc2")
    if dwc2_configured:
        result.ok(f"dwc2 configured in {dwc2_location}")
    else:
        result.warn("dwc2 not in module autoload (may be loaded via overlay)")

    libcomp_configured, libcomp_location = check_modules_configured("libcomposite")
    if libcomp_configured:
        result.ok(f"libcomposite configured in {libcomp_location}")
    else:
        result.warn(
            "libcomposite not in module autoload (loaded manually or by script)"
        )
    print()

    # 3. Kernel Modules
    print("Kernel Modules:")

    if check_dwc2_active():
        result.ok("dwc2 active (UDC available or module loaded)")
    else:
        result.fail("dwc2 not active", "Reboot after configuring dtoverlay=dwc2")

    if check_module_loaded("libcomposite"):
        result.ok("libcomposite module loaded")
    else:
        result.fail("libcomposite module not loaded", "Run: sudo modprobe libcomposite")
    print()

    # 4. ConfigFS
    print("ConfigFS:")

    if check_configfs_mounted():
        result.ok("/sys/kernel/config mounted")
    else:
        result.fail(
            "configfs not mounted",
            "Run: sudo mount -t configfs none /sys/kernel/config",
        )
    print()

    # 5. USB Device Controller
    print("USB Device Controller:")

    udc_name = get_udc_name()
    if udc_name:
        result.ok(f"UDC available: {udc_name}")
    else:
        result.fail(
            "No UDC found in /sys/class/udc/",
            "Ensure dwc2 module is loaded and hardware supports USB gadget",
        )
    print()

    # 6. USB Gadget
    print("USB Gadget:")

    gadget_exists, gadget_name = check_gadget_configured()
    if gadget_exists:
        result.ok(f"Gadget configured: {gadget_name}")

        if check_hid_function(gadget_name):
            result.ok("HID function (hid.usb0) exists")
        else:
            result.fail(
                "HID function not configured",
                "Run gadget setup script to create HID function",
            )

        bound, bound_udc = check_gadget_bound(gadget_name)
        if bound:
            result.ok(f"Gadget bound to UDC: {bound_udc}")
        else:
            result.fail(
                "Gadget not bound to UDC",
                f"Run: echo '{udc_name}' | sudo tee /sys/kernel/config/usb_gadget/{gadget_name}/UDC",
            )
    else:
        result.fail(
            "No gadget configured in /sys/kernel/config/usb_gadget/",
            "Run gadget setup script",
        )
    print()

    # 7. HID Device
    print("HID Device:")

    hidg0 = Path("/dev/hidg0")
    if hidg0.exists():
        result.ok("/dev/hidg0 exists")

        # Check if writable
        if os.access(hidg0, os.W_OK):
            result.ok("/dev/hidg0 is writable")
        else:
            result.warn(
                "/dev/hidg0 not writable by current user (run as root or add to group)"
            )
    else:
        result.fail("/dev/hidg0 does not exist", "Configure and bind USB gadget first")
    print()

    # Summary
    print("=== Summary ===")

    if result.issues == 0:
        print("Status: READY")
        if result.warnings > 0:
            print(f"Warnings: {result.warnings}")
        return 0
    else:
        print("Status: NOT READY")
        print(f"Issues: {result.issues}")
        if result.warnings > 0:
            print(f"Warnings: {result.warnings}")

        if result.next_steps:
            print()
            print("Next steps:")
            for i, step in enumerate(result.next_steps, 1):
                print(f"  {i}. {step}")

        return 1


if __name__ == "__main__":
    sys.exit(main())
