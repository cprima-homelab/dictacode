# dictacode Architecture Plan v0.3.8 — IPC Foundation for Diagnostics/State

## Status / ToDo
- [x] Define a lightweight IPC protocol over local sockets for diagnostics/state.
- [x] Add a server in the main STT service process (UDS on POSIX; pipe placeholder for Windows).
- [x] Add a shared Python client used by API and CLI (no HTTP dependency).
- [x] Make socket path configurable and secure by default.
- [x] Tests for request/response round-trips and error handling.

---

## Prerequisites
- STT service runs as a systemd-managed process separate from API/CLI.
- DiagnosticsService and SttState already exist as authorities.

---

## Scope
- IPC transport for diagnostics (and later state) between the main service and local consumers (API, CLI, tools).
- Platform: POSIX first (UDS); plan a named-pipe variant for Windows/macOS if needed.

---

## Design
- Transport: Unix domain socket (UDS) on POSIX; configurable path via `DICTACODE_IPC_SOCKET` (default under `/run/dictacode/diag.sock` or temp if unavailable). Future: named pipe on Windows/macOS.
- Protocol: Length-prefixed JSON, JSON-RPC 2.0–like (method, params, id). Methods initially: `diag.list`, `diag.run`, `diag.status`, `diag.history`; reserve `state.*` for next steps.
- Security: File perms restrict to service user/group; socket created/owned by the service. No extra auth for local use.
- Versioning: Include `api_version` in responses; reserve error codes for unsupported methods/params.
- Server: Runs inside the main STT service process; dispatches to DiagnosticsService (and later SttState). Single-threaded async handler is sufficient.
- Client: Tiny helper to connect, send one request, read one response; shared by API and CLI. If socket absent/unreachable, raise a clear “service not reachable” error.
- Fallbacks: CLI may offer `--standalone` to run local diagnostics when IPC is unreachable; otherwise, error out.

---

## Implementation Phases

### Phase 1: Server skeleton
1. Add IPC server module (UDS) in the STT process; configurable socket path; create/remove socket safely.
2. Implement request parsing, dispatch table for `diag.list|run|status|history`, and structured error responses.

### Phase 2: Client helper
1. Add a Python client module to issue requests over UDS; expose simple call functions.
2. Wire API and CLI to use the client by default; on failure, return “service not reachable” (CLI may support `--standalone`).

### Phase 3: Config & security
1. Config options: `DICTACODE_IPC_SOCKET`, optional `DICTACODE_DIAG_HISTORY_SIZE` (for service history).
2. Set socket perms (service user/group) and ensure cleanup on exit.

### Phase 4: Testing
1. Unit/integration: start the IPC server in-process; round-trip `diag.list|run|status|history`.
2. Error cases: bad method, bad params, unreachable socket.
3. Platform guards: skip UDS tests on Windows; plan named-pipe follow-up.

---

## Open Questions
- Windows/macOS: implement named-pipe transport now or later?
- Should we allow notifications (fire-and-forget) or keep request/response only? (Default: request/response only for now.)
