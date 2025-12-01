# dictacode Architecture Plan v0.2.8 - Transport Adapter & Multi-HID

## Status

### Phase 1: Transport Adapter Interface
- [ ] Create `transport/` package in both STT and HID apps
- [ ] Define `TransportAdapter` ABC
- [ ] Define `TransportConfig`, `ConnectionStatus` types
- [ ] Extract existing UART logic to `UartTransport` adapter
- [ ] Unit tests for transport types

### Phase 2: USB-Serial Transport (USB TTL Cable)
- [ ] Implement `UsbSerialTransport` adapter for USB TTL cables
- [ ] Support FTDI chips (FT4232H, FT2232H, FT232R)
- [ ] USB device detection by vendor/product ID
- [ ] Auto-detect serial port from USB path
- [ ] Handle hot-plug events
- [ ] Unit tests with mock serial

### Phase 3: WiFi Transport
- [ ] Implement `WifiTransport` adapter (TCP socket)
- [ ] Service discovery via mDNS (Avahi)
- [ ] Connection retry and reconnection logic
- [ ] Unit tests with mock sockets

### Phase 4: Transport Factory & Config
- [ ] Implement `get_transport(name)` factory function
- [ ] Add transport config to `/etc/dictacode/`
- [ ] Add `--transport` CLI flag
- [ ] Integration tests

### Phase 5: Multi-HID Device Registry
- [ ] Define `HidDevice`, `HidDeviceRegistry` classes
- [ ] Implement device config file (`/etc/dictacode/hid/devices.d/`)
- [ ] Support multiple configured devices, one active
- [ ] Device switching via CLI/API

### Phase 6: HID Device Selection
- [ ] Add `--hid-device` flag to STT service
- [ ] Add device selection to transport layer
- [ ] Implement device health checks
- [ ] Failover to backup device (optional)

### Phase 7: Service Discovery
- [ ] Register HID devices via mDNS
- [ ] Auto-discover HID devices on network
- [ ] Update device registry from discovery

**v0.2.8 NOT STARTED**

---

## Prerequisites

v0.2.8 builds on top of:
- ✅ v0.2.1: `UartTransport` class with link supervision
- ✅ v0.2.3: Serial port locking
- ✅ v0.2.6: Adapter pattern established (TranscriptionAdapter)

---

## Problem Statement

### Current Transport Limitation

Communication between Pi5 (STT) and Pi Zero 2W (HID) is hardcoded to UART:

```python
# Current: UART only
class UartTransport:
    def __init__(self, port: str = "/dev/serial0", baudrate: int = 115200):
        ...
```

**Issues:**
- No abstraction for alternative transports
- WiFi would enable wireless HID placement
- Can't easily switch between wired/wireless
- Single HID device assumption
- No support for USB TTL cables (common development setup)

### USB TTL Cable Use Case

USB-to-serial adapters (USB TTL cables) are commonly used for:
- **Development:** Connect Pi5 to Pi Zero via USB cable instead of GPIO wiring
- **Distance:** USB cables can be longer than direct GPIO UART wiring
- **Flexibility:** Hot-pluggable, no GPIO pin conflicts
- **Multi-channel:** FTDI FT4232H provides 4 independent serial ports

Common USB-Serial chips:
| Chip | Channels | USB ID | Notes |
|------|----------|--------|-------|
| FTDI FT232R | 1 | 0403:6001 | Basic USB-serial |
| FTDI FT2232H | 2 | 0403:6010 | Dual channel, high-speed |
| FTDI FT4232H | 4 | 0403:6011 | Quad channel, high-speed |
| CH340 | 1 | 1a86:7523 | Budget option |
| CP2102 | 1 | 10c4:ea60 | Silicon Labs |

**Device paths:** `/dev/ttyUSB0`, `/dev/ttyUSB1`, etc. (Linux)

### Multi-HID Use Case

Users may want multiple HID devices:
- **Primary:** Pi Zero 2W connected to main workstation
- **Secondary:** Another Pi Zero 2W connected to laptop
- **Backup:** Fallback if primary fails

**Goal:** Adapter pattern for transport + multi-device registry.

---

## Design

### Transport Adapter ABC

```python
# transport/adapter.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Callable
from enum import Enum

class ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"

@dataclass
class TransportConfig:
    """Configuration for a transport connection."""
    name: str                      # "uart", "wifi"
    target_device: str             # Device ID or address
    timeout_ms: int = 5000
    retry_count: int = 3
    retry_delay_ms: int = 1000

# Callback types
DataCallback = Callable[[bytes], None]
StatusCallback = Callable[[ConnectionStatus], None]

class TransportAdapter(ABC):
    """Abstract transport layer for STT↔HID communication."""

    @abstractmethod
    def get_name(self) -> str:
        """Return transport name (e.g., 'uart', 'wifi')."""
        pass

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to HID device.

        Returns:
            True if connected successfully
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection."""
        pass

    @abstractmethod
    def send(self, data: bytes) -> bool:
        """
        Send data to HID device.

        Args:
            data: Encoded message bytes

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    def receive(self, timeout_ms: int = 1000) -> Optional[bytes]:
        """
        Receive data from HID device.

        Args:
            timeout_ms: Read timeout

        Returns:
            Received bytes or None on timeout
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Return True if connection is active."""
        pass

    @abstractmethod
    def get_status(self) -> ConnectionStatus:
        """Return current connection status."""
        pass

    def set_status_callback(self, callback: StatusCallback) -> None:
        """Register callback for status changes."""
        self._status_callback = callback

    def supports_discovery(self) -> bool:
        """Return True if transport supports auto-discovery."""
        return False
```

### UartTransport Implementation

```python
# transport/uart.py

class UartTransport(TransportAdapter):
    """UART/Serial transport (existing, refactored)."""

    def __init__(
        self,
        port: str = "/dev/serial0",
        baudrate: int = 115200,
        lock_timeout: float = 5.0,
    ):
        self.port = port
        self.baudrate = baudrate
        self.lock_timeout = lock_timeout
        self._serial: Optional[serial.Serial] = None
        self._lock: Optional[SerialLock] = None
        self._status = ConnectionStatus.DISCONNECTED

    def get_name(self) -> str:
        return "uart"

    def connect(self) -> bool:
        try:
            self._lock = SerialLock(self.port)
            if not self._lock.acquire(timeout=self.lock_timeout):
                self._status = ConnectionStatus.ERROR
                return False

            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0,
            )
            self._status = ConnectionStatus.CONNECTED
            return True

        except Exception as e:
            logger.error(f"UART connect failed: {e}")
            self._status = ConnectionStatus.ERROR
            return False

    def disconnect(self) -> None:
        if self._serial:
            self._serial.close()
            self._serial = None
        if self._lock:
            self._lock.release()
            self._lock = None
        self._status = ConnectionStatus.DISCONNECTED

    def send(self, data: bytes) -> bool:
        if not self._serial:
            return False
        try:
            self._serial.write(data)
            self._serial.flush()
            return True
        except Exception as e:
            logger.error(f"UART send failed: {e}")
            self._status = ConnectionStatus.ERROR
            return False

    def receive(self, timeout_ms: int = 1000) -> Optional[bytes]:
        if not self._serial:
            return None
        try:
            self._serial.timeout = timeout_ms / 1000.0
            data = self._serial.readline()
            return data if data else None
        except Exception:
            return None

    def is_connected(self) -> bool:
        return self._serial is not None and self._serial.is_open

    def get_status(self) -> ConnectionStatus:
        return self._status
```

### UsbSerialTransport Implementation

```python
# transport/usb_serial.py

import serial
import serial.tools.list_ports
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class UsbSerialDevice:
    """Detected USB-serial device."""
    port: str                    # e.g., "/dev/ttyUSB0"
    vendor_id: int               # e.g., 0x0403 (FTDI)
    product_id: int              # e.g., 0x6011 (FT4232H)
    serial_number: Optional[str] # Unique device serial
    description: str             # e.g., "FT4232H"
    manufacturer: Optional[str]  # e.g., "FTDI"

# Known USB-Serial chip identifiers
KNOWN_USB_SERIAL_DEVICES = {
    (0x0403, 0x6001): "FTDI FT232R",
    (0x0403, 0x6010): "FTDI FT2232H",
    (0x0403, 0x6011): "FTDI FT4232H",
    (0x0403, 0x6014): "FTDI FT232H",
    (0x1a86, 0x7523): "CH340",
    (0x10c4, 0xea60): "CP2102",
    (0x067b, 0x2303): "Prolific PL2303",
}

class UsbSerialTransport(TransportAdapter):
    """USB-Serial transport via USB TTL cables (FTDI, CH340, etc.)."""

    def __init__(
        self,
        port: Optional[str] = None,
        vendor_id: Optional[int] = None,
        product_id: Optional[int] = None,
        serial_number: Optional[str] = None,
        channel: int = 0,           # For multi-channel adapters (FT4232H)
        baudrate: int = 115200,
        lock_timeout: float = 5.0,
    ):
        # Device identification (priority: port > serial > vid:pid)
        self._port_override = port
        self._vendor_id = vendor_id
        self._product_id = product_id
        self._serial_number = serial_number
        self._channel = channel

        self.baudrate = baudrate
        self.lock_timeout = lock_timeout

        self._serial: Optional[serial.Serial] = None
        self._lock: Optional[SerialLock] = None
        self._status = ConnectionStatus.DISCONNECTED
        self._detected_port: Optional[str] = None

    def get_name(self) -> str:
        return "usb-serial"

    @classmethod
    def list_devices(cls) -> List[UsbSerialDevice]:
        """Enumerate all USB-serial devices."""
        devices = []
        for port_info in serial.tools.list_ports.comports():
            if port_info.vid is not None:  # USB device
                devices.append(UsbSerialDevice(
                    port=port_info.device,
                    vendor_id=port_info.vid,
                    product_id=port_info.pid,
                    serial_number=port_info.serial_number,
                    description=port_info.description or "",
                    manufacturer=port_info.manufacturer,
                ))
        return devices

    def _find_port(self) -> Optional[str]:
        """Find serial port matching configuration."""
        # Direct port override
        if self._port_override:
            return self._port_override

        devices = self.list_devices()

        # Match by serial number (most specific)
        if self._serial_number:
            for dev in devices:
                if dev.serial_number == self._serial_number:
                    return self._select_channel(dev, devices)

        # Match by vendor:product ID
        if self._vendor_id and self._product_id:
            matching = [
                d for d in devices
                if d.vendor_id == self._vendor_id and d.product_id == self._product_id
            ]
            if matching:
                return self._select_channel(matching[0], matching)

        # Match any known USB-serial device
        for dev in devices:
            if (dev.vendor_id, dev.product_id) in KNOWN_USB_SERIAL_DEVICES:
                return dev.port

        return None

    def _select_channel(
        self,
        device: UsbSerialDevice,
        all_devices: List[UsbSerialDevice],
    ) -> str:
        """Select specific channel for multi-port adapters."""
        if self._channel == 0:
            return device.port

        # Multi-channel adapters create multiple ports with same serial
        # e.g., FT4232H creates /dev/ttyUSB0, /dev/ttyUSB1, /dev/ttyUSB2, /dev/ttyUSB3
        same_adapter = [
            d for d in all_devices
            if d.serial_number == device.serial_number
        ]
        same_adapter.sort(key=lambda d: d.port)

        if self._channel < len(same_adapter):
            return same_adapter[self._channel].port

        return device.port

    def connect(self) -> bool:
        try:
            self._detected_port = self._find_port()
            if not self._detected_port:
                logger.error("No USB-serial device found matching criteria")
                self._status = ConnectionStatus.ERROR
                return False

            self._lock = SerialLock(self._detected_port)
            if not self._lock.acquire(timeout=self.lock_timeout):
                self._status = ConnectionStatus.ERROR
                return False

            self._serial = serial.Serial(
                port=self._detected_port,
                baudrate=self.baudrate,
                timeout=1.0,
            )
            self._status = ConnectionStatus.CONNECTED
            logger.info(f"USB-serial connected: {self._detected_port}")
            return True

        except Exception as e:
            logger.error(f"USB-serial connect failed: {e}")
            self._status = ConnectionStatus.ERROR
            return False

    def disconnect(self) -> None:
        if self._serial:
            self._serial.close()
            self._serial = None
        if self._lock:
            self._lock.release()
            self._lock = None
        self._status = ConnectionStatus.DISCONNECTED
        self._detected_port = None

    def send(self, data: bytes) -> bool:
        if not self._serial:
            return False
        try:
            self._serial.write(data)
            self._serial.flush()
            return True
        except serial.SerialException as e:
            logger.error(f"USB-serial send failed: {e}")
            # Device may have been unplugged
            self._status = ConnectionStatus.ERROR
            return False

    def receive(self, timeout_ms: int = 1000) -> Optional[bytes]:
        if not self._serial:
            return None
        try:
            self._serial.timeout = timeout_ms / 1000.0
            data = self._serial.readline()
            return data if data else None
        except serial.SerialException:
            self._status = ConnectionStatus.ERROR
            return None

    def is_connected(self) -> bool:
        if not self._serial or not self._serial.is_open:
            return False
        # Verify device still present (hot-unplug detection)
        try:
            self._serial.in_waiting  # Triggers exception if unplugged
            return True
        except serial.SerialException:
            self._status = ConnectionStatus.ERROR
            return False

    def get_status(self) -> ConnectionStatus:
        return self._status

    def get_device_info(self) -> Optional[UsbSerialDevice]:
        """Get info about connected USB device."""
        if not self._detected_port:
            return None
        for dev in self.list_devices():
            if dev.port == self._detected_port:
                return dev
        return None
```

### WifiTransport Implementation

```python
# transport/wifi.py

import socket
from typing import Optional

class WifiTransport(TransportAdapter):
    """WiFi/TCP transport for wireless HID connection."""

    DEFAULT_PORT = 9876

    def __init__(
        self,
        host: str,                          # IP or hostname
        port: int = DEFAULT_PORT,
        timeout_ms: int = 5000,
    ):
        self.host = host
        self.port = port
        self.timeout_ms = timeout_ms
        self._socket: Optional[socket.socket] = None
        self._status = ConnectionStatus.DISCONNECTED

    def get_name(self) -> str:
        return "wifi"

    def connect(self) -> bool:
        try:
            self._status = ConnectionStatus.CONNECTING
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout_ms / 1000.0)
            self._socket.connect((self.host, self.port))
            self._status = ConnectionStatus.CONNECTED
            logger.info(f"WiFi connected to {self.host}:{self.port}")
            return True

        except socket.timeout:
            logger.error(f"WiFi connect timeout: {self.host}:{self.port}")
            self._status = ConnectionStatus.ERROR
            return False

        except Exception as e:
            logger.error(f"WiFi connect failed: {e}")
            self._status = ConnectionStatus.ERROR
            return False

    def disconnect(self) -> None:
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        self._status = ConnectionStatus.DISCONNECTED

    def send(self, data: bytes) -> bool:
        if not self._socket:
            return False
        try:
            # Length-prefix for framing
            length = len(data)
            self._socket.sendall(length.to_bytes(4, "big") + data)
            return True
        except Exception as e:
            logger.error(f"WiFi send failed: {e}")
            self._status = ConnectionStatus.ERROR
            return False

    def receive(self, timeout_ms: int = 1000) -> Optional[bytes]:
        if not self._socket:
            return None
        try:
            self._socket.settimeout(timeout_ms / 1000.0)
            # Read length prefix
            length_bytes = self._socket.recv(4)
            if not length_bytes:
                return None
            length = int.from_bytes(length_bytes, "big")
            # Read payload
            data = self._socket.recv(length)
            return data if data else None
        except socket.timeout:
            return None
        except Exception as e:
            logger.error(f"WiFi receive failed: {e}")
            return None

    def is_connected(self) -> bool:
        return self._socket is not None

    def get_status(self) -> ConnectionStatus:
        return self._status

    def supports_discovery(self) -> bool:
        return True  # mDNS discovery supported
```

### Transport Factory

```python
# transport/__init__.py

def get_transport(
    name: str,
    **kwargs,
) -> TransportAdapter:
    """
    Factory function to get transport adapter by name.

    Args:
        name: Transport name ('uart', 'usb-serial', 'wifi')
        **kwargs: Transport-specific configuration

    Returns:
        TransportAdapter instance
    """
    transports: dict[str, type[TransportAdapter]] = {
        "uart": UartTransport,
        "usb-serial": UsbSerialTransport,
        "wifi": WifiTransport,
    }

    if name not in transports:
        raise ValueError(f"Unknown transport: {name}. Available: {list(transports.keys())}")

    return transports[name](**kwargs)


def list_usb_serial_devices() -> List[UsbSerialDevice]:
    """List all detected USB-serial devices."""
    return UsbSerialTransport.list_devices()
```

---

## Multi-HID Device Registry

### HID Device Model

```python
# hid/device.py

from dataclasses import dataclass
from typing import Optional
from enum import Enum

class HidDeviceStatus(Enum):
    UNKNOWN = "unknown"
    ONLINE = "online"
    OFFLINE = "offline"
    ACTIVE = "active"       # Currently selected

@dataclass
class HidDevice:
    """Represents a configured HID device."""
    device_id: str              # Unique identifier (e.g., "pi0-desk")
    name: str                   # Human-readable name
    transport: str              # "uart" or "wifi"
    address: str                # Port path or IP address
    port: Optional[int] = None  # TCP port for WiFi
    priority: int = 100         # Lower = higher priority for failover
    status: HidDeviceStatus = HidDeviceStatus.UNKNOWN

    def get_transport_kwargs(self) -> dict:
        """Return kwargs for transport factory."""
        if self.transport == "uart":
            return {"port": self.address}
        elif self.transport == "wifi":
            return {"host": self.address, "port": self.port or 9876}
        return {}
```

### Device Registry

```python
# hid/registry.py

from typing import List, Optional
from pathlib import Path
import configparser

class HidDeviceRegistry:
    """Registry of configured HID devices."""

    def __init__(self, config_dir: Path = Path("/etc/dictacode/hid/devices.d")):
        self.config_dir = config_dir
        self._devices: dict[str, HidDevice] = {}
        self._active_device_id: Optional[str] = None

    def load_devices(self) -> None:
        """Load device configurations from config directory."""
        self._devices.clear()

        if not self.config_dir.exists():
            return

        for conf_file in self.config_dir.glob("*.conf"):
            device = self._parse_device_config(conf_file)
            if device:
                self._devices[device.device_id] = device

    def _parse_device_config(self, path: Path) -> Optional[HidDevice]:
        """Parse a device configuration file."""
        config = configparser.ConfigParser()
        config.read(path)

        if "device" not in config:
            return None

        return HidDevice(
            device_id=config["device"].get("id", path.stem),
            name=config["device"].get("name", path.stem),
            transport=config["device"].get("transport", "uart"),
            address=config["device"].get("address", "/dev/serial0"),
            port=config["device"].getint("port", 9876),
            priority=config["device"].getint("priority", 100),
        )

    def list_devices(self) -> List[HidDevice]:
        """Return all configured devices."""
        return list(self._devices.values())

    def get_device(self, device_id: str) -> Optional[HidDevice]:
        """Get device by ID."""
        return self._devices.get(device_id)

    def get_active_device(self) -> Optional[HidDevice]:
        """Get currently active device."""
        if self._active_device_id:
            return self._devices.get(self._active_device_id)
        return None

    def set_active_device(self, device_id: str) -> bool:
        """Set the active device."""
        if device_id not in self._devices:
            return False
        self._active_device_id = device_id
        self._devices[device_id].status = HidDeviceStatus.ACTIVE
        return True

    def get_default_device(self) -> Optional[HidDevice]:
        """Get device with highest priority (lowest number)."""
        if not self._devices:
            return None
        return min(self._devices.values(), key=lambda d: d.priority)

    def update_device_status(self, device_id: str, status: HidDeviceStatus) -> None:
        """Update device status after health check."""
        if device_id in self._devices:
            self._devices[device_id].status = status
```

---

## Device Configuration Files

### File Locations

```
/etc/dictacode/hid/
├── devices.d/                    # Device profile directory
│   ├── pi0-desk.conf             # Primary: UART-connected Pi Zero
│   ├── pi0-laptop.conf           # Secondary: WiFi Pi Zero
│   └── pi0-backup.conf           # Backup device
└── hid.conf                      # Main config (active device selection)
```

### Device Profile Format

```ini
# /etc/dictacode/hid/devices.d/pi0-desk.conf
[device]
id = pi0-desk
name = Desk Pi Zero (UART)
transport = uart
address = /dev/serial0
priority = 10

# Optional: device-specific settings
[uart]
baudrate = 115200
```

```ini
# /etc/dictacode/hid/devices.d/pi0-laptop.conf
[device]
id = pi0-laptop
name = Laptop Pi Zero (WiFi)
transport = wifi
address = 192.168.1.50
port = 9876
priority = 20

# Optional: WiFi-specific settings
[wifi]
timeout_ms = 5000
reconnect_delay_ms = 3000
```

```ini
# /etc/dictacode/hid/devices.d/pi0-usb.conf
[device]
id = pi0-usb
name = Dev Pi Zero (USB TTL Cable)
transport = usb-serial
priority = 15

# USB-serial device identification (multiple options)
[usb-serial]
# Option 1: Direct port path (least stable across reboots)
# port = /dev/ttyUSB0

# Option 2: USB vendor:product ID (matches any device of this type)
vendor_id = 0x0403
product_id = 0x6011

# Option 3: Serial number (most stable, unique per adapter)
# serial_number = FT4232H_12345

# For multi-channel adapters (FT4232H has 4 channels: 0-3)
channel = 0

baudrate = 115200
```

```ini
# /etc/dictacode/hid/devices.d/pi0-ftdi-ch2.conf
[device]
id = pi0-ftdi-ch2
name = Second Channel (FT4232H Ch2)
transport = usb-serial
priority = 25

[usb-serial]
serial_number = FT4232H_12345
channel = 1
baudrate = 115200
```

### Main Configuration

```ini
# /etc/dictacode/hid/hid.conf
[hid]
# Active device selection
# device = auto          # Use highest priority online device
# device = pi0-desk      # Specific device
device = auto

# Failover behavior
failover = true           # Switch to backup on failure
failover_delay_ms = 5000  # Wait before failover
```

---

## Service Discovery (mDNS)

### HID Service Registration (on Pi Zero)

```python
# On HID device (Pi Zero)
# Register via Avahi/mDNS

def register_hid_service():
    """Register HID device for discovery."""
    # Service type: _dictacode-hid._tcp
    # Port: 9876
    # TXT records: device_id, transport, version

    # Using python-avahi or zeroconf library
    from zeroconf import Zeroconf, ServiceInfo

    info = ServiceInfo(
        "_dictacode-hid._tcp.local.",
        "pi0-laptop._dictacode-hid._tcp.local.",
        addresses=[socket.inet_aton("192.168.1.50")],
        port=9876,
        properties={
            "device_id": "pi0-laptop",
            "transport": "wifi",
            "version": "0.2.8",
        },
    )

    zeroconf = Zeroconf()
    zeroconf.register_service(info)
```

### HID Discovery (on Pi5)

```python
# On STT device (Pi5)
# Discover HID devices on network

class HidDiscovery:
    """Discover HID devices via mDNS."""

    SERVICE_TYPE = "_dictacode-hid._tcp.local."

    def __init__(self, registry: HidDeviceRegistry):
        self.registry = registry

    def discover(self, timeout: float = 5.0) -> List[HidDevice]:
        """Scan for HID devices on network."""
        from zeroconf import Zeroconf, ServiceBrowser

        discovered = []
        zeroconf = Zeroconf()

        class Listener:
            def add_service(self, zc, type_, name):
                info = zc.get_service_info(type_, name)
                if info:
                    device = HidDevice(
                        device_id=info.properties.get(b"device_id", b"").decode(),
                        name=name.split(".")[0],
                        transport="wifi",
                        address=socket.inet_ntoa(info.addresses[0]),
                        port=info.port,
                    )
                    discovered.append(device)

        browser = ServiceBrowser(zeroconf, self.SERVICE_TYPE, Listener())
        time.sleep(timeout)
        zeroconf.close()

        return discovered
```

---

## CLI Integration

### STT Service

```bash
# Use default/auto device selection
dictacode-stt

# Specify transport type
dictacode-stt --transport uart --port /dev/serial0
dictacode-stt --transport usb-serial --vendor-id 0x0403 --product-id 0x6011
dictacode-stt --transport usb-serial --serial-number FT4232H_12345 --channel 0
dictacode-stt --transport wifi --host 192.168.1.50

# Specify configured HID device
dictacode-stt --hid-device pi0-desk
dictacode-stt --hid-device pi0-usb
dictacode-stt --hid-device pi0-laptop

# List configured HID devices
dictacode-stt-hid list
HID DEVICES
───────────────────────────────────────────────────────
DEVICE_ID     TRANSPORT    ADDRESS              STATUS    PRIORITY
pi0-desk      uart         /dev/serial0         active    10
pi0-usb       usb-serial   0403:6011 ch0        online    15
pi0-laptop    wifi         192.168.1.50         online    20
pi0-backup    wifi         192.168.1.51         offline   30

# List detected USB-serial devices
dictacode-stt-hid usb-list
USB-SERIAL DEVICES
───────────────────────────────────────────────────────
PORT          VID:PID      SERIAL           DESCRIPTION
/dev/ttyUSB0  0403:6011    FT4232H_12345    FTDI FT4232H (Ch A)
/dev/ttyUSB1  0403:6011    FT4232H_12345    FTDI FT4232H (Ch B)
/dev/ttyUSB2  0403:6011    FT4232H_12345    FTDI FT4232H (Ch C)
/dev/ttyUSB3  0403:6011    FT4232H_12345    FTDI FT4232H (Ch D)

# Discover HID devices on network
dictacode-stt-hid discover
Scanning for HID devices...
Found 2 devices:
  pi0-laptop (192.168.1.50:9876) - WiFi
  pi0-backup (192.168.1.51:9876) - WiFi

# Switch active device
dictacode-stt-hid select pi0-usb
Active device: pi0-usb (Dev Pi Zero - USB TTL Cable)
```

---

## File Structure

```
apps/stt/src/dictacode_stt/
├── transport/                    # NEW: Transport adapters
│   ├── __init__.py               # Factory function, exports
│   ├── adapter.py                # TransportAdapter ABC
│   ├── uart.py                   # UartTransport (refactored)
│   ├── usb_serial.py             # UsbSerialTransport (NEW - FTDI, CH340, etc.)
│   ├── wifi.py                   # WifiTransport (NEW)
│   └── discovery.py              # mDNS discovery (NEW)
├── hid/                          # NEW: HID device management
│   ├── __init__.py               # Exports
│   ├── device.py                 # HidDevice dataclass
│   └── registry.py               # HidDeviceRegistry
├── service.py                    # Use TransportAdapter
├── cli.py                        # Add hid commands
└── ...

apps/hid/src/dictacode_hid/
├── transport/                    # NEW: Transport adapters (HID side)
│   ├── __init__.py
│   ├── adapter.py                # Same ABC
│   ├── uart.py                   # UartTransport (server mode)
│   ├── usb_serial.py             # UsbSerialTransport (server mode)
│   └── wifi.py                   # WifiTransport (server mode)
├── discovery.py                  # mDNS registration
└── ...
```

---

## Files to Modify

### STT App
1. `apps/stt/src/dictacode_stt/transport/__init__.py` - NEW: Package, factory
2. `apps/stt/src/dictacode_stt/transport/adapter.py` - NEW: TransportAdapter ABC
3. `apps/stt/src/dictacode_stt/transport/uart.py` - Refactor existing UartTransport
4. `apps/stt/src/dictacode_stt/transport/usb_serial.py` - NEW: UsbSerialTransport (FTDI, etc.)
5. `apps/stt/src/dictacode_stt/transport/wifi.py` - NEW: WifiTransport
6. `apps/stt/src/dictacode_stt/transport/discovery.py` - NEW: mDNS discovery
7. `apps/stt/src/dictacode_stt/hid/__init__.py` - NEW: HID device package
8. `apps/stt/src/dictacode_stt/hid/device.py` - NEW: HidDevice model
9. `apps/stt/src/dictacode_stt/hid/registry.py` - NEW: HidDeviceRegistry
10. `apps/stt/src/dictacode_stt/service.py` - Use TransportAdapter
11. `apps/stt/src/dictacode_stt/cli.py` - Add hid commands, usb-list
12. `apps/stt/src/dictacode_stt/main.py` - Add --transport, --hid-device flags

### HID App
13. `apps/hid/src/dictacode_hid/transport/__init__.py` - NEW: Package
14. `apps/hid/src/dictacode_hid/transport/adapter.py` - NEW: TransportAdapter ABC
15. `apps/hid/src/dictacode_hid/transport/uart.py` - Refactor existing
16. `apps/hid/src/dictacode_hid/transport/usb_serial.py` - NEW: USB-serial server
17. `apps/hid/src/dictacode_hid/transport/wifi.py` - NEW: WiFi server
18. `apps/hid/src/dictacode_hid/discovery.py` - NEW: mDNS registration
19. `apps/hid/src/dictacode_hid/main.py` - Add --transport flag

### Configuration
20. `ops/packaging/etc/dictacode/hid/hid.conf` - Main HID config
21. `ops/packaging/etc/dictacode/hid/devices.d/default.conf` - Default device

---

## Success Criteria

v0.2.8 is complete when:

1. ✅ `TransportAdapter` ABC defined with connect/send/receive
2. ✅ `UartTransport` refactored to implement adapter
3. ✅ `UsbSerialTransport` implements USB TTL cable support
4. ✅ USB-serial auto-detection by vendor:product ID
5. ✅ USB-serial auto-detection by serial number
6. ✅ Multi-channel adapter support (FT4232H channels 0-3)
7. ✅ `WifiTransport` implements TCP socket transport
8. ✅ Factory function `get_transport(name)` works
9. ✅ `HidDevice` and `HidDeviceRegistry` classes defined
10. ✅ Device configs stored in `/etc/dictacode/hid/devices.d/`
11. ✅ Multiple HID devices can be configured
12. ✅ `--hid-device` flag selects active device
13. ✅ `dictacode-stt-hid list` shows configured devices
14. ✅ `dictacode-stt-hid usb-list` shows detected USB-serial devices
15. ✅ mDNS service registration on HID devices
16. ✅ mDNS discovery finds HID devices on network
17. ✅ Existing UART behavior unchanged as default
18. ✅ Unit tests for transports and registry
19. ✅ Integration tests for USB-serial transport
20. ✅ Integration tests for WiFi transport

---

## Out of Scope (v0.2.8)

- Encryption/TLS for WiFi transport (security layer)
- Authentication between STT and HID devices
- Bluetooth transport
- USB gadget over network (USB/IP)
- Load balancing across multiple HID devices
- Real-time device status in web UI (v0.3.0)
