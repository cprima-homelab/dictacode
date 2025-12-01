"""
transport.py - Backward compatibility wrapper (v0.2.8 Phase 1)

This module provides backward compatibility for code importing from the old
transport.py location. All transport classes have been moved to the transport
package with the adapter pattern.

Old import (still works):
    from dictacode_hid.transport import UartTransport, HidTransport, TransportError

New import (recommended):
    from dictacode_hid.transport import UartTransport, UartConfig, HidTransport, HidConfig

Migration Guide:
    Both UartTransport and HidTransport now use config-based constructors
    and implement the TransportAdapter interface with new method names:

    Old UART API:
        uart = UartTransport(device="/dev/serial0", baud_rate=115200)
        uart.open()
        data = uart.read(1024)
        uart.write(b"hello")
        uart.close()

    New UART API (recommended):
        from dictacode_hid.transport import UartTransport, UartConfig
        config = UartConfig(device="/dev/serial0", baud_rate=115200)
        uart = UartTransport(config)
        uart.connect()
        data = uart.receive(1024)
        uart.send(b"hello")
        uart.disconnect()

    Old HID API:
        hid = HidTransport(device="/dev/hidg0")
        hid.open()
        hid.write_report(bytes([0, 0, 4, 0, 0, 0, 0, 0]))
        hid.send_key(4)
        hid.close()

    New HID API (recommended):
        from dictacode_hid.transport import HidTransport, HidConfig
        config = HidConfig(device="/dev/hidg0")
        hid = HidTransport(config)
        hid.connect()
        hid.write_report(bytes([0, 0, 4, 0, 0, 0, 0, 0]))
        hid.send_key(4)
        hid.disconnect()

    Legacy API (still supported):
        Both transports maintain compatibility with the old API through
        legacy methods (open, close, read, write) and property accessors.
"""

# Re-export all transport classes for backward compatibility
from dictacode_hid.transport.adapter import (
    TransportAdapter,
    TransportConfig,
    TransportError,
    ConnectionStatus,
)

from dictacode_hid.transport.uart import (
    UartTransport as _NewUartTransport,
    UartConfig,
)

from dictacode_hid.transport.hid import (
    HidTransport as _NewHidTransport,
    HidConfig,
)

# For backward compatibility: Allow old-style constructors

class _LegacyUartTransport(_NewUartTransport):
    """Backward compatibility wrapper for old UartTransport constructor.

    This allows existing code using:
        uart = UartTransport(device="/dev/serial0", baud_rate=115200)

    To continue working without changes.
    """

    def __init__(
        self,
        device: str = "/dev/serial0",
        baud_rate: int = 115200,
        timeout: float = 1.0,
        lock_dir: str = None,
    ):
        """Legacy constructor - converts args to UartConfig."""
        config = UartConfig(
            device=device,
            baud_rate=baud_rate,
            timeout=timeout,
            lock_dir=lock_dir,
        )
        super().__init__(config)


class _LegacyHidTransport(_NewHidTransport):
    """Backward compatibility wrapper for old HidTransport constructor.

    This allows existing code using:
        hid = HidTransport(device="/dev/hidg0")

    To continue working without changes.
    """

    def __init__(self, device: str = "/dev/hidg0"):
        """Legacy constructor - converts args to HidConfig."""
        config = HidConfig(device=device)
        super().__init__(config)


# Export legacy wrappers for maximum compatibility
UartTransport = _LegacyUartTransport
HidTransport = _LegacyHidTransport

__all__ = [
    "UartTransport",
    "UartConfig",
    "HidTransport",
    "HidConfig",
    "TransportError",
    "TransportAdapter",
    "TransportConfig",
    "ConnectionStatus",
]
