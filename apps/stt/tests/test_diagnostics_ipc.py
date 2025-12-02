"""Tests for diagnostics IPC (v0.3.7, v0.3.8).

Tests IPC server/client for diagnostics access to running service.

v0.3.8: Tests updated for length-prefixed JSON-RPC protocol.
"""

import json
import os
import socket
import struct
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from dictacode_stt.diagnostics.ipc import (
    API_VERSION,
    DEFAULT_SOCKET_PATH,
    DiagnosticsIpcClient,
    DiagnosticsIpcServer,
    _decode_message,
    _encode_message,
    _make_error,
    _make_response,
    get_socket_path,
)
from dictacode_stt.diagnostics.service import DiagnosticsService


def _recv_response(sock: socket.socket, timeout: float = 5.0) -> dict:
    """Receive and decode a length-prefixed response (v0.3.8).

    Args:
        sock: Connected socket
        timeout: Receive timeout

    Returns:
        Decoded response dict
    """
    sock.settimeout(timeout)

    # Read 4-byte length header
    header = sock.recv(4)
    if len(header) < 4:
        # Fallback: try plain JSON (v0.3.7 compat)
        data = header + sock.recv(4096)
        return json.loads(data.decode())

    length = struct.unpack("!I", header)[0]
    if length > 10_000_000:
        raise ValueError(f"Response too large: {length}")

    # Read payload
    payload = b""
    while len(payload) < length:
        chunk = sock.recv(min(length - len(payload), 65536))
        if not chunk:
            break
        payload += chunk

    return json.loads(payload.decode())


class TestGetSocketPath:
    """Tests for socket path resolution (v0.3.8)."""

    def test_default_path(self):
        """Returns default path when env not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear both env vars if they exist
            os.environ.pop("DICTACODE_IPC_SOCKET", None)
            os.environ.pop("DICTACODE_DIAG_SOCKET", None)
            assert get_socket_path() == DEFAULT_SOCKET_PATH

    def test_custom_path_from_ipc_socket_env(self):
        """Returns custom path from DICTACODE_IPC_SOCKET (v0.3.8)."""
        with patch.dict(os.environ, {"DICTACODE_IPC_SOCKET": "/tmp/ipc.sock"}):
            assert get_socket_path() == "/tmp/ipc.sock"

    def test_custom_path_from_legacy_env(self):
        """Returns custom path from legacy DICTACODE_DIAG_SOCKET."""
        with patch.dict(os.environ, {"DICTACODE_DIAG_SOCKET": "/tmp/custom.sock"}, clear=True):
            os.environ.pop("DICTACODE_IPC_SOCKET", None)
            assert get_socket_path() == "/tmp/custom.sock"

    def test_ipc_socket_takes_precedence(self):
        """DICTACODE_IPC_SOCKET takes precedence over legacy DICTACODE_DIAG_SOCKET."""
        with patch.dict(os.environ, {
            "DICTACODE_IPC_SOCKET": "/tmp/ipc.sock",
            "DICTACODE_DIAG_SOCKET": "/tmp/legacy.sock",
        }):
            assert get_socket_path() == "/tmp/ipc.sock"


class TestDiagnosticsIpcServer:
    """Tests for DiagnosticsIpcServer."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock DiagnosticsService."""
        service = MagicMock(spec=DiagnosticsService)

        # Mock list_checks
        service.list_checks.return_value = [
            {"check_id": "audio_device", "name": "Audio Device", "enabled": True}
        ]

        # Mock run_all
        mock_result = MagicMock()
        mock_result.overall_status.value = "passed"
        mock_result.passed = 3
        mock_result.failures = 0
        mock_result.warnings = 0
        mock_result.exit_code = 0
        mock_result.checks = []
        service.run_all.return_value = mock_result

        # Mock quick_status
        service.quick_status.return_value = {
            "overall": "passed",
            "passed": 3,
            "failed": 0,
            "warnings": 0,
            "total": 3,
        }

        # Mock list_categories
        service.list_categories.return_value = [
            {"id": "system", "name": "System"},
            {"id": "audio", "name": "Audio"},
        ]

        # Mock get_history
        service.get_history.return_value = []

        return service

    @pytest.fixture
    def temp_socket_path(self, tmp_path):
        """Create a temporary socket path."""
        return str(tmp_path / "test.sock")

    def test_server_starts_and_stops(self, mock_service, temp_socket_path):
        """Server starts and stops cleanly."""
        server = DiagnosticsIpcServer(mock_service, socket_path=temp_socket_path)

        assert server.start() is True
        assert Path(temp_socket_path).exists()

        server.stop()
        assert not Path(temp_socket_path).exists()

    def test_server_handles_list_action(self, mock_service, temp_socket_path):
        """Server handles 'list' action (v0.3.7 compat)."""
        server = DiagnosticsIpcServer(mock_service, socket_path=temp_socket_path)
        server.start()

        try:
            # Connect and send request (plain JSON for backward compat)
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(temp_socket_path)
            sock.sendall(json.dumps({"action": "list"}).encode())

            # Receive length-prefixed response (v0.3.8)
            response = _recv_response(sock)
            sock.close()

            # v0.3.8: response is JSON-RPC format with "result"
            result = response.get("result", response)
            assert "checks" in result
            assert len(result["checks"]) == 1
            assert result["checks"][0]["check_id"] == "audio_device"
        finally:
            server.stop()

    def test_server_handles_run_action(self, mock_service, temp_socket_path):
        """Server handles 'run' action (v0.3.7 compat)."""
        server = DiagnosticsIpcServer(mock_service, socket_path=temp_socket_path)
        server.start()

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(temp_socket_path)
            sock.sendall(json.dumps({"action": "run"}).encode())

            # Receive length-prefixed response (v0.3.8)
            response = _recv_response(sock)
            sock.close()

            # v0.3.8: response is JSON-RPC format with "result"
            result = response.get("result", response)
            assert result["status"] == "passed"
            assert result["passed"] == 3
            assert result["exit_code"] == 0
        finally:
            server.stop()

    def test_server_handles_status_action(self, mock_service, temp_socket_path):
        """Server handles 'status' action (v0.3.7 compat)."""
        server = DiagnosticsIpcServer(mock_service, socket_path=temp_socket_path)
        server.start()

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(temp_socket_path)
            sock.sendall(json.dumps({"action": "status"}).encode())

            # Receive length-prefixed response (v0.3.8)
            response = _recv_response(sock)
            sock.close()

            # v0.3.8: response is JSON-RPC format with "result"
            result = response.get("result", response)
            assert result["overall"] == "passed"
            assert result["total"] == 3
        finally:
            server.stop()

    def test_server_handles_unknown_action(self, mock_service, temp_socket_path):
        """Server returns error for unknown action (v0.3.8 JSON-RPC error format)."""
        server = DiagnosticsIpcServer(mock_service, socket_path=temp_socket_path)
        server.start()

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(temp_socket_path)
            sock.sendall(json.dumps({"action": "invalid"}).encode())

            # Receive length-prefixed response (v0.3.8)
            response = _recv_response(sock)
            sock.close()

            # v0.3.8: error is JSON-RPC format with "error" containing "code" and "message"
            assert "error" in response
            assert "message" in response["error"]
            assert "invalid" in response["error"]["message"]
        finally:
            server.stop()


class TestDiagnosticsIpcClient:
    """Tests for DiagnosticsIpcClient."""

    @pytest.fixture
    def running_server(self, tmp_path):
        """Start a server with mock service for client tests."""
        socket_path = str(tmp_path / "client_test.sock")

        service = MagicMock(spec=DiagnosticsService)
        service.list_checks.return_value = []

        mock_result = MagicMock()
        mock_result.overall_status.value = "passed"
        mock_result.passed = 1
        mock_result.failures = 0
        mock_result.warnings = 0
        mock_result.exit_code = 0
        mock_result.checks = []
        service.run_all.return_value = mock_result

        service.quick_status.return_value = {"overall": "passed", "passed": 1, "failed": 0, "warnings": 0, "total": 1}
        service.list_categories.return_value = []
        service.get_history.return_value = []

        server = DiagnosticsIpcServer(service, socket_path=socket_path)
        server.start()

        yield socket_path

        server.stop()

    def test_client_is_available_true(self, running_server):
        """Client detects available server."""
        client = DiagnosticsIpcClient(socket_path=running_server)
        assert client.is_available() is True

    def test_client_is_available_false(self, tmp_path):
        """Client detects unavailable server."""
        socket_path = str(tmp_path / "nonexistent.sock")
        client = DiagnosticsIpcClient(socket_path=socket_path)
        assert client.is_available() is False

    def test_client_run_diagnostics(self, running_server):
        """Client can run diagnostics."""
        client = DiagnosticsIpcClient(socket_path=running_server)
        result = client.run_diagnostics()

        assert result["status"] == "passed"
        assert result["exit_code"] == 0

    def test_client_get_status(self, running_server):
        """Client can get status."""
        client = DiagnosticsIpcClient(socket_path=running_server)
        result = client.get_status()

        assert result["overall"] == "passed"

    def test_client_connection_error(self, tmp_path):
        """Client raises ConnectionError when server unavailable."""
        socket_path = str(tmp_path / "unavailable.sock")
        client = DiagnosticsIpcClient(socket_path=socket_path)

        with pytest.raises(ConnectionError):
            client.run_diagnostics()


class TestHistorySizeConfig:
    """Tests for configurable history size (v0.3.7)."""

    def test_default_history_size(self):
        """Default history size is 10."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DICTACODE_DIAG_HISTORY_SIZE", None)
            service = DiagnosticsService()
            assert service._history_max == 10

    def test_custom_history_size_from_env(self):
        """History size can be set via env."""
        with patch.dict(os.environ, {"DICTACODE_DIAG_HISTORY_SIZE": "5"}):
            # Need to reimport to pick up new env value
            from dictacode_stt.diagnostics.service import _get_history_max

            assert _get_history_max() == 5

    def test_invalid_history_size_fallback(self):
        """Invalid history size falls back to default."""
        with patch.dict(os.environ, {"DICTACODE_DIAG_HISTORY_SIZE": "invalid"}):
            from dictacode_stt.diagnostics.service import _get_history_max

            assert _get_history_max() == 10


class TestProtocolV038:
    """Tests for v0.3.8 JSON-RPC-like protocol."""

    def test_encode_message_adds_length_prefix(self):
        """_encode_message adds 4-byte length prefix."""
        data = {"test": "value"}
        encoded = _encode_message(data)

        # First 4 bytes are length in network byte order
        import struct
        length = struct.unpack("!I", encoded[:4])[0]
        payload = encoded[4:]

        assert length == len(payload)
        assert json.loads(payload.decode()) == data

    def test_decode_message_with_prefix(self):
        """_decode_message decodes length-prefixed message."""
        data = {"test": "value"}
        encoded = _encode_message(data)

        decoded = _decode_message(encoded)
        assert decoded == data

    def test_decode_message_plain_json_compat(self):
        """_decode_message handles plain JSON (v0.3.7 compat)."""
        data = {"action": "run"}
        plain_json = json.dumps(data).encode()

        decoded = _decode_message(plain_json)
        assert decoded == data

    def test_make_response_includes_api_version(self):
        """_make_response includes api_version."""
        response = _make_response({"foo": "bar"}, request_id=1)

        assert response["jsonrpc"] == "2.0"
        assert response["result"] == {"foo": "bar"}
        assert response["id"] == 1
        assert response["api_version"] == API_VERSION

    def test_make_error_structure(self):
        """_make_error creates proper error response."""
        from dictacode_stt.diagnostics.ipc import ERROR_METHOD_NOT_FOUND

        response = _make_error(ERROR_METHOD_NOT_FOUND, "Unknown method", request_id=1)

        assert response["jsonrpc"] == "2.0"
        assert response["error"]["code"] == ERROR_METHOD_NOT_FOUND
        assert response["error"]["message"] == "Unknown method"
        assert response["id"] == 1
        assert response["api_version"] == API_VERSION


class TestJsonRpcMethods:
    """Tests for JSON-RPC method names (v0.3.8)."""

    @pytest.fixture
    def mock_service(self):
        """Create a mock DiagnosticsService."""
        service = MagicMock(spec=DiagnosticsService)
        service.list_checks.return_value = []

        mock_result = MagicMock()
        mock_result.overall_status.value = "passed"
        mock_result.passed = 1
        mock_result.failures = 0
        mock_result.warnings = 0
        mock_result.exit_code = 0
        mock_result.checks = []
        service.run_all.return_value = mock_result

        service.quick_status.return_value = {"overall": "passed", "passed": 1, "failed": 0, "warnings": 0, "total": 1}
        service.list_categories.return_value = []
        service.get_history.return_value = []

        return service

    @pytest.fixture
    def server_with_socket(self, mock_service, tmp_path):
        """Start server and return socket path."""
        socket_path = str(tmp_path / "jsonrpc_test.sock")
        server = DiagnosticsIpcServer(mock_service, socket_path=socket_path)
        server.start()
        yield socket_path
        server.stop()

    def test_diag_run_method(self, server_with_socket):
        """Server responds to diag.run method."""
        client = DiagnosticsIpcClient(socket_path=server_with_socket)
        result = client._call("diag.run")

        assert result["status"] == "passed"

    def test_diag_status_method(self, server_with_socket):
        """Server responds to diag.status method."""
        client = DiagnosticsIpcClient(socket_path=server_with_socket)
        result = client._call("diag.status")

        assert result["overall"] == "passed"

    def test_legacy_action_compat(self, server_with_socket):
        """Server accepts legacy 'action' format (v0.3.7 compat)."""
        client = DiagnosticsIpcClient(socket_path=server_with_socket)
        # Use send_request which converts action to method
        result = client.send_request({"action": "status"})

        assert result["overall"] == "passed"

    def test_unknown_method_error(self, server_with_socket):
        """Server returns error for unknown method."""
        client = DiagnosticsIpcClient(socket_path=server_with_socket)

        with pytest.raises(RuntimeError) as excinfo:
            client._call("unknown.method")

        assert "Method not found" in str(excinfo.value)


class TestStateIpc:
    """Tests for state IPC methods (v0.3.5)."""

    @pytest.fixture
    def mock_state(self):
        """Create a mock state dict."""
        return {
            "state": "listening",
            "failure_reason": None,
            "model": "tiny",
            "language": "en",
            "hid_keymap": "en_us",
        }

    @pytest.fixture
    def mock_history(self):
        """Create mock state history."""
        return [
            {
                "timestamp": "2024-01-01T12:00:00",
                "old_state": "unconfigured",
                "new_state": "listening",
                "reason": None,
                "source": "service",
            }
        ]

    @pytest.fixture
    def mock_service_with_state(self, mock_state, mock_history):
        """Create mock DiagnosticsService."""
        service = MagicMock(spec=DiagnosticsService)
        service.list_checks.return_value = []

        mock_result = MagicMock()
        mock_result.overall_status.value = "passed"
        mock_result.passed = 1
        mock_result.failures = 0
        mock_result.warnings = 0
        mock_result.exit_code = 0
        mock_result.checks = []
        service.run_all.return_value = mock_result

        service.quick_status.return_value = {"overall": "passed"}
        service.list_categories.return_value = []
        service.get_history.return_value = []

        return service

    @pytest.fixture
    def server_with_state(self, mock_service_with_state, mock_state, mock_history, tmp_path):
        """Start server with state providers."""
        socket_path = str(tmp_path / "state_test.sock")

        server = DiagnosticsIpcServer(
            mock_service_with_state,
            socket_path=socket_path,
            state_provider=lambda: mock_state,
            history_provider=lambda: mock_history,
        )
        server.start()
        yield socket_path
        server.stop()

    def test_state_get_returns_current_state(self, server_with_state, mock_state):
        """state.get returns current service state."""
        client = DiagnosticsIpcClient(socket_path=server_with_state)
        result = client.get_state()

        assert result["state"] == "listening"
        assert result["model"] == "tiny"
        assert result["language"] == "en"

    def test_state_history_returns_transitions(self, server_with_state, mock_history):
        """state.history returns transition history."""
        client = DiagnosticsIpcClient(socket_path=server_with_state)
        result = client.get_state_history()

        assert "history" in result
        assert len(result["history"]) == 1
        assert result["history"][0]["old_state"] == "unconfigured"
        assert result["history"][0]["new_state"] == "listening"

    def test_state_get_without_provider_returns_error(self, tmp_path):
        """state.get without state_provider returns error."""
        socket_path = str(tmp_path / "no_state.sock")

        service = MagicMock(spec=DiagnosticsService)
        service.list_checks.return_value = []
        mock_result = MagicMock()
        mock_result.overall_status.value = "passed"
        mock_result.passed = 0
        mock_result.failures = 0
        mock_result.warnings = 0
        mock_result.exit_code = 0
        mock_result.checks = []
        service.run_all.return_value = mock_result
        service.quick_status.return_value = {}
        service.list_categories.return_value = []
        service.get_history.return_value = []

        # No state_provider
        server = DiagnosticsIpcServer(service, socket_path=socket_path)
        server.start()

        try:
            client = DiagnosticsIpcClient(socket_path=socket_path)
            with pytest.raises(RuntimeError) as excinfo:
                client.get_state()

            assert "State provider not configured" in str(excinfo.value)
        finally:
            server.stop()

    def test_state_history_without_provider_returns_error(self, tmp_path):
        """state.history without history_provider returns error."""
        socket_path = str(tmp_path / "no_history.sock")

        service = MagicMock(spec=DiagnosticsService)
        service.list_checks.return_value = []
        mock_result = MagicMock()
        mock_result.overall_status.value = "passed"
        mock_result.passed = 0
        mock_result.failures = 0
        mock_result.warnings = 0
        mock_result.exit_code = 0
        mock_result.checks = []
        service.run_all.return_value = mock_result
        service.quick_status.return_value = {}
        service.list_categories.return_value = []
        service.get_history.return_value = []

        # No history_provider
        server = DiagnosticsIpcServer(service, socket_path=socket_path)
        server.start()

        try:
            client = DiagnosticsIpcClient(socket_path=socket_path)
            with pytest.raises(RuntimeError) as excinfo:
                client.get_state_history()

            assert "History provider not configured" in str(excinfo.value)
        finally:
            server.stop()
