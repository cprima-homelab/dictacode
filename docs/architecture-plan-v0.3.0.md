# dictacode Architecture Plan v0.3.0

## Prerequisites

v0.3.0 builds on top of v0.2.0:
- ✅ 5-layer architecture (transport, protocol, service, supervisor)
- ✅ systemd integration
- ✅ Signal handling for graceful shutdown

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
Response: {"mode": "listening", "keymap": "en_us", "model": "tiny"}

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
{"type": "status", "data": {"mode": "listening", ...}}
{"type": "transcription", "data": {"text": "hello world", "final": true}}
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
