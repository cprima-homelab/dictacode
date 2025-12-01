# dictacode Testing Guide

## Devices

| Device | Hostname | Role | Platform |
|--------|----------|------|----------|
| Raspberry Pi 5 | `dictacode-pi5` | STT Engine | ARM64 |
| Raspberry Pi Zero 2 W | `dictacode-pi0` | HID Gadget | ARM32 |

**Connection:** Pi5 TX → Pi0 RX via UART (`/dev/serial0` @ 115200 baud)

---

## Development Workflow

### Prerequisites

```bash
# On development machine
# Ensure SSH keys are set up for both devices
ssh-copy-id dietpi@dictacode-pi5
ssh-copy-id dietpi@dictacode-pi0
```

---

## Deploy Code to Devices

**IMPORTANT:** The standard workflow is:
1. **PUSH** code to git from your development machine
2. **PULL** code on devices via SSH (devices pull from git)
3. **EXECUTE** commands on devices via SSH

### Standard Workflow (Git-based)

```bash
# Step 1: Push from development machine
git add .
git commit -m "your changes"
git push origin exploration

# Step 2: SSH to devices and pull latest code
ssh dietpi@dictacode-pi5 "cd /opt/dictacode && git pull"
ssh dietpi@dictacode-pi0 "cd /opt/dictacode && git pull"

# Step 3: Reinstall packages on devices
ssh dietpi@dictacode-pi5 "cd /opt/dictacode/stt && source venv/bin/activate && pip install -e ."
ssh dietpi@dictacode-pi0 "cd /opt/dictacode/hid && source venv/bin/activate && pip install -e ."

# Step 4: Restart services on devices
ssh dietpi@dictacode-pi5 "sudo systemctl restart dictacode-stt"
ssh dietpi@dictacode-pi0 "sudo systemctl restart dictacode-hid"
```

### Alternative: Build and Deploy .deb (Release)

```bash
# Build packages locally
./ops/packaging/build-deb.sh dictacode-stt
./ops/packaging/build-deb.sh dictacode-hid

# Copy to devices
scp ops/packaging/dist/dictacode-stt_*.deb dietpi@dictacode-pi5:/tmp/
scp ops/packaging/dist/dictacode-hid_*.deb dietpi@dictacode-pi0:/tmp/

# Install on devices
ssh dietpi@dictacode-pi5 "sudo dpkg -i /tmp/dictacode-stt_*.deb"
ssh dietpi@dictacode-pi0 "sudo dpkg -i /tmp/dictacode-hid_*.deb"
```

---

## Pull Code from Devices

Retrieve logs, recordings, or modified files:

```bash
# Pull logs from Pi5
ssh dietpi@dictacode-pi5 "journalctl -u dictacode-stt --no-pager -n 100" > stt.log

# Pull test recordings
rsync -avz dietpi@dictacode-pi5:/tmp/*.wav ./test-recordings/

# Pull any modified source files
rsync -avz dietpi@dictacode-pi5:/opt/dictacode/stt/src/ ./recovered-stt-src/
```

---

## Run Tests

### Local Tests (Development Machine)

```bash
# STT tests
cd apps/stt
uv sync                    # Install dependencies
uv run pytest              # Run all tests
uv run pytest -v           # Verbose output
uv run pytest tests/test_protocol.py  # Specific file

# HID tests
cd apps/hid
uv sync
uv run pytest
```

### On-Device Tests

```bash
# SSH to Pi5 and run STT tests
ssh dietpi@dictacode-pi5
cd /opt/dictacode/stt
source venv/bin/activate
pytest tests/

# SSH to Pi0 and run HID tests
ssh dietpi@dictacode-pi0
cd /opt/dictacode/hid
source venv/bin/activate
pytest tests/
```

---

## Diagnostics

### Quick Health Check

```bash
# Pi5 - STT prerequisites
ssh dietpi@dictacode-pi5 "dictacode-stt-check"

# Pi0 - HID prerequisites
ssh dietpi@dictacode-pi0 "dictacode-hid-check"
```

### Full Diagnostics

```bash
# Pi5 - Full STT diagnostics
ssh dietpi@dictacode-pi5 "dictacode-stt-diagnose"

# Pi0 - Full HID diagnostics
ssh dietpi@dictacode-pi0 "dictacode-hid-diagnose"
```

### Audio Testing (Pi5)

```bash
# List audio devices
ssh dietpi@dictacode-pi5 "dictacode-stt-audio list"

# Test recording (5 seconds)
ssh dietpi@dictacode-pi5 "dictacode-stt-audio test --duration 5"

# Record to file
ssh dietpi@dictacode-pi5 "dictacode-stt-audio record /tmp/test.wav --duration 3"
```

### Whisper Testing (Pi5)

```bash
# Check whisper installation
ssh dietpi@dictacode-pi5 "dictacode-stt-whisper check"

# Test transcription
ssh dietpi@dictacode-pi5 "dictacode-stt-whisper test /tmp/test.wav"
```

---

## Service Management

### Start/Stop Services

```bash
# Pi5 - STT service
ssh dietpi@dictacode-pi5 "sudo systemctl start dictacode-stt"
ssh dietpi@dictacode-pi5 "sudo systemctl stop dictacode-stt"
ssh dietpi@dictacode-pi5 "sudo systemctl status dictacode-stt"

# Pi0 - HID service
ssh dietpi@dictacode-pi0 "sudo systemctl start dictacode-hid"
ssh dietpi@dictacode-pi0 "sudo systemctl stop dictacode-hid"
ssh dietpi@dictacode-pi0 "sudo systemctl status dictacode-hid"
```

### View Logs

```bash
# Pi5 - Follow STT logs
ssh dietpi@dictacode-pi5 "journalctl -u dictacode-stt -f"

# Pi0 - Follow HID logs
ssh dietpi@dictacode-pi0 "journalctl -u dictacode-hid -f"
```

---

## End-to-End Testing

### Manual Pipeline Test

1. **Start both services:**
   ```bash
   ssh dietpi@dictacode-pi5 "sudo systemctl start dictacode-stt"
   ssh dietpi@dictacode-pi0 "sudo systemctl start dictacode-hid"
   ```

2. **Monitor HID output:**
   ```bash
   # On Pi0 - watch for typed characters
   ssh dietpi@dictacode-pi0 "journalctl -u dictacode-hid -f"
   ```

3. **Speak into microphone** connected to Pi5

4. **Observe:** Transcribed text should appear in HID logs (and type on connected computer)

### Protocol Test (Direct UART)

```bash
# Send test message from Pi5 to Pi0
ssh dietpi@dictacode-pi5 "dictacode-stt-send 'Hello World'"

# Watch Pi0 receive it
ssh dietpi@dictacode-pi0 "journalctl -u dictacode-hid -f"
```

---

## Troubleshooting

### UART Connection

```bash
# Check UART device exists
ssh dietpi@dictacode-pi5 "ls -la /dev/serial0"
ssh dietpi@dictacode-pi0 "ls -la /dev/serial0"

# Check permissions
ssh dietpi@dictacode-pi5 "groups dictacode"  # Should include 'dialout'
```

### HID Device (Pi0)

```bash
# Check HID gadget exists
ssh dietpi@dictacode-pi0 "ls -la /dev/hidg0"

# Check gadget setup
ssh dietpi@dictacode-pi0 "ls /sys/kernel/config/usb_gadget/"
```

### Audio Device (Pi5)

```bash
# List ALSA devices
ssh dietpi@dictacode-pi5 "arecord -l"

# Check sounddevice sees devices
ssh dietpi@dictacode-pi5 "python3 -c 'import sounddevice; print(sounddevice.query_devices())'"
```
