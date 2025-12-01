# dictacode Architecture Plan v0.2.7 - Streaming Transcription

## Status

### Phase 1: Streaming Interface
- [ ] Extend `TranscriptionAdapter` ABC with streaming methods
- [ ] Define `StreamingTranscriptionAdapter` mixin/protocol
- [ ] Define `PartialResult`, `FinalResult` types
- [ ] Unit tests for streaming types

### Phase 2: Vosk Streaming Implementation
- [ ] Implement `VoskAdapter.start_streaming()`
- [ ] Implement `VoskAdapter.feed_audio()`
- [ ] Implement `VoskAdapter.stop_streaming()`
- [ ] Handle partial results callback
- [ ] Unit tests with mock Vosk

### Phase 3: Ring Buffer Integration
- [ ] Connect `AudioRingBuffer` (v0.2.4) to streaming adapter
- [ ] Implement continuous feed loop
- [ ] Handle buffer overflow gracefully
- [ ] Integration tests with streaming pipeline

### Phase 4: Service Layer Updates
- [ ] Update `SttService` to support streaming mode
- [ ] Add `--streaming` flag to enable streaming transcription
- [ ] Graceful fallback to batch for non-streaming adapters
- [ ] Real-time partial result handling

### Phase 5: Whisper Streaming (Future-Proof)
- [ ] Document Whisper streaming limitations
- [ ] Implement chunked batch as pseudo-streaming
- [ ] Compare latency vs true streaming

**v0.2.7 NOT STARTED**

---

## Prerequisites

v0.2.7 builds on top of:
- ✅ v0.2.4: Audio Port Abstraction with `AudioRingBuffer`
- ✅ v0.2.6: `TranscriptionAdapter` ABC with batch `transcribe()` method

---

## Problem Statement

v0.2.6 introduced `TranscriptionAdapter` with batch-only transcription:

```python
# v0.2.6 - Batch only
def transcribe(self, audio_path: Path, language: str = "en") -> TranscriptionResult:
    """Transcribe complete audio file."""
    ...
```

**Limitations of batch-only:**
- User must wait for entire recording before seeing text
- Higher perceived latency (record → save → transcribe → display)
- Cannot leverage Vosk's native streaming capabilities
- Ring buffer (v0.2.4) feeds chunks, but adapter expects complete files

**Goal:** Extend adapter pattern to support streaming transcription where:
- Audio chunks flow continuously from ring buffer to transcriber
- Partial results appear in real-time as user speaks
- Final results are emitted when speech segment ends
- Batch adapters (Whisper) still work via fallback

---

## Design

### Streaming vs Batch Comparison

| Aspect | Batch (v0.2.6) | Streaming (v0.2.7) |
|--------|----------------|-------------------|
| Input | Complete audio file | Continuous audio chunks |
| Output | Single result | Partial + final results |
| Latency | High (wait for recording) | Low (real-time) |
| Vosk | ✅ Supported | ✅ Native streaming |
| Whisper | ✅ Supported | ⚠️ Chunked batch fallback |
| Online | ✅ Supported | ⚠️ Provider-dependent |

### StreamingTranscriptionAdapter Protocol

```python
# transcription/streaming.py

from typing import Protocol, Callable, Optional
from dataclasses import dataclass

@dataclass
class PartialResult:
    """Intermediate transcription result (may change)."""
    text: str
    is_final: bool = False
    confidence: Optional[float] = None

@dataclass
class FinalResult:
    """Confirmed transcription result (speech segment complete)."""
    text: str
    confidence: Optional[float] = None
    duration_ms: Optional[int] = None

# Callback types
PartialCallback = Callable[[PartialResult], None]
FinalCallback = Callable[[FinalResult], None]
ErrorCallback = Callable[[Exception], None]

class StreamingTranscriptionAdapter(Protocol):
    """Protocol for streaming-capable transcription adapters."""

    def supports_streaming(self) -> bool:
        """Return True if adapter supports streaming."""
        ...

    def start_streaming(
        self,
        language: str = "en",
        on_partial: Optional[PartialCallback] = None,
        on_final: Optional[FinalCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        """
        Start streaming transcription session.

        Args:
            language: Language code
            on_partial: Called with intermediate results
            on_final: Called when speech segment completes
            on_error: Called on transcription errors
        """
        ...

    def feed_audio(self, chunk: bytes) -> None:
        """
        Feed audio chunk to transcriber.

        Args:
            chunk: Raw audio bytes (16kHz, 16-bit, mono)
        """
        ...

    def stop_streaming(self) -> Optional[FinalResult]:
        """
        Stop streaming and get final result.

        Returns:
            Final result for any remaining audio, or None
        """
        ...

    def is_streaming(self) -> bool:
        """Return True if currently in streaming session."""
        ...
```

### VoskAdapter Streaming Implementation

```python
# transcription/vosk.py

class VoskAdapter(TranscriptionAdapter):
    """Vosk transcription with native streaming support."""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path("~/.vosk/model").expanduser()
        self._model = None
        self._recognizer = None
        self._streaming = False
        self._callbacks: dict = {}

    def supports_streaming(self) -> bool:
        return True  # Vosk has native streaming

    def start_streaming(
        self,
        language: str = "en",
        on_partial: Optional[PartialCallback] = None,
        on_final: Optional[FinalCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        """Start Vosk streaming session."""
        try:
            from vosk import Model, KaldiRecognizer

            if self._model is None:
                self._model = Model(str(self.model_path))

            # Create recognizer for streaming
            self._recognizer = KaldiRecognizer(self._model, 16000)
            self._recognizer.SetWords(True)

            self._callbacks = {
                "on_partial": on_partial,
                "on_final": on_final,
                "on_error": on_error,
            }
            self._streaming = True

        except Exception as e:
            if on_error:
                on_error(e)

    def feed_audio(self, chunk: bytes) -> None:
        """Feed audio chunk and emit results via callbacks."""
        if not self._streaming or not self._recognizer:
            return

        try:
            import json

            if self._recognizer.AcceptWaveform(chunk):
                # Final result for this utterance
                result = json.loads(self._recognizer.Result())
                text = result.get("text", "")
                if text and self._callbacks.get("on_final"):
                    self._callbacks["on_final"](FinalResult(text=text))
            else:
                # Partial result
                partial = json.loads(self._recognizer.PartialResult())
                text = partial.get("partial", "")
                if text and self._callbacks.get("on_partial"):
                    self._callbacks["on_partial"](PartialResult(text=text))

        except Exception as e:
            if self._callbacks.get("on_error"):
                self._callbacks["on_error"](e)

    def stop_streaming(self) -> Optional[FinalResult]:
        """Stop streaming and return final result."""
        if not self._streaming or not self._recognizer:
            return None

        try:
            import json
            result = json.loads(self._recognizer.FinalResult())
            text = result.get("text", "")
            return FinalResult(text=text) if text else None
        finally:
            self._recognizer = None
            self._streaming = False
            self._callbacks = {}

    def is_streaming(self) -> bool:
        return self._streaming
```

### WhisperAdapter Chunked Batch (Pseudo-Streaming)

```python
# transcription/whisper.py

class WhisperAdapter(TranscriptionAdapter):
    """Whisper.cpp - batch only, with chunked fallback for streaming API."""

    def __init__(self, ...):
        ...
        self._chunk_buffer = bytearray()
        self._chunk_threshold = 16000 * 2 * 3  # 3 seconds of audio
        self._streaming = False

    def supports_streaming(self) -> bool:
        return False  # Native streaming not supported

    def start_streaming(
        self,
        language: str = "en",
        on_partial: Optional[PartialCallback] = None,
        on_final: Optional[FinalCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        """
        Start pseudo-streaming via chunked batch.

        Note: Whisper doesn't support true streaming. This accumulates
        audio and transcribes in chunks, providing delayed "final" results.
        """
        self._language = language
        self._callbacks = {
            "on_partial": on_partial,
            "on_final": on_final,
            "on_error": on_error,
        }
        self._chunk_buffer = bytearray()
        self._streaming = True

    def feed_audio(self, chunk: bytes) -> None:
        """Accumulate audio and transcribe when threshold reached."""
        if not self._streaming:
            return

        self._chunk_buffer.extend(chunk)

        # Transcribe when we have enough audio
        if len(self._chunk_buffer) >= self._chunk_threshold:
            self._transcribe_buffer()

    def _transcribe_buffer(self) -> None:
        """Transcribe accumulated buffer via batch method."""
        if not self._chunk_buffer:
            return

        try:
            # Write buffer to temp file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                self._write_wav(f, bytes(self._chunk_buffer))
                temp_path = Path(f.name)

            # Use batch transcription
            result = self.transcribe(temp_path, self._language)

            if result.success and self._callbacks.get("on_final"):
                self._callbacks["on_final"](FinalResult(text=result.text))

            # Clear buffer
            self._chunk_buffer = bytearray()

        except Exception as e:
            if self._callbacks.get("on_error"):
                self._callbacks["on_error"](e)
        finally:
            temp_path.unlink(missing_ok=True)

    def stop_streaming(self) -> Optional[FinalResult]:
        """Transcribe remaining buffer."""
        if self._chunk_buffer:
            self._transcribe_buffer()
        self._streaming = False
        return None
```

### Ring Buffer Integration

```python
# service.py

class SttService:
    def __init__(
        self,
        transcriber: TranscriptionAdapter,
        streaming: bool = False,
        ...
    ):
        self.transcriber = transcriber
        self.streaming_mode = streaming and transcriber.supports_streaming()
        self._audio_buffer = AudioRingBuffer(max_seconds=5.0)

    def _on_audio_data(self, chunk: bytes) -> None:
        """Callback: audio chunk from AudioPort."""
        resampled = self._resampler.process(chunk)

        if self.streaming_mode:
            # Feed directly to streaming transcriber
            self.transcriber.feed_audio(resampled)
        else:
            # Accumulate in ring buffer for batch
            self._audio_buffer.write(resampled)

    def _on_partial_result(self, result: PartialResult) -> None:
        """Handle partial transcription (display but don't send)."""
        logger.debug(f"Partial: {result.text}")
        # Could update a status display here

    def _on_final_result(self, result: FinalResult) -> None:
        """Handle final transcription (send to HID)."""
        if result.text:
            logger.info(f"Final: {result.text}")
            self.send_text(result.text)

    def start(self) -> None:
        """Start transcription service."""
        if self.streaming_mode:
            self.transcriber.start_streaming(
                language=self.language,
                on_partial=self._on_partial_result,
                on_final=self._on_final_result,
                on_error=self._on_transcription_error,
            )

        self._start_audio_capture()

    def stop(self) -> None:
        """Stop transcription service."""
        self._stop_audio_capture()

        if self.streaming_mode:
            final = self.transcriber.stop_streaming()
            if final and final.text:
                self.send_text(final.text)
```

---

## Data Flow Comparison

### Batch Mode (v0.2.6)

```
AudioPort → RingBuffer → [accumulate] → temp.wav → transcribe() → result
                              ↑                          ↓
                         wait for                   single result
                         threshold
```

### Streaming Mode (v0.2.7)

```
AudioPort → feed_audio() → [Vosk internal] → on_partial() → display
     ↓                           ↓
  continuous              on_final() → send to HID
   chunks
```

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── transcription/
│   ├── __init__.py             # Add streaming exports
│   ├── adapter.py              # Base TranscriptionAdapter (unchanged)
│   ├── streaming.py            # NEW: StreamingTranscriptionAdapter protocol
│   ├── result.py               # Add PartialResult, FinalResult
│   ├── whisper.py              # Add chunked batch pseudo-streaming
│   ├── vosk.py                 # Add native streaming support
│   └── online.py               # Document streaming support per provider
├── service.py                  # Add streaming mode, callbacks
├── main.py                     # Add --streaming flag
└── ...
```

---

## Configuration

### CLI Flags

```bash
# Batch mode (default, works with all adapters)
dictacode-stt --transcriber vosk

# Streaming mode (real-time, Vosk only)
dictacode-stt --transcriber vosk --streaming

# Streaming with Whisper (falls back to chunked batch)
dictacode-stt --transcriber whisper --streaming
# Warning: Whisper doesn't support native streaming, using chunked batch
```

### Config File

```ini
# /etc/dictacode/stt.conf
transcriber=vosk
streaming=true

# Streaming tuning
partial_results=true      # Show partial results (default: true)
chunk_interval_ms=100     # How often to feed audio (default: 100)
```

---

## Files to Modify

1. `apps/stt/src/dictacode_stt/transcription/streaming.py` - NEW: Streaming protocol
2. `apps/stt/src/dictacode_stt/transcription/result.py` - Add PartialResult, FinalResult
3. `apps/stt/src/dictacode_stt/transcription/vosk.py` - Native streaming
4. `apps/stt/src/dictacode_stt/transcription/whisper.py` - Chunked batch fallback
5. `apps/stt/src/dictacode_stt/transcription/__init__.py` - Export streaming types
6. `apps/stt/src/dictacode_stt/service.py` - Streaming mode support
7. `apps/stt/src/dictacode_stt/main.py` - Add --streaming flag
8. `apps/stt/tests/test_streaming.py` - NEW: Streaming tests

---

## Success Criteria

v0.2.7 is complete when:

1. ✅ `StreamingTranscriptionAdapter` protocol defined
2. ✅ `PartialResult`, `FinalResult` types defined
3. ✅ `VoskAdapter` implements native streaming
4. ✅ `WhisperAdapter` implements chunked batch fallback
5. ✅ `SttService` supports streaming mode with callbacks
6. ✅ Ring buffer feeds streaming adapter continuously
7. ✅ `--streaming` CLI flag enables streaming mode
8. ✅ Graceful fallback for non-streaming adapters
9. ✅ Partial results displayed in real-time (Vosk)
10. ✅ Final results sent to HID immediately
11. ✅ Unit tests for streaming protocol
12. ✅ Integration tests with ring buffer

---

## Out of Scope (v0.2.7)

- WebSocket streaming to web UI (v0.3.0)
- Online provider streaming implementations
- Voice activity detection (VAD) for smarter segmentation
- Speaker diarization
- Confidence-based filtering of partial results
