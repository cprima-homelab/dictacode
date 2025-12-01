# Bill of Materials

Complete hardware list for building a dictacode speech-to-text system.

## Overview

| Category | Purpose |
|----------|---------|
| Compute | Speech processing (Pi 5) and HID output (Pi Zero 2 W) |
| Audio | Voice capture |
| Interconnect | UART communication between compute units |
| Power | Power supply for all components |
| Enclosure | Optional housing |

---

## Core Components

### Compute Units

| Qty | Component | Specification | Role | Est. Price |
|-----|-----------|---------------|------|------------|
| 1 | Raspberry Pi 5 | 4GB or 8GB RAM | STT processing (whisper.cpp) | $60-80 |
| 1 | Raspberry Pi Zero 2 W | 512MB RAM | USB HID keyboard gadget | $15 |

**Notes:**
- Pi 5 8GB recommended for larger whisper models
- Pi Zero 2 W required (not Pi Zero W) for adequate performance
- Pi Zero 2 W must use **USB data port** (not PWR) for HID output

### Audio Input

| Qty | Component | Specification | Role | Est. Price |
|-----|-----------|---------------|------|------------|
| 1 | USB Microphone | See recommendations below | Voice capture | $50-300 |

**Tested Microphones:**

| Model | Sample Rate | Notes |
|-------|-------------|-------|
| RODE VideoMic NTG | 48kHz stereo (native) | Excellent quality, resampled to 16kHz mono |

**Requirements:**
- USB Audio Class compliant
- Minimum 16kHz sample rate (or higher, will be resampled)
- Low latency preferred

---

## Interconnect

### UART Connection (Pi 5 to Pi Zero)

| Qty | Component | Specification | Purpose |
|-----|-----------|---------------|---------|
| 3 | Jumper wires (F-F) | 10-20cm | TX, RX, GND connections |

**Wiring:**

| Pi 5 | Pi Zero 2 W | Function |
|------|-------------|----------|
| GPIO 14 (Pin 8) | GPIO 15 (Pin 10) | TX -> RX |
| GPIO 15 (Pin 10) | GPIO 14 (Pin 8) | RX -> TX |
| GND (Pin 6) | GND (Pin 6) | Common ground |

**UART Configuration:**
- Baud rate: 115200
- Data bits: 8
- Stop bits: 1
- Parity: None

### USB Connections

| Connection | Cable Type | Purpose |
|------------|------------|---------|
| Pi 5 <- Microphone | USB-A to device | Audio input |
| Pi Zero -> Target PC | USB Micro-B (data port) | HID keyboard output |

---

## Power Supply

| Qty | Component | Specification | Powers |
|-----|-----------|---------------|--------|
| 1 | USB-C Power Supply | 5V 5A (27W) PD | Raspberry Pi 5 |
| 1 | USB Power Supply | 5V 2.5A | Raspberry Pi Zero 2 W |

**Notes:**
- Pi 5 requires official 27W USB-C power supply for full performance
- Pi Zero can be powered via USB from target PC (if sufficient power available)
- Consider powered USB hub if target PC USB power is insufficient

---

## Storage

| Qty | Component | Specification | Purpose |
|-----|-----------|---------------|---------|
| 1 | microSD Card | 32GB+ Class 10/A1 | Pi 5 boot/storage |
| 1 | microSD Card | 16GB+ Class 10 | Pi Zero boot/storage |

**Recommended:**
- SanDisk Extreme or Samsung EVO Select
- A2 rating for Pi 5 (better random I/O)

---

## Optional Components

### Enclosure

| Qty | Component | Purpose |
|-----|-----------|---------|
| 1 | Pi 5 case | Protection, cooling |
| 1 | Pi Zero case | Protection |
| 1 | Project enclosure | Combined housing |

### Cooling (Pi 5)

| Qty | Component | Purpose |
|-----|-----------|---------|
| 1 | Active cooler / heatsink | Thermal management during STT processing |

**Note:** whisper.cpp is CPU-intensive; active cooling recommended for sustained use.

### Debug/Development

| Qty | Component | Purpose |
|-----|-----------|---------|
| 1 | USB-TTL Serial adapter | Debug UART connection |
| 1 | HDMI cable + monitor | Initial setup |
| 1 | USB keyboard | Initial setup |

---

## Complete System Cost Estimate

| Category | Min | Max |
|----------|-----|-----|
| Compute (Pi 5 + Pi Zero 2 W) | $75 | $95 |
| Microphone | $50 | $300 |
| Power supplies | $20 | $40 |
| Storage (2x microSD) | $15 | $30 |
| Cables and wiring | $10 | $20 |
| **Total** | **$170** | **$485** |

---

## Supplier References

| Component | Suppliers |
|-----------|-----------|
| Raspberry Pi | raspberrypi.com, Adafruit, SparkFun, The Pi Hut |
| RODE Microphones | rode.com, B&H Photo, Amazon |
| General electronics | Adafruit, SparkFun, Mouser, Digi-Key |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-11-30 | Initial BOM for sandbox/prototype phase |
