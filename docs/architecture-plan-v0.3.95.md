# dictacode Architecture Plan v0.3.12 — Pipeline Diagnostics Refactor

## Status / ToDo
- [ ] Add PipelineStatus (live pipeline observability).
- [ ] Instrument audio/ASR/transport stages.
- [ ] Component status methods (tolerant, structured).
- [ ] DiagnosticsAggregator to merge component + pipeline status.
- [ ] IPC/API surface for live pipeline status.
- [ ] Metrics tied to pipeline status.
- [ ] CP/CLI updates to display live status.
- [ ] Tests for status/aggregator/IPC/API/CP.

---

## Prerequisites
- Existing diagnostics service (probe-based) and IPC already in place.
- IPC-backed API endpoints for diagnostics/state are available.

---

## Scope
- STT pipeline observability (live view): audio → buffer → ASR/LLM → protocol send.
- Does not change HID-side diagnostics, but transport status is included.

---

## Design
- PipelineStatus: lightweight object holding stage timestamps, counters, flags, recent errors:
  - timestamps: last_audio_ts, last_buffer_ts, last_asr_start_ts, last_asr_success_ts, last_send_ts
  - counters: audio_chunks_total, asr_success_total, asr_error_total, send_success_total, send_error_total
  - flags: mic_present, active_port_valid, link_up, asr_available, llm_enabled, llm_healthy
  - current_profile/state
  - recent_errors: small ring buffer of {stage, message, ts}
  - derived: pipeline_stalled_stage (audio|asr|transport) based on stale timestamps
- Component status methods: add `get_status()`/`diagnostics()` to:
  - audio manager (ports, active, mic_present)
  - transport (type, device/host, connected, last error)
  - transcriber/LLM (type, model, available, last error)
  - state/service (SolutionState, profile)
- DiagnosticsAggregator:
  - Collects component statuses + PipelineStatus into a single snapshot (live view).
  - Probe-based run (ASR/UART/Whisper) can remain separate for point-in-time checks.

---

## Implementation Phases

### Phase 1: PipelineStatus + Instrumentation
1. Add PipelineStatus dataclass.
2. Instrument audio capture, buffer write, ASR call, protocol send to update timestamps/counters/errors; guard for missing components.

### Phase 2: Component Status Methods
1. Add `get_status()` to audio manager, transport, transcriber/LLM, state/service; return tolerant, structured dicts (no exceptions on missing devices).

### Phase 3: Aggregator
1. Implement DiagnosticsAggregator to merge component statuses + PipelineStatus into a snapshot.
2. Keep existing probe runs separate for deep diagnostics if needed.

### Phase 4: IPC/API
1. Add IPC method (e.g., diag.pipeline_status or extend diag.status) returning the aggregated snapshot.
2. Update `/v1/api/diagnostics/status` (and scratch CP page) to use the new snapshot; return 5xx if IPC unavailable (no silent fallback).

### Phase 5: Metrics
1. Tie PipelineStatus updates to metrics: state gauge/transition counter, audio/ASR/send success/error counters, latency histograms, link flags.

### Phase 6: CP/CLI
1. CP diagnostics/scratch shows per-stage timestamps/flags/stalled stage.
2. CLI add `--live` to dump pipeline status via IPC; standalone optional.

### Phase 7: Tests
1. Unit: PipelineStatus updates, component status outputs (with missing devices), aggregator composition.
2. IPC/API round-trip for pipeline status; error when IPC down.
3. CP JS hitting correct endpoints; mock hardware/ASR/transport.

---

## Testing
- Stale detection: fresh audio_ts but stale asr/send → stalled stage reported.
- Flags: mic_present/link_up/asr_available reflect actual state.
- Counters increment correctly per stage; errors recorded.
- API/IPC return structured snapshot; CP/CLI render it.

---

## Open Questions
- Do we keep the legacy probe-based diagnostics run, or map some probes into the live snapshot? (Default: keep probe run for deep checks; use snapshot for live view.)
- Latency thresholds: do we emit warnings/events on latency spikes, or just expose metrics? (Default: expose metrics; no hard alerts yet.)
