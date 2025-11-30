# dictacode

Speech-to-text dictation system using Raspberry Pi hardware as a USB HID keyboard.

## Architecture

```
+------------------+      UART       +------------------+      USB HID      +----------+
|      Pi 5        |  ------------>  |   Pi Zero 2 W    |  --------------> | Target   |
|  (STT Engine)    |   115200 baud   |  (HID Gadget)    |    Keyboard      |   PC     |
|                  |   /dev/serial0  |                  |   /dev/hidg0     |          |
+------------------+                 +------------------+                  +----------+
      ^
      | Audio
+-----+-----+
|   RODE    |
| VideoMic  |
|   NTG     |
+-----------+
```

**How it works:**
1. Speak into microphone connected to Pi 5
2. whisper.cpp transcribes speech to text
3. Text sent via UART to Pi Zero 2 W
4. Pi Zero types text as USB keyboard to target PC

## Quick Start

### Bootstrap (Fresh Pi)

Run the bootstrap script on a fresh Raspberry Pi OS installation:

```bash
# Pi 5 (STT Engine)
curl -sSL https://raw.githubusercontent.com/cprima-homelab/dictacode/exploration/tools/bootstrap.sh | sudo sh -s -- -t pi5

# Pi Zero 2 W (HID Gadget)
curl -sSL https://raw.githubusercontent.com/cprima-homelab/dictacode/exploration/tools/bootstrap.sh | sudo sh -s -- -t pi0
```

**Options:**
- `-t pi5|pi0` - Target device (required)
- `-U` - Upgrade system first (apt dist-upgrade)
- `-v 0.1.0` - Specify package version

Bootstrap downloads and installs:
- `dictacode-core` - Creates user, directories, groups
- `dictacode-stt` (Pi 5) - STT pipeline and whisper.cpp installer
- `dictacode-hid` (Pi Zero) - USB HID gadget setup

### Pi Zero 2 W (HID Gadget)

After bootstrap:

```bash
# Reboot to enable HID gadget
sudo reboot

# Verify HID device exists
ls -la /dev/hidg0

# Set keyboard layout (default: en_us)
sudo dictacode-keymap set de_de  # for German layout
```

### Pi 5 (STT Engine)

After bootstrap:

```bash
# Build whisper.cpp (required once)
sudo /opt/dictacode/stt/install-whisper.sh

# Start the STT service
sudo systemctl enable --now dictacode-stt
```

**Manual testing (without service):**
```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and run
git clone https://github.com/cprima-homelab/dictacode.git
cd dictacode/apps/stt
uv sync
uv run sandbox/pipeline_stream.py
```

## Packages

| Package | Target | Description |
|---------|--------|-------------|
| `dictacode-core` | All | Base: creates user, directories, groups |
| `dictacode-hid` | Pi Zero | USB HID keyboard gadget |
| `dictacode-stt` | Pi 5 | Speech-to-text engine |

Packages are available as [GitHub Releases](https://github.com/cprima-homelab/dictacode/releases).

## Components

| Directory | Description |
|-----------|-------------|
| `apps/stt/` | Speech-to-text engine (Pi 5) |
| `apps/hid/` | USB HID keyboard bridge (Pi Zero) |
| `ops/packaging/` | Debian packages |
| `tools/` | Bootstrap script |

## Configuration

### /etc/dictacode/stt.conf (Pi 5)

```ini
model=tiny          # whisper model: tiny, base, small, medium, large
language=en         # transcription language
uart_device=/dev/serial0
uart_baud=115200
```

### /etc/dictacode/keymap.conf (Pi Zero)

```ini
keymap=en_us        # keyboard layout: en_us, de_de
```

## Keyboard Layouts

The Pi Zero must be configured to match the target PC's keyboard layout.

```bash
# List available layouts
dictacode-keymap list

# Set layout
sudo dictacode-keymap set de_de

# Get current layout
dictacode-keymap get
```

Available layouts:
- `en_us` - US English (QWERTY)
- `de_de` - German (QWERTZ)

## Hardware Requirements

- Raspberry Pi 5 (4GB+ recommended for STT processing)
- Raspberry Pi Zero 2 W (USB HID gadget)
- USB microphone (tested: RODE VideoMic NTG)
- UART connection between Pi 5 and Pi Zero (3 wires: TX, RX, GND)

See [hardware/bill-of-materials.md](hardware/bill-of-materials.md) for detailed parts list.

## License

CC BY 4.0

Maintained by **cprima-homelab**.
