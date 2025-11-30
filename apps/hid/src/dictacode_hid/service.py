"""
service.py - Layer 4: HID service with command/text handlers.

Coordinates protocol, state, transport, and keymaps to provide HID bridge functionality.

Usage:
    service = HidService(
        uart_device="/dev/serial0",
        hid_device="/dev/hidg0",
        protocol="json",
    )
    service.start()  # Blocks until stopped
"""

import logging
import time
from typing import Optional

from dictacode_hid.protocol import (
    ProtocolAdapter,
    get_protocol,
    detect_protocol,
    TextMessage,
    CommandMessage,
)
from dictacode_hid.state import DeviceMode, HidState
from dictacode_hid.transport import UartTransport, HidTransport, TransportError
from dictacode_hid.keymaps import Keymap, load_keymap
from dictacode_hid.supervisor import LinkSupervisor

logger = logging.getLogger(__name__)


class HidService:
    """
    HID service - Layer 4: Application logic.

    Responsibilities:
    - Receive protocol messages from UART
    - Handle commands (keymap, pause, resume, maintenance, normal)
    - Handle text messages (type via HID based on state)
    - Manage state and buffering
    """

    def __init__(
        self,
        uart_device: str = "/dev/serial0",
        hid_device: str = "/dev/hidg0",
        baud_rate: int = 115200,
        protocol_name: str = "json",
        initial_mode: DeviceMode = DeviceMode.NORMAL,
        initial_keymap: str = "en_us",
        dry_run: bool = False,
        supervisor_timeout: float = 30.0,
        supervisor_ping_interval: float = 5.0,
        supervisor_enabled: bool = True,
    ):
        """
        Initialize HID service.

        Args:
            uart_device: UART device path
            hid_device: HID gadget device path
            baud_rate: UART baud rate
            protocol_name: Protocol to use (json or msgpack)
            initial_mode: Initial device mode
            initial_keymap: Initial keymap name
            dry_run: If True, don't actually type (for testing)
            supervisor_timeout: Link timeout in seconds (default: 30)
            supervisor_ping_interval: Ping interval in seconds (default: 5)
            supervisor_enabled: Enable supervisor (default: True)
        """
        self.uart_device = uart_device
        self.hid_device = hid_device
        self.baud_rate = baud_rate
        self.protocol_name = protocol_name
        self.dry_run = dry_run
        self.supervisor_enabled = supervisor_enabled

        # Initialize layers
        self.protocol: ProtocolAdapter = get_protocol(protocol_name)
        self.state: HidState = HidState(mode=initial_mode)
        self.uart: Optional[UartTransport] = None
        self.hid: Optional[HidTransport] = None

        # Initialize supervisor (Layer 5)
        self.supervisor: LinkSupervisor = LinkSupervisor(
            timeout=supervisor_timeout,
            ping_interval=supervisor_ping_interval,
        )

        # Load keymap
        self.keymap: Keymap = load_keymap(initial_keymap)
        self.state.set_keymap(initial_keymap)

        logger.info(
            f"HID service initialized: uart={uart_device}, hid={hid_device}, "
            f"protocol={protocol_name}, mode={initial_mode.name}, keymap={initial_keymap}"
        )
        if supervisor_enabled:
            logger.info(
                f"Supervisor enabled: timeout={supervisor_timeout}s, "
                f"ping_interval={supervisor_ping_interval}s"
            )

    def start(self) -> None:
        """
        Start the service (blocking).

        Opens transports and runs main loop until interrupted.
        """
        logger.info("Starting HID service...")

        # Open transports
        self.uart = UartTransport(self.uart_device, self.baud_rate)
        self.uart.open()
        logger.info(f"UART opened: {self.uart_device}")

        if not self.dry_run:
            self.hid = HidTransport(self.hid_device)
            self.hid.open()
            logger.info(f"HID opened: {self.hid_device}")
        else:
            logger.info("DRY RUN mode - HID not opened")

        try:
            self._run_loop()
        finally:
            self.stop()

    def stop(self) -> None:
        """Stop the service and close transports."""
        logger.info("Stopping HID service...")

        if self.uart:
            self.uart.close()
            logger.info("UART closed")

        if self.hid:
            self.hid.close()
            logger.info("HID closed")

    def _run_loop(self) -> None:
        """Main receive loop with supervisor health checks."""
        logger.info("Listening for messages... (Ctrl+C to stop)")

        while True:
            try:
                # Supervisor: check health and handle reconnection
                if self.supervisor_enabled:
                    if not self.supervisor.check_health():
                        logger.warning("Link unhealthy, attempting reconnection...")
                        if not self._reconnect():
                            # Reconnection failed, wait and retry
                            delay = self.supervisor.reconnect_delay()
                            logger.info(f"Waiting {delay:.1f}s before retry...")
                            time.sleep(delay)
                            continue

                    # Supervisor: notify systemd watchdog
                    self.supervisor.notify_watchdog()

                # Read message based on protocol
                if self.protocol_name == "json":
                    raw_data = self.uart.readline()
                    if not raw_data:
                        continue
                else:  # msgpack
                    # Read 2-byte length prefix
                    length_bytes = self.uart.read(2)
                    if len(length_bytes) < 2:
                        continue
                    length = int.from_bytes(length_bytes, "big")

                    # Read payload
                    payload = self.uart.read(length)
                    if len(payload) < length:
                        logger.warning(
                            f"Incomplete message: got {len(payload)}/{length} bytes"
                        )
                        continue
                    raw_data = payload

                # Supervisor: mark activity on successful read
                if self.supervisor_enabled:
                    self.supervisor.mark_activity()

                # Decode message
                try:
                    msg = self.protocol.decode(raw_data)
                except Exception as e:
                    # Try auto-detection on decode failure
                    detected = detect_protocol(
                        raw_data if self.protocol_name == "json" else length_bytes + raw_data
                    )
                    if detected != self.protocol_name:
                        logger.warning(
                            f"Protocol mismatch? detected={detected}, expected={self.protocol_name}"
                        )
                    logger.error(f"Decode error: {e}")
                    continue

                # Handle message
                if isinstance(msg, TextMessage):
                    self._handle_text(msg)
                elif isinstance(msg, CommandMessage):
                    self._handle_command(msg)

            except KeyboardInterrupt:
                logger.info("Interrupted")
                break
            except TransportError as e:
                logger.error(f"Transport error: {e}")
                if self.supervisor_enabled:
                    self.supervisor._mark_unhealthy()
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)

    def _reconnect(self) -> bool:
        """
        Attempt to reconnect UART transport.

        Returns:
            True if reconnection successful, False otherwise
        """
        self.supervisor.on_reconnect_attempt()

        try:
            # Close existing transport
            if self.uart:
                try:
                    self.uart.close()
                except Exception:
                    pass  # Ignore close errors

            # Reopen transport
            self.uart = UartTransport(self.uart_device, self.baud_rate)
            self.uart.open()

            # Success
            self.supervisor.on_reconnect_success()
            logger.info(f"UART reconnected: {self.uart_device}")
            return True

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            return False

    def _handle_command(self, msg: CommandMessage) -> None:
        """Process a command message."""
        cmd = msg.command
        arg = msg.argument

        logger.info(f"Command received: {cmd}" + (f" {arg}" if arg else ""))

        old_mode = self.state.mode

        if cmd == "keymap" and arg:
            try:
                self.keymap = load_keymap(arg)
                self.state.set_keymap(arg)
                logger.info(f"Keymap changed: {arg}")
            except ValueError as e:
                logger.error(f"Invalid keymap: {e}")

        elif cmd == "pause":
            self.state.set_mode(DeviceMode.PAUSED)
            logger.info("Mode: PAUSED")

        elif cmd == "resume":
            self.state.set_mode(DeviceMode.NORMAL)
            logger.info("Mode: NORMAL")

            # Flush buffer if resuming from paused
            if old_mode == DeviceMode.PAUSED:
                self._flush_buffer()

        elif cmd == "maintenance":
            self.state.set_mode(DeviceMode.MAINTENANCE)
            logger.info("Mode: MAINTENANCE")

        elif cmd == "normal":
            self.state.set_mode(DeviceMode.NORMAL)
            logger.info("Mode: NORMAL")

        else:
            logger.warning(f"Unknown command: {cmd}")

    def _handle_text(self, msg: TextMessage) -> None:
        """Process a text message based on current state."""
        text = msg.payload

        if self.state.should_type():
            # Type immediately
            count = self._type_text(text)
            if count > 0:
                logger.info(f"Typed {count} chars: {text}")
            else:
                logger.warning(f"No mappable chars in: {text}")

        elif self.state.should_buffer():
            # Buffer for later (paused mode)
            self.state.add_to_buffer(text)
            logger.info(f"Buffered (paused): {text}")

        else:
            # Maintenance mode - log only
            logger.info(f"Received (maintenance): {text}")

    def _type_text(self, text: str) -> int:
        """
        Type text via HID.

        Args:
            text: Text to type

        Returns:
            Number of characters typed
        """
        count = 0

        for char in text:
            mapping = self.keymap.get(char)
            if mapping:
                if self.dry_run:
                    logger.debug(f"Would type: {char} (code={mapping.scancode}, mod={mapping.modifier})")
                else:
                    try:
                        self.hid.send_key(mapping.scancode, mapping.modifier)
                    except TransportError as e:
                        logger.error(f"HID write failed: {e}")
                        return count
                count += 1
            else:
                logger.debug(f"No mapping for char: {char!r}")

        # Add space after each utterance
        space_mapping = self.keymap.get(" ")
        if space_mapping:
            if self.dry_run:
                logger.debug("Would type: <space>")
            else:
                try:
                    self.hid.send_key(space_mapping.scancode, space_mapping.modifier)
                except TransportError as e:
                    logger.error(f"HID write failed: {e}")

        return count

    def _flush_buffer(self) -> None:
        """Flush buffered text after resume."""
        buffered = self.state.flush_buffer()
        if not buffered:
            return

        logger.info(f"Flushing {len(buffered)} buffered messages")
        for text in buffered:
            count = self._type_text(text)
            if count > 0:
                logger.info(f"Typed (from buffer) {count} chars: {text}")
