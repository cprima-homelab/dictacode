# dictacode Architecture Plan v0.3.13 — Diagnostics Refactor (Component Visitor + Live Status)

## Status / ToDo
- [x] Replace "check" registry with component-based diagnostics/status.
- [x] Implement a visitor/aggregator that pulls live status from components.
- [ ] Keep a lightweight probe runner for point-in-time snapshots (optional).
- [x] Update IPC/API/CLI/CP to consume the new status structure.
- [ ] Tests for live status, IPC/API round-trips, and CP rendering.

### Completed (v0.3.9-v0.3.13)
- **Phase 1**: Component `status()` methods implemented (SttState, audio, ASR, transport, IPC)
- **Phase 2**: `DiagnosticsAggregator` in `diagnostics/aggregator.py` with flow/staleness detection
- **Phase 3**: IPC `status.live` method + API `GET /v1/api/status/live` (IPC-backed, 503 fallback)
- **Phase 4**: CP `/cp/live` page with pipeline flow visualization, health summary, auto-refresh
- **Phase 5**: Metrics counters wired (audio_chunks, asr_success/error, send_success/error)

### Remaining
- [ ] CLI command `dictacode-stt-status` to print live status via IPC
- [ ] Unit tests for aggregator staleness logic
- [ ] IPC/API round-trip tests
- [ ] LLM postproc status() (when LLM feature enabled)
- [ ] Profile loader status() (when profiles feature implemented)

---

## Goals
- Live observability: “mic dropped”, “audio flowing but stuck before ASR”, “link down”.
- Tolerate hot-plug/vanishing devices without hard failures.
- Simplify adding diagnostics by exposing `status()`/`diagnostics()` on components.
- Provide structured data over IPC/API/CP; probes/tests optional for historical runs.

---

## Design
- Component status contract:
  - Each component implements `status()` returning a dict with:
    - `present`/`healthy` flags
    - timestamps/counters (e.g., `last_audio_ts`, `last_asr_ts`, `last_send_ts`, `audio_chunks_total`, `send_errors_total`)
    - identifiers (device path, port id, backend/model)
    - link/transport status, mic presence, profile name
  - Components: SttState, AudioPortManager/audio capture, Transcriber/ASR, LLM postproc, Transport, IPC server, Config/Profile loader.
- Aggregator:
  - A `DiagnosticsAggregator` visits components and returns a merged status payload (live view).
  - Optionally runs “probes” (simple functions) for deeper checks (paths readable, model present) and includes results separately.
- IPC:
  - Add `status.live` method returning aggregated status.
  - Keep `diag.run/status/history` for probes/snapshots (optional).
- API:
  - Add `GET /v1/api/status/live` returning aggregated status.
  - Adjust diagnostics endpoints if needed to return probe results separately from live status.
- CLI/CP:
  - Display live status (tolerant of missing devices) with clear indicators for stale timestamps or missing resources.
- Hot-plug handling:
  - Missing devices reported as `present: false` with neutral status; no exceptions.
  - Stale flow detection by comparing timestamps across stages (audio vs ASR vs send).
- Metrics:
  - Expose counters/gauges for key flow points (audio read, ASR success, send success/errors) and current state/link.

---

## Implementation Phases

### Phase 1: Status API in Components
1. Add `status()` to key components:
   - SttState: state, failure_reason, history summary, profile name
   - AudioPortManager/audio capture: active port, mic_present, last_audio_ts, audio_chunks_total
   - Transcriber: backend/model, available?, last_asr_ts, asr_success/err counts
   - LLM postproc: enabled?, provider/model, last_postproc_ts, success/err counts
   - Transport: type/device/host, connected?, last_send_ts, send_success/err counts, link_up
   - IPC server: socket path, available flag
   - Config/Profile loader: current profile, validation status

### Phase 2: Aggregator
1. Create `DiagnosticsAggregator` that gathers statuses from components and merges into a single dict.
2. Include simple flow analysis (stale detection: audio fresh but ASR/send stale).

### Phase 3: IPC/API Surface
1. Add `status.live` IPC method returning the aggregated status.
2. Add `GET /v1/api/status/live` returning the aggregated status (IPC-backed).
3. Keep existing diag.* methods for probe-style snapshots (optional).

### Phase 4: UI/CLI
1. CP scratch (or new status page) renders live status with presence/staleness indicators.
2. CLI command `dictacode-stt-status` (or reuse existing) to print live status via IPC.

### Phase 5: Metrics
1. Wire counters/gauges to audio/ASR/send flow and current state/link.
2. Optionally expose live status summary in metrics (state, link, mic_present).

### Phase 6: Tests
1. Unit: component `status()` outputs with/without devices; stale detection logic.
2. IPC/API: `status.live` round-trip; CP/CLI parsing of status.
3. Regression: existing diag.run/status still work or are marked legacy.

---

## Notes
- Backward compatibility can be broken (alpha); deprecate “check” terminology and old registry.
- Prefer “status”/“probe” naming over “check”.
- Handle missing deps (psutil/lm-sensors) gracefully: mark metrics unavailable, not fatal.

---

## Implementation Instructions (Junior Developer)

Follow these steps carefully; test after each phase.

1) Add `status()` to components
- In `apps/stt/src/dictacode_stt/state.py`, add a `status()` method returning a dict: `{state, failure_reason, history_count, current_profile}` and a `history_summary` (list of last N transitions). Expose profile name if available.
- In `audio` (AudioPortManager or a thin wrapper in `service.py`), add a `status()` that reports: `active_port`, `mic_present` (True/False), `last_audio_ts` (timestamp of last audio chunk), `audio_chunks_total` (increment in audio read loop). If no mic/device, set `present=false` and no exception.
- In transcriber (`transcription` adapter), add a `status()` that reports backend/model, `available` flag (if `is_available` exists), `last_asr_ts` (set when ASR returns), `asr_success_total`, `asr_error_total`. Initialize counters in the adapter or wrap calls in service.
- In LLM postproc (`llm` adapter), add `status()` with `enabled`, provider/model, `last_postproc_ts`, `postproc_success_total`, `postproc_error_total`. If LLM disabled, return `enabled=false`.
- In transport (`transport` adapters), add `status()` with `type`, `device/host`, `connected`, `last_send_ts`, `send_success_total`, `send_error_total`, `link_up` if available. For UART, include device path; for WiFi, host/port.
- In IPC server (`diagnostics/ipc.py`), add `status()` on the server instance: `{socket_path, available: running_flag}`.
- In config/profile loader (once implemented), add a simple `status()` with `current_profile`, `profiles_available_count`, `validation_errors` if any.

2) Create a `DiagnosticsAggregator`
- New file (e.g., `diagnostics/aggregator.py`): class `DiagnosticsAggregator` that takes references to the components above (state, audio manager, transcriber, llm, transport, ipc server, optional profile loader).
- Implement `get_status()` that calls each component’s `status()` and merges into one dict, e.g.:
  ```python
  return {
    "state": state.status(),
    "audio": audio.status(),
    "asr": transcriber.status(),
    "llm": llm.status(),
    "transport": transport.status(),
    "ipc": ipc.status(),
    "profile": profile_loader.status() if available,
    "flow": { "staleness": <computed from timestamps> }
  }
  ```
- Flow/staleness: compare timestamps: if `last_audio_ts` is fresh but `last_asr_ts` is stale, mark `asr_stale=true`; similarly for send. Use simple thresholds (e.g., 10s) for now.
- Ensure exceptions are caught; if a component errors, set `{"error": str(e)}` and continue.

3) Wire timestamps/counters
- In the audio capture loop (`service.py` where audio chunks are read), update `last_audio_ts` and increment `audio_chunks_total`.
- After ASR returns, update `last_asr_ts`, increment `asr_success_total`; on ASR failure, increment `asr_error_total`.
- After sending over transport, update `last_send_ts`, increment success/error counters.
- In LLM postproc, set `last_postproc_ts` and counters.

4) IPC: add `status.live`
- In `diagnostics/ipc.py`, extend the handler to support `status.live` returning `aggregator.get_status()`. Pass the aggregator (or a callable) into the IPC server at construction.
- Add client methods `get_live_status()` calling `status.live`.

5) API: add `/v1/api/status/live`
- In `api.py`, add an endpoint `GET /v1/api/status/live` that calls IPC `status.live`; fallback only if same-process service exists; return 503 otherwise. Add to API router (not CP).

6) CLI/CP
- Add a CLI command `dictacode-stt-status` (or reuse `state_main`) to fetch `status.live` via IPC and print JSON/human-readable summary.
- In CP scratch page (or new page), add a panel to fetch `/v1/api/status/live` and render the JSON; show errors if unreachable.

7) Metrics
- In `metrics.py`, add gauges/counters: `audio_chunks_total`, `asr_success_total`, `asr_error_total`, `send_success_total`, `send_error_total`, and current state/link gauges if not already present. Hook them where you updated timestamps.

8) Tests
- Unit: mock components and assert `DiagnosticsAggregator.get_status()` merges data and handles exceptions. Test staleness flags with fake timestamps.
- IPC/API: add tests for `status.live` IPC method and `/v1/api/status/live` endpoint (mock IPC client).
- CLI: mock IPC client to verify output and exit codes.

9) Cleanup
- Mark old “check” registry as legacy (if still present); update docs to reflect the new status model.
- Update `docs/diagrams.md`/plan files if needed to reflect the new live status endpoint.
