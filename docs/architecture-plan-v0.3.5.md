# dictacode Architecture Plan v0.3.5 — Observable STT State

## Status / ToDO

- [x] Single authoritative `SttState` instance managed by STT service.
- [x] API surface for current state (JSON) and live updates (via IPC to the running service).
- [x] CLI command to display current state (via IPC to the running service; standalone only when forced).
- [x] Notifications/metrics on state transitions.
- [x] State history buffer + endpoints.
- [x] Tests for API, CLI, history, and transition side-effects.

---

## Prerequisites
- `SttState` instantiated in `main.py` and owned by the running service process.
- API/CLI run in separate processes; they must query the running service via IPC (no in-process globals).
- IPC transport already exists for diagnostics; state must use the same IPC channel.

---

## Scope
- STT service only (state authority).
- Surfaces: HTTP/WS API, CLI output, metrics/logging.

---

## Design
- Authority: One `SttState` held by the running STT process; service components mutate it.
- API (via IPC):
  - Read-only endpoint `GET /v1/service/state` (or `/api/service/state` until v1 cutover) calling IPC `state.get` to return `{state, failure_reason, model, language, hid_keymap}`.
  - History endpoint `GET /v1/service/state/history` calling IPC `state.history` to return recent transitions from the service-owned ring buffer (configurable size via `DICTACODE_STATE_HISTORY_SIZE`, default 20; entries include timestamp/old_state/new_state/reason/source; optional max-age pruning).
  - WebSocket event `state_change` pushed on transitions; optional `state_history` snapshot on connect (values sourced via IPC).
- CLI:
  - Add `dictacode-stt state` subcommand that queries the running service via IPC `state.get` and prints a concise table; if IPC unreachable, print a clear error (no HTTP fallback); optional `--standalone` for local-only mode.
  - Add `dictacode-stt state --history` to fetch and render the history buffer via IPC `state.history`.
- Notifications:
  - In `SttState.transition_to`, emit to observers (WS broadcaster hook, metrics) after logging and append to history ring buffer (respect max size/age).
  - Metrics: set a gauge or labeled counter per state in `metrics.py`.
- Logging: keep transition log; include reason when entering FAILED/DEGRADED.

---

## Implementation Phases

### Phase 1: State ownership
1. Ensure `main.py` creates a single `SttState` and the running service owns it.
2. Remove any secondary instantiations.

### Phase 2: API surface
1. Add IPC methods `state.get` and `state.history` on the server (same transport as diagnostics).
2. Add `GET /v1/service/state` and `/v1/service/state/history` endpoints using IPC.
3. Add WS broadcast on transitions (`state_change` payload with state/reason) sourced via IPC.

### Phase 3: CLI surface
1. Add `dictacode-stt state` command that calls the running service via IPC and renders state; handle offline with a clear message; optional `--standalone` to run locally.

### Phase 4: History buffer
1. Add in-memory ring buffer with size configurable via `DICTACODE_STATE_HISTORY_SIZE` (default 20); optional max-age pruning (e.g., 24h).
2. Append on every transition (timestamp/old_state/new_state/reason/source).
3. Expose `GET /v1/service/state/history`; add WS `state_history` snapshot on connect if needed.

### Phase 5: Metrics/hooks
1. Add transition hook in `SttState.transition_to` that updates metrics, triggers WS notifier, and writes history buffer.

### Phase 6: Testing
1. Unit: IPC server/client round-trip for `state.get`/`state.history`; history buffer bounds (size, ordering); transition hook called; metrics updated.
2. Integration: WS receives `state_change` after a forced transition; API endpoints show recent transitions (via IPC).
3. CLI: mock IPC to verify state/history output/error handling; standalone guarded by flag.

---

## Testing
- API: returns current state fields; 200 OK; no mutation.
- WS: receives `state_change` on transition.
- Metrics: gauge/counter reflects latest state after transition.
- CLI: prints state when API reachable; shows clear error when not.

---

## Open Questions
- Should CLI ever read a local cache if API is down? (Default: no, just report unreachable.)
- Do we also expose `failure_reason` over WS, or only in API? (Recommend yes, with redaction if needed.)
- Should history prune by age as well as size? (Default: size-bound only; consider 24h max-age if buffer grows.)
