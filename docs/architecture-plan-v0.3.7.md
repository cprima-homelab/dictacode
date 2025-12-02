# dictacode Architecture Plan v0.3.7 — Mandatory Diagnostics Access to Running Service

## Status / ToDo
- [x] Ensure diagnostics for a systemd-started STT instance are queryable from the CLI.
- [x] Provide a mandatory shared access path (IPC or HTTP) from CLI to the running service.
- [x] Bind API diagnostics to the live service instance (no fallback divergence).
- [x] Update CLI to use the shared path by default; no standalone run unless explicitly forced.
- [x] Tests for service binding and CLI query of running service.

---

## Prerequisites
- Running STT service (systemd) must expose diagnostics over a local channel.
- `SttService` should register itself for API/IPC consumption on startup.
- Agreement on transport: IPC preferred; HTTP acceptable only if mandated.

---

## Scope
- STT diagnostics only (list/run/status/history).
- Surfaces: CLI (must reach running service), API (must use live service instance).

---

## Design
- Authority: `SttService` owns `DiagnosticsService` (with history).
- Binding to API: on service startup, call `health.set_service_instance(self)` (or inject via `create_app`) so API diagnostics use the live instance; remove/favor fallback only when the service is absent.
- Transport for CLI → running service (mandatory):
  - Preferred: Local IPC server in the STT process (UDS on POSIX, named pipe on Windows/macOS), JSON request/response for `list`, `run`, `status`, `history`. Configurable path/env (`DICTACODE_DIAG_SOCKET`).
  - CLI uses IPC by default; if IPC unreachable, emit “service not reachable” and exit non-zero. Optional flag `--standalone` to run local checks explicitly (documented).
- HTTP alternative (only if IPC is not chosen): CLI calls diagnostics API endpoints after ensuring API binds to the live service instance. Avoid if IPC is implemented.
- History: keep per-service-instance ring buffer; make size configurable (`DICTACODE_DIAG_HISTORY_SIZE`), default 10.

---

## Implementation Phases

### Phase 1: Bind API to live service
1. In `SttService` startup, register the instance (e.g., `health.set_service_instance(self)`), or inject via FastAPI dependency override.
2. In diagnostics routes, prefer the live service; use fallback only when no service instance exists.

### Phase 2: IPC server (preferred)
1. Add a lightweight IPC server in the STT process (UDS/pipe) exposing diagnostics actions.
2. Add configuration for socket/pipe path (`DICTACODE_DIAG_SOCKET`); default to a runtime dir suitable for systemd.

### Phase 3: CLI client
1. Update diagnostics CLI to use IPC by default; on failure, report unreachable. Add `--standalone` to force local run (rare).
2. Keep output formatting; no HTTP dependency.

### Phase 4: History config
1. Make history size configurable via env/config; default 10.

### Phase 5: Testing
1. Unit: IPC server/client round-trip; history size config applied.
2. Integration: with a running service (systemd-style), CLI retrieves diagnostics via IPC; API diagnostics use the live instance (no default fallback divergence).
3. Error paths: CLI reports unreachable when IPC is down; optional standalone flag runs locally.

---

## Open Questions
- If IPC is unavailable on some platforms, is HTTP fallback acceptable, or must we implement a named pipe variant on Windows/macOS?
- Should standalone CLI mode be allowed at all, or only with an explicit `--standalone` flag?
