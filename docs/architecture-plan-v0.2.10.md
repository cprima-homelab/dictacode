# dictacode Architecture Plan v0.2.10 - Cross-Platform Audio Backend

## Status

### Phase 1: Audio Backend Interface ✅ COMPLETE
- [x] Create `audio/backends/` package
- [x] Define `AudioBackend` ABC
- [x] Define `AudioInputStream`, `BackendDeviceInfo` protocols
- [x] Define `BackendType`, `BackendCapabilities`
- [x] Create platform detection module
- [ ] Unit tests for backend types

### Phase 2: ALSA Backend (Linux)
- [ ] Implement `AlsaBackend` wrapping current sounddevice/ALSA code
- [ ] Extract platform-specific device enumeration
- [ ] Handle ALSA-specific error codes
- [ ] Unit tests with mock ALSA

### Phase 3: PortAudio Backend (Cross-Platform)
- [ ] Implement `PortAudioBackend` (via sounddevice)
- [ ] Abstract sounddevice calls behind backend interface
- [ ] Test on Linux with PortAudio

### Phase 4: CoreAudio Backend (macOS)
- [ ] Implement `CoreAudioBackend` stub
- [ ] Document macOS-specific requirements
- [ ] Test basic functionality on macOS (if available)

### Phase 5: WASAPI Backend (Windows)
- [ ] Implement `WasapiBackend` stub
- [ ] Document Windows-specific requirements
- [ ] Test basic functionality on Windows (if available)

### Phase 6: Backend Factory & Detection
- [ ] Implement `get_audio_backend()` with auto-detection
- [ ] Platform detection logic
- [ ] Fallback chain (native → PortAudio)
- [ ] Add `--audio-backend` CLI flag

**v0.2.10 NOT STARTED**

---

## Prerequisites

v0.2.10 builds on top of:
- ✅ v0.2.4: Audio Port Abstraction (`AudioPort`, `AudioPortManager`)
- ✅ v0.2.6: Adapter pattern established

---

## Problem Statement

### Current ALSA Coupling

Audio handling is tightly coupled to ALSA/Linux:

```python
# Current: sounddevice assumes ALSA on Linux
import sounddevice as sd

# ALSA-specific device queries
devices = sd.query_devices()

# ALSA-specific error handling
try:
    stream = sd.InputStream(...)
except sd.PortAudioError as e:
    # ALSA error codes leak through
    if "Device or resource busy" in str(e):
        ...
```

**Issues:**
- `sounddevice` abstracts some, but ALSA assumptions leak through
- Device naming follows ALSA conventions (`hw:0`, `plughw:1,0`)
- Error messages are ALSA-specific
- No path to macOS (CoreAudio) or Windows (WASAPI)
- Android would need OpenSL ES or AAudio

### Cross-Platform Vision

| Platform | Native API | Python Library | Priority |
|----------|------------|----------------|----------|
| Linux | ALSA | sounddevice/pyalsaaudio | Primary |
| macOS | CoreAudio | sounddevice/pyaudio | Future |
| Windows | WASAPI | sounddevice/pyaudio | Future |
| Android | AAudio/OpenSL | python-for-android | Future |

**Goal:** Abstract audio backend to enable future cross-platform support.

---

## Design

### Audio Backend ABC

```python
# audio/backends/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Callable
from enum import Enum

class BackendType(Enum):
    ALSA = "alsa"           # Linux native
    PULSEAUDIO = "pulseaudio"  # Linux with PulseAudio
    PORTAUDIO = "portaudio" # Cross-platform via PortAudio
    COREAUDIO = "coreaudio" # macOS native
    WASAPI = "wasapi"       # Windows native
    AAUDIO = "aaudio"       # Android native

@dataclass
class BackendCapabilities:
    """Capabilities of an audio backend."""
    name: str
    platform: str                  # "linux", "darwin", "win32", "android"
    supports_exclusive: bool       # Exclusive device access
    supports_loopback: bool        # System audio capture
    supports_hot_plug: bool        # Device change notifications
    min_latency_ms: int
    max_channels: int

@dataclass
class BackendDeviceInfo:
    """Platform-agnostic device information."""
    device_id: str                 # Backend-specific ID
    name: str                      # Human-readable name
    is_input: bool
    is_output: bool
    is_default: bool
    sample_rates: List[int]
    channels: int
    backend_type: BackendType

    # Platform-specific metadata (optional)
    alsa_card: Optional[int] = None
    alsa_device: Optional[int] = None
    usb_vendor_id: Optional[str] = None
    usb_product_id: Optional[str] = None

# Callback types
AudioDataCallback = Callable[[bytes, int], None]  # (data, frames)
DeviceChangeCallback = Callable[[List[BackendDeviceInfo]], None]

class AudioBackend(ABC):
    """Abstract audio backend for platform-specific audio APIs."""

    @abstractmethod
    def get_type(self) -> BackendType:
        """Return backend type."""
        pass

    @abstractmethod
    def get_capabilities(self) -> BackendCapabilities:
        """Return backend capabilities."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if backend is available on this system."""
        pass

    @abstractmethod
    def initialize(self) -> None:
        """Initialize the audio backend."""
        pass

    @abstractmethod
    def terminate(self) -> None:
        """Cleanup backend resources."""
        pass

    @abstractmethod
    def list_devices(self) -> List[BackendDeviceInfo]:
        """Enumerate available audio devices."""
        pass

    @abstractmethod
    def get_default_input_device(self) -> Optional[BackendDeviceInfo]:
        """Get system default input device."""
        pass

    @abstractmethod
    def open_input_stream(
        self,
        device_id: str,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
        buffer_frames: int = 1024,
    ) -> "AudioInputStream":
        """Open an input stream on the specified device."""
        pass

    def register_device_change_callback(
        self,
        callback: DeviceChangeCallback,
    ) -> None:
        """Register callback for device changes (if supported)."""
        pass  # Optional, default no-op


class AudioInputStream(ABC):
    """Abstract audio input stream."""

    @abstractmethod
    def start(self) -> None:
        """Start capturing audio."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop capturing audio."""
        pass

    @abstractmethod
    def close(self) -> None:
        """Close and release stream resources."""
        pass

    @abstractmethod
    def is_active(self) -> bool:
        """Return True if stream is capturing."""
        pass

    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Actual sample rate of stream."""
        pass

    @property
    @abstractmethod
    def channels(self) -> int:
        """Number of channels."""
        pass

    @property
    @abstractmethod
    def latency_ms(self) -> float:
        """Current stream latency."""
        pass
```

### ALSA Backend (Linux Native)

```python
# audio/backends/alsa.py

import platform
from typing import List, Optional

class AlsaBackend(AudioBackend):
    """ALSA audio backend for Linux."""

    def __init__(self):
        self._initialized = False

    def get_type(self) -> BackendType:
        return BackendType.ALSA

    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            name="ALSA",
            platform="linux",
            supports_exclusive=True,
            supports_loopback=False,  # Requires aloop module
            supports_hot_plug=False,  # Need udev for this
            min_latency_ms=5,
            max_channels=32,
        )

    def is_available(self) -> bool:
        if platform.system() != "Linux":
            return False
        try:
            # Check for ALSA libraries
            import sounddevice as sd
            sd.query_devices()
            return True
        except Exception:
            return False

    def initialize(self) -> None:
        if self._initialized:
            return
        # Any ALSA-specific initialization
        self._initialized = True

    def terminate(self) -> None:
        self._initialized = False

    def list_devices(self) -> List[BackendDeviceInfo]:
        import sounddevice as sd

        devices = []
        sd_devices = sd.query_devices()

        for idx, dev in enumerate(sd_devices):
            if dev["max_input_channels"] == 0:
                continue  # Skip output-only devices

            # Parse ALSA card/device from name
            alsa_card, alsa_device = self._parse_alsa_name(dev["name"])

            devices.append(BackendDeviceInfo(
                device_id=str(idx),
                name=dev["name"],
                is_input=dev["max_input_channels"] > 0,
                is_output=dev["max_output_channels"] > 0,
                is_default=(idx == sd.default.device[0]),
                sample_rates=self._get_supported_rates(idx),
                channels=dev["max_input_channels"],
                backend_type=BackendType.ALSA,
                alsa_card=alsa_card,
                alsa_device=alsa_device,
            ))

        return devices

    def get_default_input_device(self) -> Optional[BackendDeviceInfo]:
        devices = self.list_devices()
        for dev in devices:
            if dev.is_default and dev.is_input:
                return dev
        return devices[0] if devices else None

    def open_input_stream(
        self,
        device_id: str,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
        buffer_frames: int = 1024,
    ) -> "AlsaInputStream":
        return AlsaInputStream(
            device_id=int(device_id),
            sample_rate=sample_rate,
            channels=channels,
            callback=callback,
            buffer_frames=buffer_frames,
        )

    def _parse_alsa_name(self, name: str) -> tuple[Optional[int], Optional[int]]:
        """Extract ALSA card/device numbers from device name."""
        # e.g., "hw:0,0" or "HDA Intel PCH: ALC..."
        import re
        match = re.search(r"hw:(\d+),(\d+)", name)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None, None

    def _get_supported_rates(self, device_id: int) -> List[int]:
        """Query supported sample rates for device."""
        # Common rates to test
        standard_rates = [8000, 16000, 22050, 44100, 48000, 96000]
        supported = []

        import sounddevice as sd
        for rate in standard_rates:
            try:
                sd.check_input_settings(
                    device=device_id,
                    samplerate=rate,
                )
                supported.append(rate)
            except Exception:
                pass

        return supported or [48000]  # Fallback


class AlsaInputStream(AudioInputStream):
    """ALSA input stream implementation."""

    def __init__(
        self,
        device_id: int,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
        buffer_frames: int,
    ):
        import sounddevice as sd

        self._device_id = device_id
        self._sample_rate = sample_rate
        self._channels = channels
        self._callback = callback
        self._buffer_frames = buffer_frames
        self._stream: Optional[sd.InputStream] = None

    def start(self) -> None:
        import sounddevice as sd

        def sd_callback(indata, frames, time, status):
            if status:
                logger.warning(f"ALSA stream status: {status}")
            self._callback(indata.tobytes(), frames)

        self._stream = sd.InputStream(
            device=self._device_id,
            samplerate=self._sample_rate,
            channels=self._channels,
            blocksize=self._buffer_frames,
            callback=sd_callback,
            dtype="int16",
        )
        self._stream.start()

    def stop(self) -> None:
        if self._stream:
            self._stream.stop()

    def close(self) -> None:
        if self._stream:
            self._stream.close()
            self._stream = None

    def is_active(self) -> bool:
        return self._stream is not None and self._stream.active

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels

    @property
    def latency_ms(self) -> float:
        if self._stream:
            return self._stream.latency * 1000
        return 0.0
```

### PortAudio Backend (Cross-Platform)

```python
# audio/backends/portaudio.py

class PortAudioBackend(AudioBackend):
    """PortAudio backend - works on Linux, macOS, Windows."""

    def get_type(self) -> BackendType:
        return BackendType.PORTAUDIO

    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            name="PortAudio",
            platform=platform.system().lower(),
            supports_exclusive=False,
            supports_loopback=False,
            supports_hot_plug=False,
            min_latency_ms=10,
            max_channels=16,
        )

    def is_available(self) -> bool:
        try:
            import sounddevice as sd
            sd.query_devices()
            return True
        except Exception:
            return False

    # ... similar implementation using sounddevice
    # But without ALSA-specific assumptions
```

### CoreAudio Backend Stub (macOS)

```python
# audio/backends/coreaudio.py

class CoreAudioBackend(AudioBackend):
    """CoreAudio backend for macOS."""

    def get_type(self) -> BackendType:
        return BackendType.COREAUDIO

    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            name="CoreAudio",
            platform="darwin",
            supports_exclusive=True,
            supports_loopback=True,  # Via aggregate devices
            supports_hot_plug=True,
            min_latency_ms=3,
            max_channels=64,
        )

    def is_available(self) -> bool:
        return platform.system() == "Darwin"

    def initialize(self) -> None:
        # Would use pyobjc or native bindings
        raise NotImplementedError("CoreAudio support not yet implemented")

    # ... stub implementations
```

### WASAPI Backend Stub (Windows)

```python
# audio/backends/wasapi.py

class WasapiBackend(AudioBackend):
    """WASAPI backend for Windows."""

    def get_type(self) -> BackendType:
        return BackendType.WASAPI

    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            name="WASAPI",
            platform="win32",
            supports_exclusive=True,
            supports_loopback=True,  # WASAPI loopback capture
            supports_hot_plug=True,
            min_latency_ms=3,
            max_channels=32,
        )

    def is_available(self) -> bool:
        return platform.system() == "Windows"

    def initialize(self) -> None:
        # Would use pycaw or comtypes
        raise NotImplementedError("WASAPI support not yet implemented")

    # ... stub implementations
```

### Backend Factory

```python
# audio/backends/__init__.py

import platform
from typing import Optional

def get_audio_backend(
    backend_type: Optional[str] = None,
) -> AudioBackend:
    """
    Get audio backend by type or auto-detect best for platform.

    Args:
        backend_type: 'alsa', 'portaudio', 'coreaudio', 'wasapi', or None for auto

    Returns:
        AudioBackend instance
    """
    backends = {
        "alsa": AlsaBackend,
        "portaudio": PortAudioBackend,
        "coreaudio": CoreAudioBackend,
        "wasapi": WasapiBackend,
    }

    if backend_type:
        if backend_type not in backends:
            raise ValueError(f"Unknown backend: {backend_type}")
        backend = backends[backend_type]()
        if not backend.is_available():
            raise RuntimeError(f"Backend {backend_type} not available on this system")
        return backend

    # Auto-detect based on platform
    return _auto_detect_backend()


def _auto_detect_backend() -> AudioBackend:
    """Auto-detect best backend for current platform."""
    system = platform.system()

    # Platform-specific preference order
    if system == "Linux":
        preference = [AlsaBackend, PortAudioBackend]
    elif system == "Darwin":
        preference = [CoreAudioBackend, PortAudioBackend]
    elif system == "Windows":
        preference = [WasapiBackend, PortAudioBackend]
    else:
        preference = [PortAudioBackend]

    for backend_class in preference:
        backend = backend_class()
        if backend.is_available():
            return backend

    raise RuntimeError("No audio backend available")


def list_available_backends() -> List[str]:
    """List backends available on this system."""
    available = []
    for name, cls in [
        ("alsa", AlsaBackend),
        ("portaudio", PortAudioBackend),
        ("coreaudio", CoreAudioBackend),
        ("wasapi", WasapiBackend),
    ]:
        try:
            if cls().is_available():
                available.append(name)
        except Exception:
            pass
    return available
```

---

## Integration with AudioPortManager

```python
# audio/manager.py

class AudioPortManager:
    """Platform-agnostic audio port manager."""

    def __init__(
        self,
        backend: Optional[AudioBackend] = None,
    ):
        self.backend = backend or get_audio_backend()
        self.backend.initialize()
        self._device_cache: List[AudioPort] = []

    def list_ports(self) -> List[AudioPort]:
        """List available audio input ports."""
        backend_devices = self.backend.list_devices()

        ports = []
        for dev in backend_devices:
            if not dev.is_input:
                continue

            # Map backend device to AudioPort
            port = AudioPort(
                port_id=self._generate_port_id(dev),
                port_type=self._map_port_type(dev),
                name=dev.name,
                capabilities=AudioPortCapabilities(
                    sample_rates=dev.sample_rates,
                    channels=dev.channels,
                    formats=["int16"],  # Standard format
                    native_rate=dev.sample_rates[-1] if dev.sample_rates else 48000,
                ),
                status=PortStatus.AVAILABLE,
                backend_device=dev,  # Store for later use
            )
            ports.append(port)

        self._device_cache = ports
        return ports

    def _generate_port_id(self, dev: BackendDeviceInfo) -> str:
        """Generate stable port ID from device info."""
        # Prefer USB IDs if available
        if dev.usb_vendor_id and dev.usb_product_id:
            return f"usb:{dev.usb_vendor_id}:{dev.usb_product_id}"
        # Fall back to name-based ID
        return dev.name.lower().replace(" ", "-")[:32]

    def _map_port_type(self, dev: BackendDeviceInfo) -> str:
        """Map backend device to port type."""
        name_lower = dev.name.lower()
        if "usb" in name_lower:
            return "usb"
        if dev.alsa_card is not None:
            return "alsa"
        return "generic"

    def open_stream(
        self,
        port: AudioPort,
        sample_rate: int,
        channels: int,
        callback: AudioDataCallback,
    ) -> AudioInputStream:
        """Open audio input stream on port."""
        return self.backend.open_input_stream(
            device_id=port.backend_device.device_id,
            sample_rate=sample_rate,
            channels=channels,
            callback=callback,
        )
```

---

## Platform Detection

```python
# audio/platform.py

import platform
import os
from dataclasses import dataclass

@dataclass
class PlatformInfo:
    """Detected platform information."""
    system: str           # "Linux", "Darwin", "Windows"
    release: str          # Kernel/OS version
    machine: str          # "x86_64", "aarch64", "armv7l"
    is_raspberry_pi: bool
    is_android: bool
    recommended_backend: str

def detect_platform() -> PlatformInfo:
    """Detect current platform and recommend backend."""
    system = platform.system()
    release = platform.release()
    machine = platform.machine()

    # Raspberry Pi detection
    is_rpi = False
    if system == "Linux":
        try:
            with open("/proc/cpuinfo") as f:
                cpuinfo = f.read()
            is_rpi = "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo
        except Exception:
            pass

    # Android detection
    is_android = "ANDROID_ROOT" in os.environ or "android" in release.lower()

    # Recommend backend
    if is_android:
        recommended = "aaudio"
    elif system == "Linux":
        recommended = "alsa"
    elif system == "Darwin":
        recommended = "coreaudio"
    elif system == "Windows":
        recommended = "wasapi"
    else:
        recommended = "portaudio"

    return PlatformInfo(
        system=system,
        release=release,
        machine=machine,
        is_raspberry_pi=is_rpi,
        is_android=is_android,
        recommended_backend=recommended,
    )
```

---

## CLI Integration

```bash
# List available backends
dictacode-stt-audio backends
Available audio backends:
  alsa       - Linux ALSA (native) [active]
  portaudio  - PortAudio (cross-platform)

# Use specific backend
dictacode-stt --audio-backend portaudio

# Show platform info
dictacode-stt-audio platform
Platform: Linux 6.1.0-rpi
Machine: aarch64
Raspberry Pi: Yes
Recommended backend: alsa

# List devices with backend info
dictacode-stt-audio ports --verbose
PORT_ID              BACKEND  NAME                    SAMPLE RATES
usb:19f7:0015        alsa     RØDE VideoMic NTG       48000
hw:0                 alsa     bcm2835 Headphones      44100,48000
```

---

## Configuration

```ini
# /etc/dictacode/audio/audio.conf
[audio]
# Backend selection
# backend = auto        # Auto-detect best for platform
# backend = alsa        # Force ALSA
# backend = portaudio   # Force PortAudio
backend = auto

# Fallback if preferred backend unavailable
fallback_backend = portaudio
```

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── audio/
│   ├── __init__.py               # Public exports
│   ├── port.py                   # AudioPort (unchanged)
│   ├── manager.py                # MODIFIED: Use AudioBackend
│   ├── buffer.py                 # AudioRingBuffer (unchanged)
│   ├── resampler.py              # Resampler (unchanged)
│   ├── platform.py               # NEW: Platform detection
│   └── backends/                 # NEW: Backend implementations
│       ├── __init__.py           # Factory, exports
│       ├── base.py               # AudioBackend ABC
│       ├── alsa.py               # ALSA backend (Linux)
│       ├── portaudio.py          # PortAudio backend (cross-platform)
│       ├── coreaudio.py          # CoreAudio stub (macOS)
│       └── wasapi.py             # WASAPI stub (Windows)
├── cli.py                        # Add backend commands
└── ...
```

---

## Files to Modify

1. `apps/stt/src/dictacode_stt/audio/backends/__init__.py` - NEW: Factory
2. `apps/stt/src/dictacode_stt/audio/backends/base.py` - NEW: AudioBackend ABC
3. `apps/stt/src/dictacode_stt/audio/backends/alsa.py` - NEW: ALSA implementation
4. `apps/stt/src/dictacode_stt/audio/backends/portaudio.py` - NEW: PortAudio implementation
5. `apps/stt/src/dictacode_stt/audio/backends/coreaudio.py` - NEW: CoreAudio stub
6. `apps/stt/src/dictacode_stt/audio/backends/wasapi.py` - NEW: WASAPI stub
7. `apps/stt/src/dictacode_stt/audio/platform.py` - NEW: Platform detection
8. `apps/stt/src/dictacode_stt/audio/manager.py` - Use AudioBackend
9. `apps/stt/src/dictacode_stt/cli.py` - Add backends, platform commands
10. `apps/stt/src/dictacode_stt/main.py` - Add --audio-backend flag
11. `ops/packaging/etc/dictacode/audio/audio.conf` - Add backend config

---

## Success Criteria

v0.2.10 is complete when:

1. ✅ `AudioBackend` ABC defined with platform-agnostic interface
2. ✅ `AlsaBackend` wraps current ALSA/sounddevice code
3. ✅ `PortAudioBackend` provides cross-platform fallback
4. ✅ `CoreAudioBackend` stub ready for macOS implementation
5. ✅ `WasapiBackend` stub ready for Windows implementation
6. ✅ `get_audio_backend()` factory with auto-detection
7. ✅ Platform detection identifies Linux/macOS/Windows/RPi
8. ✅ `AudioPortManager` uses backend abstraction
9. ✅ `--audio-backend` CLI flag works
10. ✅ `dictacode-stt-audio backends` lists available backends
11. ✅ Existing Linux/ALSA functionality unchanged
12. ✅ Unit tests for backend interface
13. ✅ Integration tests with ALSA backend

---

## Out of Scope (v0.2.10)

- Full CoreAudio implementation (macOS)
- Full WASAPI implementation (Windows)
- Android/AAudio implementation
- iOS/AVFoundation implementation
- Bluetooth audio handling
- Virtual audio devices
- Multi-backend simultaneous use
