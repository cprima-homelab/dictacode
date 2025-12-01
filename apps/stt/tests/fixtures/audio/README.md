# Audio Test Fixtures

This directory contains audio files used for testing dictacode STT.

## Fixture Files

### hello_world.wav
- **Duration:** ~2 seconds
- **Content:** "Hello world"
- **Use case:** Basic transcription test
- **Expected transcription:** "Hello world" (case-insensitive)

### numbers_1_to_5.wav
- **Duration:** ~3 seconds
- **Content:** "One two three four five"
- **Use case:** Number recognition test
- **Expected transcription:** Contains "one", "two", "three", "four", "five"

### silence_1s.wav
- **Duration:** 1 second
- **Content:** Pure silence
- **Use case:** Silence detection, empty transcription test
- **Expected transcription:** "" (empty)

### short_phrase.wav
- **Duration:** ~1 second
- **Content:** "Testing"
- **Use case:** Short audio test, looping tests
- **Expected transcription:** "Testing" or "Test"

## File Format

All test audio files are:
- **Format:** WAV (RIFF)
- **Sample Rate:** 16000 Hz (Whisper native)
- **Channels:** 1 (mono)
- **Bit Depth:** 16-bit signed PCM

## Generating Test Files

You can generate test audio using:

### Using Python (synthetic)
```python
from dictacode_stt.audio.sources import create_audio_source
import wave

# Generate silence
source = create_audio_source("synthetic:silence:1000")
chunks = []

def collect(data, frames):
    chunks.append(data)

source.open()
source.start(callback=collect, on_end=lambda: None)

while source.is_active():
    time.sleep(0.01)

source.close()

# Save to WAV
with wave.open("silence_1s.wav", "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes(b"".join(chunks))
```

### Using text-to-speech
```bash
# Using espeak (Linux)
espeak "Hello world" -w hello_world_raw.wav
sox hello_world_raw.wav -r 16000 -c 1 hello_world.wav

# Using say (macOS)
say "Hello world" -o hello_world_raw.aiff
sox hello_world_raw.aiff -r 16000 -c 1 hello_world.wav
```

### Recording your own
```python
import sounddevice as sd
import wave
import numpy as np

# Record
audio = sd.rec(int(2 * 16000), samplerate=16000, channels=1, dtype='int16')
sd.wait()

# Save
with wave.open("recording.wav", "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes(audio.tobytes())
```

## Usage in Tests

```python
from pathlib import Path
from dictacode_stt.audio.sources import create_audio_source

fixtures_dir = Path(__file__).parent / "fixtures" / "audio"
source = create_audio_source(f"file:{fixtures_dir}/hello_world.wav:fast")
```

## Notes

- Keep audio files small (< 10 seconds) for fast CI/CD
- Use actual speech samples when possible (more realistic than TTS)
- Document expected transcription for each fixture
- Commit test audio to git (files are small)
