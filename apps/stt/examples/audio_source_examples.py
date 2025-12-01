"""Examples of using audio sources for testing (v0.2.11).

This demonstrates how to use file and synthetic audio sources
instead of a physical microphone for testing.
"""

from pathlib import Path
from dictacode_stt.audio.sources import (
    create_audio_source,
    FileSource,
    SyntheticSource,
    AudioSourceConfig,
    SourceType,
    PlaybackMode,
)


def example_file_source_fast():
    """Example: Fast file replay for CI/CD testing."""
    # Create source from string specification
    source = create_audio_source("file:test_audio.wav:fast")

    # Or create directly with config
    source = FileSource(AudioSourceConfig(
        source_type=SourceType.FILE,
        file_path=Path("test_audio.wav"),
        playback_mode=PlaybackMode.FAST,  # No timing delays, max speed
    ))

    # Track chunks received
    chunks_received = []

    def on_audio(data: bytes, frames: int):
        """Process audio chunk."""
        chunks_received.append(len(data))
        print(f"Received {frames} frames ({len(data)} bytes)")

    def on_end():
        """Called when file ends."""
        print(f"File complete! Total chunks: {len(chunks_received)}")

    # Use the source
    source.open()
    source.start(callback=on_audio, on_end=on_end)

    # Wait for completion
    import time
    while source.is_active():
        time.sleep(0.1)

    source.close()


def example_file_source_realtime():
    """Example: Real-time file replay simulating microphone."""
    # Simulate real microphone timing
    source = create_audio_source("file:speech_sample.wav:realtime")

    def on_audio(data: bytes, frames: int):
        # Process exactly as if from microphone
        print(f"Processing {frames} frames (just like mic input)")

    source.open()
    source.start(callback=on_audio)

    # Runs at real-time speed
    import time
    time.sleep(5)  # Let it run for 5 seconds

    source.stop()
    source.close()


def example_file_source_looping():
    """Example: Loop a short audio file for continuous testing."""
    source = FileSource(AudioSourceConfig(
        source_type=SourceType.FILE,
        file_path=Path("short_phrase.wav"),
        loop=True,  # Repeat indefinitely
        playback_mode=PlaybackMode.FAST,
    ))

    total_frames = 0

    def on_audio(data: bytes, frames: int):
        nonlocal total_frames
        total_frames += frames
        if total_frames % 16000 == 0:  # Every second at 16kHz
            print(f"Processed {total_frames / 16000:.1f} seconds")

    source.open()
    source.start(callback=on_audio)

    # Run for a while
    import time
    time.sleep(2)

    source.stop()
    source.close()
    print(f"Total: {total_frames} frames")


def example_synthetic_silence():
    """Example: Generate silence for testing silence detection."""
    # 1 second of silence, fast mode
    source = create_audio_source("synthetic:silence:1000")

    def on_audio(data: bytes, frames: int):
        # Verify it's actually silence
        import numpy as np
        samples = np.frombuffer(data, dtype=np.int16)
        assert np.all(samples == 0), "Expected silence!"
        print(f"Verified {frames} frames of silence")

    def on_end():
        print("Silence generation complete")

    source.open()
    source.start(callback=on_audio, on_end=on_end)

    import time
    while source.is_active():
        time.sleep(0.01)

    source.close()


def example_file_with_segment():
    """Example: Play only a segment of a file."""
    source = FileSource(AudioSourceConfig(
        source_type=SourceType.FILE,
        file_path=Path("long_recording.wav"),
        start_offset_ms=5000,  # Start at 5 seconds
        end_offset_ms=10000,   # End at 10 seconds
        playback_mode=PlaybackMode.FAST,
    ))

    def on_audio(data: bytes, frames: int):
        print(f"Processing segment: {frames} frames")

    def on_end():
        print("Segment complete (5s-10s)")

    source.open()
    source.start(callback=on_audio, on_end=on_end)

    import time
    while source.is_active():
        time.sleep(0.01)

    source.close()


def example_integration_test_pattern():
    """Example: Typical integration test pattern."""
    import time

    # Setup: Create test source
    test_file = Path("tests/fixtures/audio/hello_world.wav")
    source = create_audio_source(f"file:{test_file}:fast")

    # Mock transcriber or use real one
    transcriptions = []

    def on_audio(data: bytes, frames: int):
        # Feed to transcription pipeline
        # In real test, this would go to SttService
        transcriptions.append(f"chunk_{len(transcriptions)}")

    def on_end():
        # Verify results
        print(f"Test complete: {len(transcriptions)} chunks processed")
        # assert "hello world" in final_transcription.lower()

    # Execute
    source.open()
    source.start(callback=on_audio, on_end=on_end)

    while source.is_active():
        time.sleep(0.01)

    source.close()

    # Cleanup
    print("Integration test passed!")


if __name__ == "__main__":
    print("Audio Source Examples")
    print("=" * 60)

    print("\n1. File Source (Fast Mode)")
    print("-" * 60)
    # example_file_source_fast()

    print("\n2. File Source (Real-time Mode)")
    print("-" * 60)
    # example_file_source_realtime()

    print("\n3. File Source (Looping)")
    print("-" * 60)
    # example_file_source_looping()

    print("\n4. Synthetic Silence")
    print("-" * 60)
    example_synthetic_silence()

    print("\n5. File Segment")
    print("-" * 60)
    # example_file_with_segment()

    print("\n6. Integration Test Pattern")
    print("-" * 60)
    # example_integration_test_pattern()
