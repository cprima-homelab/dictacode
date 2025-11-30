# dictacode Architecture Plan v0.2.0

## Layer Taxonomy

```
┌─────────────────────────────────────────────────────────────┐
│  5. Supervisor                                               │
│     Link health, reconnection, timeouts, watchdog           │
├─────────────────────────────────────────────────────────────┤
│  4. Service/App                                              │
│     State (mode, keymap), commands, handlers, business logic│
├─────────────────────────────────────────────────────────────┤
│  3. Protocol/Codec                                           │
│     Message encoding/decoding (JSON, msgpack)               │
├─────────────────────────────────────────────────────────────┤
│  2. Transport                                                │
│     Raw byte I/O (UART read/write, HID write)               │
├─────────────────────────────────────────────────────────────┤
│  1. Driver (OS)                                              │
│     /dev/serial0, /dev/hidg0 (kernel provides)              │
└─────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Module | Owns |
|-------|--------|------|
| **Supervisor** | `supervisor.py` | link_healthy, last_msg_time, reconnect, watchdog |
| **Service** | `service.py`, `state.py` | DeviceMode, keymap, buffer, command handlers |
| **Protocol** | `protocol.py` | TextMessage, CommandMessage, encode/decode |
| **Transport** | `transport.py` | UartTransport, HidTransport (open/read/write/close) |
| **Driver** | kernel | `/dev/serial0`, `/dev/hidg0` |

---

## Current State (Post v0.1.0)

| Module | HID | STT |
|--------|-----|-----|
| `protocol.py` | ✅ done | ✅ done |
| `state.py` | ✅ done | ✅ done |
| `transport.py` | ❌ missing | ❌ missing |
| `service.py` | ❌ missing | ❌ missing |
| `supervisor.py` | ❌ missing | ❌ missing |

---

## Target File Structure

```
apps/hid/src/dictacode_hid/
├── __init__.py
├── transport.py      # Layer 2: UartTransport, HidTransport
├── protocol.py       # Layer 3: ✅ exists
├── state.py          # Layer 4: ✅ exists
├── service.py        # Layer 4: command handlers, text handlers
├── supervisor.py     # Layer 5: link health, reconnection
├── keymaps/          # ✅ exists
└── cli.py            # ✅ exists

apps/stt/src/dictacode_stt/
├── __init__.py
├── transport.py      # Layer 2: UartTransport
├── protocol.py       # Layer 3: ✅ exists
├── state.py          # Layer 4: ✅ exists
├── audio.py          # Layer 4: AudioCapture service
├── transcribe.py     # Layer 4: WhisperService
├── service.py        # Layer 4: pipeline orchestration
├── supervisor.py     # Layer 5: link health
└── cli.py            # CLI commands
```

---

## Implementation Phases

### Phase 1: Transport Layer
1. Create `transport.py` in both packages
2. `UartTransport`: open, read, write, close with error handling
3. `HidTransport` (HID only): write HID reports to /dev/hidg0
4. Tests for transport layer

### Phase 2: Service Layer
1. Create `service.py` in both packages
2. HID: `HidService` - command handlers, text handlers, uses keymaps
3. STT: `SttService` - audio capture, transcription, pipeline orchestration
4. Wire service → protocol → transport
5. Tests for service layer

### Phase 3: Supervisor Layer
1. Create `supervisor.py` in both packages
2. `LinkSupervisor`: monitor link health, detect failures
3. Reconnection logic with backoff
4. Watchdog timeout (no data = alert/restart)
5. Tests for supervisor

### Phase 4: Integration
1. Create new `main.py` that wires all layers
2. Deprecate sandbox scripts (or make them thin wrappers)
3. End-to-end integration tests
4. Update pyproject.toml entry points

---

## systemd Integration

### Signal Handling (Required)

All entry points must handle SIGTERM for graceful shutdown:

```python
import signal
import sys

_shutdown_requested = False

def request_shutdown(signum, frame):
    global _shutdown_requested
    _shutdown_requested = True

def main():
    signal.signal(signal.SIGTERM, request_shutdown)
    signal.signal(signal.SIGINT, request_shutdown)

    while not _shutdown_requested:
        # main loop
        pass

    cleanup()
    sys.exit(0)
```

### Unit File Templates

**dictacode-hid.service:**
```ini
[Unit]
Description=dictacode HID Bridge
After=local-fs.target
Requires=dictacode-gadget.service

[Service]
Type=simple
User=dictacode
Group=dialout
WorkingDirectory=/home/dictacode/dictacode/apps/hid
ExecStart=/home/dictacode/.local/bin/uv run python -m dictacode_hid
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

**dictacode-stt.service:**
```ini
[Unit]
Description=dictacode STT Service
After=sound.target

[Service]
Type=simple
User=dictacode
Group=audio
WorkingDirectory=/home/dictacode/dictacode/apps/stt
ExecStart=/home/dictacode/.local/bin/uv run python -m dictacode_stt
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Supervisor + systemd Watchdog

Use both for defense in depth:
- `supervisor.py` handles reconnection within the service
- `WatchdogSec=30` as a fallback if supervisor fails

```ini
[Service]
WatchdogSec=30
```

```python
try:
    from systemd.daemon import notify
    notify('READY=1')
    # In main loop:
    notify('WATCHDOG=1')
except ImportError:
    pass  # Not running under systemd
```

---

## Out of Scope (v0.2.0)

- Web panel
- Daemon mode with HTTP API
- Streaming transcription
- Bidirectional protocol (HID → STT responses)

See [architecture-plan-v0.3.0.md](architecture-plan-v0.3.0.md) for future work.
