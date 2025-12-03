# v0.3.16 - Pause Typing & Mute Mic Buttons in Live Status

## Goal

Add two control buttons to `/cp/live`:
1. **Pause Typing** - Pauses HID keyboard output (transcription continues, text buffered)
2. **Mute Mic** - Software mute of microphone input (stops transcription at source)

## Architecture

### Pause Typing (HID)

**Current behavior:**
- Protocol supports `CommandMessage(command="pause")` to HID
- HID has `DeviceMode.PAUSED` that buffers text instead of typing
- No API endpoint currently sends pause command to HID

**Desired behavior:**
- STT continues transcribing and sending text
- HID receives text but buffers it (doesn't type)
- Transcriptions visible in `/cp/live`
- Clear "Typing Paused" indicator
- Resume flushes buffer and types all buffered text

### Mute Mic (Audio)

**Current behavior:**
- Audio stream feeds directly to ring buffer → transcriber
- No way to temporarily stop audio without stopping the stream
- `POST /v1/api/service/pause` pauses entire STT state machine

**Desired behavior:**
- Software mute stops feeding audio to transcriber
- Audio stream stays open (no device reconnection needed)
- "Muted" indicator shown in UI
- Unmute resumes normal audio flow immediately
- Transcription iteration continues but gets silence/no data

## Implementation

### Phase 1: HID Typing Pause

#### 1.1 Add HID Typing State to SttService

**File:** `apps/stt/src/dictacode_stt/service.py`

Track whether we've sent pause to HID:
```python
# In __init__:
self._hid_typing_paused: bool = False

def pause_hid_typing(self) -> bool:
    """Send pause command to HID (typing only)."""
    if self.send_command("pause"):
        self._hid_typing_paused = True
        return True
    return False

def resume_hid_typing(self) -> bool:
    """Send resume command to HID."""
    if self.send_command("resume"):
        self._hid_typing_paused = False
        return True
    return False

def is_hid_typing_paused(self) -> bool:
    return self._hid_typing_paused
```

#### 1.2 Add HID API Endpoints

**File:** `apps/stt/src/dictacode_stt/api.py`

```python
@app.post("/v1/api/hid/pause")
async def pause_hid_typing():
    """Pause HID typing (transcription continues)."""
    if _service_instance.pause_hid_typing():
        return {"status": "ok", "hid_paused": True}
    return JSONResponse({"status": "error", "message": "Failed to send pause"}, 500)

@app.post("/v1/api/hid/resume")
async def resume_hid_typing():
    """Resume HID typing (flushes buffer)."""
    if _service_instance.resume_hid_typing():
        return {"status": "ok", "hid_paused": False}
    return JSONResponse({"status": "error", "message": "Failed to send resume"}, 500)

@app.get("/v1/api/hid/status")
async def get_hid_status():
    """Get HID typing status."""
    return {"hid_paused": _service_instance.is_hid_typing_paused()}
```

#### 1.3 Include HID Typing State in Live Status

**File:** `apps/stt/src/dictacode_stt/diagnostics/aggregator.py`

Add to `get_status()` response:
```python
# In transport component or as separate field:
components["hid_typing"] = {
    "paused": self.service.is_hid_typing_paused() if hasattr(self.service, "is_hid_typing_paused") else False
}
```

### Phase 2: Microphone Software Mute

#### 2.1 Add Mute State to SttService

**File:** `apps/stt/src/dictacode_stt/service.py`

```python
# In __init__:
self._mic_muted: bool = False

def mute_mic(self) -> bool:
    """Software mute - stop feeding audio to transcriber."""
    self._mic_muted = True
    return True

def unmute_mic(self) -> bool:
    """Resume feeding audio to transcriber."""
    self._mic_muted = False
    return True

def is_mic_muted(self) -> bool:
    return self._mic_muted
```

#### 2.2 Gate Audio in Transcription Loop

**File:** `apps/stt/src/dictacode_stt/service.py`

In the audio callback or ring buffer read:
```python
# Before passing audio to transcriber:
if self._mic_muted:
    # Skip this audio chunk - effectively silence
    continue
```

#### 2.3 Add Mute API Endpoints

**File:** `apps/stt/src/dictacode_stt/api.py`

```python
@app.post("/v1/api/audio/mute")
async def mute_mic():
    """Software mute microphone input."""
    _service_instance.mute_mic()
    return {"status": "ok", "mic_muted": True}

@app.post("/v1/api/audio/unmute")
async def unmute_mic():
    """Unmute microphone input."""
    _service_instance.unmute_mic()
    return {"status": "ok", "mic_muted": False}

@app.get("/v1/api/audio/status")
async def get_audio_mute_status():
    """Get microphone mute status."""
    return {"mic_muted": _service_instance.is_mic_muted()}
```

#### 2.4 Include Mute State in Live Status

**File:** `apps/stt/src/dictacode_stt/diagnostics/aggregator.py`

```python
components["audio"]["muted"] = self.service.is_mic_muted() if hasattr(self.service, "is_mic_muted") else False
```

### Phase 3: UI Implementation

#### 3.1 Add UI Elements to live.html

**File:** `apps/stt/src/dictacode_stt/templates/live.html`

Add buttons in refresh-controls:
```html
<div class="refresh-controls">
  <button class="primary" id="refresh-btn">Refresh</button>
  <button class="primary" id="pause-typing-btn">⏸ Pause Typing</button>
  <button class="primary" id="mute-mic-btn">🎤 Mute Mic</button>
  <!-- existing auto-refresh controls -->
</div>
```

Add dedicated indicators:
```html
<div class="control-status" id="typing-status" style="display: none;">
  <span class="status-icon">⏸</span>
  <span class="status-text">Typing Paused - transcriptions buffered</span>
</div>

<div class="control-status muted" id="mute-status" style="display: none;">
  <span class="status-icon">🔇</span>
  <span class="status-text">Microphone Muted</span>
</div>
```

Add CSS:
```css
.control-status {
  padding: 8px 16px;
  border-radius: 4px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
}

#typing-status {
  background: #fff3cd;
  border: 1px solid #ffc107;
  color: #856404;
}

#mute-status {
  background: #f8d7da;
  border: 1px solid #f5c6cb;
  color: #721c24;
}

.control-status .status-icon {
  font-size: 1.2em;
}
```

#### 3.2 Add JavaScript Handlers

**File:** `apps/stt/src/dictacode_stt/static/js/live.js`

```javascript
// Toggle pause/resume typing
async function toggleTypingPause() {
  const btn = document.getElementById('pause-typing-btn');
  const isPaused = btn.dataset.paused === 'true';
  const endpoint = isPaused ? '/v1/api/hid/resume' : '/v1/api/hid/pause';

  btn.disabled = true;
  try {
    const resp = await fetch(endpoint, { method: 'POST' });
    const data = await resp.json();
    if (data.status === 'ok') {
      updateTypingStatus(data.hid_paused);
    }
  } finally {
    btn.disabled = false;
  }
}

// Toggle mute/unmute mic
async function toggleMicMute() {
  const btn = document.getElementById('mute-mic-btn');
  const isMuted = btn.dataset.muted === 'true';
  const endpoint = isMuted ? '/v1/api/audio/unmute' : '/v1/api/audio/mute';

  btn.disabled = true;
  try {
    const resp = await fetch(endpoint, { method: 'POST' });
    const data = await resp.json();
    if (data.status === 'ok') {
      updateMuteStatus(data.mic_muted);
    }
  } finally {
    btn.disabled = false;
  }
}

function updateTypingStatus(paused) {
  const btn = document.getElementById('pause-typing-btn');
  const indicator = document.getElementById('typing-status');

  btn.textContent = paused ? '▶ Resume Typing' : '⏸ Pause Typing';
  btn.dataset.paused = paused;
  indicator.style.display = paused ? 'flex' : 'none';
}

function updateMuteStatus(muted) {
  const btn = document.getElementById('mute-mic-btn');
  const indicator = document.getElementById('mute-status');

  btn.textContent = muted ? '🔊 Unmute Mic' : '🎤 Mute Mic';
  btn.dataset.muted = muted;
  indicator.style.display = muted ? 'flex' : 'none';
}

// In updateUI(), add:
updateTypingStatus(data.components?.hid_typing?.paused || false);
updateMuteStatus(data.components?.audio?.muted || false);

// Event listeners
document.getElementById('pause-typing-btn').addEventListener('click', toggleTypingPause);
document.getElementById('mute-mic-btn').addEventListener('click', toggleMicMute);
```

## Files to Modify

| File | Changes |
|------|---------|
| `service.py` | Add `_hid_typing_paused`, `_mic_muted`, pause/resume/mute methods |
| `api.py` | Add `/v1/api/hid/pause`, `/v1/api/hid/resume`, `/v1/api/audio/mute`, `/v1/api/audio/unmute` |
| `aggregator.py` | Include `hid_typing.paused` and `audio.muted` in live status |
| `templates/live.html` | Add buttons and indicators with CSS |
| `static/js/live.js` | Add toggle functions, update handlers, event listeners |

## Protocol Flow

### Pause Typing

```
User clicks "Pause Typing"
    → POST /v1/api/hid/pause
    → SttService.pause_hid_typing()
    → SttService.send_command("pause")
    → Transport sends: {"t": "cmd", "c": "pause"}
    → HID receives, sets DeviceMode.PAUSED
    → HID buffers incoming text instead of typing

User clicks "Resume Typing"
    → POST /v1/api/hid/resume
    → SttService.resume_hid_typing()
    → SttService.send_command("resume")
    → Transport sends: {"t": "cmd", "c": "resume"}
    → HID receives, sets DeviceMode.NORMAL
    → HID flushes buffer (types all buffered text)
```

### Mute Mic

```
User clicks "Mute Mic"
    → POST /v1/api/audio/mute
    → SttService.mute_mic()
    → Sets _mic_muted = True
    → Audio callback skips chunks
    → Transcriber receives no audio
    → No transcriptions generated

User clicks "Unmute Mic"
    → POST /v1/api/audio/unmute
    → SttService.unmute_mic()
    → Sets _mic_muted = False
    → Audio flows to transcriber again
    → Transcriptions resume
```

## Display

**Transport component** shows:
- Connected status (existing)
- "(Typing Paused)" label when paused

**Audio component** shows:
- Device info (existing)
- "(Muted)" label when muted

**Dedicated indicators**:
- Yellow bar: "⏸ Typing Paused - transcriptions buffered"
- Red bar: "🔇 Microphone Muted"
- Visible only when active

**Button states:**
- Pause: "⏸ Pause Typing" ↔ "▶ Resume Typing"
- Mute: "🎤 Mute Mic" ↔ "🔊 Unmute Mic"

## Testing

1. Start STT service with HID connected
2. Navigate to `/cp/live`
3. Click "Pause Typing" - verify:
   - Button changes to "Resume Typing"
   - Yellow indicator appears
   - Speaking still produces transcriptions in list
   - No typing occurs on HID
4. Click "Resume Typing" - verify:
   - Buffered text is typed
   - Button reverts
   - Indicator disappears
5. Click "Mute Mic" - verify:
   - Button changes to "Unmute Mic"
   - Red indicator appears
   - No new transcriptions appear
   - Audio stream stays connected
6. Click "Unmute Mic" - verify:
   - Transcriptions resume
   - Button reverts
   - Indicator disappears
