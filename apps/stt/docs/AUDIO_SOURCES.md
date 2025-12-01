# Audio Sources for Testing

**Status:** v0.2.11 Phases 1-3 Complete

This document describes the audio source abstraction that enables testing dictacode STT without physical microphones.

## Overview

The audio source abstraction allows you to inject different audio sources into the STT pipeline:

- **File Sources**: Replay WAV files (for integration tests)
- **Synthetic Sources**: Generate test audio (for unit tests)
- **Microphone Sources**: Live microphone (production) [Not yet implemented]

## Why This Matters

### Before (No Testing Without Mic)
```python
# ❌ Can't test without physical microphone
service = SttService()
service.start()  # Requires real mic!
```

### After (Test with Files)
```python
# ✅ Test with file replay
source = create_audio_source("file:test.wav:fast")
service = SttService(audio_source=source)
service.start()  # Runs in CI/CD!
```

## Quick Start

### File Replay (Most Common)

```python
from dictacode_stt.audio.sources import create_audio_source

# Fast mode (for CI/CD)
source = create_audio_source("file:hello_world.wav:fast")

# Real-time mode (simulate mic)
source = create_audio_source("file:hello_world.wav:realtime")

# Use the source
source.open()
source.start(callback=on_audio_chunk, on_end=on_complete)
# ... wait for completion ...
source.close()
```

### Synthetic Silence (Edge Cases)

```python
# Generate 1 second of silence
source = create_audio_source("synthetic:silence:1000")

source.open()
source.start(callback=on_audio_chunk, on_end=on_complete)
# ... wait ...
source.close()
```

## File Sources

### Basic Usage

```python
from dictacode_stt.audio.sources import FileSource, AudioSourceConfig, SourceType, PlaybackMode
from pathlib import Path

config = AudioSourceConfig(
    source_type=SourceType.FILE,
    file_path=Path("speech.wav"),
    playback_mode=PlaybackMode.FAST,
)

source = FileSource(config)
```

### Playback Modes

#### Fast Mode (CI/CD)
```python
# No timing delays - delivers audio as fast as possible
playback_mode=PlaybackMode.FAST
```
**Use for:** CI/CD pipelines, unit tests, quick integration tests

#### Real-time Mode (Development)
```python
# Simulates real microphone timing
playback_mode=PlaybackMode.REALTIME
```
**Use for:** Manual testing, debugging, simulating production behavior

### Advanced Options

#### Looping
```python
config = AudioSourceConfig(
    source_type=SourceType.FILE,
    file_path=Path("short_phrase.wav"),
    loop=True,  # Repeat forever
    playback_mode=PlaybackMode.FAST,
)
```

#### Segments
```python
config = AudioSourceConfig(
    source_type=SourceType.FILE,
    file_path=Path("long_recording.wav"),
    start_offset_ms=5000,  # Start at 5 seconds
    end_offset_ms=10000,   # End at 10 seconds
    playback_mode=PlaybackMode.FAST,
)
```

#### Seeking
```python
source.open()
source.seek(3000)  # Jump to 3 seconds
source.start(callback=on_audio)
```

### Format Support

- **Supported:** 16-bit WAV files
- **Sample Rates:** Any (automatically resampled to target rate)
- **Channels:** Mono or stereo (automatically converted)

## Synthetic Sources

### Silence Generation

```python
from dictacode_stt.audio.sources import create_audio_source

# Generate 2 seconds of silence
source = create_audio_source("synthetic:silence:2000")
```

**Use cases:**
- Test silence detection
- Test timeout behavior
- Test start/stop edge cases

### Other Patterns

The implementation includes tone, noise, click, and sweep generators, but these are **not relevant for transcription testing**. They're available for audio pipeline debugging if needed.

## Source Specification Strings

The `create_audio_source()` factory accepts specification strings:

### File Sources
```python
"file:path/to/audio.wav"           # Real-time playback
"file:path/to/audio.wav:fast"      # Fast playback
"file:path/to/audio.wav:realtime"  # Real-time playback
```

### Synthetic Sources
```python
"synthetic:silence"           # Infinite silence
"synthetic:silence:1000"      # 1 second of silence
```

## Configuration Options

### AudioSourceConfig

```python
@dataclass
class AudioSourceConfig:
    source_type: SourceType          # MICROPHONE, FILE, SYNTHETIC
    sample_rate: int = 16000         # Target sample rate
    channels: int = 1                # Mono (1) or stereo (2)
    chunk_size: int = 1024           # Frames per callback
    playback_mode: PlaybackMode = REALTIME  # Timing behavior

    # File-specific
    file_path: Optional[Path] = None
    loop: bool = False
    start_offset_ms: int = 0
    end_offset_ms: Optional[int] = None

    # Synthetic-specific
    pattern: str = "silence"
    duration_ms: Optional[int] = None
    frequency_hz: float = 440.0
```

## Integration with Tests

### Unit Test Pattern

```python
def test_silence_handling():
    """Test that service handles silence correctly."""
    # Arrange
    source = create_audio_source("synthetic:silence:1000")
    service = SttService(audio_source=source)

    # Act
    service.start()
    while source.is_active():
        time.sleep(0.01)

    # Assert
    assert service.get_transcription() == ""  # No speech detected
```

### Integration Test Pattern

```python
def test_hello_world_transcription():
    """Test transcription of known audio."""
    # Arrange
    source = create_audio_source("file:fixtures/hello_world.wav:fast")
    service = SttService(audio_source=source)

    # Act
    service.start()
    while source.is_active():
        time.sleep(0.01)

    # Assert
    transcription = service.get_transcription()
    assert "hello" in transcription.lower()
    assert "world" in transcription.lower()
```

## Testing Best Practices

### 1. Use Fast Mode in CI/CD

```python
# CI/CD: Fast mode for speed
source = create_audio_source("file:test.wav:fast")

# Development: Real-time for debugging
source = create_audio_source("file:test.wav:realtime")
```

### 2. Create Test Fixtures

```
tests/fixtures/audio/
├── hello_world.wav
├── numbers_1_to_10.wav
├── silence_1s.wav
└── noisy_speech.wav
```

### 3. Test Edge Cases

```python
# Empty input
test_with_source("synthetic:silence:100")

# Very short audio
test_with_source("file:short_click.wav:fast")

# Long audio
test_with_source("file:long_speech.wav:fast")
```

## Limitations

### Current
- Only WAV file format supported
- Microphone source not yet implemented
- No MP3/OGG support

### Future (Not Implemented)
- Network streaming sources (RTP, RTSP)
- Audio augmentation (noise injection, speed changes)
- Multi-source mixing

## Examples

See `apps/stt/examples/audio_source_examples.py` for complete working examples.

## Architecture

### Class Hierarchy

```
AudioSource (ABC)
├── FileSource        [✅ Implemented]
├── SyntheticSource   [✅ Implemented]
└── MicrophoneSource  [❌ Not yet implemented]
```

### Key Components

- **`AudioSource`**: Abstract base class defining the interface
- **`AudioSourceConfig`**: Configuration dataclass
- **`create_audio_source()`**: Factory function for easy instantiation
- **`FileSource`**: WAV file playback with resampling
- **`SyntheticSource`**: Audio generation for testing

## Related Documentation

- [Architecture Plan v0.2.11](../../docs/architecture-plan-v0.2.11.md) - Full design
- [Audio Backend Abstraction](../../docs/architecture-plan-v0.2.10.md) - Platform abstraction
- [Examples](../examples/audio_source_examples.py) - Code examples

## Next Steps

The following phases are not yet implemented:

- **Phase 4**: Source injection into SttService
- **Phase 5**: Test harness and fixtures
- **Phase 6**: CLI integration (`--audio-source` flag)

## Questions?

See the examples or architecture plans for more details.
