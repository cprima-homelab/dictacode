# dictacode Architecture Plan v0.3.6 — Diagnostics Service Refactor

## Status / ToDo
- [x] Central diagnostics service (logic decoupled from API).
- [x] API handlers wrap the shared service (no inline registry logic).
- [x] CLI consumes diagnostics via shared service (no HTTP).
- [ ] Optional local IPC for out-of-process CLI (UDS/pipe).
- [x] Tests for service, API wrappers, and CLI flow.

---

## Prerequisites
- `SttService` can own/inject dependencies (state, diagnostics).
- FastAPI `create_app()` supports dependency injection for diagnostics service.
- Agree on local IPC path env/CLI (`DICTACODE_DIAG_SOCKET`) for multi-process use; default to in-process when shared interpreter is used.

---

## Scope
- STT diagnostics only (existing checks/registry).
- Surfaces: API (HTTP/WS) and CLI, both backed by the same service.

---

## Design
- DiagnosticsService (new/central):
  - Methods: `list_checks(category, enabled_only)`, `run_all(device_index, uart_device, whisper_binary/model)`, `quick_status()`, `list_categories()`, optional `get_snapshot(detail_level)`; optional history ring buffer of recent runs.
  - Lives alongside `SttService` and reuses existing registry/run_all_checks under the hood.
- API (`diagnostics_api.py`):
  - Handlers become thin wrappers that call DiagnosticsService injected via FastAPI dependency.
  - Response models remain; no registry logic in the route layer.
- CLI:
  - New/updated diagnostics command calls DiagnosticsService directly when in-process; if running as separate process, use a small local IPC client (UDS on POSIX, named pipe on Windows) with simple JSON request/response (`action: list|run|status|categories`).
  - No HTTP calls from CLI.
- IPC (optional, portable):
  - POSIX: Unix domain socket; Windows: named pipe. Configurable via `DICTACODE_DIAG_SOCKET`; default off if in-process.
- History (optional):
  - Small in-memory ring buffer of recent runs with timestamp/status/summary; exposed via service snapshot if needed (not via Prometheus).

---

## Implementation Phases

### Phase 1: Service extraction
1. Create DiagnosticsService wrapping existing registry/run logic; expose pure methods.
2. Wire `SttService` to create/hold DiagnosticsService.

### Phase 2: API wiring
1. Inject DiagnosticsService into `diagnostics_api.py` handlers via dependency.
2. Remove inline registry/runner usage from the FastAPI layer.

### Phase 3: CLI wiring
1. Update diagnostics CLI command to call DiagnosticsService directly (in-process) or via IPC client when out-of-process; remove any HTTP coupling.

### Phase 4 (optional): IPC transport
1. Implement minimal local IPC server in the STT process (UDS/pipe) serving diagnostics actions.
2. Add client helper in CLI to talk to the socket/pipe when needed.

### Phase 5: Testing
1. Unit: DiagnosticsService methods (list/run/status/categories), optional history buffer behavior.
2. API: handlers call service and return correct models; error mapping.
3. CLI: mocked service/IPC client to verify outputs and no HTTP usage.

---

## Testing
- Service: deterministic results with mocked checks; category/enabled filtering; failure propagation.
- API: 200s for happy paths; 4xx on bad categories; 5xx on service exceptions.
- CLI: renders summaries; reports “service not reachable” when IPC unavailable (no HTTP fallback).
- IPC (if built): round-trip request/response for list/run/status.

---

## Open Questions
- Do we need diagnostics history surfaced externally, or keep it internal for now?
- Should IPC be enabled by default, or only when CLI detects it runs out-of-process?
