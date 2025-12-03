# v0.3.17: Per-Utterance Tracing

**Goal**: Diagnose dropped content by tracing each utterance through the pipeline with unique IDs.

## Problem
Speech is captured but parts don't get typed. Need visibility into WHERE content is lost.

## Key Insight
`protocol.py` already has `request_id` fields on TextMessage (line 23) and ResponseMessage (lines 56-69) - currently unused. We leverage this for end-to-end tracing.

---

## Architecture

```
STT Device                                    HID Device
──────────                                    ──────────
[1] run_once() → create trace_id
     ↓
[2] audio capture → mark audio_captured
     ↓
[3] transcribe() → mark transcription_*
     ↓
[4] send_text(text, trace_id) → mark transport_sent
     │                                        │
     └═══════ UART/WiFi ═════════════════════►[5] extract trace_id
                                              ↓
                                         [6] _type_text() → ResponseMessage(trace_id, status)
                                              │
◄═══════════════════════════════════════════════╝
     ↓
[7] mark completed or dropped
```

---

## Implementation

### Phase 1: Core Infrastructure

**New file**: `apps/stt/src/dictacode_stt/tracing.py`
- `TraceStatus` enum: `IN_PROGRESS`, `COMPLETED`, `DROPPED`, `TIMEOUT`
- `UtteranceTrace` dataclass: timestamps for each stage, drop_point, drop_reason
- `TraceRegistry` class: ring buffer of 100 traces, methods for create/mark/stats

### Phase 2: STT Instrumentation

**File**: `apps/stt/src/dictacode_stt/service.py`

| Location | Change |
|----------|--------|
| `__init__` | Add `self._trace_registry = TraceRegistry()` |
| `run_once()` ~1651 | Create trace: `trace = self._trace_registry.create_trace()` |
| After audio read ~1677 | `trace.mark_stage("audio_captured")` |
| Empty audio ~1673 | `trace.mark_drop("no_audio", "No audio data received")` |
| Before transcribe ~1689 | `trace.mark_stage("transcription_started")` |
| After transcribe ~1691 | `trace.mark_stage("transcription_completed"); trace.text_raw = text` |
| Empty transcription ~1717 | `trace.mark_drop("transcription_empty", "ASR returned empty")` |
| `send_text()` | Pass `request_id=trace.trace_id` in TextMessage |

**File**: `apps/stt/src/dictacode_stt/audio/buffer.py`
- Add `on_eviction` callback to `__init__`
- Call callback when chunks evicted (line 88-93)
- Service registers callback to mark drop: `trace.mark_drop("buffer_eviction", ...)`

### Phase 3: HID Response

**File**: `apps/hid/src/dictacode_hid/service.py`

| Location | Change |
|----------|--------|
| `_handle_text()` ~397 | Extract: `trace_id = msg.request_id` |
| After typing ~416 | Send: `ResponseMessage(request_id=trace_id, status="ok")` |
| On error | Send: `ResponseMessage(request_id=trace_id, status="error", message=reason)` |

**File**: `apps/stt/src/dictacode_stt/service.py`
- Handle incoming ResponseMessage in receive loop
- On response: `self._trace_registry.mark_completed(trace_id, timestamp)`

### Phase 4: IPC & API

**File**: `apps/stt/src/dictacode_stt/diagnostics/ipc.py`
Add methods:
- `trace.recent` → get last N traces
- `trace.drops` → get dropped traces only
- `trace.stats` → aggregate stats (completed/dropped/drop_points histogram)

**File**: `apps/stt/src/dictacode_stt/diagnostics/aggregator.py`
- Include `traces` component in status response with stats + recent list

### Phase 5: Live UI

**File**: `apps/stt/src/dictacode_stt/templates/live.html`
Add "Utterance Traces" panel:
- Summary: completed/dropped/in-progress counts
- Drop histogram: bar chart of drop points
- Recent traces table: trace_id, status, drop_point, latency, age

**File**: `apps/stt/src/dictacode_stt/static/js/live.js`
- `updateTracePanel()` function
- Call from `updateUI()` when trace data present

### Phase 6: Logging & Metrics

**File**: `apps/stt/src/dictacode_stt/logging_config.py`
- Add `trace_id`, `trace_stage`, `drop_point` to JSON formatter

**File**: `apps/stt/src/dictacode_stt/metrics.py`
Add:
- `dictacode_utterances_total{status}` counter
- `dictacode_utterance_drops_total{drop_point}` counter
- `dictacode_utterance_latency_seconds` histogram

---

## Files to Modify

| File | Type |
|------|------|
| `apps/stt/src/dictacode_stt/tracing.py` | NEW |
| `apps/stt/src/dictacode_stt/service.py` | MODIFY |
| `apps/stt/src/dictacode_stt/audio/buffer.py` | MODIFY |
| `apps/stt/src/dictacode_stt/diagnostics/ipc.py` | MODIFY |
| `apps/stt/src/dictacode_stt/diagnostics/aggregator.py` | MODIFY |
| `apps/stt/src/dictacode_stt/metrics.py` | MODIFY |
| `apps/stt/src/dictacode_stt/logging_config.py` | MODIFY |
| `apps/stt/src/dictacode_stt/templates/live.html` | MODIFY |
| `apps/stt/src/dictacode_stt/static/js/live.js` | MODIFY |
| `apps/hid/src/dictacode_hid/service.py` | MODIFY |

---

## Known Drop Points to Instrument

| Stage | Condition | Drop Point Name |
|-------|-----------|-----------------|
| Audio capture | `_mic_muted = True` | `mic_muted` |
| Audio capture | No audio data | `no_audio` |
| Buffer | Eviction (>5s) | `buffer_eviction` |
| Transcription | Empty result | `transcription_empty` |
| Transcription | ASR error | `transcription_error` |
| Transport | Send failure | `transport_error` |
| HID | Unmapped chars | `unmapped_chars` |

---

## Output Channels

1. **Live UI**: Real-time trace panel at `/cp/live`
2. **Logs**: JSON logs with `trace_id` field for filtering (`jq 'select(.trace_id)'`)
3. **Metrics**: Prometheus endpoint at `:9100/metrics`
4. **IPC**: `trace.*` methods via Unix socket

---

## Quick Diagnosis Flow

1. Open `/cp/live` → check drop histogram
2. If drops concentrated at one stage → investigate that component
3. Filter logs: `journalctl -u dictacode-stt | jq 'select(.drop_point)'`
4. Check metrics: `curl :9100/metrics | grep utterance`
