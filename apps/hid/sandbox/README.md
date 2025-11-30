# HID Sandbox Scripts

Standalone scripts to verify and test Pi Zero USB HID gadget setup.

## Prerequisites

From `apps/hid/`:

```bash
cd apps/hid
uv sync
```

## Scripts

### check_hardware.py - Verify HID Prerequisites

Checks all requirements for USB HID gadget operation:

```bash
uv run sandbox/check_hardware.py
```

Verifies:
- Boot config (`dtoverlay=dwc2` in config.txt)
- Module configuration (dwc2, libcomposite)
- Kernel modules loaded
- ConfigFS mounted
- USB gadget configured
- HID function exists
- `/dev/hidg0` device present

Exit code: 0 = READY, 1 = NOT READY

## USB HID Gadget Setup Reference

Based on https://www.isticktoit.net/?p=1383 (adapted for modern Pi OS)

### 1. Enable dwc2 overlay

```bash
# Modern Pi OS (Bookworm+)
echo "dtoverlay=dwc2" | sudo tee -a /boot/firmware/config.txt

# Legacy Pi OS
echo "dtoverlay=dwc2" | sudo tee -a /boot/config.txt
```

### 2. Configure modules

```bash
echo "dwc2" | sudo tee -a /etc/modules
echo "libcomposite" | sudo tee -a /etc/modules
```

### 3. Reboot

```bash
sudo reboot
```

### 4. Create gadget (run as root after each boot)

The gadget configuration is volatile - it must be recreated after each reboot.
A setup script should be run at boot via systemd or rc.local.
