# dictacode Architecture Plan v0.2.6 - Transcription Adapter Pattern

## Status

### Phase 1: Abstract Interface
- [ ] Create `transcription/` package
- [ ] Define `TranscriptionAdapter` ABC
- [ ] Define `TranscriptionResult`, `AudioRequirements` dataclasses
- [ ] Unit tests for result types

### Phase 2: Whisper Adapter
- [ ] Implement `WhisperAdapter` (extract from service.py)
- [ ] Move whisper subprocess logic
- [ ] Keep existing behavior
- [ ] Unit tests with mock subprocess

### Phase 3: Service Integration
- [ ] Update `SttService` to use adapter
- [ ] Inject transcriber via constructor
- [ ] Audio resampling based on `get_audio_requirements()`
- [ ] Integration tests

### Phase 4: Vosk Adapter
- [ ] Implement `VoskAdapter`
- [ ] Add vosk to optional dependencies
- [ ] Unit tests with mock Vosk

### Phase 5: Online Adapter (Stub)
- [ ] Implement `OnlineAdapter` base
- [ ] Document extension points for providers
- [ ] No actual API implementation (out of scope)

### Phase 6: CLI/Config Integration
- [ ] Add `--transcriber` flag to main.py
- [ ] Update config file parsing
- [ ] Update diagnostics for adapter-agnostic checks

**v0.2.6 NOT STARTED**

---

## Prerequisites

v0.2.6 builds on top of v0.2.5:
- ✅ Backend/CLI/API separation
- ✅ Shared response types

---

## Problem Statement

Current transcription is tightly coupled to whisper.cpp:
- `service.py` directly invokes whisper-cli via subprocess
- Audio format hardcoded to 16kHz mono WAV (Whisper requirement)
- No abstraction for alternative engines

**Goal:** Implement Adapter pattern (like existing `ProtocolAdapter`) to enable choice between:
- **Whisper.cpp** (offline, subprocess)
- **Vosk** (offline, Python library)
- **Online providers** (Google, Azure, Deepgram, etc.)

---

## Existing Pattern to Follow

### ProtocolAdapter (in protocol.py)

```python
class ProtocolAdapter(ABC):
    """Abstract protocol encoder/decoder."""

    @abstractmethod
    def encode(self, msg: Message) -> bytes: ...

    @abstractmethod
    def decode(self, data: bytes) -> Message: ...

class JsonProtocol(ProtocolAdapter): ...
class MsgpackProtocol(ProtocolAdapter): ...

def get_protocol(name: str) -> ProtocolAdapter:
    """Factory function."""
    protocols = {"json": JsonProtocol, "msgpack": MsgpackProtocol}
    return protocols[name]()
```

---

## Design

### TranscriptionAdapter ABC

```python
# transcription/adapter.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

@dataclass
class TranscriptionResult:
    """Result of a transcription operation."""
    text: str
    confidence: Optional[float] = None
    language: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.text) > 0

@dataclass
class AudioRequirements:
    """Audio format requirements for a transcription engine."""
    sample_rate: int           # e.g., 16000
    channels: int              # e.g., 1 (mono)
    bit_depth: int             # e.g., 16
    formats: list[str]         # e.g., ["wav", "mp3", "ogg"]

class TranscriptionAdapter(ABC):
    """Abstract speech-to-text transcription engine."""

    @abstractmethod
    def get_name(self) -> str:
        """Return engine name (e.g., 'whisper', 'vosk', 'google')."""
        pass

    @abstractmethod
    def get_audio_requirements(self) -> AudioRequirements:
        """Return audio format requirements for this engine."""
        pass

    @abstractmethod
    def transcribe(self, audio_path: Path, language: str = "en") -> TranscriptionResult:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file
            language: Language code (e.g., "en", "de")

        Returns:
            TranscriptionResult with text or error
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if engine is available (binary exists, API key set, etc.)."""
        pass

    def supports_streaming(self) -> bool:
        """Return True if engine supports streaming transcription."""
        return False  # Default: no streaming
```

### WhisperAdapter Implementation

```python
# transcription/whisper.py

class WhisperAdapter(TranscriptionAdapter):
    """Whisper.cpp transcription via subprocess."""

    def __init__(
        self,
        binary_path: Optional[Path] = None,
        model_path: Optional[Path] = None,
        timeout: float = 60.0,
    ):
        self.binary = binary_path or self._find_binary()
        self.model = model_path or self._find_model()
        self.timeout = timeout

    def get_name(self) -> str:
        return "whisper"

    def get_audio_requirements(self) -> AudioRequirements:
        return AudioRequirements(
            sample_rate=16000,
            channels=1,
            bit_depth=16,
            formats=["wav"],
        )

    def transcribe(self, audio_path: Path, language: str = "en") -> TranscriptionResult:
        cmd = [
            str(self.binary),
            "-m", str(self.model),
            "-f", str(audio_path),
            "--language", language,
            "--no-timestamps",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=self.timeout)
            text = self._parse_output(result.stdout.decode())
            return TranscriptionResult(text=text, language=language)
        except subprocess.TimeoutExpired:
            return TranscriptionResult(text="", error="Timeout")
        except Exception as e:
            return TranscriptionResult(text="", error=str(e))

    def is_available(self) -> bool:
        return self.binary.exists() and self.model.exists()
```

### VoskAdapter Implementation

```python
# transcription/vosk.py

class VoskAdapter(TranscriptionAdapter):
    """Vosk transcription via Python library."""

    def __init__(self, model_path: Optional[Path] = None):
        self.model_path = model_path or Path("~/.vosk/model").expanduser()
        self._model = None  # Lazy load

    def get_name(self) -> str:
        return "vosk"

    def get_audio_requirements(self) -> AudioRequirements:
        return AudioRequirements(
            sample_rate=16000,
            channels=1,
            bit_depth=16,
            formats=["wav"],
        )

    def transcribe(self, audio_path: Path, language: str = "en") -> TranscriptionResult:
        try:
            from vosk import Model, KaldiRecognizer
            import wave
            import json

            if self._model is None:
                self._model = Model(str(self.model_path))

            with wave.open(str(audio_path), "rb") as wf:
                rec = KaldiRecognizer(self._model, wf.getframerate())
                rec.SetWords(True)

                while True:
                    data = wf.readframes(4000)
                    if len(data) == 0:
                        break
                    rec.AcceptWaveform(data)

                result = json.loads(rec.FinalResult())
                return TranscriptionResult(
                    text=result.get("text", ""),
                    language=language,
                )
        except ImportError:
            return TranscriptionResult(text="", error="Vosk not installed")
        except Exception as e:
            return TranscriptionResult(text="", error=str(e))

    def is_available(self) -> bool:
        try:
            import vosk
            return self.model_path.exists()
        except ImportError:
            return False

    def supports_streaming(self) -> bool:
        return True  # Vosk supports streaming
```

### OnlineAdapter Implementation (Stub)

```python
# transcription/online.py

class OnlineAdapter(TranscriptionAdapter):
    """Online transcription API (Google, Azure, Deepgram, etc.)."""

    def __init__(
        self,
        provider: str = "google",
        api_key: Optional[str] = None,
    ):
        self.provider = provider
        self.api_key = api_key or os.environ.get(f"{provider.upper()}_API_KEY")

    def get_name(self) -> str:
        return f"online:{self.provider}"

    def get_audio_requirements(self) -> AudioRequirements:
        # Most online APIs are flexible
        return AudioRequirements(
            sample_rate=16000,
            channels=1,
            bit_depth=16,
            formats=["wav", "mp3", "ogg", "flac"],
        )

    def transcribe(self, audio_path: Path, language: str = "en") -> TranscriptionResult:
        # Stub - implement per provider
        return TranscriptionResult(text="", error="Not implemented")

    def is_available(self) -> bool:
        return self.api_key is not None
```

### Factory Function

```python
# transcription/__init__.py

def get_transcriber(
    name: str,
    **kwargs,
) -> TranscriptionAdapter:
    """
    Factory function to get transcription adapter by name.

    Args:
        name: Engine name ('whisper', 'vosk', 'google', 'azure', 'deepgram')
        **kwargs: Engine-specific configuration

    Returns:
        TranscriptionAdapter instance
    """
    adapters: dict[str, type[TranscriptionAdapter]] = {
        "whisper": WhisperAdapter,
        "vosk": VoskAdapter,
        "google": lambda **kw: OnlineAdapter(provider="google", **kw),
        "azure": lambda **kw: OnlineAdapter(provider="azure", **kw),
        "deepgram": lambda **kw: OnlineAdapter(provider="deepgram", **kw),
    }

    if name not in adapters:
        raise ValueError(f"Unknown transcriber: {name}. Available: {list(adapters.keys())}")

    return adapters[name](**kwargs)
```

---

## Integration with SttService

```python
# service.py

class SttService:
    def __init__(
        self,
        transcriber: Optional[TranscriptionAdapter] = None,
        transcriber_name: str = "whisper",
        # ... other params
    ):
        self.transcriber = transcriber or get_transcriber(transcriber_name)
        self.audio_requirements = self.transcriber.get_audio_requirements()

    def transcribe(self, wav_path: str) -> str:
        """Transcribe using configured adapter."""
        result = self.transcriber.transcribe(Path(wav_path), self.language)
        if result.success:
            return result.text
        else:
            logger.error(f"Transcription failed: {result.error}")
            return ""

    def _prepare_audio(self, raw_audio: bytes) -> Path:
        """Resample audio to match transcriber requirements."""
        target_rate = self.audio_requirements.sample_rate
        # ... resampling logic using target_rate
```

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── transcription/              # NEW: Transcription adapters
│   ├── __init__.py             # Factory function, exports
│   ├── adapter.py              # TranscriptionAdapter ABC
│   ├── result.py               # TranscriptionResult, AudioRequirements
│   ├── whisper.py              # WhisperAdapter
│   ├── vosk.py                 # VoskAdapter
│   └── online.py               # OnlineAdapter (stub)
├── service.py                  # MODIFIED: Use TranscriptionAdapter
├── cli.py                      # MODIFIED: --transcriber flag
├── main.py                     # MODIFIED: --transcriber flag
├── diagnostics/
│   ├── whisper.py              # Keep for Whisper-specific checks
│   └── transcription.py        # NEW: Generic transcription checks
└── ...
```

---

## Configuration

### CLI Flags

```bash
# Use Whisper (default)
dictacode-stt --transcriber whisper

# Use Vosk
dictacode-stt --transcriber vosk --vosk-model ~/.vosk/model-small-en

# Use online provider
dictacode-stt --transcriber google --api-key $GOOGLE_API_KEY
```

### Config File

```ini
# /etc/dictacode/stt.conf
transcriber=whisper
whisper_binary=/opt/whisper.cpp/bin/whisper-cli
whisper_model=/opt/whisper.cpp/models/ggml-tiny.bin

# Or for Vosk:
# transcriber=vosk
# vosk_model=/opt/vosk/model-en-us
```

---

## Files to Modify

1. `apps/stt/src/dictacode_stt/transcription/__init__.py` - NEW
2. `apps/stt/src/dictacode_stt/transcription/adapter.py` - NEW
3. `apps/stt/src/dictacode_stt/transcription/result.py` - NEW
4. `apps/stt/src/dictacode_stt/transcription/whisper.py` - NEW
5. `apps/stt/src/dictacode_stt/transcription/vosk.py` - NEW
6. `apps/stt/src/dictacode_stt/transcription/online.py` - NEW
7. `apps/stt/src/dictacode_stt/service.py` - Use TranscriptionAdapter
8. `apps/stt/src/dictacode_stt/main.py` - Add --transcriber flag
9. `apps/stt/src/dictacode_stt/cli.py` - Update whisper commands
10. `apps/stt/pyproject.toml` - Add vosk as optional dependency

---

## Success Criteria

v0.2.6 is complete when:

1. ✅ `TranscriptionAdapter` ABC defined with clear interface
2. ✅ `WhisperAdapter` extracts current whisper.cpp logic
3. ✅ `VoskAdapter` works with Vosk Python library
4. ✅ `OnlineAdapter` stub documented for extension
5. ✅ `SttService` uses injected adapter (not hardcoded)
6. ✅ Audio resampling respects adapter's `get_audio_requirements()`
7. ✅ `--transcriber` CLI flag switches between engines
8. ✅ Factory function `get_transcriber(name)` works
9. ✅ Unit tests for all adapters
10. ✅ Existing behavior unchanged when using Whisper

---

## Out of Scope (v0.2.6)

- Actual online provider implementations (Google, Azure, etc.)
- Streaming transcription (uses v0.2.4 ring buffer, but adapter is batch)
- Model download/management
- GPU acceleration configuration
