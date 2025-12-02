# dictacode Architecture Plan v0.3.0

## Status

### Phase 1: HTTP API ✅ COMPLETE
- [x] Create `api.py` in dictacode_stt
- [x] Implement REST endpoints for status/control
- [x] Wire API to service layer
- [x] Tests for API
- [x] systemd unit `dictacode-stt-api.service` (v0.2.15)
- [x] Config file support for API settings (v0.2.15)

### Phase 2: WebSocket ✅ COMPLETE
- [x] Add WebSocket endpoint for live updates
- [x] Broadcast transcription results
- [x] Client-side reconnection logic
- [x] Test client with exponential backoff reconnection

### Phase 3: Web Panel ✅ COMPLETE
- [x] Create `templates/` and `static/` directories
- [x] HTML structure with status, controls, live feed (control panel, config, diagnostics, metrics)
- [x] JavaScript for API calls and WebSocket
- [x] Serve static files and templates from FastAPI
- [x] Jinja2 templates with 3 switchable themes
- [x] Pause/Resume service control (Phase 3.4)

### Phase 4: Bidirectional Protocol ⏸️ PARTIAL
- [x] Add `ResponseMessage` to protocol.py (Part 1 complete)
- [x] Add request ID tracking to TextMessage and CommandMessage
- [x] Update JsonProtocol and MsgpackProtocol encoders/decoders
- [ ] Update HID to send responses (Part 2 - see implementation guide)
- [ ] Update STT to receive/handle responses (Part 2 - see implementation guide)
- [ ] Add unit tests for bidirectional flow

### Phase 5: Streaming (Optional)
- [ ] Evaluate whisper.cpp streaming support
- [ ] Or evaluate Vosk for streaming STT
- [ ] Implement partial result handling
- [ ] Update web panel for partial display

**v0.3.0 STATUS:**
- ✅ **Phase 3 COMPLETE** - Web control panel fully implemented
- ⏸️ **Phase 4 PARTIAL** - Protocol foundation complete, service integration deferred (see implementation guide)

---

## Prerequisites

v0.3.0 builds on top of v0.2.1:
- ✅ 5-layer architecture (transport, protocol, service)
- ✅ Supervisor layer (v0.2.1: link health, reconnection, watchdog)
- ✅ systemd integration with WatchdogSec
- ✅ Signal handling for graceful shutdown
- ✅ CLI entry points (dictacode-hid, dictacode-stt)

---

## Note on Supervisor Integration

The supervisor layer from v0.2.1 provides essential data for the web panel:
- **Link health status**: Display "Connected" vs "Reconnecting" in UI
- **Last activity timestamp**: Show time since last message
- **Reconnection attempts**: Display reconnect counter/backoff delay
- **Watchdog status**: Alert if service is unhealthy

This makes v0.2.1 a **hard prerequisite** for v0.3.0 web panel features.

---

## Scope

### Web Panel (STT)

Browser-based control interface served by the STT backend.

```
┌─────────────────────────────────────────────────────────────┐
│                    STT Backend                               │
│                                                              │
│  HTTP API                              Web Panel             │
│  ├── GET  /api/status                  ┌────────────────┐   │
│  ├── POST /api/keymap                  │  Status: 🎤    │   │
│  ├── POST /api/pause                   │  Keymap: [▼]   │   │
│  ├── POST /api/resume                  │  [Pause]       │   │
│  └── WS   /api/ws  ◄─────────────────► │  Live: "..."   │   │
│                                         └────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Features:**
- Status display (listening, paused, typing)
- Keymap selector dropdown
- Pause/Resume button
- Live transcription preview (WebSocket)
- Settings (model, language)

**Technology:**
- Static HTML/CSS/JS (no build step)
- Vanilla JS or Alpine.js for reactivity
- Served by Python HTTP server (aiohttp or built-in)

### Bidirectional Protocol

Add response messages from HID → STT for acknowledgment and status.

```json
// Request (STT → HID)
{"t":"cmd","c":"keymap","a":"de_de","id":"abc123"}

// Response (HID → STT)
{"t":"rsp","id":"abc123","s":"ok"}
{"t":"rsp","id":"abc123","s":"error","e":"unknown_layout"}
```

**Use cases:**
- Confirm keymap change was applied
- Report HID errors back to STT
- Health check ping/pong

### Streaming Transcription

Real-time partial results during speech.

```
Speaking: "Hello world"
          ↓
Partial:  "Hel"
Partial:  "Hello"
Partial:  "Hello wor"
Final:    "Hello world"
```

**Requires:**
- Whisper streaming mode (or switch to Vosk)
- WebSocket updates to web panel
- Partial text buffering before final send

---

## Implementation Phases

### Phase 1: HTTP API
1. Create `api.py` in dictacode_stt
2. Implement REST endpoints for status/control
3. Wire API to service layer
4. Tests for API

### Phase 2: WebSocket
1. Add WebSocket endpoint for live updates
2. Broadcast transcription results
3. Client-side reconnection logic

### Phase 3: Web Panel
1. Create `web/` directory with static files
2. HTML structure with status, controls, log
3. JavaScript for API calls and WebSocket
4. Serve static files from Python

### Phase 4: Bidirectional Protocol
1. Add `ResponseMessage` to protocol.py
2. Update HID to send responses
3. Update STT to receive/handle responses
4. Add request ID tracking

### Phase 5: Streaming (Optional)
1. Evaluate whisper.cpp streaming support
2. Or evaluate Vosk for streaming STT
3. Implement partial result handling
4. Update web panel for partial display

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── ...existing...
├── api.py            # HTTP/WebSocket API
└── web/
    ├── index.html
    ├── style.css
    └── app.js
```

---

## API Specification

### REST Endpoints

```
GET  /api/status
Response: {
  "mode": "listening",
  "keymap": "en_us",
  "model": "tiny",
  "supervisor": {
    "link_healthy": true,
    "last_activity": "2025-11-30T21:53:18Z",
    "reconnect_attempts": 0
  }
}

POST /api/keymap
Body: {"layout": "de_de"}
Response: {"status": "ok"} or {"status": "error", "message": "..."}

POST /api/pause
Response: {"status": "ok"}

POST /api/resume
Response: {"status": "ok"}

GET  /api/config
Response: {"model": "tiny", "language": "en", ...}

POST /api/config
Body: {"model": "small", "language": "de"}
Response: {"status": "ok"}
```

### WebSocket

```
WS /api/ws

// Server → Client
{"type": "status", "data": {"mode": "listening", "keymap": "en_us", ...}}
{"type": "transcription", "data": {"text": "hello world", "final": true}}
{"type": "supervisor", "data": {"link_healthy": true, "last_activity": "...", "reconnect_attempts": 0}}
{"type": "error", "data": {"message": "UART disconnected"}}

// Client → Server (optional)
{"type": "ping"}
```

---

## Out of Scope (v0.3.0)

- Mobile app
- Cloud sync
- Multi-device management
- Voice commands (non-dictation)
- Custom wake word

---

## Dependencies

```toml
[project]
dependencies = [
    # ...existing...
    "aiohttp>=3.8",  # or use built-in http.server
]
```
