# dictacode Testing Checklist

## Test Devices

| Device | Hostname | SSH Alias | Role | Platform |
|--------|----------|-----------|------|----------|
| Raspberry Pi 5 | `dictacode-stt` | `dictacode-stt` | STT Engine | ARM64 |
| Raspberry Pi Zero 2 W | `dictacode-hid` | `dictacode-hid` | HID Gadget | ARM32 |

**Connection:** Pi5 TX → Pi0 RX via UART (`/dev/serial0` @ 115200 baud)

---

## ⚠️ IMPORTANT: Deployment Method

**ALL testing uses Debian packages (.deb) - no direct code deployment**

This ensures:
- Configuration files come from canonical templates (`ops/packaging/templates/`)
- System files are properly installed and validated
- Checksums are verified during build
- Consistent deployment across environments

**Local development with `uv`:**
```bash
# On your local machine, uv should be in PATH
cd apps/stt
uv run pytest tests/
```

---

## Deployment Workflow (Debian Packages)

**Use for ALL changes** - code, config, or system files.

```bash
# 1. Local testing first (MANDATORY)
cd apps/stt
uv run pytest tests/

# 2. Build packages locally
cd ops/packaging
./build-deb.sh                    # Build all packages
# Or build specific:
./build-deb.sh dictacode-stt
./build-deb.sh dictacode-hid

# 3. Validate artifacts (optional but recommended)
./validate-artifacts.sh

# 4. Copy to devices (use -O for legacy SCP)
scp -O dist/dictacode-core.deb dictacode-stt:/tmp/
scp -O dist/dictacode-stt.deb dictacode-stt:/tmp/
scp -O dist/dictacode-core.deb dictacode-hid:/tmp/
scp -O dist/dictacode-hid.deb dictacode-hid:/tmp/

# 5. Install on devices (use apt install to auto-resolve dependencies)
ssh dictacode-stt "sudo apt install -y /tmp/dictacode-core.deb /tmp/dictacode-stt.deb"
ssh dictacode-hid "sudo apt install -y /tmp/dictacode-core.deb /tmp/dictacode-hid.deb"

# 6. Restart services
ssh dictacode-stt "sudo systemctl daemon-reload && sudo systemctl restart dictacode-stt"
ssh dictacode-hid "sudo systemctl daemon-reload && sudo systemctl restart dictacode-hid"

# 7. Verify installation
ssh dictacode-stt "systemctl status dictacode-stt --no-pager"
ssh dictacode-hid "systemctl status dictacode-hid --no-pager"
```

### Package Contents

| Package | Contents |
|---------|----------|
| `dictacode-core` | `compatibility.json`, shared assets |
| `dictacode-stt` | `stt.conf`, `stt.d/`, systemd units, audio config |
| `dictacode-hid` | `hid.conf`, `keymap.conf`, `hid.d/`, systemd units |

### Template Management (v0.3.2+)

All configuration templates are sourced from `ops/packaging/templates/`:
- `stt.conf` - STT service configuration
- `hid.conf` - HID service configuration
- `keymap.conf` - Keyboard mapping

Build scripts validate template checksums against canonical source.

---

## Verification Checklist

### After Deployment

- [ ] Services started successfully
  ```bash
  ssh dictacode-stt "systemctl is-active dictacode-stt"
  ssh dictacode-hid "systemctl is-active dictacode-hid"
  ```

- [ ] No errors in logs (last 50 lines)
  ```bash
  ssh dictacode-stt "sudo journalctl -u dictacode-stt -n 50 --no-pager"
  ssh dictacode-hid "sudo journalctl -u dictacode-hid -n 50 --no-pager"
  ```

- [ ] State transitions working (v0.2.3+)
  ```bash
  # Check for state transition logs
  ssh dictacode-stt "sudo journalctl -u dictacode-stt --no-pager | grep 'State transition'"
  ```

- [ ] UART link established
  ```bash
  ssh dictacode-stt "ls -la /dev/serial0"
  ssh dictacode-hid "ls -la /dev/serial0"
  ```

- [ ] HID device available (Pi0)
  ```bash
  ssh dictacode-hid "ls -la /dev/hidg0"
  ```

---

## Diagnostics

### Service Status

```bash
# Quick health check
ssh dictacode-stt "sudo systemctl status dictacode-stt --no-pager"
ssh dictacode-hid "sudo systemctl status dictacode-hid --no-pager"

# Follow live logs
ssh dictacode-stt "sudo journalctl -u dictacode-stt -f"
ssh dictacode-hid "sudo journalctl -u dictacode-hid -f"

# View recent errors only
ssh dictacode-stt "sudo journalctl -u dictacode-stt -p err --no-pager -n 20"
```

### Device Prerequisites

```bash
# Pi5 - Check whisper installation
ssh dictacode-stt "which whisper-cli && echo 'Whisper OK' || echo 'Whisper MISSING'"
ssh dictacode-stt "test -f /opt/dictacode/models/ggml-tiny.bin && echo 'Model OK' || echo 'Model MISSING'"

# Pi5 - Check UART permissions
ssh dictacode-stt "groups dictacode | grep dialout && echo 'Permissions OK' || echo 'Add to dialout group'"

# Pi5 - Check package installed
ssh dictacode-stt "dpkg -s dictacode-stt >/dev/null 2>&1 && echo 'Package OK' || echo 'Package MISSING'"

# Pi0 - Check HID gadget service
ssh dictacode-hid "systemctl is-active dictacode-hid-gadget.service"

# Pi0 - Check package installed
ssh dictacode-hid "dpkg -s dictacode-hid >/dev/null 2>&1 && echo 'Package OK' || echo 'Package MISSING'"
```

### Audio Testing (Pi5)

```bash
# List audio input devices
ssh dictacode-stt "arecord -l"

# Test 5-second recording
ssh dictacode-stt "arecord -D hw:3,0 -f S16_LE -r 16000 -d 5 /tmp/test.wav"

# Test whisper transcription (if whisper-cli in PATH)
ssh dictacode-stt "whisper-cli -m /opt/dictacode/models/ggml-tiny.bin /tmp/test.wav"
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check systemd unit file syntax
ssh dictacode-stt "systemd-analyze verify dictacode-stt.service"

# Check ExecStart path
ssh dictacode-stt "cat /lib/systemd/system/dictacode-stt.service | grep ExecStart"

# Check working directory
ssh dictacode-stt "cat /lib/systemd/system/dictacode-stt.service | grep WorkingDirectory"

# Check config file exists
ssh dictacode-stt "test -f /etc/dictacode/stt.conf && echo 'Config OK' || echo 'Config MISSING'"

# Check package is installed correctly
ssh dictacode-stt "dpkg --verify dictacode-stt"
```

### Systemd Start Timeout

If `systemctl restart` times out but service is actually running:

```bash
# Check if process is running despite timeout
ssh dictacode-stt "ps aux | grep dictacode"

# Check logs - service may be running in state machine loop
ssh dictacode-stt "sudo journalctl -u dictacode-stt -n 50 --no-pager | grep -E 'State|transition|ready'"

# For Type=notify services, timeout means READY=1 wasn't received in time
# Service may still be functional - check state transitions in logs
```

**Common cause**: Service stuck in HANDSHAKE_INIT waiting for peer response.

### Import Errors

```bash
# Verify package installation
ssh dictacode-stt "dpkg -L dictacode-stt | grep python"

# Check installed version
ssh dictacode-stt "dpkg -s dictacode-stt | grep Version"

# Reinstall package
ssh dictacode-stt "sudo apt install --reinstall -y /tmp/dictacode-stt.deb"
```

### UART Communication Issues

```bash
# Check if device exists on both ends
ssh dictacode-stt "ls -la /dev/serial0"
ssh dictacode-hid "ls -la /dev/serial0"

# Check permissions
ssh dictacode-stt "sudo chmod 666 /dev/serial0"
ssh dictacode-hid "sudo chmod 666 /dev/serial0"

# Test raw UART (Pi5 → Pi0)
# Terminal 1:
ssh dictacode-hid "cat /dev/serial0"
# Terminal 2:
ssh dictacode-stt "echo 'test' > /dev/serial0"
```

---

## End-to-End Test

### Manual Pipeline Test

```bash
# 1. Start both services
ssh dictacode-stt "sudo systemctl restart dictacode-stt"
ssh dictacode-hid "sudo systemctl restart dictacode-hid"

# 2. Monitor logs in separate terminals
# Terminal 1 (STT):
ssh dictacode-stt "sudo journalctl -u dictacode-stt -f"

# Terminal 2 (HID):
ssh dictacode-hid "sudo journalctl -u dictacode-hid -f"

# 3. Speak into microphone on Pi5

# 4. Expected flow:
# - STT logs: "Recording started"
# - STT logs: "Transcription: <your words>"
# - STT logs: "Sending text via UART"
# - HID logs: "Received text: <your words>"
# - HID logs: "Typing on HID device"
# - Text appears on computer connected to Pi0
```

---

## Quick Reference

### File Locations

**Local Development:**
- Source: `apps/{stt,hid}/src/`
- Tests: `apps/{stt,hid}/tests/`
- Templates: `ops/packaging/templates/`
- Package specs: `ops/packaging/debian/`

**On Device (Debian Package):**
- Service files: `/lib/systemd/system/dictacode-{stt,hid}.service`
- Config files: `/etc/dictacode/{stt,hid}.conf`
- Drop-in dirs: `/etc/dictacode/{stt,hid}.d/`
- Shared data: `/opt/dictacode/shared/`
- State directory: `/var/lib/dictacode/`
- Runtime directory: `/run/dictacode-{stt,hid}/`
- Logs: `journalctl -u dictacode-{stt,hid}`

### Common Commands

```bash
# Build and deploy (full workflow) - use scp -O for legacy protocol
./ops/packaging/build-deb.sh && \
scp -O ops/packaging/dist/*.deb dictacode-stt:/tmp/ && \
ssh dictacode-stt "sudo apt install -y /tmp/dictacode-*.deb && sudo systemctl daemon-reload && sudo systemctl restart dictacode-stt"

# Note: -O flag required for SCP to Raspberry Pi (uses legacy SCP protocol)

# View last 100 log lines
ssh dictacode-stt "sudo journalctl -u dictacode-stt -n 100 --no-pager"

# Clear failed state
ssh dictacode-stt "sudo systemctl reset-failed dictacode-stt"

# Stop service
ssh dictacode-stt "sudo systemctl stop dictacode-stt"

# Check installed package version
ssh dictacode-stt "dpkg -l | grep dictacode"

# View installed config
ssh dictacode-stt "cat /etc/dictacode/stt.conf"
```
