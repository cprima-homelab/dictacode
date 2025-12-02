# Phase 4: Bidirectional Protocol Implementation Guide

## Status

**✅ Part 1: Protocol Foundation (COMPLETE)**
- ResponseMessage type added to protocol.py
- Request ID tracking added to TextMessage and CommandMessage
- Both JsonProtocol and MsgpackProtocol updated
- Backward compatible with existing code

**⏸️ Part 2: Service Integration (DEFERRED)**
- Requires careful implementation and testing
- Non-trivial changes to transport layer
- Risk of breaking existing functionality

---

## Part 1: What's Complete

### Protocol Changes

**New Message Types:**
```python
@dataclass(frozen=True)
class TextMessage:
    payload: str
    request_id: str | None = None  # NEW: Optional request tracking

@dataclass(frozen=True)
class CommandMessage:
    command: str
    argument: str | None = None
    request_id: str | None = None  # NEW: Optional request tracking

@dataclass(frozen=True)
class ResponseMessage:
    """Response from HID to STT."""
    request_id: str  # Links to original request
    status: str      # "ok", "error", "buffered"
    message: str | None = None  # Optional error/status message
```

**Wire Format Examples:**
```json
// STT → HID: Text with request ID
{"t":"text","p":"Hello world","id":"req-001"}

// HID → STT: Success response
{"t":"rsp","id":"req-001","s":"ok"}

// HID → STT: Error response
{"t":"rsp","id":"req-002","s":"error","m":"Buffer full"}

// HID → STT: Buffered response
{"t":"rsp","id":"req-003","s":"buffered","m":"Paused, buffered for later"}
```

**Backward Compatibility:**
- request_id is optional (defaults to None)
- Old code works unchanged (no request_id in messages)
- New code can gradually adopt request IDs
- Old HID ignores unknown ResponseMessage type

---

## Part 2: Service Integration (Implementation Guide)

### Overview

To complete bidirectional communication, both services need:
1. **Request ID generation** (STT side)
2. **Response sending** (HID side)
3. **Response receiving** (STT side)
4. **Request tracking with timeouts** (STT side)

### 1. STT Service: Add Request ID Generation

**File:** `apps/stt/src/dictacode_stt/service.py`

**Add to __init__:**
```python
def __init__(self, ...):
    # ... existing code ...

    # v0.3.0 Phase 4: Request tracking
    self._request_counter = 0
    self._pending_requests: dict[str, PendingRequest] = {}
    self._request_lock = threading.Lock()

@dataclass
class PendingRequest:
    """Track a pending request awaiting response."""
    request_id: str
    message_type: str  # "text" or "command"
    payload: str
    sent_at: float
    timeout: float = 5.0
```

**Update send_text:**
```python
def send_text(self, text: str) -> str:
    """Send text over transport with request tracking.

    Returns:
        request_id for tracking the response
    """
    if not text:
        logger.warning("Empty text, not sending")
        return None

    # Generate unique request ID
    with self._request_lock:
        self._request_counter += 1
        request_id = f"text-{self._request_counter}"

    # Create message with request ID
    msg = TextMessage(payload=text, request_id=request_id)
    encoded = self.protocol.encode(msg)

    # Track pending request
    with self._request_lock:
        self._pending_requests[request_id] = PendingRequest(
            request_id=request_id,
            message_type="text",
            payload=text,
            sent_at=time.time(),
            timeout=5.0
        )

    if self.dry_run:
        logger.info(f"Would send {len(encoded)} bytes: {text} (id={request_id})")
        # ... existing dry_run code ...
        return request_id

    try:
        self.transport.send(encoded)
        logger.info(f"Sent {len(encoded)} bytes: {text} (id={request_id})")
        # ... existing success code ...
        return request_id
    except TransportError as e:
        # Remove from pending on send failure
        with self._request_lock:
            self._pending_requests.pop(request_id, None)
        logger.error(f"Transport send failed: {e}")
        # ... existing error handling ...
        return None
```

**Update send_command similarly:**
```python
def send_command(self, cmd: str, arg: Optional[str] = None) -> str:
    """Send command with request tracking.

    Returns:
        request_id for tracking the response
    """
    # Generate unique request ID
    with self._request_lock:
        self._request_counter += 1
        request_id = f"cmd-{self._request_counter}"

    msg = CommandMessage(command=cmd, argument=arg, request_id=request_id)
    # ... similar tracking logic as send_text ...
```

**Add request cleanup:**
```python
def _cleanup_stale_requests(self) -> None:
    """Remove stale requests that timed out."""
    now = time.time()
    with self._request_lock:
        stale = [
            req_id for req_id, req in self._pending_requests.items()
            if now - req.sent_at > req.timeout
        ]
        for req_id in stale:
            req = self._pending_requests.pop(req_id)
            logger.warning(
                f"Request {req_id} timed out after {req.timeout}s, no response from HID"
            )
            # TODO: Could trigger retry logic here
```

---

### 2. HID Service: Send Response Messages

**File:** `apps/hid/src/dictacode_hid/service.py`

**Update _handle_text:**
```python
def _handle_text(self, msg: TextMessage) -> None:
    """Process text message and send acknowledgment."""
    try:
        text = msg.payload
        request_id = msg.request_id

        # Handle typing based on mode
        if self.state.should_type():
            count = self._type_text(text)
            status = "ok"
            response_msg = f"Typed {count} characters"
        elif self.state.should_buffer():
            self.state.add_to_buffer(text)
            status = "buffered"
            response_msg = f"Buffered {len(text)} chars (mode={self.state.state.value})"
        else:
            status = "error"
            response_msg = f"Cannot type in {self.state.state.value} mode"

        # Send response if request_id present (v0.3.0 Phase 4)
        if request_id:
            self._send_response(request_id, status, response_msg)

        logger.info(
            f"Processed text: {len(text)} chars, status={status}"
            + (f", request_id={request_id}" if request_id else "")
        )

    except Exception as e:
        logger.error(f"Error typing text: {e}")
        if msg.request_id:
            self._send_response(msg.request_id, "error", str(e))

def _send_response(self, request_id: str, status: str, message: str = None) -> None:
    """Send ResponseMessage back to STT (v0.3.0 Phase 4).

    Args:
        request_id: Request ID from original message
        status: "ok", "error", or "buffered"
        message: Optional status message
    """
    from dictacode_hid.protocol import ResponseMessage

    response = ResponseMessage(
        request_id=request_id,
        status=status,
        message=message
    )

    try:
        data = self.protocol.encode(response)
        self.uart.write(data)
        logger.debug(f"Sent response: id={request_id}, status={status}")
    except Exception as e:
        logger.error(f"Failed to send response: {e}")
```

**Update _handle_command similarly:**
```python
def _handle_command(self, msg: CommandMessage) -> None:
    """Process command and send acknowledgment."""
    cmd = msg.command
    arg = msg.argument
    request_id = msg.request_id

    try:
        # Handle command
        if cmd == "keymap":
            success = self._change_keymap(arg)
            status = "ok" if success else "error"
            response_msg = f"Keymap changed to {arg}" if success else f"Unknown keymap: {arg}"
        elif cmd == "pause":
            self.state.transition_to(HidState.PAUSED)
            status = "ok"
            response_msg = "Service paused"
        # ... other commands ...
        else:
            status = "error"
            response_msg = f"Unknown command: {cmd}"

        # Send response
        if request_id:
            self._send_response(request_id, status, response_msg)

    except Exception as e:
        logger.error(f"Error handling command {cmd}: {e}")
        if request_id:
            self._send_response(request_id, "error", str(e))
```

---

### 3. STT Service: Receive and Handle Responses

**File:** `apps/stt/src/dictacode_stt/service.py`

**Challenge:** Current transport is **write-only** from STT perspective. Need to add **read capability**.

**Option 1: Polling in background thread**
```python
def __init__(self, ...):
    # ... existing code ...

    # Start response reader thread (v0.3.0 Phase 4)
    if not self.dry_run:
        self._response_reader_thread = threading.Thread(
            target=self._read_responses_loop,
            daemon=True
        )
        self._response_reader_thread.start()

def _read_responses_loop(self) -> None:
    """Background thread to read responses from HID."""
    logger.info("Response reader thread started")

    while not self._shutdown:
        try:
            # Try to read with timeout
            data = self.transport.readline_with_timeout(timeout=0.1)

            if data:
                msg = self.protocol.decode(data)

                if isinstance(msg, ResponseMessage):
                    self._handle_response(msg)
                else:
                    logger.warning(f"Unexpected message from HID: {type(msg).__name__}")

        except Exception as e:
            logger.error(f"Error reading response: {e}")
            time.sleep(0.1)  # Backoff on error

    logger.info("Response reader thread stopped")

def _handle_response(self, msg: ResponseMessage) -> None:
    """Handle ResponseMessage from HID."""
    request_id = msg.request_id
    status = msg.status
    message = msg.message or ""

    # Remove from pending
    with self._request_lock:
        req = self._pending_requests.pop(request_id, None)

    if not req:
        logger.warning(f"Received response for unknown request: {request_id}")
        return

    # Log result
    latency = time.time() - req.sent_at
    logger.info(
        f"Response for {request_id}: {status} "
        f"(latency={latency*1000:.1f}ms, msg='{message}')"
    )

    # Handle different statuses
    if status == "ok":
        # Success - nothing more to do
        pass
    elif status == "error":
        logger.error(f"HID reported error for {request_id}: {message}")
        # TODO: Could trigger retry logic
    elif status == "buffered":
        logger.info(f"HID buffered {request_id}: {message}")
        # Text will be typed when HID resumes

    # Broadcast status to WebSocket clients
    self._broadcast_websocket({
        "type": "response",
        "data": {
            "request_id": request_id,
            "status": status,
            "message": message,
            "latency_ms": latency * 1000
        }
    })
```

**Option 2: Async with asyncio** (more complex, requires refactoring)

---

### 4. Transport Layer Changes

**Challenge:** Current UART transport is asymmetric:
- STT: Only writes
- HID: Only reads

**Required:** Both sides need read+write capability.

**File:** `apps/stt/src/dictacode_stt/transport/uart.py` (and HID equivalent)

**Add readline_with_timeout:**
```python
class UartTransport(TransportAdapter):
    def readline_with_timeout(self, timeout: float = 1.0) -> bytes | None:
        """Read a line from UART with timeout.

        For JSON protocol (newline-delimited).

        Args:
            timeout: Read timeout in seconds

        Returns:
            Line bytes if available, None if timeout
        """
        if not self._serial:
            raise TransportError("Not connected")

        try:
            self._serial.timeout = timeout
            line = self._serial.readline()
            return line if line else None
        except serial.SerialException as e:
            raise TransportError(f"UART read failed: {e}")
```

**For MessagePack (length-prefixed):**
```python
def read_message_with_timeout(self, timeout: float = 1.0) -> bytes | None:
    """Read a msgpack message with timeout.

    Reads 2-byte length prefix, then reads that many bytes.
    """
    if not self._serial:
        raise TransportError("Not connected")

    try:
        self._serial.timeout = timeout

        # Read 2-byte length prefix
        length_bytes = self._serial.read(2)
        if len(length_bytes) < 2:
            return None  # Timeout

        length = int.from_bytes(length_bytes, "big")

        # Read message blob
        message_blob = self._serial.read(length)
        if len(message_blob) < length:
            raise TransportError(f"Incomplete message: got {len(message_blob)}/{length} bytes")

        return message_blob

    except serial.SerialException as e:
        raise TransportError(f"UART read failed: {e}")
```

---

## Testing Strategy

### Unit Tests

**File:** `apps/stt/tests/test_bidirectional_protocol.py`

```python
"""Tests for bidirectional protocol (v0.3.0 Phase 4)."""

import pytest
from dictacode_stt.protocol import (
    TextMessage, CommandMessage, ResponseMessage,
    JsonProtocol, MsgpackProtocol
)

def test_text_message_with_request_id():
    """Test encoding/decoding TextMessage with request_id."""
    protocol = JsonProtocol()

    msg = TextMessage(payload="hello", request_id="req-123")
    encoded = protocol.encode(msg)
    decoded = protocol.decode(encoded)

    assert decoded.payload == "hello"
    assert decoded.request_id == "req-123"

def test_text_message_without_request_id():
    """Test backward compatibility - no request_id."""
    protocol = JsonProtocol()

    msg = TextMessage(payload="hello")  # No request_id
    encoded = protocol.encode(msg)
    decoded = protocol.decode(encoded)

    assert decoded.payload == "hello"
    assert decoded.request_id is None

def test_response_message():
    """Test ResponseMessage encoding/decoding."""
    protocol = JsonProtocol()

    msg = ResponseMessage(request_id="req-456", status="ok", message="Success")
    encoded = protocol.encode(msg)
    decoded = protocol.decode(encoded)

    assert decoded.request_id == "req-456"
    assert decoded.status == "ok"
    assert decoded.message == "Success"

def test_response_message_error():
    """Test error response."""
    protocol = JsonProtocol()

    msg = ResponseMessage(request_id="req-789", status="error", message="Buffer full")
    encoded = protocol.encode(msg)
    decoded = protocol.decode(encoded)

    assert decoded.status == "error"
    assert decoded.message == "Buffer full"

def test_msgpack_protocol():
    """Test MessagePack protocol with ResponseMessage."""
    protocol = MsgpackProtocol()

    msg = ResponseMessage(request_id="req-001", status="buffered")
    encoded = protocol.encode(msg)

    # Strip 2-byte length prefix for decode
    message_blob = encoded[2:]
    decoded = protocol.decode(message_blob)

    assert decoded.request_id == "req-001"
    assert decoded.status == "buffered"
    assert decoded.message is None
```

### Integration Tests

**End-to-end test with mock transport:**

```python
def test_bidirectional_flow():
    """Test full request/response cycle."""
    # Create STT service with mock transport
    stt = SttService(dry_run=False, ...)

    # Create HID service with mock transport
    hid = HidService(...)

    # Connect them via in-memory queue
    stt_to_hid = queue.Queue()
    hid_to_stt = queue.Queue()

    # STT sends text with request_id
    request_id = stt.send_text("hello")

    # HID receives and responds
    msg = hid.receive_message()  # Gets TextMessage
    assert msg.request_id == request_id
    hid._handle_text(msg)  # Sends ResponseMessage

    # STT receives response
    response = stt.receive_response(timeout=1.0)
    assert response.request_id == request_id
    assert response.status == "ok"
```

---

## Rollout Plan

### Phase 1: Testing (Safe)
1. Deploy protocol changes (already done - backward compatible)
2. Verify old code still works
3. Monitor for any issues

### Phase 2: STT Request IDs (Low Risk)
1. Add request ID generation to STT send_text/send_command
2. Deploy to test device
3. Verify HID still processes messages (ignores unknown request_id field)

### Phase 3: HID Responses (Medium Risk)
1. Add response sending to HID service
2. Deploy to test device
3. Verify STT ignores unknown ResponseMessage type (not reading yet)

### Phase 4: STT Response Reading (High Risk)
1. Add background reader thread to STT
2. Add transport read methods
3. **Thorough testing** - this is the risky part
4. Deploy gradually, monitor closely

---

## Risks and Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Transport read blocks send** | STT can't send while waiting for response | Use timeout reads, separate thread |
| **Backward compatibility** | Old HID/STT can't communicate | request_id is optional, ResponseMessage ignored by old code |
| **Deadlock** | Both sides waiting to read | Non-blocking reads with timeout |
| **Buffer overflow** | Too many pending requests | Limit pending queue size, cleanup stale requests |
| **Performance** | Extra overhead from tracking | Minimal - only when request_id used |

---

## Future Enhancements

Once bidirectional protocol is stable:

1. **Retry Logic**: Automatically retry failed messages
2. **Flow Control**: HID tells STT to slow down when buffer full
3. **Health Checks**: Ping/pong to verify link is alive
4. **Statistics**: Track success rate, latency, errors
5. **Web UI**: Display response status and latency in control panel

---

## References

- Protocol implementation: `apps/stt/src/dictacode_stt/protocol.py`
- STT service: `apps/stt/src/dictacode_stt/service.py`
- HID service: `apps/hid/src/dictacode_hid/service.py`
- Architecture plan: `docs/architecture-plan-v0.3.0.md`
