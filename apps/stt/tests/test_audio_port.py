"""Tests for audio port abstraction layer."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dictacode_stt.audio.port import (
    AudioPort,
    AudioPortCapabilities,
    PortStatus,
)
from dictacode_stt.audio.device_id import (
    generate_port_id,
    sanitize_port_id,
    _try_device_serial,
    _try_usb_path,
    _fallback_alsa_card,
)
from dictacode_stt.audio.manager import AudioPortManager


class TestDeviceID:
    """Test stable port ID generation."""

    def test_device_serial_rode_mic(self):
        """Test ID generation for RØDE VideoMic NTG (known device)."""
        port_id, port_type = _try_device_serial("RØDE VideoMic NTG: USB Audio (hw:2,0)")
        assert port_id == "rode-videomic-ntg"
        assert port_type == "usb"

    def test_device_serial_blue_yeti(self):
        """Test ID generation for Blue Yeti (known device)."""
        port_id, port_type = _try_device_serial("Yeti Stereo Microphone: USB Audio (hw:1,0)")
        assert port_id == "blue-yeti"
        assert port_type == "usb"

    def test_device_serial_generic_usb(self):
        """Test ID generation for generic USB device."""
        port_id, port_type = _try_device_serial("USB PnP Sound Device: USB Audio (hw:3,0)")
        # Should create a cleaned-up version of the name
        assert port_id is not None
        assert "usb-pnp-sound-device" in port_id
        assert port_type == "usb"

    def test_device_serial_no_match(self):
        """Test ID generation when no serial/name match found."""
        port_id, port_type = _try_device_serial("bcm2835 Headphones (hw:0,0)")
        # Not a USB device, should return None
        assert port_id is None
        assert port_type is None

    def test_fallback_alsa_card(self):
        """Test ALSA card fallback for built-in audio."""
        port_id, port_type = _fallback_alsa_card("bcm2835 Headphones (hw:0,0)", 0)
        assert port_id == "hw:0"
        assert port_type == "jack"

    def test_fallback_alsa_card_usb(self):
        """Test ALSA card fallback for USB device."""
        port_id, port_type = _fallback_alsa_card("USB Audio (hw:2,0)", 2)
        assert port_id == "hw:2"
        assert port_type == "usb"

    def test_generate_port_id_full_chain(self):
        """Test full port ID generation chain."""
        device_info = {
            "name": "RØDE VideoMic NTG: USB Audio (hw:2,0)",
            "index": 2,
        }
        port_id, port_type = generate_port_id(device_info)
        assert port_id == "rode-videomic-ntg"
        assert port_type == "usb"

    def test_generate_port_id_fallback(self):
        """Test port ID fallback to ALSA card."""
        device_info = {
            "name": "bcm2835 Headphones (hw:0,0)",
            "index": 0,
        }
        port_id, port_type = generate_port_id(device_info)
        assert port_id == "hw:0"
        assert port_type == "jack"

    def test_sanitize_port_id(self):
        """Test port ID sanitization."""
        assert sanitize_port_id("usb:1-1.3") == "usb:1-1.3"
        assert sanitize_port_id("RØDE VideoMic") == "rode-videomic"
        assert sanitize_port_id("hw:0,0") == "hw:0-0"
        assert sanitize_port_id("USB/Audio-Device") == "usb-audio-device"


class TestAudioPortCapabilities:
    """Test audio port capabilities."""

    @patch("sounddevice.check_input_settings")
    def test_from_device_info(self, mock_check):
        """Test creating capabilities from device info."""
        mock_check.return_value = None  # No exception means supported

        device_info = {
            "index": 0,
            "name": "Test Device",
            "default_samplerate": 48000.0,
            "max_input_channels": 2,
        }

        caps = AudioPortCapabilities.from_device_info(device_info)

        assert caps.native_rate == 48000
        assert caps.channels == 2
        assert 48000 in caps.sample_rates
        assert "int16" in caps.formats
        assert "float32" in caps.formats

    @patch("sounddevice.check_input_settings")
    def test_from_device_info_limited_rates(self, mock_check):
        """Test device with limited sample rate support."""

        def check_side_effect(device, channels, samplerate):
            if samplerate not in [48000]:
                raise Exception("Unsupported rate")

        mock_check.side_effect = check_side_effect

        device_info = {
            "index": 0,
            "name": "Limited Device",
            "default_samplerate": 48000.0,
            "max_input_channels": 1,
        }

        caps = AudioPortCapabilities.from_device_info(device_info)

        assert caps.native_rate == 48000
        assert 48000 in caps.sample_rates
        # Should only have 48000 if other rates are unsupported
        assert len(caps.sample_rates) >= 1


class TestAudioPort:
    """Test AudioPort functionality."""

    def create_test_port(self) -> AudioPort:
        """Create a test audio port."""
        caps = AudioPortCapabilities(
            sample_rates=[16000, 48000],
            channels=2,
            formats=["int16"],
            native_rate=48000,
        )

        return AudioPort(
            port_id="test-port",
            port_type="usb",
            name="Test Audio Device",
            capabilities=caps,
            status=PortStatus.AVAILABLE,
            device_index=0,
        )

    def test_port_open_close(self):
        """Test opening and closing a port."""
        port = self.create_test_port()

        assert port.status == PortStatus.AVAILABLE

        port.open()
        assert port.status == PortStatus.IN_USE

        port.close()
        assert port.status == PortStatus.AVAILABLE

    def test_port_configure_valid(self):
        """Test configuring port with valid parameters."""
        port = self.create_test_port()

        # Should not raise
        port.configure(sample_rate=48000, channels=2)

    def test_port_configure_invalid_rate(self):
        """Test configuring port with unsupported sample rate."""
        port = self.create_test_port()

        with pytest.raises(ValueError, match="Sample rate.*not supported"):
            port.configure(sample_rate=96000, channels=1)

    def test_port_configure_invalid_channels(self):
        """Test configuring port with too many channels."""
        port = self.create_test_port()

        with pytest.raises(ValueError, match="Requested.*channels"):
            port.configure(sample_rate=48000, channels=4)

    def test_port_is_healthy(self):
        """Test port health check."""
        port = self.create_test_port()

        port.status = PortStatus.AVAILABLE
        assert port.is_healthy() is True

        port.status = PortStatus.IN_USE
        assert port.is_healthy() is True

        port.status = PortStatus.ERROR
        assert port.is_healthy() is False

        port.status = PortStatus.DISCONNECTED
        assert port.is_healthy() is False


class TestAudioPortManager:
    """Test AudioPortManager functionality."""

    @patch("sounddevice.query_devices")
    def test_list_ports(self, mock_query):
        """Test port enumeration."""
        mock_query.return_value = [
            {
                "index": 0,
                "name": "bcm2835 Headphones (hw:0,0)",
                "max_input_channels": 2,
                "default_samplerate": 44100.0,
            },
            {
                "index": 1,
                "name": "RØDE VideoMic NTG: USB Audio (hw:1,0)",
                "max_input_channels": 2,
                "default_samplerate": 48000.0,
            },
            {
                "index": 2,
                "name": "HDMI Output (hw:2,0)",
                "max_input_channels": 0,  # Output only
                "default_samplerate": 48000.0,
            },
        ]

        manager = AudioPortManager()
        ports = manager.list_ports()

        # Should find 2 input ports (skip output-only device)
        assert len(ports) == 2

        # Check port IDs
        port_ids = [p.port_id for p in ports]
        assert "hw:0" in port_ids
        assert "rode-videomic-ntg" in port_ids

        # Verify sorting by port_id
        assert ports[0].port_id < ports[1].port_id

    @patch("sounddevice.query_devices")
    def test_list_ports_caching(self, mock_query):
        """Test that ports are cached."""
        mock_query.return_value = [
            {
                "index": 0,
                "name": "Test Device (hw:0,0)",
                "max_input_channels": 1,
                "default_samplerate": 48000.0,
            },
        ]

        manager = AudioPortManager()

        # First call - should query devices
        ports1 = manager.list_ports()
        assert mock_query.call_count == 1

        # Second call - should use cache
        ports2 = manager.list_ports()
        assert mock_query.call_count == 1  # Not called again

        assert ports1 == ports2

        # Force refresh
        ports3 = manager.list_ports(force_refresh=True)
        assert mock_query.call_count == 2  # Called again

    @patch("sounddevice.query_devices")
    def test_get_port(self, mock_query):
        """Test getting specific port by ID."""
        mock_query.return_value = [
            {
                "index": 0,
                "name": "RØDE VideoMic NTG: USB Audio (hw:0,0)",
                "max_input_channels": 2,
                "default_samplerate": 48000.0,
            },
        ]

        manager = AudioPortManager()

        port = manager.get_port("rode-videomic-ntg")
        assert port is not None
        assert port.port_id == "rode-videomic-ntg"

        # Non-existent port
        port = manager.get_port("nonexistent-port")
        assert port is None

    @patch("sounddevice.query_devices")
    def test_get_default_port(self, mock_query_all):
        """Test getting default input port."""
        mock_query_all.return_value = [
            {
                "index": 0,
                "name": "Device 1 (hw:0,0)",
                "max_input_channels": 2,
                "default_samplerate": 48000.0,
            },
            {
                "index": 1,
                "name": "Device 2 (hw:1,0)",
                "max_input_channels": 2,
                "default_samplerate": 48000.0,
            },
        ]

        with patch("sounddevice.query_devices") as mock_query_default:
            # Mock default device query
            mock_query_default.return_value = {"index": 1}

            manager = AudioPortManager()
            default_port = manager.get_default_port()

            assert default_port is not None
            assert default_port.device_index == 1

    @patch("sounddevice.query_devices")
    def test_get_active_port(self, mock_query):
        """Test getting active streaming port."""
        mock_query.return_value = [
            {
                "index": 0,
                "name": "Test Device (hw:0,0)",
                "max_input_channels": 2,
                "default_samplerate": 48000.0,
            },
        ]

        manager = AudioPortManager()
        ports = manager.list_ports()

        # No active port initially
        assert manager.get_active_port() is None

        # Mock a port as streaming
        ports[0]._stream = MagicMock()
        ports[0]._stream.active = True

        active_port = manager.get_active_port()
        assert active_port is not None
        assert active_port.port_id == ports[0].port_id
