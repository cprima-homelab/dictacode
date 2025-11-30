# dictacode Target Architecture v0.0.1

## Purpose

This document describes the **target architecture** for dictacode. The `sandbox/` experiments validate assumptions before committing to implementation details.

---

## 1. System Goal

Voice-to-keyboard: speak into microphone, text appears as keystrokes on target PC.

```
[Mic] → [Pi5: STT] → [UART] → [Pi0: HID] → [Target PC]
```

---

## 2. Critical Constraint

**The keyboard must type in sequence.**

- Characters must arrive in exact order
- No reordering, no silent drops
- Better to halt than type wrong text

Failure example:
- Spoken: "The quick brown fox jumps over the lazy dog"
- Catastrophe: "The lazy dog jumps."

This constraint drives all protocol decisions.

---

## 3. Device Roles

### Pi5 (STT Node)

**Inputs:**
- USB microphone (RØDE VideoMic NTG, hw:0,0)

**Processing:**
- Audio capture (16kHz mono)
- STT engine (whisper.cpp initially)

**Outputs:**
- Text over UART to Pi0

### Pi0 (HID Node)

**Inputs:**
- Text over UART from Pi5

**Processing:**
- Text → HID keycodes (DE QWERTZ layout)

**Outputs:**
- USB HID keyboard reports to target PC

---

## 4. Communication

### UART Link (Pi5 ↔ Pi0)

**Physical:**
- Pi5 TX (GPIO14) → Pi0 RX (GPIO15)
- Pi5 RX (GPIO15) → Pi0 TX (GPIO14)
- GND ↔ GND
- 115200 baud, 8N1

**Capacity:**
- UART: ~11,500 chars/sec
- Dictation: ~200 wpm max ≈ 17 chars/sec
- Headroom: 700x

### Protocol (TBD)

The sandbox must determine:
1. Is simple newline-delimited text sufficient?
2. Do we need sequence numbers?
3. Do we need checksums?
4. Do we need ACK/NAK?

Start simple. Add complexity only when failures are observed.

---

## 5. Sandbox Experiments

### 5.1 Measure Reality

| Experiment | Question |
|------------|----------|
| `record.py` | Does mic capture work reliably? |
| `transcribe.py` | What's actual transcription latency? |
| `send_uart.py` | Does UART drop bytes at dictation rate? |
| `pipeline.py` | End-to-end latency? Failure modes? |

### 5.2 Stress Tests

| Test | Purpose |
|------|---------|
| Fast speech | What happens at 200+ wpm? |
| Long session | Memory leaks? Drift? |
| Corrupt UART | What fails? How to detect? |

### 5.3 Protocol Discovery

Start with:
```
text\n
text\n
```

If failures observed, progressively add:
```json
{"seq":1,"text":"hello"}\n
{"seq":2,"text":"world"}\n
```

Then if needed:
```json
{"seq":1,"text":"hello","crc":12345}\n
```

Then if needed:
```json
{"seq":1,"total":5,"text":"hello","crc":12345}\n
```

Only add complexity that solves observed problems.

---

## 6. Configuration

Single inventory file: `/etc/dictacode/inventory.yaml`

```yaml
devices:
  stt:
    role: stt
    audio:
      microphone:
        device: hw:0,0
        sample_rate: 16000
    stt:
      engine: whisper.cpp
      whisper:
        binary: ~/whisper.cpp/build/bin/whisper-cli
        model: ~/whisper.cpp/models/ggml-tiny.bin

  hid:
    role: hid
    hid:
      gadget_device: /dev/hidg0
      keymap: de_qwertz

connections:
  - from: stt
    to: hid
    transport: uart
    uart:
      device: /dev/serial0
      baud_rate: 115200
```

Each device reads by role. Same file deployed everywhere.

---

## 7. Software Stack

### Pi5 (apps/stt)

```
dictacode-stt run
├── load config (role=stt)
├── open microphone
├── init STT engine
├── open UART
└── loop:
    ├── capture audio chunk
    ├── transcribe
    └── send text over UART
```

### Pi0 (apps/hid)

```
dictacode-hid run
├── load config (role=hid)
├── open UART
├── open /dev/hidg0
└── loop:
    ├── read text from UART
    ├── convert to keycodes
    └── write HID report
```

---

## 8. What the Sandbox Must Answer

Before implementing the full stack:

1. **Latency budget:** How long from speech to keystroke?
2. **Reliability:** Does UART ever fail at real dictation rates?
3. **Protocol needs:** Simple text? Or seq/checksum/ack?
4. **Buffering:** Where does backpressure happen?
5. **Error handling:** What actually fails? How to recover?

The sandbox is the truth. This document is the hypothesis.

---

## 9. Out of Scope (v0.0.1)

- Web panel
- WiFi transport
- Vosk / cloud STT
- Multi-language support
- Partial/streaming transcription display
- Foot pedal / commit gate

These may be needed later. Sandbox first.
