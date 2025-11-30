# Debian Packages

This directory contains Debian package definitions for dictacode components.

## Packages

| Package | Target | Description |
|---------|--------|-------------|
| `dictacode-core` | All | Base package: creates user and directories |
| `dictacode-hid` | Pi Zero 2 W | USB HID keyboard gadget setup |
| `dictacode-stt` | Pi 5 | Speech-to-text engine and whisper.cpp installer |

## Installation Order

```bash
# 1. Install base package (all devices)
sudo dpkg -i dictacode-core_*.deb

# 2a. On Pi 5 (STT Engine):
sudo dpkg -i dictacode-stt_*.deb
sudo apt-get install -f  # Install recommended deps
sudo /opt/dictacode/stt/install-whisper.sh
sudo systemctl enable --now dictacode-stt

# 2b. On Pi Zero 2 W (HID Gadget):
sudo dpkg -i dictacode-hid_*.deb
sudo reboot  # Required for USB gadget
```

## Building

Use the build script from the packaging directory:

```bash
cd ops/packaging
./build-deb.sh dictacode-core
./build-deb.sh dictacode-hid
./build-deb.sh dictacode-stt
```

Built packages are placed in `ops/packaging/dist/`.

## Package Structure

```
/opt/dictacode/                    # Base (dictacode-core)
    hid/                           # dictacode-hid
        setup_hid_gadget.sh
    stt/                           # dictacode-stt
        install-whisper.sh
        pipeline_stream.py
    whisper.cpp/                   # Built by install-whisper.sh

/etc/dictacode/
    keymap.conf                    # dictacode-hid
    stt.conf                       # dictacode-stt
```

## Package Details

### dictacode-core

Base package that prepares the system for other dictacode components.

**Creates:**
- `dictacode` system user
- `/opt/dictacode/` directory
- `/var/lib/dictacode/` for runtime data
- `/etc/dictacode/` for configuration

**Dependencies:** `adduser`, `systemd`

### dictacode-hid

Configures Pi Zero 2 W as USB HID keyboard gadget.

**Installs:**
- `/opt/dictacode/hid/setup_hid_gadget.sh` - Creates USB gadget via ConfigFS
- `/lib/systemd/system/dictacode-hid-gadget.service` - Runs setup at boot
- `/etc/udev/rules.d/99-dictacode-hid.rules` - Device permissions
- `/etc/dictacode/keymap.conf` - Keyboard layout config

**Post-install actions:**
- Adds `dtoverlay=dwc2` to boot config
- Adds `dwc2` and `libcomposite` to /etc/modules
- Enables and starts systemd service

**Requires reboot** after first install.

**Dependencies:** `dictacode-core`, `python3`, `python3-venv`, `systemd`

### dictacode-stt

Speech-to-text pipeline for Pi 5.

**Installs:**
- `/opt/dictacode/stt/install-whisper.sh` - Downloads and builds whisper.cpp
- `/lib/systemd/system/dictacode-stt.service` - STT pipeline service
- `/etc/dictacode/stt.conf` - STT configuration (model, language, UART)

**Post-install steps:**
1. Edit `/etc/dictacode/stt.conf` (optional - select model, language)
2. Run `sudo /opt/dictacode/stt/install-whisper.sh`
3. Start service: `sudo systemctl enable --now dictacode-stt`

**Dependencies:** `dictacode-core`, `python3`, `python3-venv`, `alsa-utils`, `libportaudio2`

**Recommends:** `build-essential`, `cmake`, `git`, `portaudio19-dev`

## Configuration Files

### /etc/dictacode/keymap.conf

```ini
# Available: en_us, de_de
keymap=en_us
```

### /etc/dictacode/stt.conf

```ini
# Whisper model: tiny, base, small, medium, large
model=tiny

# Language for transcription
language=en

# UART settings for HID output
uart_device=/dev/serial0
uart_baud=115200
```

---

**Note:** This README is not included in the built packages.
