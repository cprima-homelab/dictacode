# dictacode Architecture Plan v0.2.4 - Audio Port Abstraction

## Status

### Phase 1: Port Discovery
- [x] Create `apps/stt/src/dictacode_stt/audio/` package
- [x] Implement `AudioPortCapabilities`, `PortStatus`, `AudioPort` dataclasses
- [x] Implement `AudioPortManager.list_ports()` using sounddevice
- [x] Generate stable port IDs (serial/name → USB path → ALSA fallback)
- [x] Unit tests for port enumeration

**Phase 1 COMPLETED** - Commit: 8c4d449

### Phase 2: Streaming + Buffer
- [x] Implement `AudioPort.start_stream()`, `stop_stream()` with callbacks
- [x] Implement `AudioRingBuffer` with overlap for word cutoff fix
- [x] Implement `Resampler` class (native rate → 16kHz)
- [x] Handle device errors (underrun, disconnection)
- [x] Unit tests for streaming and buffer

**Phase 2 COMPLETED** - Commit: 0a55fec

### Phase 3: CLI Integration
- [x] Add `dictacode-stt-audio ports` command
- [x] Human-readable and `--json` output
- [x] Add `--port` flag to `dictacode-stt-audio test` and `record`
- [x] Update `dictacode-stt` main service to accept `--port PORT_ID`

**Phase 3 COMPLETED** - Commit: 54c48fa

### Phase 4: Service Layer Refactor
- [ ] Inject `AudioPortManager` into `SttService`
- [ ] Replace direct sounddevice calls with streaming callbacks
- [ ] Use `AudioRingBuffer` for continuous capture
- [ ] Deduplicate overlapping transcriptions
- [ ] Integration tests with service

### Phase 5: Device Configuration Files
- [ ] Create `/etc/dictacode/audio/` directory structure
- [ ] Implement `generic.conf` baseline profile
- [ ] Implement `rode-videomic-ntg.conf` known device profile
- [ ] Implement `audio.conf` main configuration
- [ ] Add profile matching logic (exact → vendor → generic)
- [ ] Update .deb packaging to install conffiles

### Phase 6: Backend API (for web)
- [ ] Add `/api/audio/ports` endpoint (preparation for v0.3.0)
- [ ] Add `/api/audio/select` endpoint to change active port
- [ ] Document API schema

**v0.2.4 NOT STARTED**

---

## Prerequisites

v0.2.4 builds on top of v0.2.3:
- ✅ SolutionState model with lifecycle management
- ✅ Supervisor detection and signaling
- ✅ systemd watchdog integration

---

## Problem Statement

### Immediate Issue (Symptom)
During testing of `dictacode-stt-audio test`, the command failed:
```
ERROR: Audio recording failed: Invalid sample rate
```
Root cause: Code hardcoded 16kHz, but RØDE VideoMic NTG only supports 48kHz.

### Deeper Issue (Architecture Gap)
The STT app lacks a proper **Audio Port Abstraction Layer**. Compare to UART:

| Concern | UART (v0.2.x) | Audio (current) |
|---------|---------------|-----------------|
| Transport layer | ✅ `UartTransport` class | ❌ Direct sounddevice calls |
| Device enumeration | ✅ `/dev/serial0` path | ❌ Integer index only |
| Capabilities query | - | ❌ Hardcoded 48kHz/16kHz |
| Exclusive locking | ✅ `SerialLock` | ❌ None |
| Error abstraction | ✅ Transport exceptions | ❌ Raw sounddevice errors |
| Hot-plug handling | - | ❌ None |

### Device Driver Functions (Inspiration)
A proper audio abstraction should mirror device driver patterns:
- **init hardware** - detect available ports
- **configure interface** - sample rate, channels, format
- **read data** - capture audio
- **handle callbacks** - on_data, on_error
- **manage buffers** - ring buffer, overflow handling
- **expose exclusive handle** - prevent concurrent access
- **report errors** - underrun, overrun, device lost
- **provide raw byte I/O API** - for pipeline consumption

### Hardware Reality
Solution must support:
- **USB microphones** (current: RØDE VideoMic NTG @ 48kHz)
- **Board-native 3.5mm jacks** (future: Pi audio jack, I2S mics)
- Different sample rates per device
- Multiple devices potentially in parallel

### Known Issue: Word Cutoff Bug

**Symptom:** Current pipeline cuts off 1-2 words at audio boundaries.

**Suspected cause:**
- Fixed-duration recording windows (e.g., 3 seconds)
- No overlap between recording segments
- Speech that spans recording boundaries gets split

**Solution in v0.2.4:**
```
Current (broken):
  [record 3s]───[transcribe]───[record 3s]───[transcribe]
                     ↑ gap here - words lost

New (ring buffer):
  ════════════════════════════════════════════  ← continuous stream
        ↓ read pointer with overlap
  [───────transcribe───────]
            [───────transcribe───────]
                  [───────transcribe───────]
```

---

## Scope

### Audio Port Abstraction Layer

Proper driver-like abstraction for audio hardware.

```
┌─────────────────────────────────────────────────────────────────┐
│                    Audio Port Abstraction                        │
│                                                                  │
│  AudioPortManager                    AudioPort                   │
│  ├── list_ports() → List[AudioPort] ├── port_id                 │
│  ├── get_port(id) → AudioPort       ├── port_type (USB/JACK)    │
│  ├── get_default_port()             ├── capabilities            │
│  └── on_port_changed callback       ├── open() / close()        │
│                                      ├── configure(rate, ch)    │
│                                      └── start_stream(callbacks) │
│                                                                  │
│  CLI Interface                       Backend API (for web)       │
│  └── dictacode-stt-audio ports       └── GET /api/audio/ports   │
│      Returns port list with          Returns JSON for frontend  │
│      metadata for human or JSON                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Design

### Port Identification

Stable port IDs with fallback hierarchy (device follows user, not port):

```
PORT_ID Resolution Priority:
  1. Device serial/name  → "rode-ntg-12345" (USB serial number or unique name)
  2. USB bus path        → "usb:1-1.3"      (fallback if no serial)
  3. ALSA card path      → "hw:1,0"         (last resort for built-in)

Examples:
  rode-ntg-12345     - USB mic with serial (preferred - follows device)
  usb:1-1.3          - USB device without serial (stable per port)
  hw:0               - Built-in audio (ALSA card 0)
```

**Rationale:** Device serial/name makes the port ID follow the physical device
when moved to a different USB port. User's configuration stays valid.

### AudioPort Class

```python
@dataclass
class AudioPortCapabilities:
    """Hardware capabilities of an audio port."""
    sample_rates: List[int]           # [44100, 48000, 96000]
    channels: int                      # max input channels
    formats: List[str]                 # ["int16", "float32"]
    native_rate: int                   # default/optimal rate

class PortStatus(Enum):
    AVAILABLE = "available"
    IN_USE = "in_use"
    ERROR = "error"
    DISCONNECTED = "disconnected"

# Callback types for streaming API
AudioDataCallback = Callable[[bytes], None]      # on_data(chunk)
AudioErrorCallback = Callable[[Exception], None] # on_error(err)

@dataclass
class AudioPort:
    """Abstraction of a physical audio input port."""
    port_id: str                       # Stable identifier (serial/name preferred)
    port_type: str                     # "usb" | "jack" | "alsa"
    name: str                          # Human-readable name
    capabilities: AudioPortCapabilities
    status: PortStatus

    # Driver-like interface
    def open(self) -> None: ...
    def close(self) -> None: ...
    def configure(self, sample_rate: int, channels: int) -> None: ...

    # Streaming API (primary)
    def start_stream(
        self,
        on_data: AudioDataCallback,
        on_error: AudioErrorCallback,
        chunk_size: int = 1024
    ) -> None:
        """Start continuous audio capture with callbacks."""
        ...

    def stop_stream(self) -> None:
        """Stop audio capture."""
        ...

    def is_streaming(self) -> bool: ...
    def is_healthy(self) -> bool: ...
```

**Streaming rationale:** Real-time STT benefits from continuous audio flow.
The service can process chunks as they arrive rather than waiting for
a full duration. This also enables future partial/streaming transcription.

### AudioPortManager Class

```python
class AudioPortManager:
    """
    Manages audio port discovery and lifecycle.
    Backend returns this data to CLI and web frontend.
    """

    def list_ports(self) -> List[AudioPort]:
        """Enumerate all available audio input ports."""
        ...

    def get_port(self, port_id: str) -> Optional[AudioPort]:
        """Get specific port by stable ID."""
        ...

    def get_default_port(self) -> Optional[AudioPort]:
        """Get system default audio input."""
        ...

    def get_active_port(self) -> Optional[AudioPort]:
        """Get currently recording port (if any)."""
        ...

    # For future hot-plug support
    def register_callback(self, on_port_changed: Callable) -> None:
        ...
```

### AudioRingBuffer Class

```python
class AudioRingBuffer:
    """Circular buffer with overlap for continuous audio."""

    def __init__(self, max_seconds: float, overlap_seconds: float = 0.5):
        self.overlap_samples = int(overlap_seconds * SAMPLE_RATE)
        self._buffer = collections.deque(maxlen=max_samples)
        self._read_pos = 0

    def write(self, chunk: bytes) -> None:
        """Write audio chunk to buffer."""
        ...

    def read_for_transcription(self) -> bytes:
        """Read audio with overlap to prevent word cutoff."""
        # Include overlap_samples from previous segment
        start = max(0, self._read_pos - self.overlap_samples)
        audio = self._buffer[start:]
        self._read_pos = len(self._buffer)  # Move read pointer
        return audio
```

**Overlap ensures:** Words at segment boundaries are captured in both
segments. Whisper sees them in context; duplicate text can be deduplicated
by comparing with previous transcription.

### CLI Output (Human + JSON)

```bash
$ dictacode-stt-audio ports
AUDIO PORTS
───────────────────────────────────────────────────────────
PORT_ID           TYPE  NAME                    STATUS     RATES
rode-ntg-12345    USB   RØDE VideoMic NTG       available  48000
hw:0              JACK  bcm2835 Headphones      available  44100,48000

Active: rode-ntg-12345 (recording @ 48kHz)

$ dictacode-stt-audio ports --json
{
  "ports": [
    {
      "port_id": "rode-ntg-12345",
      "port_type": "usb",
      "name": "RØDE VideoMic NTG",
      "status": "available",
      "capabilities": {
        "sample_rates": [48000],
        "channels": 2,
        "formats": ["int16"],
        "native_rate": 48000
      }
    }
  ],
  "active_port": "rode-ntg-12345",
  "pipeline_target_rate": 16000
}
```

### Integration with Service Layer

```python
# In SttService
class SttService:
    def __init__(self, port_manager: AudioPortManager, port_id: str = None):
        self.port_manager = port_manager
        self.port = self._select_port(port_id)
        self._audio_buffer = AudioRingBuffer(max_seconds=5.0)
        self._resampler = Resampler(target_rate=16000)

    def _select_port(self, port_id: str) -> AudioPort:
        """Auto or manual port selection."""
        if port_id:
            return self.port_manager.get_port(port_id)
        return self.port_manager.get_default_port()

    def _on_audio_data(self, chunk: bytes) -> None:
        """Callback: new audio chunk received."""
        resampled = self._resampler.process(chunk, self.port.capabilities.native_rate)
        self._audio_buffer.write(resampled)

    def _on_audio_error(self, err: Exception) -> None:
        """Callback: audio error occurred."""
        logger.error(f"Audio error: {err}")
        self.supervisor.signal_port_error(err)

    def _start_audio_capture(self) -> None:
        """Start streaming audio from selected port."""
        self.port.open()
        self.port.configure(
            sample_rate=self.port.capabilities.native_rate,
            channels=1  # mono for STT
        )
        self.port.start_stream(
            on_data=self._on_audio_data,
            on_error=self._on_audio_error,
            chunk_size=1024
        )

    def _transcribe_buffer(self) -> Optional[str]:
        """Transcribe accumulated audio from buffer."""
        audio = self._audio_buffer.read_for_transcription()
        if len(audio) < MIN_AUDIO_SAMPLES:
            return None
        return self._whisper_transcribe(audio)
```

**Buffer + Streaming:** Audio streams continuously into a ring buffer.
The transcription loop reads from the buffer when there's enough data.
This decouples capture rate from transcription rate.

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── audio/                    # NEW: Audio port abstraction
│   ├── __init__.py           # Public exports
│   ├── port.py               # AudioPort, AudioPortCapabilities, PortStatus
│   ├── manager.py            # AudioPortManager (enumerate, select)
│   ├── buffer.py             # AudioRingBuffer with overlap (fixes word cutoff)
│   ├── resampler.py          # Resampler (native rate → 16kHz)
│   └── device_id.py          # Stable port ID generation (serial/USB/ALSA)
├── cli.py                    # MODIFIED: Add 'ports' command
├── service.py                # MODIFIED: Use AudioPortManager + streaming
└── ...existing...
```

---

## Files to Modify

1. `apps/stt/src/dictacode_stt/audio/__init__.py` - NEW: Package init, public exports
2. `apps/stt/src/dictacode_stt/audio/port.py` - NEW: AudioPort, capabilities, streaming API
3. `apps/stt/src/dictacode_stt/audio/manager.py` - NEW: AudioPortManager
4. `apps/stt/src/dictacode_stt/audio/buffer.py` - NEW: AudioRingBuffer with overlap
5. `apps/stt/src/dictacode_stt/audio/resampler.py` - NEW: Resampler class
6. `apps/stt/src/dictacode_stt/audio/device_id.py` - NEW: Stable port ID generation
7. `apps/stt/src/dictacode_stt/cli.py` - Add `ports` subcommand
8. `apps/stt/src/dictacode_stt/service.py` - Use AudioPortManager, streaming, buffer
9. `apps/stt/src/dictacode_stt/main.py` - Add `--port PORT_ID` argument
10. `apps/stt/pyproject.toml` - Update entry points if needed

---

## Tests to Add

- `test_port_enumeration` - List ports returns valid data
- `test_stable_port_id` - Port IDs persist across enumerations (serial preferred)
- `test_port_id_fallback` - Falls back to USB path, then ALSA if no serial
- `test_port_capabilities` - Sample rates, channels correctly reported
- `test_streaming_callbacks` - on_data and on_error called correctly
- `test_ring_buffer_overlap` - Overlap samples included in reads
- `test_ring_buffer_no_cutoff` - Audio at boundaries not lost
- `test_resampling` - Native rate → 16kHz resampling correct
- `test_port_not_found` - Graceful handling of invalid port_id
- `test_cli_ports_human` - Human-readable output format
- `test_cli_ports_json` - JSON output schema

---

## Success Criteria

v0.2.4 is complete when:

1. ✅ `AudioPort` with streaming API (start_stream, stop_stream, callbacks)
2. ✅ `AudioPortManager` with list_ports, get_port, get_default_port
3. ✅ Stable port IDs: device serial/name (preferred) → USB path → ALSA
4. ✅ `AudioRingBuffer` with overlap (fixes word cutoff bug)
5. ✅ `Resampler` class (native rate → 16kHz for Whisper)
6. ✅ `dictacode-stt-audio ports` returns all input ports with metadata
7. ✅ `--json` output suitable for web frontend consumption
8. ✅ `dictacode-stt --port PORT_ID` selects specific audio input
9. ✅ Service layer uses streaming callbacks + ring buffer
10. ✅ Unit tests for port enumeration, streaming, buffer overlap

---

## Device Configuration Files

### Requirements

Device-specific audio configuration must be:
1. **Persisted outside code** - Not bundled in Python packages
2. **Distributed via .deb** - Shipped as config files in packages
3. **User-customizable** - Generic baseline that users can extend

### File Locations

```
/etc/dictacode/audio/
├── devices.d/                    # Device profile directory
│   ├── generic.conf              # Baseline (shipped with .deb)
│   ├── rode-videomic-ntg.conf    # Known device (shipped with .deb)
│   └── custom-mic.conf           # User-created profile
└── audio.conf                    # Main config (active device selection)
```

### Device Profile Format

```ini
# /etc/dictacode/audio/devices.d/rode-videomic-ntg.conf
[device]
name = RØDE VideoMic NTG
vendor_id = 19f7
product_id = 0015
serial_pattern = RODE*

[capabilities]
sample_rates = 48000
channels = 2
native_rate = 48000
formats = int16

[defaults]
# Recommended settings for this device
gain = 0.8
```

### Generic Device (Baseline)

```ini
# /etc/dictacode/audio/devices.d/generic.conf
[device]
name = Generic USB Microphone
vendor_id = *
product_id = *
serial_pattern = *

[capabilities]
# Conservative defaults that work with most devices
sample_rates = 44100,48000
channels = 1,2
native_rate = 48000
formats = int16,float32

[defaults]
gain = 1.0
```

### Main Configuration

```ini
# /etc/dictacode/audio/audio.conf
[audio]
# Auto-detect or specify device
# device = auto
# device = rode-videomic-ntg
# device = usb:1-1.3
device = auto

# Fallback if auto-detect fails
fallback_device = generic

# Target sample rate for pipeline (Whisper requires 16kHz)
target_rate = 16000
```

### .deb Package Integration

```
dictacode-stt_x.y.z_arm64.deb
├── /opt/dictacode/stt/           # Python package
├── /etc/dictacode/audio/
│   ├── audio.conf                # conffile (preserved on upgrade)
│   └── devices.d/
│       ├── generic.conf          # conffile
│       └── rode-videomic-ntg.conf # conffile
└── /usr/lib/systemd/system/
    └── dictacode-stt.service
```

**Debian conffile behavior:**
- Files in `/etc/` marked as conffiles are preserved on package upgrade
- If user modifies, dpkg prompts to keep or replace
- New device profiles can be added without disturbing user customizations

### Device Matching Priority

When `device = auto`:

1. **Exact match** - vendor_id + product_id + serial_pattern
2. **Vendor match** - vendor_id + product_id (any serial)
3. **Generic fallback** - Use generic.conf defaults

```python
def match_device(usb_info: UsbDeviceInfo) -> DeviceProfile:
    """Match connected device to profile."""
    profiles = load_profiles_from("/etc/dictacode/audio/devices.d/")

    # Priority 1: Exact match
    for profile in profiles:
        if profile.matches_exact(usb_info):
            return profile

    # Priority 2: Vendor match
    for profile in profiles:
        if profile.matches_vendor(usb_info):
            return profile

    # Priority 3: Generic fallback
    return profiles["generic"]
```

### Files to Add (Configuration)

11. `ops/packaging/debian/conffiles` - List conffiles for dpkg
12. `ops/packaging/etc/dictacode/audio/audio.conf` - Default audio config
13. `ops/packaging/etc/dictacode/audio/devices.d/generic.conf` - Generic baseline
14. `ops/packaging/etc/dictacode/audio/devices.d/rode-videomic-ntg.conf` - Known device

### Additional Success Criteria

11. ✅ Device profiles stored in `/etc/dictacode/audio/devices.d/`
12. ✅ Generic device profile ships as baseline
13. ✅ Known devices (RØDE) have pre-configured profiles
14. ✅ User can add custom profiles without modifying code
15. ✅ .deb package installs config files as conffiles
16. ✅ Auto-detection uses profile matching hierarchy

---

## Out of Scope (v0.2.4)

- Hot-plug detection (can poll on demand)
- Audio output ports (only input needed for STT)
- Web API endpoints (v0.3.0)
- Multiple simultaneous recording pipelines
- GUI for device profile editing (users edit .conf files directly)
