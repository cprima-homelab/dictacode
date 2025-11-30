"""Tests for dictacode_stt.protocol module."""

import pytest

from dictacode_stt import (
    TextMessage,
    CommandMessage,
    JsonProtocol,
    MsgpackProtocol,
    get_protocol,
)


class TestTextMessage:
    """Tests for TextMessage dataclass."""

    def test_create(self):
        msg = TextMessage(payload="hello")
        assert msg.payload == "hello"

    def test_frozen(self):
        msg = TextMessage(payload="hello")
        with pytest.raises(AttributeError):
            msg.payload = "world"

    def test_equality(self):
        msg1 = TextMessage(payload="hello")
        msg2 = TextMessage(payload="hello")
        assert msg1 == msg2


class TestCommandMessage:
    """Tests for CommandMessage dataclass."""

    def test_create_with_arg(self):
        msg = CommandMessage(command="keymap", argument="de_de")
        assert msg.command == "keymap"
        assert msg.argument == "de_de"

    def test_create_without_arg(self):
        msg = CommandMessage(command="pause")
        assert msg.command == "pause"
        assert msg.argument is None

    def test_frozen(self):
        msg = CommandMessage(command="pause")
        with pytest.raises(AttributeError):
            msg.command = "resume"


class TestJsonProtocol:
    """Tests for JsonProtocol."""

    @pytest.fixture
    def protocol(self):
        return JsonProtocol()

    def test_encode_text(self, protocol):
        msg = TextMessage(payload="hello world")
        encoded = protocol.encode(msg)
        assert encoded == b'{"t": "text", "p": "hello world"}\n'

    def test_encode_text_unicode(self, protocol):
        msg = TextMessage(payload="Hello 世界")
        encoded = protocol.encode(msg)
        # ensure_ascii=False keeps unicode as-is
        assert "世界" in encoded.decode("utf-8")

    def test_encode_command_with_arg(self, protocol):
        msg = CommandMessage(command="keymap", argument="de_de")
        encoded = protocol.encode(msg)
        assert b'"t": "cmd"' in encoded
        assert b'"c": "keymap"' in encoded
        assert b'"a": "de_de"' in encoded

    def test_encode_command_without_arg(self, protocol):
        msg = CommandMessage(command="pause")
        encoded = protocol.encode(msg)
        assert b'"t": "cmd"' in encoded
        assert b'"c": "pause"' in encoded
        assert b'"a":' not in encoded

    def test_decode_text(self, protocol):
        data = b'{"t": "text", "p": "hello world"}\n'
        msg = protocol.decode(data)
        assert isinstance(msg, TextMessage)
        assert msg.payload == "hello world"

    def test_decode_text_unicode(self, protocol):
        data = '{"t": "text", "p": "Hello 世界"}\n'.encode("utf-8")
        msg = protocol.decode(data)
        assert isinstance(msg, TextMessage)
        assert msg.payload == "Hello 世界"

    def test_decode_command_with_arg(self, protocol):
        data = b'{"t": "cmd", "c": "keymap", "a": "de_de"}\n'
        msg = protocol.decode(data)
        assert isinstance(msg, CommandMessage)
        assert msg.command == "keymap"
        assert msg.argument == "de_de"

    def test_decode_command_without_arg(self, protocol):
        data = b'{"t": "cmd", "c": "pause"}\n'
        msg = protocol.decode(data)
        assert isinstance(msg, CommandMessage)
        assert msg.command == "pause"
        assert msg.argument is None

    def test_roundtrip_text(self, protocol):
        original = TextMessage(payload="test message")
        encoded = protocol.encode(original)
        decoded = protocol.decode(encoded)
        assert decoded == original

    def test_roundtrip_command(self, protocol):
        original = CommandMessage(command="keymap", argument="en_us")
        encoded = protocol.encode(original)
        decoded = protocol.decode(encoded)
        assert decoded == original

    def test_decode_unknown_type(self, protocol):
        data = b'{"t": "unknown", "p": "data"}\n'
        with pytest.raises(ValueError, match="Unknown message type"):
            protocol.decode(data)


class TestMsgpackProtocol:
    """Tests for MsgpackProtocol."""

    @pytest.fixture
    def protocol(self):
        return MsgpackProtocol()

    def test_encode_has_length_prefix(self, protocol):
        msg = TextMessage(payload="hello")
        encoded = protocol.encode(msg)
        # First 2 bytes are big-endian length
        length = int.from_bytes(encoded[:2], "big")
        assert length == len(encoded) - 2

    def test_encode_text(self, protocol):
        msg = TextMessage(payload="hello world")
        encoded = protocol.encode(msg)
        # Skip 2-byte length prefix for decoding
        decoded = protocol.decode(encoded[2:])
        assert decoded == msg

    def test_encode_text_unicode(self, protocol):
        msg = TextMessage(payload="Hello 世界")
        encoded = protocol.encode(msg)
        decoded = protocol.decode(encoded[2:])
        assert decoded.payload == "Hello 世界"

    def test_encode_command_with_arg(self, protocol):
        msg = CommandMessage(command="keymap", argument="de_de")
        encoded = protocol.encode(msg)
        decoded = protocol.decode(encoded[2:])
        assert decoded == msg

    def test_encode_command_without_arg(self, protocol):
        msg = CommandMessage(command="pause")
        encoded = protocol.encode(msg)
        decoded = protocol.decode(encoded[2:])
        assert decoded == msg

    def test_roundtrip_text(self, protocol):
        original = TextMessage(payload="test message with 日本語")
        encoded = protocol.encode(original)
        decoded = protocol.decode(encoded[2:])
        assert decoded == original

    def test_roundtrip_command(self, protocol):
        original = CommandMessage(command="maintenance")
        encoded = protocol.encode(original)
        decoded = protocol.decode(encoded[2:])
        assert decoded == original


class TestGetProtocol:
    """Tests for get_protocol factory function."""

    def test_get_json(self):
        protocol = get_protocol("json")
        assert isinstance(protocol, JsonProtocol)

    def test_get_msgpack(self):
        protocol = get_protocol("msgpack")
        assert isinstance(protocol, MsgpackProtocol)

    def test_unknown_protocol(self):
        with pytest.raises(ValueError, match="Unknown protocol"):
            get_protocol("protobuf")


class TestProtocolInteroperability:
    """Test that both protocols can encode/decode the same messages."""

    @pytest.fixture
    def json_protocol(self):
        return JsonProtocol()

    @pytest.fixture
    def msgpack_protocol(self):
        return MsgpackProtocol()

    def test_same_text_message(self, json_protocol, msgpack_protocol):
        """Both protocols should produce equivalent decoded messages."""
        msg = TextMessage(payload="Hello 世界 🌍")

        json_encoded = json_protocol.encode(msg)
        msgpack_encoded = msgpack_protocol.encode(msg)

        json_decoded = json_protocol.decode(json_encoded)
        msgpack_decoded = msgpack_protocol.decode(msgpack_encoded[2:])

        assert json_decoded == msgpack_decoded == msg

    def test_same_command_message(self, json_protocol, msgpack_protocol):
        """Both protocols should produce equivalent decoded messages."""
        msg = CommandMessage(command="keymap", argument="de_de")

        json_encoded = json_protocol.encode(msg)
        msgpack_encoded = msgpack_protocol.encode(msg)

        json_decoded = json_protocol.decode(json_encoded)
        msgpack_decoded = msgpack_protocol.decode(msgpack_encoded[2:])

        assert json_decoded == msgpack_decoded == msg
