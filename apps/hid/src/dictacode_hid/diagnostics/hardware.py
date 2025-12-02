"""Hardware diagnostic checks for HID gadget.

Checks boot config, kernel modules, configfs, USB gadget, and HID device.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from .base import DiagnosticResult


def find_config_txt() -> Tuple[Optional[Path], str]:
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
    """Check if file contains pattern (ignoring comments)."""
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
    udc_path = Path("/sys/class/udc")
    if udc_path.exists() and list(udc_path.iterdir()):
        return True
    return check_module_loaded("dwc2")


def get_udc_name() -> Optional[str]:
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


def check_gadget_configured() -> Tuple[bool, Optional[str]]:
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


def check_gadget_bound(gadget_name: str) -> Tuple[bool, Optional[str]]:
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


def run_hardware_checks(quick: bool = False) -> DiagnosticResult:
    """Run all HID hardware diagnostic checks.

    Args:
        quick: If True, only run essential checks for systemd ExecStartPre.
    """
    result = DiagnosticResult(component="hid")

    # 1. Boot Configuration
    config_txt, distro_type = find_config_txt()

    if config_txt:
        if check_file_contains(config_txt, "dtoverlay=dwc2"):
            result.ok("boot_config", "dtoverlay=dwc2 configured")
        else:
            result.fail(
                "boot_config",
                "dtoverlay=dwc2 not found in config.txt",
                f"Add 'dtoverlay=dwc2' to {config_txt}",
            )
    else:
        result.fail(
            "boot_config",
            "config.txt not found",
            "Check Pi boot partition mount",
        )

    # 2. Kernel Modules
    if check_dwc2_active():
        result.ok("kernel_dwc2", "dwc2 active (UDC available)")
    else:
        result.fail(
            "kernel_dwc2",
            "dwc2 not active",
            "Reboot after configuring dtoverlay=dwc2",
        )

    if check_module_loaded("libcomposite"):
        result.ok("kernel_libcomposite", "libcomposite module loaded")
    else:
        result.fail(
            "kernel_libcomposite",
            "libcomposite module not loaded",
            "Run: sudo modprobe libcomposite",
        )

    # 3. ConfigFS
    if check_configfs_mounted():
        result.ok("configfs_mount", "/sys/kernel/config mounted")
    else:
        result.fail(
            "configfs_mount",
            "configfs not mounted",
            "Run: sudo mount -t configfs none /sys/kernel/config",
        )

    # 4. UDC
    udc_name = get_udc_name()
    if udc_name:
        result.ok("udc_available", f"UDC available: {udc_name}")
    else:
        result.fail(
            "udc_available",
            "No UDC found in /sys/class/udc/",
            "Ensure dwc2 module is loaded and hardware supports USB gadget",
        )

    # 5. USB Gadget
    gadget_exists, gadget_name = check_gadget_configured()
    if gadget_exists:
        result.ok("gadget_configured", f"Gadget configured: {gadget_name}")

        if check_hid_function(gadget_name):
            result.ok("gadget_hid_function", "HID function (hid.usb0) exists")
        else:
            result.fail(
                "gadget_hid_function",
                "HID function not configured",
                "Run gadget setup script to create HID function",
            )

        bound, bound_udc = check_gadget_bound(gadget_name)
        if bound:
            result.ok("gadget_bound", f"Gadget bound to UDC: {bound_udc}")
        else:
            result.fail(
                "gadget_bound",
                "Gadget not bound to UDC",
                f"Run: echo '{udc_name}' | sudo tee /sys/kernel/config/usb_gadget/{gadget_name}/UDC",
            )
    else:
        result.fail(
            "gadget_configured",
            "No gadget configured in /sys/kernel/config/usb_gadget/",
            "Run gadget setup script",
        )

    # 6. HID Device
    hidg0 = Path("/dev/hidg0")
    if hidg0.exists():
        result.ok("hid_device_exists", "/dev/hidg0 exists")

        if os.access(hidg0, os.W_OK):
            result.ok("hid_device_writable", "/dev/hidg0 is writable")
        else:
            result.warn(
                "hid_device_writable",
                "/dev/hidg0 not writable by current user",
                "Run as root or add user to appropriate group",
            )
    else:
        result.fail(
            "hid_device_exists",
            "/dev/hidg0 does not exist",
            "Configure and bind USB gadget first",
        )

    return result


def run_uart_checks(uart_device: str = "/dev/serial0") -> DiagnosticResult:
    """Run UART device checks."""
    result = DiagnosticResult(component="hid")

    uart_path = Path(uart_device)
    if uart_path.exists():
        result.ok("uart_exists", f"{uart_device} exists")

        if os.access(uart_path, os.R_OK):
            result.ok("uart_readable", f"{uart_device} is readable")
        else:
            result.warn(
                "uart_readable",
                f"{uart_device} not readable by current user",
                "Run as root or add user to dialout group",
            )
    else:
        result.fail(
            "uart_exists",
            f"{uart_device} does not exist",
            "Check UART configuration and device path",
        )

    return result
