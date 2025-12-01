# dictacode Architecture Plan v0.2.5 - Backend/CLI/API Separation

## Status

### Phase 1: Audit CLI for Backend Leakage
- [ ] Review `cli.py` for any business logic that should move to `service.py`
- [ ] Ensure CLI only does: argparse, console output, call service methods
- [ ] Document any refactoring needed

### Phase 2: API Scaffold (Preparation for v0.3.0)
- [ ] Create `api.py` with stub endpoints
- [ ] Define REST API contract (OpenAPI/JSON schema)
- [ ] No implementation yet - just structure

### Phase 3: Shared Response Types
- [ ] Define response dataclasses that both CLI and API can use
- [ ] CLI formats as human text, API formats as JSON
- [ ] Example: `TranscriptionResult`, `StatusResponse`, `PortInfo`

**v0.2.5 NOT STARTED**

---

## Prerequisites

v0.2.5 builds on top of v0.2.4:
- ✅ Audio port abstraction
- ✅ Streaming with ring buffer

---

## Problem Statement

A future web control panel (v0.3.0) needs to communicate with the STT backend via API, not CLI.

**Current state:**
- `cli.py` - CLI-specific code (argparse, console output, entry points)
- `service.py` - Business logic (`SttService`) - already backend-ready
- No `api.py` exists

**Goal:** Ensure clean separation so both CLI and API share `SttService` as the backend controller.

---

## Naming Decision

| Layer | File | Class | Role |
|-------|------|-------|------|
| Backend | `service.py` | `SttService` | Shared business logic (keep as-is) |
| CLI | `cli.py` | - | CLI entry points and console output |
| API | `api.py` | - | REST/WebSocket endpoints (v0.3.0 prep) |

**Rationale:** Current naming is already correct. `SttService` has no CLI dependencies.

---

## Current Architecture (Already Good)

```
┌─────────────────────────────────────────────────────────────────┐
│  Entry Points (Adapters)                                         │
│                                                                  │
│  main.py          cli.py              (future) api.py           │
│  └── systemd      └── dictacode-stt-* └── REST/WebSocket        │
│      service          CLI tools           endpoints             │
│          │                │                    │                │
│          └────────────────┼────────────────────┘                │
│                           ▼                                      │
├─────────────────────────────────────────────────────────────────┤
│  Backend (Shared)                                                │
│                                                                  │
│  service.py                                                      │
│  └── SttService                                                  │
│      ├── check_prerequisites()                                   │
│      ├── record_audio() → bytes                                  │
│      ├── transcribe(wav_path) → str                              │
│      ├── send_text(text) → bool                                  │
│      ├── send_command(cmd, arg) → bool                           │
│      ├── run_once() → Dict                                       │
│      └── run_continuous() → None                                 │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  Support Layers (Already Shared)                                 │
│                                                                  │
│  state.py       transport.py    supervisor.py    protocol.py    │
│  └── SttState   └── UartTransport └── LinkSupervisor └── JsonProtocol │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design

### Response Types (Shared)

```python
# In a new file: responses.py or in service.py

@dataclass
class StatusResponse:
    """Shared response for status queries."""
    mode: str
    keymap: str
    model: str
    link_healthy: bool
    last_activity: Optional[str]

    def to_dict(self) -> dict:
        """For JSON serialization (API)."""
        return asdict(self)

@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""
    text: str
    duration_ms: int
    success: bool
    error: Optional[str] = None
```

### CLI Usage

```python
# cli.py
def cmd_status():
    service = create_service()
    status = service.get_status()  # Returns StatusResponse

    # CLI formats for humans
    print(f"Mode: {status.mode}")
    print(f"Link: {'OK' if status.link_healthy else 'DOWN'}")
```

### API Usage (v0.3.0)

```python
# api.py
@app.get("/api/status")
async def get_status():
    status = service.get_status()  # Same method
    return status.to_dict()        # API returns JSON
```

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── service.py        # Backend: SttService (keep as-is)
├── cli.py            # CLI: Entry points (audit for purity)
├── api.py            # API: REST endpoints (NEW - scaffold only)
├── responses.py      # Shared: Response dataclasses (NEW)
├── main.py           # systemd entry point
├── state.py          # Shared: SttState
├── transport.py      # Shared: UartTransport
├── supervisor.py     # Shared: LinkSupervisor
├── protocol.py       # Shared: Message encoding
└── ...
```

---

## Files to Modify

1. `apps/stt/src/dictacode_stt/cli.py` - Audit, ensure no business logic
2. `apps/stt/src/dictacode_stt/service.py` - Add `get_status()` if missing
3. `apps/stt/src/dictacode_stt/responses.py` - NEW: Shared response types
4. `apps/stt/src/dictacode_stt/api.py` - NEW: Stub endpoints

---

## Success Criteria

v0.2.5 is complete when:

1. ✅ CLI contains only presentation logic (argparse, print)
2. ✅ `SttService` methods return typed responses (not raw dicts)
3. ✅ `api.py` exists with documented endpoint stubs
4. ✅ Response types defined and used by both CLI and API
5. ✅ No code duplication between CLI and API

---

## Out of Scope (v0.2.5)

- Actual API implementation (v0.3.0)
- WebSocket for live updates (v0.3.0)
- Authentication/authorization
- Web UI static files
