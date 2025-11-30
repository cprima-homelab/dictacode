# Sandbox Scripts

Standalone throwaway scripts to validate the STT pipeline before building the real implementation.

## Prerequisites

From `apps/stt/`:

```bash
cd apps/stt
uv sync
```

## Scripts

Run from `apps/stt/` directory using `uv run`:

### record.py - Mic → WAV

```bash
uv run sandbox/record.py                    # 5 sec to recording.wav
uv run sandbox/record.py test.wav 10        # 10 sec to test.wav
uv run sandbox/record.py --list             # list audio devices
```

### transcribe.py - WAV → Text

```bash
uv run sandbox/transcribe.py recording.wav
```

### send_uart.py - Text → UART

```bash
uv run sandbox/send_uart.py "hello world"
uv run sandbox/send_uart.py --file input.txt
uv run sandbox/send_uart.py --stress 1000   # stress test
```

### pipeline.py - Full Chain

```bash
uv run sandbox/pipeline.py                  # record 5 sec, transcribe, send
uv run sandbox/pipeline.py --duration 10    # 10 sec recording
uv run sandbox/pipeline.py --loop           # continuous (Ctrl+C to stop)
uv run sandbox/pipeline.py --dry-run        # skip UART
```

## Hardcoded Values

These scripts use hardcoded paths from `config/inventory.example.yaml`:

| Setting | Value |
|---------|-------|
| Mic | `hw:0,0` (device index 0) |
| Sample rate | 16000 Hz |
| Whisper | `~/whisper.cpp/build/bin/whisper-cli` |
| Model | `~/whisper.cpp/models/ggml-tiny.bin` |
| UART | `/dev/serial0` @ 115200 |

Edit the scripts directly to change these.

## Questions to Answer

1. Does mic capture work reliably?
2. What's actual transcription latency?
3. Does UART drop bytes at dictation rate?
4. End-to-end latency?
5. Failure modes?
