# dictacode Testing Checklist

## Test Devices

| Device | Hostname | SSH Alias | Role | Platform |
|--------|----------|-----------|------|----------|
| Raspberry Pi 5 | `dictacode-stt` | `dictacode-stt` | STT Engine | ARM64 |
| Raspberry Pi Zero 2 W | `dictacode-hid` | `dictacode-hid` | HID Gadget | ARM32 |

**Connection:** Pi5 TX → Pi0 RX via UART (`/dev/serial0` @ 115200 baud)

---

## Development Testing Workflows

### Quick Development (Code Changes Only)

**Use when:** Only Python code in `~/dictacode` changed (no system files)

```bash
# 1. Local testing first (MANDATORY)
cd apps/stt
uv run pytest tests/

# 2. Push to GitHub
git add .
git commit -m "Your changes"
git push origin exploration

# 3. Pull on devices
ssh dictacode-stt "cd ~/dictacode && git pull"
ssh dictacode-hid "cd ~/dictacode && git pull"

# 4. Restart services (uses code from ~/dictacode)
ssh dictacode-stt "sudo systemctl restart dictacode-stt"
ssh dictacode-hid "sudo systemctl restart dictacode-hid"

# 5. Check logs
ssh dictacode-stt "sudo journalctl -u dictacode-stt -n 50 --no-pager"
ssh dictacode-hid "sudo journalctl -u dictacode-hid -n 50 --no-pager"
```

---

### System Changes (Debian Package Deployment)

**MANDATORY when:** Changes to files outside `~/dictacode`:
- systemd service files (`*.service`)
- Configuration files (`/etc/dictacode/*`)
- System scripts (`/usr/bin/*`, `/opt/dictacode/*`)
- Boot configuration (`/boot/*`)

```bash
# 1. Local testing first (MANDATORY)
cd apps/stt
uv run pytest tests/

# 2. Update package version in control files
# Edit: ops/packaging/debian/dictacode-stt/DEBIAN/control
# Edit: ops/packaging/debian/dictacode-hid/DEBIAN/control

# 3. Build packages locally
cd ops/packaging
./build-deb.sh dictacode-stt
./build-deb.sh dictacode-hid

# 4. Copy to devices (use -O for legacy SCP)
scp -O dist/dictacode-stt_*.deb dictacode-stt:/tmp/
scp -O dist/dictacode-hid_*.deb dictacode-hid:/tmp/

# 5. Install on devices
ssh dictacode-stt "sudo dpkg -i /tmp/dictacode-stt_*.deb"
ssh dictacode-hid "sudo dpkg -i /tmp/dictacode-hid_*.deb"

# 6. Restart services
ssh dictacode-stt "sudo systemctl daemon-reload && sudo systemctl restart dictacode-stt"
ssh dictacode-hid "sudo systemctl daemon-reload && sudo systemctl restart dictacode-hid"

# 7. Verify installation
ssh dictacode-stt "systemctl status dictacode-stt --no-pager"
ssh dictacode-hid "systemctl status dictacode-hid --no-pager"
```

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
ssh dictacode-stt "test -f ~/dictacode/apps/stt/whisper.cpp/build/bin/whisper-cli && echo 'Whisper OK' || echo 'Whisper MISSING'"
ssh dictacode-stt "test -f ~/dictacode/apps/stt/models/ggml-tiny.bin && echo 'Model OK' || echo 'Model MISSING'"

# Pi5 - Check UART
ssh dictacode-stt "groups dictacode | grep dialout && echo 'Permissions OK' || echo 'Add to dialout group'"

# Pi0 - Check HID gadget service
ssh dictacode-hid "systemctl is-active dictacode-hid-gadget.service"
```

### Audio Testing (Pi5)

```bash
# List audio input devices
ssh dictacode-stt "arecord -l"

# Test 5-second recording
ssh dictacode-stt "arecord -D hw:3,0 -f S16_LE -r 16000 -d 5 /tmp/test.wav"

# Test whisper transcription
ssh dictacode-stt "~/dictacode/apps/stt/whisper.cpp/build/bin/whisper-cli -m ~/dictacode/apps/stt/models/ggml-tiny.bin /tmp/test.wav"
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check systemd unit file syntax
ssh dictacode-stt "systemd-analyze verify dictacode-stt.service"

# Check ExecStart path exists
ssh dictacode-stt "cat /lib/systemd/system/dictacode-stt.service | grep ExecStart"
ssh dictacode-stt "test -f ~/dictacode/apps/stt/.venv/bin/python && echo 'Python OK' || echo 'VENV MISSING'"

# Check working directory exists
ssh dictacode-stt "cat /lib/systemd/system/dictacode-stt.service | grep WorkingDirectory"
ssh dictacode-stt "test -d ~/dictacode/apps/stt && echo 'WorkDir OK' || echo 'DIR MISSING'"
```

### Import Errors

```bash
# Verify package installation
ssh dictacode-stt "cd ~/dictacode/apps/stt && source .venv/bin/activate && python -c 'import dictacode_stt; print(dictacode_stt.__file__)'"

# Reinstall in editable mode
ssh dictacode-stt "cd ~/dictacode/apps/stt && source .venv/bin/activate && pip install -e ."
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

**Development (Git Repo):**
- Code: `~/dictacode/apps/{stt,hid}/`
- Virtual envs: `~/dictacode/apps/{stt,hid}/.venv/`
- Tests: `~/dictacode/apps/{stt,hid}/tests/`

**System (Debian Package):**
- Service files: `/lib/systemd/system/dictacode-{stt,hid}.service`
- Config files: `/etc/dictacode/{stt,hid}.conf`
- State directory: `/var/lib/dictacode/`
- Runtime directory: `/run/dictacode-{stt,hid}/`
- Logs: `journalctl -u dictacode-{stt,hid}`

### Common Commands

```bash
# Restart after code change
ssh dictacode-stt "cd ~/dictacode && git pull && sudo systemctl restart dictacode-stt"

# View last 100 log lines
ssh dictacode-stt "sudo journalctl -u dictacode-stt -n 100 --no-pager"

# Clear failed state
ssh dictacode-stt "sudo systemctl reset-failed dictacode-stt"

# Stop service
ssh dictacode-stt "sudo systemctl stop dictacode-stt"
```
