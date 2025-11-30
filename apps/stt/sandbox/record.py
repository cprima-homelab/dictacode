#!/usr/bin/env python3
"""
record.py - Record audio from USB microphone to WAV file.

Sandbox script for dictacode STT.
Tests: mic capture, audio quality, duration handling.

Usage:
    python record.py [output.wav] [duration_sec]
    python record.py                     # records to recording.wav for 5 sec
    python record.py test.wav 10         # records to test.wav for 10 sec
"""

import sys
import wave
import time

# Hardcoded from inventory - sandbox doesn't use config loader
DEVICE_INDEX = 0  # hw:0,0 - RØDE VideoMic NTG
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 1024  # frames per buffer


def record_audio(output_path: str, duration_sec: float) -> None:
    """Record audio from microphone to WAV file."""
    try:
        import sounddevice as sd
    except ImportError:
        print("ERROR: sounddevice not installed. Run: pip install sounddevice")
        sys.exit(1)

    print(f"[record] device: {DEVICE_INDEX} (hw:0,0)")
    print(f"[record] sample rate: {SAMPLE_RATE} Hz")
    print(f"[record] channels: {CHANNELS}")
    print(f"[record] duration: {duration_sec} sec")
    print(f"[record] output: {output_path}")
    print()

    # Calculate total frames
    total_frames = int(SAMPLE_RATE * duration_sec)

    print(f"[record] recording {total_frames} frames...")
    start_time = time.perf_counter()

    # Record audio
    try:
        audio_data = sd.rec(
            total_frames,
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            device=DEVICE_INDEX,
        )
        sd.wait()  # Wait until recording is finished
    except Exception as e:
        print(f"[record] ERROR: {e}")
        sys.exit(1)

    elapsed = time.perf_counter() - start_time
    print(f"[record] captured in {elapsed:.2f} sec")

    # Write to WAV file
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_data.tobytes())

    print(f"[record] wrote {len(audio_data)} frames to {output_path}")
    print(f"[record] file size: {len(audio_data) * 2} bytes")


def list_devices() -> None:
    """List available audio devices."""
    try:
        import sounddevice as sd
    except ImportError:
        print("ERROR: sounddevice not installed")
        return

    print("[record] available devices:")
    print(sd.query_devices())


def main() -> None:
    # Parse args
    output_path = sys.argv[1] if len(sys.argv) > 1 else "recording.wav"
    duration_sec = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0

    if output_path == "--list":
        list_devices()
        return

    record_audio(output_path, duration_sec)


if __name__ == "__main__":
    main()
