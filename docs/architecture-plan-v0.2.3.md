# dictacode Architecture Plan v0.2.3 - Expanded Solution State

## Status

### Phase 1: SolutionState Model
- [x] Expand state enum to cover full lifecycle
- [x] Add state behavior predicates (should_transcribe, should_poll, etc.)
- [x] Add transition_to() with logging
- [x] Unit tests for state predicates

### Phase 2: Supervisor Detection
- [x] Add check_prerequisites() method
- [x] Add check_link_available() method
- [x] Add signal_*() methods for state transitions
- [x] Supervisor holds reference to state (doesn't own it)

### Phase 3: Service Main Loop
- [x] State-driven main loop
- [x] Remove check_prerequisites() from main.py
- [x] Add sd_notify STATUS reporting

### Phase 4: Handshake Protocol
- [x] Add ProbeMessage to protocol
- [x] Add ProbeAckMessage to protocol
- [x] Implement handshake flow in service
- [x] HID responds to probe messages

### Phase 5: systemd Integration (from v0.2.2 Phase 6)
- [x] Add systemd-python dependency to pyproject.toml
- [x] Add systemd Type=notify support with READY=1 notification
- [x] Enable system-site-packages in venvs for python3-systemd access
- [x] Package python3-systemd dependency in .deb control files
- [x] Test service startup without timeout
- [x] Verify sd_notify STATUS reporting

**v0.2.3 COMPLETED** - Commits: d4acbcd (ProbeMessage/ProbeAckMessage), b7c48d4 (handshake fix), c8b0706 (systemd notify), b78582b (.deb v0.2.4)

---

## Prerequisites

v0.2.3 builds on top of v0.2.2:
- ✅ 5-layer architecture (transport, protocol, service, supervisor)
- ✅ Diagnostics CLI entry points
- ✅ Supervisor layer with link health monitoring
- ✅ Serial port locking

---

## Problem Statement

Current architecture has a critical flaw:
- `ExecStartPre=dictacode-stt-check --quiet` returns exit 1 if Whisper missing
- **Service won't start at all** after fresh install
- User must manually install Whisper, then start service
- No graceful handling of installation lifecycle

**Goal:** Service should **always start** via systemd, but operate appropriately based on **one unified solution state**.

---

## Scope

### Expanded Solution State

Single authoritative state covering the full lifecycle from package install to normal operation.

```
┌─────────────────────────────────────────────────────────────────┐
│                      Solution State                              │
│                                                                  │
│  Setup Phases          Operational Phases      Failure Phases   │
│  ├── UNCONFIGURED      ├── LISTENING           ├── DEGRADED     │
│  ├── LINK_PENDING      ├── MAINTENANCE         └── FAILED       │
│  └── HANDSHAKE_INIT    └── PAUSED                               │
│                                                                  │
│  Authoritative:  STT controller (single source of truth)        │
│  Detection:      Supervisor polls prerequisites/link            │
│  Transitions:    Supervisor signals, State owns                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architecture Principle

**Single authoritative state implementation:**
- `state.py` owns the state (single source of truth on STT controller)
- `supervisor.py` **detects** conditions (prerequisites, link health)
- Supervisor **signals** state transitions to state.py
- State determines behavior (should_transcribe, should_send, etc.)

**NOT two parallel concepts** (lifecycle + mode). Just **one expanded SolutionState enum**.

---

## Design

### SolutionState Enum

```python
class SolutionState(Enum):
    """
    Full solution state - covers entire lifecycle from install to operation.
    State name tells you what to do next.
    Authoritative source: STT controller.
    """

    # Setup phases
    UNCONFIGURED = "unconfigured"      # Prerequisites missing (whisper, model)
    LINK_PENDING = "link_pending"      # Prerequisites OK, UART not available
    HANDSHAKE_INIT = "handshake_init"  # UART open, waiting for peer response

    # Operational phases
    LISTENING = "listening"            # Normal transcription mode
    MAINTENANCE = "maintenance"        # Diagnostic mode (no transcription)
    PAUSED = "paused"                  # User-requested pause

    # Failure phases
    DEGRADED = "degraded"              # Running with issues (retries, latency)
    FAILED = "failed"                  # Unrecoverable error
```

### State Behavior Predicates

```python
@dataclass
class SttState:
    """Single source of truth for solution state (on STT controller)."""

    state: SolutionState = SolutionState.UNCONFIGURED
    failure_reason: Optional[str] = None

    def transition_to(self, new_state: SolutionState, reason: str = None) -> None:
        """Transition to new state with logging."""
        old = self.state
        self.state = new_state
        self.failure_reason = reason if new_state == SolutionState.FAILED else None
        logger.info(f"State transition: {old.value} → {new_state.value}")

    def should_transcribe(self) -> bool:
        return self.state == SolutionState.LISTENING

    def should_send(self) -> bool:
        return self.state in (SolutionState.LISTENING, SolutionState.MAINTENANCE, SolutionState.DEGRADED)

    def should_poll_prerequisites(self) -> bool:
        return self.state == SolutionState.UNCONFIGURED

    def should_poll_link(self) -> bool:
        return self.state == SolutionState.LINK_PENDING

    def should_handshake(self) -> bool:
        return self.state == SolutionState.HANDSHAKE_INIT

    def is_operational(self) -> bool:
        return self.state in (SolutionState.LISTENING, SolutionState.MAINTENANCE, SolutionState.PAUSED, SolutionState.DEGRADED)
```

---

## State Transitions

```
    ┌──────────────────────────────────────────────────────────────┐
    │                     PACKAGE INSTALL                           │
    └──────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  UNCONFIGURED                                                 │
    │  - Service starts, main loop runs                             │
    │  - Supervisor polls: whisper binary? model file?              │
    │  - systemd: READY=1, STATUS="state=unconfigured"              │
    └──────────────────────────────────────────────────────────────┘
                                    │
                    (supervisor detects prerequisites OK)
                                    ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  LINK_PENDING                                                 │
    │  - Supervisor polls: /dev/serial0 exists?                     │
    │  - systemd: STATUS="state=link_pending"                       │
    └──────────────────────────────────────────────────────────────┘
                                    │
                    (supervisor detects UART available)
                                    ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  HANDSHAKE_INIT                                               │
    │  - Open UART, send probe message                              │
    │  - Wait for peer (HID) response                               │
    │  - Timeout → back to LINK_PENDING                             │
    └──────────────────────────────────────────────────────────────┘
                                    │
                    (handshake successful)
                                    ▼
    ┌──────────────────────────────────────────────────────────────┐
    │  LISTENING                                                    │
    │  - Normal operation: transcribe + send                        │
    │  - Supervisor monitors link health                            │
    │  - systemd: STATUS="state=listening"                          │
    └──────────────────────────────────────────────────────────────┘
              │                     │                      │
     (user cmd)              (link issues)           (link dead)
              ▼                     ▼                      ▼
         PAUSED              DEGRADED                LINK_PENDING
         MAINTENANCE         (auto-recover)          (reconnect)
```

---

## Supervisor Role (Refactored)

**Current:** Supervisor tracks link health only (last_msg_time, reconnect backoff)

**Proposed:** Supervisor **detects** all conditions, **signals** state transitions:

```python
class LinkSupervisor:
    """Detect conditions and signal state transitions."""

    def __init__(self, state: SttState, config: SupervisorConfig):
        self.state = state  # Reference to authoritative state
        self.config = config

    # Detection methods (called in main loop)
    def check_prerequisites(self) -> bool:
        """Detect if whisper binary and model exist."""
        return (
            self.config.whisper_binary.exists() and
            self.config.whisper_model.exists()
        )

    def check_link_available(self) -> bool:
        """Detect if UART device exists."""
        return Path(self.config.uart_device).exists()

    def check_link_health(self) -> bool:
        """Detect if link is responsive (existing logic)."""
        return time.time() - self.last_msg_time < self.timeout

    # State transition signals
    def signal_prerequisites_ready(self) -> None:
        """Signal state: prerequisites are now available."""
        if self.state.state == SolutionState.UNCONFIGURED:
            self.state.transition_to(SolutionState.LINK_PENDING)

    def signal_link_available(self) -> None:
        """Signal state: UART is now available."""
        if self.state.state == SolutionState.LINK_PENDING:
            self.state.transition_to(SolutionState.HANDSHAKE_INIT)

    def signal_handshake_complete(self) -> None:
        """Signal state: peer responded to probe."""
        if self.state.state == SolutionState.HANDSHAKE_INIT:
            self.state.transition_to(SolutionState.LISTENING)

    def signal_link_degraded(self) -> None:
        """Signal state: link has issues but recoverable."""
        if self.state.state == SolutionState.LISTENING:
            self.state.transition_to(SolutionState.DEGRADED)

    def signal_link_lost(self) -> None:
        """Signal state: link is dead, need reconnect."""
        if self.state.is_operational():
            self.state.transition_to(SolutionState.LINK_PENDING)
```

---

## systemd Unit File Changes

### Current (problematic)

```ini
[Service]
ExecStartPre=/opt/dictacode/stt/venv/bin/dictacode-stt-check --quiet
ExecStart=/opt/dictacode/stt/venv/bin/dictacode-stt
```

**Problem:** ExecStartPre fails → service never starts

### Proposed (state-aware)

```ini
[Service]
Type=notify
ExecStart=/opt/dictacode/stt/venv/bin/dictacode-stt
# NO ExecStartPre - service handles its own state

# Watchdog active in ALL states (even UNCONFIGURED)
WatchdogSec=60

# Environment for polling intervals
Environment=DICTACODE_PREREQUISITE_POLL=30
Environment=DICTACODE_LINK_POLL=5
Environment=DICTACODE_HANDSHAKE_TIMEOUT=10
```

**Key change:** Remove `ExecStartPre`. Service starts unconditionally, state machine handles lifecycle.

### Status Reporting

```python
# In main loop - report current state via sd_notify:
notify(f"STATUS=state={state.state.value}")
notify("WATCHDOG=1")

# systemctl status shows:
#   Status: "state=unconfigured"
#   Status: "state=listening"
#   Status: "state=degraded"
```

---

## Implementation Phases

### Phase 1: SolutionState Model

**File:** `apps/stt/src/dictacode_stt/state.py`

Replace existing `DeviceMode` with expanded `SolutionState`:

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SolutionState(Enum):
    """
    Full solution state - covers entire lifecycle.
    State name tells you what to do next.
    Authoritative source: STT controller.
    """
    # Setup phases
    UNCONFIGURED = "unconfigured"
    LINK_PENDING = "link_pending"
    HANDSHAKE_INIT = "handshake_init"

    # Operational phases
    LISTENING = "listening"
    MAINTENANCE = "maintenance"
    PAUSED = "paused"

    # Failure phases
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class SttState:
    """Single source of truth for solution state (on STT controller)."""

    state: SolutionState = SolutionState.UNCONFIGURED
    failure_reason: Optional[str] = None

    def transition_to(self, new_state: SolutionState, reason: str = None) -> None:
        """Transition to new state with logging."""
        old = self.state
        self.state = new_state
        self.failure_reason = reason if new_state == SolutionState.FAILED else None
        logger.info(f"State transition: {old.value} → {new_state.value}")

    # Behavior predicates
    def should_transcribe(self) -> bool:
        return self.state == SolutionState.LISTENING

    def should_send(self) -> bool:
        return self.state in (SolutionState.LISTENING, SolutionState.MAINTENANCE, SolutionState.DEGRADED)

    def should_poll_prerequisites(self) -> bool:
        return self.state == SolutionState.UNCONFIGURED

    def should_poll_link(self) -> bool:
        return self.state == SolutionState.LINK_PENDING

    def should_handshake(self) -> bool:
        return self.state == SolutionState.HANDSHAKE_INIT

    def is_operational(self) -> bool:
        return self.state in (SolutionState.LISTENING, SolutionState.MAINTENANCE, SolutionState.PAUSED, SolutionState.DEGRADED)
```

### Phase 2: Refactor Supervisor

**File:** `apps/stt/src/dictacode_stt/supervisor.py`

- Add `check_prerequisites()`, `check_link_available()` detection methods
- Add `signal_*()` methods that call `state.transition_to()`
- Keep existing link health logic (last_msg_time, backoff)
- Supervisor holds reference to `SttState`, not its own state

### Phase 3: Refactor Service Main Loop

**File:** `apps/stt/src/dictacode_stt/service.py`

```python
def run(self):
    """Main loop - behavior driven by state."""
    notify("READY=1")  # Service is UP regardless of state

    while not self._shutdown:
        notify(f"STATUS=state={self.state.state.value}")
        notify("WATCHDOG=1")

        # State-driven behavior
        if self.state.should_poll_prerequisites():
            if self.supervisor.check_prerequisites():
                self.supervisor.signal_prerequisites_ready()
            else:
                time.sleep(self.prerequisite_poll_interval)
            continue

        if self.state.should_poll_link():
            if self.supervisor.check_link_available():
                self.supervisor.signal_link_available()
            else:
                time.sleep(self.link_poll_interval)
            continue

        if self.state.should_handshake():
            if self._perform_handshake():
                self.supervisor.signal_handshake_complete()
            else:
                # Timeout - back to link pending
                self.state.transition_to(SolutionState.LINK_PENDING)
            continue

        # Operational states
        if self.state.should_transcribe():
            self._run_transcription_iteration()

        if self.state.should_send():
            self._send_pending_messages()

        # Health monitoring (in operational states)
        if self.state.is_operational():
            if not self.supervisor.check_link_health():
                self.supervisor.signal_link_degraded()
```

### Phase 4: Handshake Protocol

**New message type for handshake:**

```python
# In protocol.py
class ProbeMessage(BaseMessage):
    """Sent during HANDSHAKE_INIT to verify peer is alive."""
    type: str = "probe"
    timestamp: float

class ProbeAckMessage(BaseMessage):
    """Response to probe from HID."""
    type: str = "probe_ack"
    timestamp: float
```

**Handshake flow:**
1. STT enters HANDSHAKE_INIT
2. STT sends ProbeMessage over UART
3. HID receives, responds with ProbeAckMessage
4. STT receives ack → transition to LISTENING
5. Timeout (10s) → back to LINK_PENDING

### Phase 5: systemd Integration

**Files:**
- `ops/packaging/debian/dictacode-stt/lib/systemd/system/dictacode-stt.service`
- `ops/packaging/debian/dictacode-hid/lib/systemd/system/dictacode-hid.service`

Changes:
- Remove `ExecStartPre`
- Add `WatchdogSec=60`
- Add environment variables for poll intervals

---

## State Behavior Summary

| State | Transcribe | Send | Poll | Watchdog | systemd STATUS |
|-------|------------|------|------|----------|----------------|
| UNCONFIGURED | ❌ | ❌ | prerequisites | ✅ | "state=unconfigured" |
| LINK_PENDING | ❌ | ❌ | link | ✅ | "state=link_pending" |
| HANDSHAKE_INIT | ❌ | probe | - | ✅ | "state=handshake_init" |
| LISTENING | ✅ | ✅ | - | ✅ | "state=listening" |
| MAINTENANCE | ❌ | ✅ | - | ✅ | "state=maintenance" |
| PAUSED | ❌ | ❌ | - | ✅ | "state=paused" |
| DEGRADED | ✅ | ✅ | - | ✅ | "state=degraded" |
| FAILED | ❌ | ❌ | - | ✅ | "state=failed" |

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── state.py          # MODIFIED: SolutionState enum, SttState class
├── supervisor.py     # MODIFIED: detection + signal methods
├── service.py        # MODIFIED: state-driven main loop
├── protocol.py       # MODIFIED: ProbeMessage, ProbeAckMessage
├── main.py           # MODIFIED: remove check_prerequisites()
└── ...existing...

apps/hid/src/dictacode_hid/
├── state.py          # MODIFIED: HidLocalState, HidMode
├── service.py        # MODIFIED: handle ProbeMessage
└── ...existing...

ops/packaging/debian/dictacode-stt/lib/systemd/system/
└── dictacode-stt.service  # MODIFIED: remove ExecStartPre, add WatchdogSec

ops/packaging/debian/dictacode-hid/lib/systemd/system/
└── dictacode-hid.service  # MODIFIED: remove ExecStartPre, add WatchdogSec
```

---

## Testing Strategy

### Unit Tests

```python
def test_solution_state_should_transcribe():
    state = SttState(state=SolutionState.LISTENING)
    assert state.should_transcribe() == True

    state.transition_to(SolutionState.MAINTENANCE)
    assert state.should_transcribe() == False

def test_solution_state_should_poll_prerequisites():
    state = SttState()  # Default: UNCONFIGURED
    assert state.should_poll_prerequisites() == True

    state.transition_to(SolutionState.LINK_PENDING)
    assert state.should_poll_prerequisites() == False

def test_supervisor_signal_transitions():
    state = SttState()
    supervisor = LinkSupervisor(state, config)

    assert state.state == SolutionState.UNCONFIGURED
    supervisor.signal_prerequisites_ready()
    assert state.state == SolutionState.LINK_PENDING
```

### Integration Tests

1. **Fresh install test:**
   - Start service without Whisper
   - Verify state = UNCONFIGURED
   - Install Whisper
   - Verify auto-transition to LINK_PENDING

2. **Handshake test:**
   - Start both services
   - Verify STT sends ProbeMessage
   - Verify HID responds with ProbeAckMessage
   - Verify transition to LISTENING

3. **Watchdog test:**
   - Start service in UNCONFIGURED
   - Verify WATCHDOG=1 pings continue
   - systemd should NOT restart service

---

## HID State (Simpler)

HID receives solution state from STT controller. HID has its own local state for its prerequisites:

```python
class HidLocalState(Enum):
    """HID-local state for device prerequisites."""
    UNCONFIGURED = "unconfigured"    # /dev/hidg0 missing
    LINK_PENDING = "link_pending"    # UART missing
    READY = "ready"                  # Ready to receive from STT

class HidMode(Enum):
    """HID operational mode (driven by commands from STT)."""
    NORMAL = "normal"                # Typing mode
    MAINTENANCE = "maintenance"      # Diagnostic mode (log, don't type)
    PAUSED = "paused"                # Buffering mode
```

HID waits for ProbeMessage during handshake, responds with ProbeAckMessage.

---

## Out of Scope (v0.2.3)

- Web panel for state monitoring (v0.3.0)
- Bidirectional state sync (HID → STT status messages)
- State persistence across restarts
- Remote state queries

---

## Success Criteria

v0.2.3 is complete when:

1. ✅ `SolutionState` enum covers full lifecycle - DONE (apps/stt/src/dictacode_stt/state.py)
2. ✅ Service starts in UNCONFIGURED state (no crash without Whisper) - DONE (tested on devices)
3. ✅ Auto-transitions: UNCONFIGURED → LINK_PENDING → HANDSHAKE_INIT → LISTENING - DONE (verified in logs)
4. ✅ Handshake protocol (probe/ack) validates peer before going live - DONE (ProbeMessage/ProbeAckMessage implemented)
5. ✅ `systemctl status` shows current state via sd_notify - DONE (Status: "state=listening" visible)
6. ✅ systemd Type=notify with READY=1 eliminates startup timeout - DONE (services show "active (running)" immediately)
7. ✅ python3-systemd packaged in .deb files - DONE (v0.2.4 packages include dependency)
8. ✅ Unit tests for state predicates and transitions - DONE (apps/stt/tests/ and apps/hid/tests/)

**ALL SUCCESS CRITERIA MET** - v0.2.3 is functionally complete and deployed to both devices.
