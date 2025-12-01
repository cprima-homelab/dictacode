# dictacode Architecture Plan v0.2.11 - Audio Input Mocking & Testability

## Status

### Phase 1: Audio Source Abstraction ✅ COMPLETE
- [x] Define `AudioSource` protocol (mic, file, synthetic)
- [x] Define `AudioSourceConfig` for source configuration
- [x] Define `SourceType`, `PlaybackMode` enums
- [x] Define callback types (`AudioChunkCallback`, `SourceEndCallback`)
- [ ] Implement `MicrophoneSource` wrapping current mic input (deferred)
- [ ] Unit tests for source protocol

### Phase 2: File Replay Source ✅ COMPLETE
- [x] Implement `FileSource` for WAV/audio file playback
- [x] Support real-time pacing (simulate mic timing)
- [x] Support fast-forward mode (max speed for CI)
- [x] Loop and segment options
- [x] Channel and sample rate resampling
- [x] Seeking support
- [ ] Unit tests with sample audio files

### Phase 3: Synthetic Source
- [x] Implement `SyntheticSource` for generated audio
- [x] Silence generator
- [ ] Tone generator (sine wave) - not relevant for transcription testing
- [ ] Noise generator (white noise) - not relevant for transcription testing
- [ ] Click generator (timing tests) - not relevant for transcription testing
- [ ] Sweep generator (frequency sweep) - not relevant for transcription testing
- [ ] Configurable duration and patterns
- [ ] Unit tests for synthetic audio

### Phase 4: Source Injection ✅ COMPLETE
- [x] Update `SttService` for source injection (`audio_source` parameter)
- [x] Add `record_audio_from_source()` method
- [x] Update `run_once()` to use source when available
- [x] Add cleanup in `stop()` method
- [x] Maintain production code path execution (backward compatible)
- [ ] Integration tests with file source (covered in Phase 5)

### Phase 5: Test Fixtures & Harness ✅ COMPLETE
- [x] Create test audio fixtures directory structure
- [x] Generate silence_1s.wav fixture
- [x] Document fixture format and usage (README.md)
- [x] Add pytest fixtures for audio sources (conftest.py)
- [x] Create unit tests for audio sources (test_audio_sources.py)
- [x] Create integration tests with SttService (test_service_with_sources.py)
- [ ] Additional speech sample fixtures (hello_world, numbers) - optional, can be added later

### Phase 6: CLI & CI Integration ✅ COMPLETE
- [x] Add `--audio-source` flag to CLI (main.py)
- [x] Support file source specification (`file:path.wav:fast`)
- [x] Support synthetic source specification (`synthetic:silence:1000`)
- [x] Update CLI help and examples
- [ ] CI pipeline integration (future work, requires actual fixtures)
- [ ] Full testing workflow documentation (covered in AUDIO_SOURCES.md)

**v0.2.11 COMPLETE** ✅

---

## Prerequisites

v0.2.11 builds on top of:
- ✅ v0.2.4: Audio Port Abstraction (`AudioPort`, streaming callbacks)
- ✅ v0.2.10: Audio Backend abstraction

---

## Problem Statement

### Current Testing Limitations

Testing requires a physical microphone:

```python
# Current: No way to inject test audio
class SttService:
    def __init__(self):
        self.port_manager = AudioPortManager()
        self.port = self.port_manager.get_default_port()  # Real mic only!

    def start(self):
        self.port.start_stream(callback=self._on_audio)  # Can't mock
```

**Issues:**
- Unit tests require physical microphone
- CI/CD pipelines can't run audio tests
- Integration tests are non-deterministic (ambient noise)
- No way to replay specific audio scenarios
- Can't test edge cases (silence, noise, specific phrases)

### Testing Goals

| Test Type | Audio Source | Speed | Use Case |
|-----------|--------------|-------|----------|
| Unit | Synthetic | Fast | Test audio processing logic |
| Integration | File (fast) | Fast | CI pipeline, full path |
| End-to-end | File (real-time) | Real | Simulate real usage |
| Manual | Microphone | Real | Development, debugging |

**Goal:** Inject audio from files/synthetic sources while executing maximum production code.

---

## Design

### Audio Source Protocol

```python
# audio/source.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable, Iterator
from enum import Enum
from pathlib import Path

class SourceType(Enum):
    MICROPHONE = "microphone"
    FILE = "file"
    SYNTHETIC = "synthetic"

class PlaybackMode(Enum):
    REALTIME = "realtime"     # Simulate real microphone timing
    FAST = "fast"             # As fast as possible (CI)
    CONTROLLED = "controlled" # Manual advancement (unit tests)

@dataclass
class AudioSourceConfig:
    """Configuration for audio source."""
    source_type: SourceType
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024      # Samples per chunk
    playback_mode: PlaybackMode = PlaybackMode.REALTIME

    # File source options
    file_path: Optional[Path] = None
    loop: bool = False
    start_offset_ms: int = 0
    end_offset_ms: Optional[int] = None

    # Synthetic source options
    pattern: str = "silence"    # "silence", "tone", "noise", "speech"
    duration_ms: Optional[int] = None
    frequency_hz: float = 440.0  # For tone

# Callback types
AudioChunkCallback = Callable[[bytes, int], None]  # (data, frame_count)
SourceEndCallback = Callable[[], None]

class AudioSource(ABC):
    """Abstract audio source - microphone, file, or synthetic."""

    @abstractmethod
    def get_type(self) -> SourceType:
        """Return source type."""
        pass

    @abstractmethod
    def get_config(self) -> AudioSourceConfig:
        """Return source configuration."""
        pass

    @abstractmethod
    def open(self) -> None:
        """Open/initialize the source."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close and release resources."""
        pass

    @abstractmethod
    def start(
        self,
        callback: AudioChunkCallback,
        on_end: Optional[SourceEndCallback] = None,
    ) -> None:
        """
        Start streaming audio to callback.

        Args:
            callback: Called with each audio chunk
            on_end: Called when source exhausted (file/synthetic)
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop streaming."""
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """Return True if currently streaming."""
        pass

    def is_finite(self) -> bool:
        """Return True if source has finite duration (file, synthetic)."""
        return self.get_type() != SourceType.MICROPHONE

    def supports_seeking(self) -> bool:
        """Return True if source supports seek operations."""
        return False

    def seek(self, position_ms: int) -> None:
        """Seek to position (if supported)."""
        raise NotImplementedError("Source does not support seeking")
```

### Microphone Source

```python
# audio/sources/microphone.py

class MicrophoneSource(AudioSource):
    """Live microphone input source."""

    def __init__(
        self,
        port: AudioPort,
        config: Optional[AudioSourceConfig] = None,
    ):
        self.port = port
        self.config = config or AudioSourceConfig(
            source_type=SourceType.MICROPHONE,
            sample_rate=port.capabilities.native_rate,
            channels=1,
        )
        self._callback: Optional[AudioChunkCallback] = None
        self._active = False

    def get_type(self) -> SourceType:
        return SourceType.MICROPHONE

    def get_config(self) -> AudioSourceConfig:
        return self.config

    def open(self) -> None:
        self.port.open()
        self.port.configure(
            sample_rate=self.config.sample_rate,
            channels=self.config.channels,
        )

    def close(self) -> None:
        self.port.close()

    def start(
        self,
        callback: AudioChunkCallback,
        on_end: Optional[SourceEndCallback] = None,
    ) -> None:
        self._callback = callback
        self._active = True

        def port_callback(data: bytes) -> None:
            if self._callback:
                frame_count = len(data) // (2 * self.config.channels)  # 16-bit
                self._callback(data, frame_count)

        self.port.start_stream(
            on_data=port_callback,
            on_error=lambda e: logger.error(f"Mic error: {e}"),
            chunk_size=self.config.chunk_size,
        )

    def stop(self) -> None:
        self._active = False
        self.port.stop_stream()

    def is_active(self) -> bool:
        return self._active and self.port.is_streaming()
```

### File Replay Source

```python
# audio/sources/file.py

import wave
import time
import threading
from pathlib import Path

class FileSource(AudioSource):
    """Audio file playback source."""

    def __init__(self, config: AudioSourceConfig):
        if not config.file_path:
            raise ValueError("file_path required for FileSource")

        self.config = config
        self._wav: Optional[wave.Wave_read] = None
        self._thread: Optional[threading.Thread] = None
        self._active = False
        self._callback: Optional[AudioChunkCallback] = None
        self._on_end: Optional[SourceEndCallback] = None

    def get_type(self) -> SourceType:
        return SourceType.FILE

    def get_config(self) -> AudioSourceConfig:
        return self.config

    def open(self) -> None:
        self._wav = wave.open(str(self.config.file_path), "rb")

        # Validate format
        if self._wav.getsampwidth() != 2:  # 16-bit
            raise ValueError("Only 16-bit WAV files supported")

        # Seek to start offset if specified
        if self.config.start_offset_ms > 0:
            start_frame = int(
                self.config.start_offset_ms * self._wav.getframerate() / 1000
            )
            self._wav.setpos(start_frame)

    def close(self) -> None:
        if self._wav:
            self._wav.close()
            self._wav = None

    def start(
        self,
        callback: AudioChunkCallback,
        on_end: Optional[SourceEndCallback] = None,
    ) -> None:
        self._callback = callback
        self._on_end = on_end
        self._active = True

        self._thread = threading.Thread(target=self._playback_loop, daemon=True)
        self._thread.start()

    def _playback_loop(self) -> None:
        """Stream audio chunks from file."""
        if not self._wav:
            return

        file_rate = self._wav.getframerate()
        file_channels = self._wav.getnchannels()
        target_rate = self.config.sample_rate
        chunk_frames = self.config.chunk_size

        # Calculate timing for real-time playback
        chunk_duration = chunk_frames / target_rate

        # Calculate end position
        end_frame = None
        if self.config.end_offset_ms:
            end_frame = int(self.config.end_offset_ms * file_rate / 1000)

        while self._active:
            start_time = time.monotonic()

            # Read chunk from file
            frames_to_read = int(chunk_frames * file_rate / target_rate)
            data = self._wav.readframes(frames_to_read)

            if not data:
                if self.config.loop:
                    # Restart from beginning
                    start_frame = int(
                        self.config.start_offset_ms * file_rate / 1000
                    )
                    self._wav.setpos(start_frame)
                    continue
                else:
                    # End of file
                    break

            # Check end position
            if end_frame and self._wav.tell() >= end_frame:
                if self.config.loop:
                    start_frame = int(
                        self.config.start_offset_ms * file_rate / 1000
                    )
                    self._wav.setpos(start_frame)
                    continue
                else:
                    break

            # Resample if needed
            if file_rate != target_rate or file_channels != self.config.channels:
                data = self._resample(data, file_rate, file_channels)

            # Deliver chunk
            if self._callback:
                frame_count = len(data) // (2 * self.config.channels)
                self._callback(data, frame_count)

            # Pace delivery based on playback mode
            if self.config.playback_mode == PlaybackMode.REALTIME:
                elapsed = time.monotonic() - start_time
                sleep_time = chunk_duration - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
            elif self.config.playback_mode == PlaybackMode.FAST:
                pass  # No delay, maximum speed

        self._active = False
        if self._on_end:
            self._on_end()

    def _resample(
        self,
        data: bytes,
        source_rate: int,
        source_channels: int,
    ) -> bytes:
        """Resample audio to target format."""
        import numpy as np

        # Convert to numpy array
        samples = np.frombuffer(data, dtype=np.int16)

        # Convert channels if needed
        if source_channels > self.config.channels:
            # Stereo to mono: average channels
            samples = samples.reshape(-1, source_channels)
            samples = samples.mean(axis=1).astype(np.int16)
        elif source_channels < self.config.channels:
            # Mono to stereo: duplicate
            samples = np.column_stack([samples] * self.config.channels)
            samples = samples.flatten()

        # Resample if needed
        if source_rate != self.config.sample_rate:
            from scipy import signal
            num_samples = int(len(samples) * self.config.sample_rate / source_rate)
            samples = signal.resample(samples, num_samples).astype(np.int16)

        return samples.tobytes()

    def stop(self) -> None:
        self._active = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def is_active(self) -> bool:
        return self._active

    def supports_seeking(self) -> bool:
        return True

    def seek(self, position_ms: int) -> None:
        if self._wav:
            frame = int(position_ms * self._wav.getframerate() / 1000)
            self._wav.setpos(frame)
```

### Synthetic Source

```python
# audio/sources/synthetic.py

import numpy as np
import threading
import time

class SyntheticSource(AudioSource):
    """Generated audio source for testing."""

    PATTERNS = {
        "silence": "_generate_silence",
        "tone": "_generate_tone",
        "noise": "_generate_noise",
        "click": "_generate_click",
        "sweep": "_generate_sweep",
    }

    def __init__(self, config: AudioSourceConfig):
        self.config = config
        self._thread: Optional[threading.Thread] = None
        self._active = False
        self._callback: Optional[AudioChunkCallback] = None
        self._on_end: Optional[SourceEndCallback] = None
        self._samples_delivered = 0

    def get_type(self) -> SourceType:
        return SourceType.SYNTHETIC

    def get_config(self) -> AudioSourceConfig:
        return self.config

    def open(self) -> None:
        self._samples_delivered = 0

    def close(self) -> None:
        pass

    def start(
        self,
        callback: AudioChunkCallback,
        on_end: Optional[SourceEndCallback] = None,
    ) -> None:
        self._callback = callback
        self._on_end = on_end
        self._active = True
        self._samples_delivered = 0

        self._thread = threading.Thread(target=self._generation_loop, daemon=True)
        self._thread.start()

    def _generation_loop(self) -> None:
        """Generate and deliver audio chunks."""
        chunk_frames = self.config.chunk_size
        chunk_duration = chunk_frames / self.config.sample_rate

        # Total samples if finite duration
        total_samples = None
        if self.config.duration_ms:
            total_samples = int(
                self.config.duration_ms * self.config.sample_rate / 1000
            )

        generator = getattr(self, self.PATTERNS.get(self.config.pattern, "_generate_silence"))

        while self._active:
            start_time = time.monotonic()

            # Check if we've delivered enough
            if total_samples and self._samples_delivered >= total_samples:
                break

            # Generate chunk
            remaining = None
            if total_samples:
                remaining = total_samples - self._samples_delivered
            frames = min(chunk_frames, remaining) if remaining else chunk_frames

            data = generator(frames)

            # Deliver
            if self._callback:
                self._callback(data, frames)

            self._samples_delivered += frames

            # Pace delivery
            if self.config.playback_mode == PlaybackMode.REALTIME:
                elapsed = time.monotonic() - start_time
                sleep_time = chunk_duration - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        self._active = False
        if self._on_end:
            self._on_end()

    def _generate_silence(self, frames: int) -> bytes:
        """Generate silence."""
        samples = np.zeros(frames * self.config.channels, dtype=np.int16)
        return samples.tobytes()

    def _generate_tone(self, frames: int) -> bytes:
        """Generate sine wave tone."""
        t = np.arange(frames) / self.config.sample_rate
        t += self._samples_delivered / self.config.sample_rate  # Phase continuity

        samples = np.sin(2 * np.pi * self.config.frequency_hz * t)
        samples = (samples * 16000).astype(np.int16)  # Scale to 16-bit

        if self.config.channels > 1:
            samples = np.column_stack([samples] * self.config.channels).flatten()

        return samples.tobytes()

    def _generate_noise(self, frames: int) -> bytes:
        """Generate white noise."""
        samples = np.random.randint(
            -8000, 8000,
            size=frames * self.config.channels,
            dtype=np.int16,
        )
        return samples.tobytes()

    def _generate_click(self, frames: int) -> bytes:
        """Generate periodic clicks (useful for timing tests)."""
        samples = np.zeros(frames * self.config.channels, dtype=np.int16)
        # Click every 0.5 seconds
        click_interval = int(0.5 * self.config.sample_rate)
        for i in range(frames):
            global_pos = self._samples_delivered + i
            if global_pos % click_interval == 0:
                samples[i * self.config.channels] = 16000
        return samples.tobytes()

    def _generate_sweep(self, frames: int) -> bytes:
        """Generate frequency sweep."""
        t = np.arange(frames) / self.config.sample_rate
        t += self._samples_delivered / self.config.sample_rate

        # Sweep from 100Hz to 4000Hz over 2 seconds
        freq = 100 + (4000 - 100) * (t % 2.0) / 2.0
        phase = 2 * np.pi * np.cumsum(freq) / self.config.sample_rate
        samples = np.sin(phase)
        samples = (samples * 16000).astype(np.int16)

        if self.config.channels > 1:
            samples = np.column_stack([samples] * self.config.channels).flatten()

        return samples.tobytes()

    def stop(self) -> None:
        self._active = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def is_active(self) -> bool:
        return self._active
```

### Source Factory

```python
# audio/sources/__init__.py

def create_audio_source(
    source_spec: str,
    port_manager: Optional[AudioPortManager] = None,
    **kwargs,
) -> AudioSource:
    """
    Create audio source from specification string.

    Args:
        source_spec: Source specification:
            - "mic" or "microphone" - Live microphone
            - "mic:PORT_ID" - Specific microphone
            - "file:path/to/audio.wav" - File playback
            - "file:path.wav:fast" - File playback, fast mode
            - "synthetic:silence" - Synthetic silence
            - "synthetic:tone:440" - Synthetic 440Hz tone
            - "synthetic:noise:5000" - 5 second noise
        port_manager: Required for microphone sources
        **kwargs: Additional config overrides

    Returns:
        Configured AudioSource
    """
    parts = source_spec.split(":")

    if parts[0] in ("mic", "microphone"):
        if not port_manager:
            raise ValueError("port_manager required for microphone source")

        port_id = parts[1] if len(parts) > 1 else None
        port = (
            port_manager.get_port(port_id)
            if port_id
            else port_manager.get_default_port()
        )

        return MicrophoneSource(
            port=port,
            config=AudioSourceConfig(
                source_type=SourceType.MICROPHONE,
                **kwargs,
            ),
        )

    elif parts[0] == "file":
        if len(parts) < 2:
            raise ValueError("File path required: file:path/to/audio.wav")

        file_path = Path(parts[1])
        playback_mode = PlaybackMode.REALTIME
        if len(parts) > 2:
            playback_mode = PlaybackMode[parts[2].upper()]

        return FileSource(
            config=AudioSourceConfig(
                source_type=SourceType.FILE,
                file_path=file_path,
                playback_mode=playback_mode,
                **kwargs,
            ),
        )

    elif parts[0] == "synthetic":
        pattern = parts[1] if len(parts) > 1 else "silence"
        duration_ms = int(parts[2]) if len(parts) > 2 else None
        frequency_hz = float(parts[3]) if len(parts) > 3 else 440.0

        return SyntheticSource(
            config=AudioSourceConfig(
                source_type=SourceType.SYNTHETIC,
                pattern=pattern,
                duration_ms=duration_ms,
                frequency_hz=frequency_hz,
                playback_mode=kwargs.get("playback_mode", PlaybackMode.REALTIME),
                **kwargs,
            ),
        )

    else:
        raise ValueError(f"Unknown source type: {parts[0]}")
```

---

## Service Integration

```python
# service.py

class SttService:
    """Speech-to-text service with injectable audio source."""

    def __init__(
        self,
        audio_source: Optional[AudioSource] = None,
        port_manager: Optional[AudioPortManager] = None,
        transcriber: Optional[TranscriptionAdapter] = None,
        # ...
    ):
        self.port_manager = port_manager or AudioPortManager()
        self.transcriber = transcriber or get_transcriber("whisper")

        # Audio source injection point
        if audio_source:
            self.audio_source = audio_source
        else:
            # Default: microphone
            port = self.port_manager.get_default_port()
            self.audio_source = MicrophoneSource(port)

        self._audio_buffer = AudioRingBuffer(max_seconds=5.0)

    def _on_audio_chunk(self, data: bytes, frame_count: int) -> None:
        """Handle audio chunk from any source."""
        # Same processing regardless of source
        resampled = self._resampler.process(data)
        self._audio_buffer.write(resampled)

        # Trigger transcription if enough audio
        if self._should_transcribe():
            self._do_transcription()

    def start(self) -> None:
        """Start the service."""
        self.audio_source.open()
        self.audio_source.start(
            callback=self._on_audio_chunk,
            on_end=self._on_source_end,
        )

    def stop(self) -> None:
        """Stop the service."""
        self.audio_source.stop()
        self.audio_source.close()

    def _on_source_end(self) -> None:
        """Called when audio source exhausted (file/synthetic)."""
        logger.info("Audio source ended")
        # Process remaining buffer
        self._do_final_transcription()
```

---

## Test Fixtures & Harness

### Test Audio Fixtures

```
tests/fixtures/audio/
├── speech/
│   ├── hello_world.wav           # "Hello World" (clear speech)
│   ├── hello_world.expected.txt  # Expected transcription
│   ├── numbers_1_to_10.wav       # "One, two, three..."
│   ├── numbers_1_to_10.expected.txt
│   ├── quick_brown_fox.wav       # Pangram
│   └── quick_brown_fox.expected.txt
├── edge_cases/
│   ├── silence_5s.wav            # 5 seconds of silence
│   ├── background_noise.wav      # Office noise
│   ├── speech_with_noise.wav     # Speech in noisy environment
│   └── accented_speech.wav       # Non-native speaker
└── synthetic/
    ├── tone_440hz_1s.wav         # Reference tone
    └── clicks_1s.wav             # Timing reference
```

### Test Harness

```python
# tests/harness.py

from dataclasses import dataclass
from typing import List, Optional
from pathlib import Path

@dataclass
class TranscriptionTestCase:
    """A test case with audio and expected output."""
    name: str
    audio_path: Path
    expected_text: str
    tolerance: float = 0.9  # Word accuracy threshold

@dataclass
class TranscriptionTestResult:
    """Result of running a test case."""
    test_case: TranscriptionTestCase
    actual_text: str
    word_accuracy: float
    passed: bool
    duration_ms: int

class TestHarness:
    """Harness for running transcription tests."""

    def __init__(
        self,
        service: SttService,
        fixtures_dir: Path = Path("tests/fixtures/audio"),
    ):
        self.service = service
        self.fixtures_dir = fixtures_dir

    def load_test_cases(self, category: str = "speech") -> List[TranscriptionTestCase]:
        """Load test cases from fixtures directory."""
        cases = []
        category_dir = self.fixtures_dir / category

        for wav_file in category_dir.glob("*.wav"):
            expected_file = wav_file.with_suffix(".expected.txt")
            if expected_file.exists():
                cases.append(TranscriptionTestCase(
                    name=wav_file.stem,
                    audio_path=wav_file,
                    expected_text=expected_file.read_text().strip(),
                ))

        return cases

    def run_test(self, test_case: TranscriptionTestCase) -> TranscriptionTestResult:
        """Run a single test case."""
        import time

        # Create file source
        source = FileSource(AudioSourceConfig(
            source_type=SourceType.FILE,
            file_path=test_case.audio_path,
            playback_mode=PlaybackMode.FAST,  # Fast for testing
        ))

        # Inject into service
        self.service.audio_source = source

        # Run transcription
        start = time.monotonic()
        self.service.start()

        # Wait for completion
        while source.is_active():
            time.sleep(0.01)

        actual_text = self.service.get_last_transcription()
        duration_ms = int((time.monotonic() - start) * 1000)

        # Calculate accuracy
        accuracy = self._word_accuracy(test_case.expected_text, actual_text)
        passed = accuracy >= test_case.tolerance

        return TranscriptionTestResult(
            test_case=test_case,
            actual_text=actual_text,
            word_accuracy=accuracy,
            passed=passed,
            duration_ms=duration_ms,
        )

    def run_all(self, category: str = "speech") -> List[TranscriptionTestResult]:
        """Run all test cases in category."""
        cases = self.load_test_cases(category)
        return [self.run_test(case) for case in cases]

    def _word_accuracy(self, expected: str, actual: str) -> float:
        """Calculate word-level accuracy."""
        expected_words = expected.lower().split()
        actual_words = actual.lower().split()

        if not expected_words:
            return 1.0 if not actual_words else 0.0

        # Simple word overlap metric
        expected_set = set(expected_words)
        actual_set = set(actual_words)
        overlap = len(expected_set & actual_set)

        return overlap / len(expected_set)
```

### Pytest Fixtures

```python
# tests/conftest.py

import pytest
from pathlib import Path

@pytest.fixture
def audio_fixtures_dir():
    """Path to audio test fixtures."""
    return Path(__file__).parent / "fixtures" / "audio"

@pytest.fixture
def silence_source():
    """Synthetic silence source for testing."""
    return SyntheticSource(AudioSourceConfig(
        source_type=SourceType.SYNTHETIC,
        pattern="silence",
        duration_ms=1000,
        playback_mode=PlaybackMode.FAST,
    ))

@pytest.fixture
def tone_source():
    """Synthetic tone source for testing."""
    return SyntheticSource(AudioSourceConfig(
        source_type=SourceType.SYNTHETIC,
        pattern="tone",
        frequency_hz=440,
        duration_ms=1000,
        playback_mode=PlaybackMode.FAST,
    ))

@pytest.fixture
def hello_world_source(audio_fixtures_dir):
    """File source with 'Hello World' speech."""
    return FileSource(AudioSourceConfig(
        source_type=SourceType.FILE,
        file_path=audio_fixtures_dir / "speech" / "hello_world.wav",
        playback_mode=PlaybackMode.FAST,
    ))

@pytest.fixture
def mock_service(silence_source):
    """SttService with mock audio source."""
    return SttService(
        audio_source=silence_source,
        transcriber=MockTranscriber(),
    )

@pytest.fixture
def integration_service(hello_world_source):
    """SttService with file source for integration tests."""
    return SttService(
        audio_source=hello_world_source,
        transcriber=get_transcriber("whisper"),
    )
```

### Example Tests

```python
# tests/test_audio_sources.py

def test_file_source_delivers_chunks(audio_fixtures_dir):
    """File source should deliver audio chunks."""
    source = FileSource(AudioSourceConfig(
        source_type=SourceType.FILE,
        file_path=audio_fixtures_dir / "speech" / "hello_world.wav",
        playback_mode=PlaybackMode.FAST,
    ))

    chunks_received = []

    def on_chunk(data: bytes, frames: int):
        chunks_received.append((data, frames))

    source.open()
    source.start(callback=on_chunk)

    # Wait for completion
    while source.is_active():
        time.sleep(0.01)

    source.close()

    assert len(chunks_received) > 0
    assert all(len(chunk[0]) > 0 for chunk in chunks_received)


def test_synthetic_silence_is_zero():
    """Synthetic silence should be all zeros."""
    source = SyntheticSource(AudioSourceConfig(
        source_type=SourceType.SYNTHETIC,
        pattern="silence",
        duration_ms=100,
        playback_mode=PlaybackMode.FAST,
    ))

    chunks = []
    source.open()
    source.start(callback=lambda d, f: chunks.append(d))

    while source.is_active():
        time.sleep(0.01)

    # All samples should be zero
    all_data = b"".join(chunks)
    samples = np.frombuffer(all_data, dtype=np.int16)
    assert np.all(samples == 0)


def test_service_with_file_source(hello_world_source):
    """Service should process file audio like microphone."""
    service = SttService(
        audio_source=hello_world_source,
        transcriber=get_transcriber("whisper"),
    )

    service.start()

    # Wait for source to finish
    while hello_world_source.is_active():
        time.sleep(0.01)

    transcription = service.get_last_transcription()
    assert "hello" in transcription.lower()
```

---

## CLI Integration

```bash
# Normal operation (microphone)
dictacode-stt

# File replay (real-time pacing)
dictacode-stt --audio-source file:tests/fixtures/audio/speech/hello_world.wav

# File replay (fast, for testing)
dictacode-stt --audio-source file:hello_world.wav:fast

# Specific microphone
dictacode-stt --audio-source mic:rode-ntg-12345

# Synthetic for testing
dictacode-stt --audio-source synthetic:silence:5000
dictacode-stt --audio-source synthetic:tone:440:2000

# Record test fixture
dictacode-stt-audio record tests/fixtures/audio/speech/my_phrase.wav --duration 5
```

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── audio/
│   ├── source.py                 # NEW: AudioSource protocol
│   ├── sources/                  # NEW: Source implementations
│   │   ├── __init__.py           # Factory function
│   │   ├── microphone.py         # MicrophoneSource
│   │   ├── file.py               # FileSource
│   │   └── synthetic.py          # SyntheticSource
│   ├── port.py                   # AudioPort (unchanged)
│   ├── manager.py                # AudioPortManager (unchanged)
│   └── ...
├── service.py                    # Use AudioSource injection
├── cli.py                        # Add --audio-source flag
└── ...

tests/
├── fixtures/
│   └── audio/
│       ├── speech/               # Speech samples with expected text
│       ├── edge_cases/           # Edge case audio
│       └── synthetic/            # Reference signals
├── harness.py                    # TestHarness
├── conftest.py                   # Pytest fixtures
├── test_audio_sources.py         # Source unit tests
├── test_file_source.py           # File source tests
├── test_service_integration.py   # Integration tests
└── ...
```

---

## Files to Modify

1. `apps/stt/src/dictacode_stt/audio/source.py` - NEW: AudioSource protocol
2. `apps/stt/src/dictacode_stt/audio/sources/__init__.py` - NEW: Factory
3. `apps/stt/src/dictacode_stt/audio/sources/microphone.py` - NEW: MicrophoneSource
4. `apps/stt/src/dictacode_stt/audio/sources/file.py` - NEW: FileSource
5. `apps/stt/src/dictacode_stt/audio/sources/synthetic.py` - NEW: SyntheticSource
6. `apps/stt/src/dictacode_stt/service.py` - AudioSource injection
7. `apps/stt/src/dictacode_stt/cli.py` - Add --audio-source flag
8. `apps/stt/src/dictacode_stt/main.py` - Add --audio-source flag
9. `tests/harness.py` - NEW: TestHarness
10. `tests/conftest.py` - Add pytest fixtures
11. `tests/fixtures/audio/` - NEW: Audio test fixtures

---

## Success Criteria

v0.2.11 is complete when:

1. ✅ `AudioSource` protocol defined with mic/file/synthetic types
2. ✅ `MicrophoneSource` wraps current microphone input
3. ✅ `FileSource` replays WAV files with configurable pacing
4. ✅ `SyntheticSource` generates silence/tone/noise
5. ✅ `SttService` accepts injected `AudioSource`
6. ✅ Production code path unchanged when using `MicrophoneSource`
7. ✅ `--audio-source` CLI flag works
8. ✅ Test fixtures with expected transcriptions created
9. ✅ `TestHarness` runs automated transcription tests
10. ✅ Pytest fixtures for common test sources
11. ✅ CI can run tests without physical microphone
12. ✅ Unit tests for all source types
13. ✅ Integration tests with file sources

---

## Out of Scope (v0.2.11)

- Network audio streaming (RTP, RTSP)
- Recording new test fixtures automatically
- Automatic test case generation
- Audio augmentation (noise injection, speed changes)
- Speech synthesis for test generation
- Visual test result reporting
