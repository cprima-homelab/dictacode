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
import time
import wave


# Hardcoded from inventory - sandbox doesn't use config loader
DEVICE_INDEX = 0  # hw:0,0 - RØDE VideoMic NTG
# RØDE VideoMic NTG native: 48000 Hz, 2 channels only
NATIVE_SAMPLE_RATE = 48000
NATIVE_CHANNELS = 2
# Whisper needs 16000 Hz mono
WHISPER_SAMPLE_RATE = 16000


def record_audio(
    output_path: str, duration_sec: float, for_whisper: bool = True
) -> None:
    """Record audio from microphone to WAV file.

    Args:
        output_path: Output WAV file path
        duration_sec: Recording duration in seconds
        for_whisper: If True, resample to 16kHz mono for whisper
    """
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError:
        print("ERROR: sounddevice/numpy not installed")
        sys.exit(1)

    print(f"[record] device: {DEVICE_INDEX} (hw:0,0)")
    print(f"[record] native: {NATIVE_SAMPLE_RATE} Hz, {NATIVE_CHANNELS} ch")
    print(f"[record] duration: {duration_sec} sec")
    print(f"[record] output: {output_path}")
    if for_whisper:
        print(f"[record] resampling to {WHISPER_SAMPLE_RATE} Hz mono for whisper")
    print()

    # Calculate total frames at native rate
    total_frames = int(NATIVE_SAMPLE_RATE * duration_sec)

    print(f"[record] recording {total_frames} frames...")
    start_time = time.perf_counter()

    # Record audio at native settings
    try:
        audio_data = sd.rec(
            total_frames,
            samplerate=NATIVE_SAMPLE_RATE,
            channels=NATIVE_CHANNELS,
            dtype="int16",
            device=DEVICE_INDEX,
        )
        sd.wait()  # Wait until recording is finished
    except Exception as e:
        print(f"[record] ERROR: {e}")
        sys.exit(1)

    elapsed = time.perf_counter() - start_time
    print(f"[record] captured in {elapsed:.2f} sec")

    if for_whisper:
        # Convert stereo to mono (average channels)
        mono = audio_data.mean(axis=1).astype(np.int16)
        # Downsample 48000 -> 16000 (factor of 3)
        resampled = mono[::3]
        out_data = resampled
        out_rate = WHISPER_SAMPLE_RATE
        out_channels = 1
        print(f"[record] resampled: {len(audio_data)} -> {len(resampled)} frames")
    else:
        out_data = audio_data
        out_rate = NATIVE_SAMPLE_RATE
        out_channels = NATIVE_CHANNELS

    # Write to WAV file
    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(out_channels)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(out_rate)
        wf.writeframes(out_data.tobytes())

    print(f"[record] wrote {len(out_data)} frames to {output_path}")


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
