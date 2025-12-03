# v0.3.14 - Transcription History Panel in Live Status

## Goal
Add a new HTML container to `/cp/live` that displays the last 12 transcribed inputs, with the latest on top.

## Architecture

The live status page uses **polling** (not WebSockets):
- `live.js` fetches `/v1/api/status/live` every 5 seconds
- `DiagnosticsAggregator.get_status()` collects data from all components
- Response includes `components` (audio, asr, transport, ipc) and `flow` (staleness detection)

Transcriptions flow through `SttService`:
- `_broadcast_websocket()` sends transcriptions to WebSocket clients
- `_last_transcription` stores last text for deduplication
- **No history is currently stored** - this is what we're adding

## Implementation

### Step 1: Add Transcription History Buffer to SttService
**File:** `apps/stt/src/dictacode_stt/service.py`

- Add `TranscriptionEntry` dataclass
- Add `_transcription_history` deque (maxlen=12) to `__init__`
- Add `_record_transcription()` method
- Add `transcription_history()` method for status API
- Call recording from `_process_pipeline_iteration()` and `_on_final_result()`

### Step 2: Update DiagnosticsAggregator
**File:** `apps/stt/src/dictacode_stt/diagnostics/aggregator.py`

- Add `transcriptions` component to `get_status()` response

### Step 3: Add UI Panel to live.html
**File:** `apps/stt/src/dictacode_stt/templates/live.html`

- Add CSS styles for transcription panel
- Add HTML section after component-grid

### Step 4: Update live.js
**File:** `apps/stt/src/dictacode_stt/static/js/live.js`

- Add `updateTranscriptions()` function
- Call from `updateUI()`

## Files to Modify

| File | Changes |
|------|---------|
| `service.py` | Add history buffer, recording, and API method |
| `aggregator.py` | Include transcriptions in status response |
| `templates/live.html` | Add transcription panel UI |
| `static/js/live.js` | Render transcriptions |

## Testing

1. Deploy and restart service
2. Speak into microphone
3. Verify transcriptions appear in Live Status page
4. Verify latest is on top, max 12 entries
