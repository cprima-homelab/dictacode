"""IPC server and client for diagnostics and state (v0.3.7, v0.3.8, v0.3.5).

Provides Unix Domain Socket server in the STT process for CLI/API access to
the running service's diagnostics and state.

v0.3.8: JSON-RPC-like protocol with length-prefixed messages.
v0.3.5: Added state.get and state.history methods.

Protocol:
    - 4-byte length header (network byte order) + JSON payload
    - Request: {"jsonrpc": "2.0", "method": "diag.run", "params": {...}, "id": 1}
    - Response: {"jsonrpc": "2.0", "result": {...}, "id": 1, "api_version": "0.3.8"}
    - Error: {"jsonrpc": "2.0", "error": {"code": -32600, "message": "..."}, "id": 1}

Environment:
    DICTACODE_IPC_SOCKET: Path to IPC socket (default: /run/dictacode/ipc.sock)
    DICTACODE_DIAG_SOCKET: Legacy alias for DICTACODE_IPC_SOCKET
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import socket
import struct
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable


if TYPE_CHECKING:
    from .service import DiagnosticsService


logger = logging.getLogger(__name__)

# Protocol version
API_VERSION = "0.3.8"

# Default socket path (systemd-friendly runtime dir)
DEFAULT_SOCKET_PATH = "/run/dictacode/diag.sock"

# JSON-RPC 2.0 error codes
ERROR_PARSE = -32700  # Parse error
ERROR_INVALID_REQUEST = -32600  # Invalid Request
ERROR_METHOD_NOT_FOUND = -32601  # Method not found
ERROR_INVALID_PARAMS = -32602  # Invalid params
ERROR_INTERNAL = -32603  # Internal error


def get_socket_path() -> str:
    """Get the IPC socket path from env or default.

    Checks DICTACODE_IPC_SOCKET first, then legacy DICTACODE_DIAG_SOCKET.

    Returns:
        Socket path string
    """
    return os.environ.get(
        "DICTACODE_IPC_SOCKET",
        os.environ.get("DICTACODE_DIAG_SOCKET", DEFAULT_SOCKET_PATH),
    )


def _encode_message(data: dict[str, Any]) -> bytes:
    """Encode message with 4-byte length prefix (v0.3.8).

    Args:
        data: JSON-serializable dict

    Returns:
        Length-prefixed bytes
    """
    payload = json.dumps(data).encode("utf-8")
    length = struct.pack("!I", len(payload))  # Network byte order
    return length + payload


def _decode_message(data: bytes) -> dict[str, Any]:
    """Decode length-prefixed message (v0.3.8).

    Args:
        data: Raw bytes (may include length prefix)

    Returns:
        Decoded dict

    Note:
        For backward compatibility, also accepts plain JSON without prefix.
    """
    if len(data) < 4:
        # Try plain JSON (backward compat with v0.3.7)
        return json.loads(data.decode("utf-8"))

    # Check if first 4 bytes look like a length prefix
    length = struct.unpack("!I", data[:4])[0]
    if length == len(data) - 4 and length < 10_000_000:  # Sanity check
        # Has valid length prefix
        return json.loads(data[4:].decode("utf-8"))

    # Fallback: plain JSON
    return json.loads(data.decode("utf-8"))


def _make_response(
    result: Any, request_id: int | None = None
) -> dict[str, Any]:
    """Create a JSON-RPC-like success response (v0.3.8).

    Args:
        result: Result data
        request_id: Request ID to echo back

    Returns:
        Response dict
    """
    return {
        "jsonrpc": "2.0",
        "result": result,
        "id": request_id,
        "api_version": API_VERSION,
    }


def _make_error(
    code: int, message: str, request_id: int | None = None
) -> dict[str, Any]:
    """Create a JSON-RPC-like error response (v0.3.8).

    Args:
        code: Error code
        message: Error message
        request_id: Request ID to echo back

    Returns:
        Error response dict
    """
    return {
        "jsonrpc": "2.0",
        "error": {"code": code, "message": message},
        "id": request_id,
        "api_version": API_VERSION,
    }


class DiagnosticsIpcServer:
    """IPC server for diagnostics and state (v0.3.7, v0.3.8, v0.3.5).

    Runs a Unix Domain Socket server that accepts JSON-RPC-like requests
    and returns diagnostics and state results from the running service.

    Supported methods:
        - diag.list: List available checks
        - diag.run: Run all diagnostics
        - diag.status: Get quick status
        - diag.categories: List categories
        - diag.history: Get run history
        - state.get: Get current service state (v0.3.5)
        - state.history: Get state transition history (v0.3.5)

    Legacy actions (v0.3.7 compat):
        - list, run, status, categories, history
    """

    def __init__(
        self,
        service: DiagnosticsService,
        socket_path: str | None = None,
        state_provider: Callable[[], dict] | None = None,
        history_provider: Callable[[], list] | None = None,
    ):
        """Initialize IPC server.

        Args:
            service: DiagnosticsService instance to serve
            socket_path: Path to socket (default: from env or DEFAULT_SOCKET_PATH)
            state_provider: Callable returning current state dict (v0.3.5)
            history_provider: Callable returning state history list (v0.3.5)
        """
        self.service = service
        self.socket_path = socket_path or get_socket_path()
        self._get_state = state_provider
        self._get_history = history_provider
        self._server_socket: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> bool:
        """Start the IPC server in a background thread.

        Returns:
            True if started successfully, False otherwise
        """
        if self._running:
            logger.warning("IPC server already running")
            return True

        try:
            # Ensure socket directory exists
            socket_dir = Path(self.socket_path).parent
            socket_dir.mkdir(parents=True, exist_ok=True)

            # Remove stale socket file
            if Path(self.socket_path).exists():
                Path(self.socket_path).unlink()

            # Create Unix socket
            self._server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_socket.bind(self.socket_path)
            self._server_socket.listen(5)
            self._server_socket.settimeout(1.0)  # Allow periodic check for shutdown

            # Set permissions (service user/group only, not world-accessible)
            Path(self.socket_path).chmod(0o660)

            self._running = True
            self._thread = threading.Thread(target=self._serve_forever, daemon=True)
            self._thread.start()

            logger.info(f"IPC server started: {self.socket_path} (v{API_VERSION})")
            return True

        except PermissionError as e:
            logger.warning(
                f"Cannot create IPC socket (permission denied): {e}. "
                f"CLI diagnostics will run standalone."
            )
            return False
        except Exception as e:
            logger.error(f"Failed to start IPC server: {e}")
            return False

    def stop(self) -> None:
        """Stop the IPC server."""
        self._running = False

        if self._server_socket:
            with contextlib.suppress(Exception):
                self._server_socket.close()
            self._server_socket = None

        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

        # Clean up socket file
        try:
            if Path(self.socket_path).exists():
                Path(self.socket_path).unlink()
        except Exception:
            pass

        logger.info("IPC server stopped")

    def _serve_forever(self) -> None:
        """Main server loop (runs in background thread)."""
        while self._running and self._server_socket:
            try:
                client_socket, _ = self._server_socket.accept()
                try:
                    self._handle_client(client_socket)
                finally:
                    client_socket.close()
            except socket.timeout:
                # Check if we should stop
                continue
            except OSError:
                # Socket closed
                break
            except Exception as e:
                if self._running:
                    logger.error(f"IPC server error: {e}")

    def _handle_client(self, client_socket: socket.socket) -> None:
        """Handle a single client connection.

        Args:
            client_socket: Connected client socket
        """
        try:
            # Read request (check for length prefix first)
            header = client_socket.recv(4)
            if not header:
                return

            if len(header) == 4:
                try:
                    length = struct.unpack("!I", header)[0]
                    if length < 10_000_000:  # Sanity check (10MB max)
                        # Length-prefixed message
                        payload = b""
                        while len(payload) < length:
                            chunk = client_socket.recv(min(length - len(payload), 65536))
                            if not chunk:
                                break
                            payload += chunk
                        data = header + payload
                    else:
                        # Probably plain JSON, read more
                        data = header + client_socket.recv(4092)
                except struct.error:
                    # Not a valid length prefix, read as plain JSON
                    data = header + client_socket.recv(4092)
            else:
                data = header

            if not data:
                return

            request = _decode_message(data)
            request.get("id")

            # Dispatch to handler
            response = self._handle_request(request)

            # Send response
            response_bytes = _encode_message(response)
            client_socket.sendall(response_bytes)

        except json.JSONDecodeError as e:
            error_response = _make_error(ERROR_PARSE, f"Parse error: {e}")
            client_socket.sendall(_encode_message(error_response))
        except Exception as e:
            error_response = _make_error(ERROR_INTERNAL, str(e))
            client_socket.sendall(_encode_message(error_response))

    def _handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle a JSON-RPC-like request (v0.3.8).

        Args:
            request: Request dict

        Returns:
            Response dict
        """
        request_id = request.get("id")

        # Get method (v0.3.8) or action (v0.3.7 compat)
        method = request.get("method") or request.get("action", "")
        params = request.get("params", {})

        # Normalize method name (v0.3.7 compat: "run" -> "diag.run")
        if not method.startswith("diag.") and method in (
            "list", "run", "status", "categories", "history"
        ):
            method = f"diag.{method}"

        # Dispatch
        if method == "diag.list":
            category = params.get("category")
            enabled_only = params.get("enabled_only", True)
            checks = self.service.list_checks(
                category=category, enabled_only=enabled_only
            )
            return _make_response({"checks": checks}, request_id)

        elif method == "diag.run":
            result = self.service.run_all()
            return _make_response(
                {
                    "status": result.overall_status.value,
                    "passed": result.passed,
                    "failed": result.failures,
                    "warnings": result.warnings,
                    "checks": [c.to_dict() for c in result.checks],
                    "exit_code": result.exit_code,
                },
                request_id,
            )

        elif method == "diag.status":
            status = self.service.quick_status()
            return _make_response(status, request_id)

        elif method == "diag.categories":
            categories = self.service.list_categories()
            return _make_response({"categories": categories}, request_id)

        elif method == "diag.history":
            history = self.service.get_history()
            return _make_response({"history": history}, request_id)

        # v0.3.5: State methods
        elif method == "state.get":
            if self._get_state is None:
                return _make_error(
                    ERROR_INTERNAL, "State provider not configured", request_id
                )
            state_info = self._get_state()
            return _make_response(state_info, request_id)

        elif method == "state.history":
            if self._get_history is None:
                return _make_error(
                    ERROR_INTERNAL, "History provider not configured", request_id
                )
            history = self._get_history()
            return _make_response({"history": history}, request_id)

        else:
            return _make_error(
                ERROR_METHOD_NOT_FOUND, f"Method not found: {method}", request_id
            )


class DiagnosticsIpcClient:
    """IPC client for diagnostics and state (v0.3.7, v0.3.8, v0.3.5).

    Connects to the running STT service's IPC socket for diagnostics and state.
    """

    def __init__(self, socket_path: str | None = None, timeout: float = 5.0):
        """Initialize IPC client.

        Args:
            socket_path: Path to socket (default: from env or DEFAULT_SOCKET_PATH)
            timeout: Connection timeout in seconds
        """
        self.socket_path = socket_path or get_socket_path()
        self.timeout = timeout

    def is_available(self) -> bool:
        """Check if the IPC server is available.

        Returns:
            True if socket exists and is connectable
        """
        if not Path(self.socket_path).exists():
            return False

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect(self.socket_path)
            sock.close()
            return True
        except Exception:
            return False

    def _call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Make a JSON-RPC-like call (v0.3.8).

        Args:
            method: Method name (e.g., "diag.run")
            params: Method parameters

        Returns:
            Result from response

        Raises:
            ConnectionError: If cannot connect to server
            TimeoutError: If connection times out
            RuntimeError: If server returns an error
        """
        if not Path(self.socket_path).exists():
            raise ConnectionError(f"Socket not found: {self.socket_path}")

        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {},
            "id": 1,
        }

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)

            try:
                sock.connect(self.socket_path)

                # Send length-prefixed request
                request_bytes = _encode_message(request)
                sock.sendall(request_bytes)

                # Receive length-prefixed response
                header = sock.recv(4)
                if len(header) < 4:
                    raise RuntimeError("Invalid response: no length header")

                length = struct.unpack("!I", header)[0]
                if length > 10_000_000:  # 10MB sanity check
                    raise RuntimeError("Response too large")

                payload = b""
                while len(payload) < length:
                    chunk = sock.recv(min(length - len(payload), 65536))
                    if not chunk:
                        break
                    payload += chunk

                response = json.loads(payload.decode("utf-8"))

                # Check for error
                if "error" in response:
                    err = response["error"]
                    raise RuntimeError(f"IPC error {err.get('code')}: {err.get('message')}")

                return response.get("result", response)

            finally:
                sock.close()

        except socket.timeout as e:
            raise TimeoutError(f"Connection timed out after {self.timeout}s") from e
        except ConnectionRefusedError as e:
            raise ConnectionError("Service not running or IPC not enabled") from e
        except FileNotFoundError as e:
            raise ConnectionError(f"Socket not found: {self.socket_path}") from e

    def send_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Send a raw request (v0.3.7 compat).

        Args:
            request: Request dict with 'action' key

        Returns:
            Response dict
        """
        # Convert v0.3.7 format to v0.3.8
        action = request.get("action", "")
        method = f"diag.{action}" if action else ""
        params = {k: v for k, v in request.items() if k not in ("action", "method")}
        return self._call(method, params)

    def list_checks(
        self, category: str | None = None, enabled_only: bool = True
    ) -> dict[str, Any]:
        """List available checks.

        Args:
            category: Filter by category
            enabled_only: Only list enabled checks

        Returns:
            Response with 'checks' list
        """
        return self._call("diag.list", {"category": category, "enabled_only": enabled_only})

    def run_diagnostics(self) -> dict[str, Any]:
        """Run all diagnostics.

        Returns:
            Response with status, checks, exit_code
        """
        return self._call("diag.run")

    def get_status(self) -> dict[str, Any]:
        """Get quick status.

        Returns:
            Response with overall status and counts
        """
        return self._call("diag.status")

    def get_categories(self) -> dict[str, Any]:
        """Get available categories.

        Returns:
            Response with 'categories' list
        """
        return self._call("diag.categories")

    def get_history(self) -> dict[str, Any]:
        """Get run history.

        Returns:
            Response with 'history' list
        """
        return self._call("diag.history")

    # v0.3.5: State methods

    def get_state(self) -> dict[str, Any]:
        """Get current service state (v0.3.5).

        Returns:
            State dict with state, failure_reason, model, language, hid_keymap
        """
        return self._call("state.get")

    def get_state_history(self) -> dict[str, Any]:
        """Get state transition history (v0.3.5).

        Returns:
            Response with 'history' list of transitions
        """
        return self._call("state.history")
