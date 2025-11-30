#!/usr/bin/env python3
"""
pipeline.py - Full STT pipeline: mic → whisper → uart.

Sandbox script for dictacode STT.
Tests: end-to-end latency, integration, failure modes.

Usage:
    python pipeline.py                    # record 5 sec, transcribe, send
    python pipeline.py --duration 10      # record 10 sec
    python pipeline.py --loop             # continuous loop (Ctrl+C to stop)
    python pipeline.py --dry-run          # skip UART send
"""

import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Hardcoded from inventory - sandbox doesn't use config loader
DEVICE_INDEX = 0  # hw:0,0 - RØDE VideoMic NTG
SAMPLE_RATE = 16000
CHANNELS = 1

WHISPER_BINARY = Path.home() / "whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL = Path.home() / "whisper.cpp/models/ggml-tiny.bin"

UART_DEVICE = "/dev/serial0"
BAUD_RATE = 115200


def record_audio(duration_sec: float) -> bytes:
    """Record audio from microphone, return raw audio data."""
    try:
        import sounddevice as sd
    except ImportError:
        print("ERROR: sounddevice not installed")
        sys.exit(1)

    total_frames = int(SAMPLE_RATE * duration_sec)

    print(f"[pipeline] recording {duration_sec} sec...")
    start = time.perf_counter()

    audio_data = sd.rec(
        total_frames,
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        device=DEVICE_INDEX,
    )
    sd.wait()

    elapsed = time.perf_counter() - start
    print(f"[pipeline] recorded in {elapsed:.2f} sec")

    return audio_data.tobytes()


def save_wav(audio_bytes: bytes, path: str) -> None:
    """Save raw audio bytes to WAV file."""
    import wave

    with wave.open(path, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_bytes)


def transcribe(wav_path: str) -> str:
    """Transcribe WAV file using whisper-cli."""
    cmd = [
        str(WHISPER_BINARY),
        "-m", str(WHISPER_MODEL),
        "-f", wav_path,
        "--language", "en",
        "--no-timestamps",
    ]

    print(f"[pipeline] transcribing...")
    start = time.perf_counter()

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    elapsed = time.perf_counter() - start
    print(f"[pipeline] transcribed in {elapsed:.2f} sec")

    if result.returncode != 0:
        print(f"[pipeline] ERROR: whisper failed: {result.stderr}")
        return ""

    # Parse output
    lines = result.stdout.strip().split("\n")
    text_parts = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if line.startswith("["):
            bracket_end = line.find("]")
            if bracket_end != -1:
                text = line[bracket_end + 1:].strip()
                if text:
                    text_parts.append(text)
        else:
            text_parts.append(line)

    return " ".join(text_parts)


def send_uart(text: str) -> None:
    """Send text over UART."""
    try:
        import serial
    except ImportError:
        print("ERROR: pyserial not installed")
        sys.exit(1)

    print(f"[pipeline] sending {len(text)} chars over UART...")
    start = time.perf_counter()

    ser = serial.Serial(UART_DEVICE, BAUD_RATE, timeout=1)
    try:
        message = text + "\n"
        ser.write(message.encode("utf-8"))
        ser.flush()
    finally:
        ser.close()

    elapsed = time.perf_counter() - start
    print(f"[pipeline] sent in {elapsed*1000:.2f} ms")


def run_once(duration_sec: float, dry_run: bool = False) -> dict:
    """Run single pipeline iteration. Returns timing stats."""
    stats = {}

    total_start = time.perf_counter()

    # Record
    record_start = time.perf_counter()
    audio_bytes = record_audio(duration_sec)
    stats["record_sec"] = time.perf_counter() - record_start

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    save_wav(audio_bytes, wav_path)

    # Transcribe
    transcribe_start = time.perf_counter()
    text = transcribe(wav_path)
    stats["transcribe_sec"] = time.perf_counter() - transcribe_start

    # Clean up temp file
    Path(wav_path).unlink()

    print()
    print(f"[pipeline] === RESULT ===")
    print(f"[pipeline] text: {text}")
    print(f"[pipeline] ================")
    print()

    stats["text"] = text
    stats["text_len"] = len(text)

    # Send over UART
    if not dry_run and text:
        send_start = time.perf_counter()
        send_uart(text)
        stats["send_sec"] = time.perf_counter() - send_start
    else:
        if dry_run:
            print("[pipeline] dry-run: skipping UART send")
        stats["send_sec"] = 0

    stats["total_sec"] = time.perf_counter() - total_start

    return stats


def print_stats(stats: dict) -> None:
    """Print timing statistics."""
    print()
    print("[pipeline] === TIMING ===")
    print(f"[pipeline] record:     {stats['record_sec']:.2f} sec")
    print(f"[pipeline] transcribe: {stats['transcribe_sec']:.2f} sec")
    print(f"[pipeline] send:       {stats['send_sec']*1000:.2f} ms")
    print(f"[pipeline] total:      {stats['total_sec']:.2f} sec")
    print(f"[pipeline] text len:   {stats['text_len']} chars")
    print("[pipeline] =================")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Full STT pipeline")
    parser.add_argument("--duration", type=float, default=5.0, help="Recording duration (sec)")
    parser.add_argument("--loop", action="store_true", help="Continuous loop")
    parser.add_argument("--dry-run", action="store_true", help="Skip UART send")
    args = parser.parse_args()

    print("[pipeline] dictacode STT sandbox")
    print(f"[pipeline] mic: hw:{DEVICE_INDEX},0")
    print(f"[pipeline] whisper: {WHISPER_BINARY}")
    print(f"[pipeline] model: {WHISPER_MODEL}")
    print(f"[pipeline] uart: {UART_DEVICE} @ {BAUD_RATE}")
    print()

    # Check prerequisites
    if not WHISPER_BINARY.exists():
        print(f"ERROR: whisper-cli not found: {WHISPER_BINARY}")
        sys.exit(1)
    if not WHISPER_MODEL.exists():
        print(f"ERROR: model not found: {WHISPER_MODEL}")
        sys.exit(1)

    if args.loop:
        print("[pipeline] loop mode - Ctrl+C to stop")
        print()
        iteration = 0
        try:
            while True:
                iteration += 1
                print(f"[pipeline] === ITERATION {iteration} ===")
                stats = run_once(args.duration, args.dry_run)
                print_stats(stats)
                print()
                time.sleep(0.5)  # Brief pause between iterations
        except KeyboardInterrupt:
            print("\n[pipeline] stopped")
    else:
        stats = run_once(args.duration, args.dry_run)
        print_stats(stats)


if __name__ == "__main__":
    main()
