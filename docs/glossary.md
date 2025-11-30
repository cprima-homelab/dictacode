# GLOSSARY – Speech-to-Text (STT)

> Working glossary for dictacode, focused on STT concepts and how we name things.

## Speech-to-Text (STT)

### Core STT Concepts

**Speech-to-Text (STT)**  
Conversion of spoken audio into machine-readable text.

**Automatic Speech Recognition (ASR)**  
Technical term for STT systems; same thing, often used in research.

**Utterance**  
A contiguous segment of speech treated as one unit for recognition (e.g. a sentence or phrase).

**Transcript / Transcription**  
The final text representation of one or more utterances.

**Partial Result**  
Intermediate hypothesis while the user is still speaking; low latency, may be wrong.

**Final Result**  
Committed transcript for an utterance; model has decided the segment is complete.

**Endpointing / Voice Activity Detection (VAD)**  
Logic that decides when speech starts and stops so the system can cut utterances.

**Latency**  
Delay between speaking and getting text. Includes audio capture, model inference, and post-processing.

**Streaming STT**  
Recognition happens while the speaker is still talking; emits partial and final results.

**Batch STT**  
Recognition on a pre-recorded file; no partials, only a final transcript.

**Language Model (LM)**  
Statistical model that predicts word sequences; improves recognition quality, especially in noisy contexts.

**Acoustic Model (AM)**  
Model that maps from raw audio to phonetic or linguistic units.

**Decoder**  
Component that combines the acoustic model and language model to select the most likely text.

**Tokenization**  
Breaking text into smaller units (tokens) the model understands (characters, subwords, etc.).

**Post-processing / Text Normalization**  
Fixing casing, punctuation, numbers (“twenty twenty-five” → “2025”), abbreviations, etc.

---

### Audio & Device Terms

**Sample Rate (Hz)**  
Number of audio samples per second (e.g. 16 000 Hz). Common STT rates: 16 kHz, 8 kHz.

**Bit Depth**  
Precision per sample (e.g. 16-bit). Higher depth → wider dynamic range.

**Mono / Stereo**  
One or two channels of audio. Most STT models assume mono.

**Frame / Chunk**  
Small block of audio processed as a unit (e.g. 10–100 ms per chunk).

**Signal-to-Noise Ratio (SNR)**  
Ratio of speech energy to background noise; high SNR → easier recognition.

**Microphone Pattern**  
How a mic picks up sound; common types: cardioid, omnidirectional, shotgun.

**USB Audio Class Device**  
Standard USB spec so OS sees mic/headset without special drivers.

---

### Interaction & UX

**Push-to-Talk (PTT)**  
User holds a key/button while speaking; release = end of utterance.

**Wake Word / Hotword**  
Word/phrase that activates listening (“computer”, “hey dictacode”).

**Dictation Mode**  
STT behaves like a keyboard: user speaks free text into any input field.

**Command Mode**  
Speech is interpreted as structured commands, not literal text (“Agent: run tests”).

**Error Rate (WER, CER)**  
Word Error Rate / Character Error Rate; standard metrics for STT quality.

---

### Architecture Patterns (dictacode Context)

**Sidecar**  
Separate process/device that provides STT as a service, independent of the main host (here: Pi5 box).

**Bridge**  
Component that carries recognized text from the sidecar into another system (here: Pi0 HID keyboard bridge).

**Sink**  
Where recognized text ultimately goes: console, file, network socket, HID keyboard, etc.

**Source**  
Where audio comes from: NTG mic, test WAV file, virtual device, etc.

**Transport**  
Mechanism used to move text/audio between components: TCP, UART, HID, etc.

---

### Model & Runtime

**On-Device Model**  
STT model that runs locally on the hardware (Pi5) without cloud calls.

**Model Size (tiny/small/medium/large)**  
Shorthand for parameter count and footprint; larger usually = better quality + higher latency.

**Runtime / Engine**  
Implementation wrapper around the model (e.g. Vosk, Whisper.cpp) that exposes a clean API.

**Session**  
Logical lifetime of an interaction with the engine (e.g. start listening → stop).

---

### Reliability & Ops

**Graceful Shutdown**  
Handling SIGTERM / SIGINT so the process stops cleanly and closes audio devices.

**Health Check**  
Simple test to confirm the service is alive (e.g. “ping” endpoint or self-test utterance).

**Backpressure**  
Strategy for handling data when downstream sinks are slower than the STT engine.

**Cold Start**  
Extra delay on first request due to model load / initialization.

## USB Gadget / HID

### Core Terms

**USB Gadget**  
A USB **device role** implemented in software (Linux USB-Gadget framework). Board pretends to be keyboard/mouse/etc.

**HID (Human Interface Device)**  
USB class for user input devices like **keyboard**, **mouse**, **gamepad**, **controls**. Driver built into OS, no install needed.

**OTG (On-The-Go) Port**  
USB port that can switch roles. On Pi Zero 2 W, the **single OTG port** is used for gadget mode to the target host.

---

### HID Device Types

**Keyboard (HID Usage Page 0x07)**  
Device sends **keycodes** + modifiers (Shift, Ctrl, Alt, Meta) to type text into host applications.

**Mouse (HID Usage Page 0x01)**  
Device sends **relative or absolute pointer movement** + button clicks.

**Consumer Control (HID Usage Page 0x0C)**  
Sends media keys like **Volume, Play, Pause, Mute, Next, Prev**.

**System Control (HID Usage Page 0x01, System)**  
Power-related keys: **Sleep, Wake, PowerOff**.

---

### HID Data & Protocol

**Report Descriptor**  
Byte code that tells the host **what the HID device is and can send** (format, buttons, axes, key layout).

**Report**  
The actual **data packet** sent to host, matching descriptor format (e.g. 8-byte keyboard report).

**Endpoint**  
USB channel used for reports. HID keyboards use **Interrupt-IN** endpoint (low latency, prioritized by host).

**Modifier Keys**  
Bitmask for modifiers (Shift/Ctrl/Alt/Meta/AltGr). Sent together with keycodes.

**Keycode**  
Standard **HID code**, not ASCII. Mapping is done on gadget side (e.g. QWERTZ table → HID codes).

---

### Key Mapping & Localization

**Keymap / Layout Map**  
Translation table from characters → HID keycodes. Example: *German QWERTZ*, AltGr for `@`, `€`, etc.

---

### Operational & Reliability

**Class-Compliant**  
Host OS already includes driver. HID keyboards are **always class-compliant**.

**Power and Data on Same Cable**  
Zero can draw **power from host** while sending HID keystrokes. No extra driver, no hub software.

**Idempotent Enumeration**  
Gadget must **always expose the same descriptor identity** (VendorID/ProductID/Descriptor) to avoid re-pairing issues.

**Debounce / Flood Protection**  
Inject text in bursts, avoid sending keystrokes too fast for stability on constrained hosts.

**Device Node on Linux**  
HID keyboard writes raw reports to e.g. `/dev/hidg0`.

## Hardware

### SBC Boards
**RPi 5 (Pi5)** – STT host sidecar  
**RPi Zero 2 W (Pi0)** – HID keyboard bridge

### System Administration
User • Permissions • Groups • systemd unit • journald • graceful shutdown

### Storage
microSD • SD card class/speed (A1/A2, UHS-I) • image flashing • idempotent bootstrap

### Power Supply
5V rail • stable current (A) • wall PSU • USB-PD handshake • overcurrent risk • power profile

### Connectors
Soldered GPIO header (40-pin, 2×20) • pin pitch • bridging risk • inspection

### Interfaces
UART • USB RNDIS/NCM (optional) • USB Audio Class

### GPIO & Pin Layout
Pin numbering (BCM/GPIO) • 5V • 3V3 • GND • TX (GPIO14) • RX (GPIO15)

### Wiring
Jumper/Dupont wires • 22–28 AWG • common GND • cross-connect TX→RX • strain relief

### Pinout Example (UART link Pi5→Pi0)
```
Pi5 GPIO14 (TX) ────────▶ Pi0 GPIO15 (RX)
Pi5 GPIO15 (RX) ◀──────── Pi0 GPIO14 (TX)
GND ──────────────────── GND
```

### Interaction Modes (project context)
Mic input → STT → text transport → HID keystroke sink

## Software Architecture (v0.2.x Rewrite)

### 5-Layer Stack

**Transport**
Physical communication layer handling raw bytes over UART, HID, or other channels.

**Protocol**
Message encoding/decoding layer. JSON (human-readable) or msgpack (binary, compact).

**State**
Device mode management via `DeviceMode` enum: LISTENING, MAINTENANCE, PAUSED.

**Service**
Application logic layer orchestrating transport, protocol, state, and business logic.

**Supervisor**
Link health monitoring, reconnection logic, and systemd watchdog integration.

---

### Protocol Messages

**TextMessage**
Protocol message type for transcribed text. JSON: `{"t":"text","p":"hello"}`.

**CommandMessage**
Protocol message type for control commands. JSON: `{"t":"cmd","c":"pause","a":"..."}`.

---

### Device Modes

**DeviceMode**
Enum controlling service behavior: LISTENING (normal), MAINTENANCE (log only), PAUSED (buffer).

**LISTENING Mode**
Normal operation. STT transcribes and sends; HID types received text.

**MAINTENANCE Mode**
Diagnostic mode. Messages logged but not acted upon. Required for `diagnose` command.

**PAUSED Mode**
Temporarily halts action. HID buffers text; STT may stop transcribing.

---

### Diagnostics

**Diagnostics**
Hardware validation and pre-flight checks before service start.

**CheckStatus**
Enum for diagnostic outcomes: OK, WARN, FAIL.

**CheckResult**
Dataclass holding single check outcome: name, status, message, next_step.

**DiagnosticResult**
Aggregated diagnostic results with computed exit code and formatters.

**ExecStartPre**
systemd directive running hardware check before service start. Exit 1 = block, Exit 2 = warn.

---

### systemd Integration

**Watchdog**
systemd feature requiring periodic `WATCHDOG=1` signals to confirm service health.

**WatchdogSec**
Timeout in seconds. If no signal received, systemd restarts the service.

**notify**
systemd service type. Service sends `READY=1` when initialized.

---

### CLI & Testing

**Entry Point**
CLI command defined in `pyproject.toml` `[project.scripts]` section.

**dry-run**
Testing mode. Service runs logic without writing to hardware (UART, HID).

**Keymap**
HID scancode mapping for different keyboard layouts (US, DE, etc.).

---

### Hardware Abstractions

**UDC (USB Device Controller)**
Linux subsystem binding USB gadget to physical USB port.

**ConfigFS**
Virtual filesystem (`/sys/kernel/config`) for configuring USB gadgets at runtime.

**hidg0**
HID gadget device file (`/dev/hidg0`). Writing 8-byte reports sends keystrokes to host.
