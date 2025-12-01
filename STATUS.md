# dictacode - Project Status

Last updated: 2025-11-30

## Architecture Overview

```
┌─────────────────┐      UART       ┌─────────────────┐      USB HID      ┌──────────┐
│     Pi 5        │  ───────────►   │   Pi Zero 2 W   │  ──────────────►  │ Target   │
│  (STT Engine)   │   115200 baud   │  (HID Gadget)   │    Keyboard       │   PC     │
│                 │   /dev/serial0  │                 │   /dev/hidg0      │          │
└─────────────────┘                 └─────────────────┘                   └──────────┘
      ▲
      │ Audio
┌─────┴─────┐
│   RØDE    │
│ VideoMic  │
│   NTG     │
└───────────┘
```

---

## Implemented Features

### Pi5 - Speech-to-Text Sandbox

| Component | File | Status |
|-----------|------|--------|
| Audio Recording | `apps/stt/sandbox/record.py` | WORKING |
| Transcription | `apps/stt/sandbox/transcribe.py` | WORKING |
| UART Transmission | `apps/stt/sandbox/send_uart.py` | WORKING |
| Full Pipeline | `apps/stt/sandbox/pipeline.py` | WORKING |

**Details:**
- RØDE VideoMic NTG at `hw:0,0` (native 48kHz stereo → resampled to 16kHz mono)
- whisper.cpp with `ggml-tiny.bin` model
- UART at `/dev/serial0` @ 115200 baud
- Continuous voice activity detection and transcription

### Pi Zero 2 W - HID Gadget Sandbox

| Component | File | Status |
|-----------|------|--------|
| Hardware Check | `apps/hid/sandbox/check_hardware.py` | WORKING |
| UART→HID Bridge | `apps/hid/sandbox/recv_uart_type.py` | WORKING |

**Details:**
- USB HID gadget via ConfigFS
- 8-byte HID keyboard reports
- US keyboard layout (basic ASCII + shifted characters)

### Debian Package: dictacode-hid

| Component | Path | Status |
|-----------|------|--------|
| Package Control | `ops/packaging/debian/dictacode-hid/DEBIAN/control` | DONE |
| Post-Install Script | `ops/packaging/debian/dictacode-hid/DEBIAN/postinst` | DONE |
| Gadget Setup Script | `ops/packaging/debian/dictacode-hid/opt/dictacode/setup_hid_gadget.sh` | DONE |
| systemd Service | `ops/packaging/debian/dictacode-hid/etc/systemd/system/dictacode-hid-gadget.service` | DONE |
| udev Rules | `ops/packaging/debian/dictacode-hid/etc/udev/rules.d/99-dictacode-hid.rules` | DONE |

**Package installs and configures:**
- Boot parameters (`dtoverlay=dwc2`)
- Kernel modules (`dwc2`, `libcomposite`)
- USB gadget creation at boot
- `/dev/hidg0` device permissions (group `dictacode`)

### Build System

| Component | File | Status |
|-----------|------|--------|
| Debian Package Builder | `ops/packaging/build-deb.sh` | WORKING |

### End-to-End Pipeline

**PROVEN WORKING** - Full speech-to-text-to-keyboard pipeline tested:
1. Spoke into microphone on Pi5
2. whisper.cpp transcribed speech
3. Text sent via UART to Pi Zero
4. Pi Zero typed text via USB HID
5. Text appeared on connected PC

---

## Todo List

### Priority 1: Keymap System

- [ ] Design keymap architecture
  - Keymaps stored on Pi Zero
  - User switches layout on target PC manually
  - Pi Zero must send correct scancodes for selected layout
- [ ] Implement German (de) keymap
  - Handle umlauts (ä, ö, ü, ß)
  - Handle shifted/AltGr characters
- [ ] Implement English (en) keymap (refactor existing US layout)
- [ ] Create CLI tool to switch keymaps
  - `dictacode-keymap list`
  - `dictacode-keymap set de`
  - `dictacode-keymap get`
- [ ] Persist keymap selection across reboots

### Priority 2: Production Code

- [ ] Move Pi5 STT from sandbox to production module (`apps/stt/src/`)
- [ ] Move Pi0 HID from sandbox to production module (`apps/hid/src/`)
- [ ] Create `dictacode-stt` Debian package for Pi5
- [ ] Add proper error handling and logging
- [ ] Add systemd service for STT pipeline on Pi5

### Priority 3: Model Options

- [ ] Support multiple whisper.cpp models (tiny, base, small)
- [ ] CLI/config to select model
- [ ] Document performance vs accuracy tradeoffs

### Priority 4: Backend & Control

- [ ] Design backend API architecture
- [ ] Implement configuration management
- [ ] Web control center (future)
  - Keymap selection
  - Model selection
  - Status monitoring
  - Start/stop pipeline

### Priority 5: Reliability

- [ ] Handle UART disconnection/reconnection
- [ ] Handle USB disconnection/reconnection
- [ ] Add watchdog for pipeline health
- [ ] Graceful shutdown handling

### Priority 6: Documentation

- [ ] Hardware assembly guide
- [ ] Installation guide
- [ ] User manual
- [ ] API documentation (when backend exists)

---

## Known Issues

1. **Keymap limited to US layout** - Only basic ASCII characters supported currently
2. **No error recovery** - Pipeline stops on error, requires manual restart
3. **stdout buffering** - Python output sometimes delayed when piped

---

## Hardware Inventory

| Device | Role | Connection |
|--------|------|------------|
| Raspberry Pi 5 | STT Engine | UART TX → Pi0 RX |
| Raspberry Pi Zero 2 W | HID Gadget | USB data port → Target PC |
| RØDE VideoMic NTG | Audio Input | USB → Pi5 |

**UART Wiring:**
- Pi5 GPIO14 (TX) → Pi0 GPIO15 (RX)
- Pi5 GPIO15 (RX) → Pi0 GPIO14 (TX)
- Common GND
