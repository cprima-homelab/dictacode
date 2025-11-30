#!/usr/bin/env python3
"""
pipeline_stream.py - Continuous STT pipeline with no speech gaps.

Records audio continuously in a background thread while transcription runs.
Uses a queue to pass audio chunks from recorder to processor.

Usage:
    python pipeline_stream.py                # continuous mode (Ctrl+C to stop)
    python pipeline_stream.py --chunk 5      # 5 second chunks (default)
    python pipeline_stream.py --dry-run      # skip UART send
"""

import queue
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

# Hardcoded from inventory
DEVICE_INDEX = 0  # hw:0,0 - RØDE VideoMic NTG
NATIVE_SAMPLE_RATE = 48000
NATIVE_CHANNELS = 2
WHISPER_SAMPLE_RATE = 16000

WHISPER_BINARY = Path.home() / "whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL = Path.home() / "whisper.cpp/models/ggml-tiny.bin"

UART_DEVICE = "/dev/serial0"
BAUD_RATE = 115200


class AudioRecorder:
    """Continuous audio recorder running in background thread."""

    def __init__(self, chunk_duration: float = 5.0):
        self.chunk_duration = chunk_duration
        self.audio_queue: queue.Queue = queue.Queue(maxsize=3)
        self.running = False
        self.thread = None

        # Import here to fail early if not available
        try:
            import sounddevice as sd
            import numpy as np
            self.sd = sd
            self.np = np
        except ImportError:
            print("ERROR: sounddevice/numpy not installed")
            sys.exit(1)

    def start(self):
        """Start background recording thread."""
        self.running = True
        self.thread = threading.Thread(target=self._record_loop, daemon=True)
        self.thread.start()
        print("[recorder] started")

    def stop(self):
        """Stop recording thread."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        print("[recorder] stopped")

    def get_chunk(self, timeout: float = None) -> bytes | None:
        """Get next audio chunk from queue. Returns None if stopped."""
        try:
            return self.audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _record_loop(self):
        """Background recording loop."""
        frames_per_chunk = int(NATIVE_SAMPLE_RATE * self.chunk_duration)

        while self.running:
            try:
                # Record one chunk
                audio_data = self.sd.rec(
                    frames_per_chunk,
                    samplerate=NATIVE_SAMPLE_RATE,
                    channels=NATIVE_CHANNELS,
                    dtype="int16",
                    device=DEVICE_INDEX,
                )
                self.sd.wait()

                if not self.running:
                    break

                # Convert stereo to mono and downsample 48000 -> 16000
                mono = audio_data.mean(axis=1).astype(self.np.int16)
                resampled = mono[::3]
                audio_bytes = resampled.tobytes()

                # Put in queue (non-blocking, drop if full)
                try:
                    self.audio_queue.put_nowait(audio_bytes)
                except queue.Full:
                    print("[recorder] WARNING: queue full, dropping chunk")

            except Exception as e:
                print(f"[recorder] ERROR: {e}")
                time.sleep(0.1)


def save_wav(audio_bytes: bytes, path: str) -> None:
    """Save 16kHz mono audio bytes to WAV file."""
    import wave

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(WHISPER_SAMPLE_RATE)
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

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        print(f"[transcribe] ERROR: {result.stderr}")
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
        return

    ser = serial.Serial(UART_DEVICE, BAUD_RATE, timeout=1)
    try:
        message = text + "\n"
        ser.write(message.encode("utf-8"))
        ser.flush()
    finally:
        ser.close()


def process_loop(recorder: AudioRecorder, dry_run: bool = False):
    """Main processing loop - takes chunks from recorder, transcribes, sends."""
    iteration = 0

    while True:
        # Get next audio chunk (blocks until available)
        audio_bytes = recorder.get_chunk(timeout=1.0)
        if audio_bytes is None:
            if not recorder.running:
                break
            continue

        iteration += 1
        print(f"\n[process] === CHUNK {iteration} ===")

        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        save_wav(audio_bytes, wav_path)

        # Transcribe
        start = time.perf_counter()
        text = transcribe(wav_path)
        elapsed = time.perf_counter() - start

        # Clean up temp file
        Path(wav_path).unlink()

        # Report
        print(f"[process] transcribed in {elapsed:.2f}s: {text[:80]}{'...' if len(text) > 80 else ''}")

        # Send over UART
        if text and not dry_run:
            send_uart(text)
            print(f"[process] sent {len(text)} chars")
        elif dry_run and text:
            print(f"[process] dry-run: would send {len(text)} chars")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Continuous STT pipeline")
    parser.add_argument("--chunk", type=float, default=5.0, help="Chunk duration in seconds")
    parser.add_argument("--dry-run", action="store_true", help="Skip UART send")
    args = parser.parse_args()

    print("[pipeline] dictacode continuous STT")
    print(f"[pipeline] mic: hw:{DEVICE_INDEX},0 ({NATIVE_SAMPLE_RATE}Hz -> {WHISPER_SAMPLE_RATE}Hz)")
    print(f"[pipeline] chunk: {args.chunk}s")
    print(f"[pipeline] whisper: {WHISPER_MODEL.name}")
    print(f"[pipeline] uart: {UART_DEVICE} @ {BAUD_RATE}")
    print()

    # Check prerequisites
    if not WHISPER_BINARY.exists():
        print(f"ERROR: whisper-cli not found: {WHISPER_BINARY}")
        sys.exit(1)
    if not WHISPER_MODEL.exists():
        print(f"ERROR: model not found: {WHISPER_MODEL}")
        sys.exit(1)

    # Start recorder
    recorder = AudioRecorder(chunk_duration=args.chunk)
    recorder.start()

    print("[pipeline] recording... (Ctrl+C to stop)")
    print()

    try:
        process_loop(recorder, dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("\n[pipeline] stopping...")
    finally:
        recorder.stop()

    print("[pipeline] done")


if __name__ == "__main__":
    main()
