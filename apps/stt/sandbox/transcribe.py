#!/usr/bin/env python3
"""
transcribe.py - Transcribe WAV file using whisper.cpp.

Sandbox script for dictacode STT.
Tests: whisper-cli invocation, latency, output parsing.

Usage:
    python transcribe.py <input.wav>
    python transcribe.py recording.wav
"""

import subprocess
import sys
import time
from pathlib import Path


# Hardcoded from inventory - sandbox doesn't use config loader
WHISPER_BINARY = Path.home() / "whisper.cpp/build/bin/whisper-cli"
WHISPER_MODEL = Path.home() / "whisper.cpp/models/ggml-tiny.bin"


def transcribe_file(wav_path: str) -> str:
    """Transcribe WAV file using whisper-cli subprocess."""
    wav_path = Path(wav_path)

    if not wav_path.exists():
        print(f"[transcribe] ERROR: file not found: {wav_path}")
        sys.exit(1)

    if not WHISPER_BINARY.exists():
        print(f"[transcribe] ERROR: whisper-cli not found: {WHISPER_BINARY}")
        sys.exit(1)

    if not WHISPER_MODEL.exists():
        print(f"[transcribe] ERROR: model not found: {WHISPER_MODEL}")
        sys.exit(1)

    print(f"[transcribe] binary: {WHISPER_BINARY}")
    print(f"[transcribe] model: {WHISPER_MODEL}")
    print(f"[transcribe] input: {wav_path}")
    print()

    # Build command
    cmd = [
        str(WHISPER_BINARY),
        "-m",
        str(WHISPER_MODEL),
        "-f",
        str(wav_path),
        "--language",
        "en",
        "--no-timestamps",
        "--output-txt",
    ]

    print(f"[transcribe] running: {' '.join(cmd)}")
    print()

    start_time = time.perf_counter()

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        print("[transcribe] ERROR: timeout after 60 sec")
        sys.exit(1)
    except Exception as e:
        print(f"[transcribe] ERROR: {e}")
        sys.exit(1)

    elapsed = time.perf_counter() - start_time

    # whisper-cli outputs to stdout with timing info
    # The actual text is in the output, we need to parse it
    stdout = result.stdout
    stderr = result.stderr

    if result.returncode != 0:
        print(f"[transcribe] ERROR: whisper-cli returned {result.returncode}")
        print(f"[transcribe] stderr: {stderr}")
        sys.exit(1)

    # Parse output - whisper-cli outputs text after timing lines
    # Format: [00:00:00.000 --> 00:00:02.000]   text here
    # With --no-timestamps, it's cleaner but still has brackets
    lines = stdout.strip().split("\n")
    text_lines = []
    for line in lines:
        line = line.strip()
        # Skip empty lines and timing info
        if not line:
            continue
        # Extract text from timestamp lines if present
        if line.startswith("["):
            # Find the closing bracket and extract text after
            bracket_end = line.find("]")
            if bracket_end != -1:
                text = line[bracket_end + 1 :].strip()
                if text:
                    text_lines.append(text)
        else:
            text_lines.append(line)

    transcription = " ".join(text_lines)

    print(f"[transcribe] elapsed: {elapsed:.2f} sec")
    print(f"[transcribe] text length: {len(transcription)} chars")
    print()
    print("=== TRANSCRIPTION ===")
    print(transcription)
    print("=====================")

    return transcription


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python transcribe.py <input.wav>")
        sys.exit(1)

    wav_path = sys.argv[1]
    transcribe_file(wav_path)


if __name__ == "__main__":
    main()
