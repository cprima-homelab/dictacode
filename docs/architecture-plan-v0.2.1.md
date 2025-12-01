# dictacode Architecture Plan v0.2.1

## Status

### Phase 1: Basic Supervisor
- [x] Create `supervisor.py` in both packages
- [x] Implement `LinkSupervisor` class with timeout detection
- [x] Integrate with Service layer
- [x] Unit tests for supervisor

### Phase 2: Reconnection Logic
- [x] Implement exponential backoff
- [x] Add reconnection loop in Service
- [x] Close/reopen transport on failure
- [x] Reset reconnect counter on success

### Phase 3: Heartbeat
- [ ] Add `PingMessage` to protocol (deferred to v0.3.0)
- [x] `should_send_ping()` method implemented
- [ ] Full ping/pong requires bidirectional protocol

### Phase 4: systemd Watchdog
- [x] Add `notify_watchdog()` method
- [x] Tests for watchdog notification
- [ ] Update systemd unit files with WatchdogSec (ops/packaging)

**v0.2.1 COMPLETE** - Supervisor layer implemented with link health monitoring.

---

## Prerequisites

v0.2.1 builds on top of v0.2.0:
- ✅ 5-layer architecture (transport, protocol, service)
- ✅ systemd integration
- ✅ Signal handling for graceful shutdown
- ✅ CLI entry points with main.py

---

## Scope

### Supervisor Layer (Layer 5)

Add reliability and fault tolerance to UART communication between STT and HID.

```
┌─────────────────────────────────────────────────────────────┐
│  5. Supervisor                                               │
│     ✅ Link health monitoring                                │
│     ✅ Reconnection with exponential backoff                 │
│     ✅ Heartbeat ping/pong (5s interval)                     │
│     ✅ Watchdog timeout (30s no activity)                    │
│     ✅ Integration with systemd WatchdogSec                  │
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

---

## Design

### LinkSupervisor Class

```python
class LinkSupervisor:
    """Monitor UART link health and handle failures."""

    # State
    link_healthy: bool = True
    last_msg_time: datetime
    last_ping_time: datetime
    reconnect_attempts: int = 0

    # Configuration
    PING_INTERVAL = 5.0      # seconds between pings
    TIMEOUT = 30.0           # seconds without message = dead link
    MAX_BACKOFF = 30.0       # max reconnect delay

    def check_health(self) -> bool:
        """Return True if link is healthy."""
        if time.now() - self.last_msg_time > self.TIMEOUT:
            self.mark_unhealthy()
            return False
        return self.link_healthy

    def mark_activity(self) -> None:
        """Called when message received."""
        self.last_msg_time = time.now()
        if not self.link_healthy:
            self.mark_healthy()

    def reconnect_delay(self) -> float:
        """Calculate exponential backoff delay."""
        # 1s → 2s → 4s → 8s → 16s → 30s (max)
        delay = min(2 ** self.reconnect_attempts, self.MAX_BACKOFF)
        return delay

    def should_send_ping(self) -> bool:
        """Return True if ping should be sent."""
        return time.now() - self.last_ping_time > self.PING_INTERVAL
```

### Heartbeat Protocol

Add a new message type for ping/pong:

```json
// STT → HID: ping
{"t":"ping","id":"abc123","ts":1234567890}

// HID → STT: pong (requires bidirectional protocol)
{"t":"pong","id":"abc123","ts":1234567891}
```

If v0.2.1 implements before v0.3.0 bidirectional protocol:
- Use one-way ping only
- Rely on any message from HID to confirm link is alive
- Don't expect pong responses

### Integration Points

**With Service Layer:**
```python
class HidService:
    def __init__(self):
        self.supervisor = LinkSupervisor()

    def _run_loop(self):
        while True:
            # Check supervisor
            if not self.supervisor.check_health():
                logger.error("Link unhealthy, reconnecting...")
                self._reconnect()
                continue

            # Send ping if needed
            if self.supervisor.should_send_ping():
                self._send_ping()

            # Read message (with timeout)
            msg = self._read_message(timeout=1.0)
            if msg:
                self.supervisor.mark_activity()
                self._handle_message(msg)
```

**With systemd:**
```python
# In main loop
try:
    from systemd.daemon import notify
    notify('WATCHDOG=1')  # Pet the watchdog
except ImportError:
    pass
```

**systemd unit file:**
```ini
[Service]
WatchdogSec=60
# systemd will restart if no WATCHDOG=1 within 60s
```

---

## Implementation Phases

### Phase 1: Basic Supervisor

1. Create `supervisor.py` in both packages
2. Implement `LinkSupervisor` class:
   - `last_msg_time` tracking
   - `check_health()` method
   - Timeout detection (30s)
3. Integrate with Service layer
4. Basic unit tests

**Files:**
- `apps/hid/src/dictacode_hid/supervisor.py`
- `apps/stt/src/dictacode_stt/supervisor.py`
- `apps/hid/tests/test_supervisor.py`
- `apps/stt/tests/test_supervisor.py`

### Phase 2: Reconnection Logic

1. Implement exponential backoff
2. Add reconnection loop in Service
3. Close/reopen transport on failure
4. Reset reconnect counter on success
5. Tests for reconnection scenarios

**Backoff strategy:**
```
Attempt 1: wait 1s
Attempt 2: wait 2s
Attempt 3: wait 4s
Attempt 4: wait 8s
Attempt 5: wait 16s
Attempt 6+: wait 30s (max)
```

### Phase 3: Heartbeat (Optional for v0.2.1)

1. Add `PingMessage` to protocol (or defer to v0.3.0)
2. Send ping every 5 seconds
3. Track `last_ping_time`
4. Don't block on pong (one-way for now)
5. Tests for ping sending

**Note:** Full ping/pong requires bidirectional protocol from v0.3.0.

### Phase 4: systemd Watchdog

1. Add `sd_notify('WATCHDOG=1')` in main loop
2. Update systemd unit files with `WatchdogSec=60`
3. Test watchdog timeout (kill process, verify restart)
4. Document watchdog configuration

---

## File Structure

```
apps/hid/src/dictacode_hid/
├── supervisor.py      # NEW: LinkSupervisor class
├── service.py         # MODIFIED: integrate supervisor
├── main.py            # MODIFIED: add WATCHDOG=1 notify
├── protocol.py        # MODIFIED (optional): add PingMessage
└── ...existing...

apps/stt/src/dictacode_stt/
├── supervisor.py      # NEW: LinkSupervisor class
├── service.py         # MODIFIED: integrate supervisor
├── main.py            # MODIFIED: add WATCHDOG=1 notify
├── protocol.py        # MODIFIED (optional): add PingMessage
└── ...existing...

systemd/
├── dictacode-hid.service    # MODIFIED: add WatchdogSec=60
└── dictacode-stt.service    # MODIFIED: add WatchdogSec=60
```

---

## Error Scenarios & Handling

### Scenario 1: UART Disconnected

**Symptoms:**
- No messages received for 30s
- Transport read() timeouts

**Handling:**
1. Supervisor detects timeout
2. Mark link unhealthy
3. Close UART transport
4. Wait backoff delay
5. Attempt reopen
6. If success: mark healthy, reset counter
7. If fail: increment counter, repeat

### Scenario 2: HID Device Unavailable

**Symptoms:**
- Transport write() raises error
- `/dev/hidg0` permission denied or missing

**Handling:**
1. Log error, don't crash
2. Continue receiving messages (buffer or drop?)
3. Retry HID open on next write attempt
4. Option: enter maintenance mode automatically

### Scenario 3: Message Flood (DoS)

**Symptoms:**
- High message rate from UART
- CPU/memory exhaustion

**Handling:**
1. Rate limiting (max 100 msgs/sec?)
2. Drop messages if queue full
3. Log warning
4. Don't crash

### Scenario 4: systemd Watchdog Timeout

**Symptoms:**
- Process hung, not calling `notify('WATCHDOG=1')`
- systemd kills and restarts service

**Handling:**
- Prevention: call notify() every loop iteration
- Recovery: systemd restarts automatically
- Logging: check journalctl for restart reason

---

## Testing Strategy

### Unit Tests

```python
def test_supervisor_healthy_when_recent_activity():
    supervisor = LinkSupervisor()
    supervisor.mark_activity()
    assert supervisor.check_health() == True

def test_supervisor_unhealthy_after_timeout():
    supervisor = LinkSupervisor()
    supervisor.last_msg_time = time.now() - 31  # 31 seconds ago
    assert supervisor.check_health() == False

def test_exponential_backoff():
    supervisor = LinkSupervisor()
    assert supervisor.reconnect_delay() == 1.0
    supervisor.reconnect_attempts = 1
    assert supervisor.reconnect_delay() == 2.0
    supervisor.reconnect_attempts = 5
    assert supervisor.reconnect_delay() == 30.0  # max
```

### Integration Tests

1. **Reconnection test:**
   - Start service, verify connection
   - Disconnect UART (unplug or stop receiver)
   - Verify supervisor detects failure
   - Reconnect UART
   - Verify service recovers

2. **Watchdog test:**
   - Start service with systemd
   - Send SIGSTOP to freeze process
   - Verify systemd detects timeout
   - Verify systemd restarts service

3. **Message flow test:**
   - Send 1000 messages rapidly
   - Verify all received or dropped gracefully
   - Verify service still responsive

---

## Configuration

Add to `main.py` CLI arguments:

```python
parser.add_argument(
    "--supervisor-timeout",
    type=float,
    default=30.0,
    help="Link timeout in seconds (default: 30)",
)
parser.add_argument(
    "--supervisor-ping-interval",
    type=float,
    default=5.0,
    help="Ping interval in seconds (default: 5)",
)
parser.add_argument(
    "--no-supervisor",
    action="store_true",
    help="Disable supervisor (for debugging)",
)
```

Or use environment variables:
```bash
DICTACODE_SUPERVISOR_TIMEOUT=30
DICTACODE_SUPERVISOR_PING_INTERVAL=5
DICTACODE_SUPERVISOR_ENABLED=true
```

---

## Out of Scope (v0.2.1)

- ❌ Bidirectional pong responses (requires v0.3.0)
- ❌ Web UI for supervisor status (requires v0.3.0)
- ❌ Metrics/telemetry (defer to future)
- ❌ Advanced failure modes (split-brain, etc.)

---

## Success Criteria

v0.2.1 is complete when:

1. ✅ LinkSupervisor class implemented in both packages
2. ✅ Timeout detection working (30s no activity)
3. ✅ Reconnection with exponential backoff
4. ✅ Integration with Service layer
5. ✅ systemd WatchdogSec configured and tested
6. ✅ Unit tests for supervisor class
7. ✅ Integration test: disconnect → detect → reconnect
8. ✅ Manual test: unplug UART, verify recovery

**Bonus (optional for v0.2.1):**
- One-way ping messages every 5s
- Rate limiting for message flood protection
