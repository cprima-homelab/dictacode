# dictacode Architecture Plan v0.3.10 — Pipeline Profiles (ASR/LLM Modes)

## Status / ToDo
- [ ] Introduce pipeline profiles (preset configurations for ASR + LLM).
- [ ] Load profiles from packaged defaults and drop-in directories.
- [ ] Expose profile selection in API/CP; apply safely at runtime.
- [ ] Persist current profile selection across restarts.
- [ ] Validate profiles per backend/provider; add tests.

---

## Prerequisites
- `SttService` currently constructs transcriber/LLM from fixed defaults/CLI.
- IPC/state APIs are in place; CP and API can surface selections.

---

## Scope
- STT only (pipeline config: ASR backend, model, LLM on/off/provider/model).
- Profiles selectable via Control Panel and API; power users can add drop-ins.

---

## Design
- Profile concept: named presets (e.g., `whisper_local`, `whisper_local_llm`, `vosk_basic`) describing:
  - ASR backend (whisper|vosk), model path/name
  - LLM enabled flag, provider, model, base_url/api_key (optional)
  - Optional transport tweaks if needed
- Storage:
  - Packaged defaults in a known dir (e.g., `/opt/dictacode/profiles/` or repo `profiles/`)
  - Drop-in overrides/additions in `/etc/dictacode/stt.d/profiles/` (power user)
- Loader:
  - Merge defaults + drop-ins; validate schema; expose list of available profiles.
- Service config:
  - Introduce `PipelineConfig` and factory methods for ASR/LLM components.
  - `SttService` consumes `PipelineConfig` instead of scattered defaults.
  - Track current profile name in state; allow runtime apply.
- Apply flow:
  - API/CP endpoint to select a profile.
  - Safe reconfigure: pause (or maintenance), rebuild transcriber/LLM per profile, resume.
  - Persist chosen profile to config/state file so it survives restart.

---

## Implementation Phases

### Phase 1: Config/Profiles
1. Define `PipelineConfig` dataclass with ASR/LLM fields.
2. Add profile loader: packaged defaults + drop-ins, schema validation.

### Phase 2: Service Refactor
1. Refactor `SttService` init to accept `PipelineConfig`; use factories to create ASR/LLM.
2. Expose current profile in state; add method to apply a new profile (with pause/reconfigure/resume).

### Phase 3: Surfaces
1. API/CP: list profiles, get current, apply profile endpoints/UI.
2. State/IPC: include current profile name in state responses.

### Phase 4: Persistence
1. Store current profile selection (config or small state file) and load on startup.

### Phase 5: Testing
1. Unit: loader validation, factory selection per profile, apply flow reconfigures components.
2. Integration: API/CP profile apply changes behavior; state reflects new profile; persists after restart.

---

## Testing
- Profile schema validation; reject invalid/missing required fields per backend/provider.
- Apply flow: transitions to paused/maintenance, rebuilds components, resumes.
- State/API/IPC reflect current profile; persists across restart.
- CP/API selection works; drop-in profiles are discovered.

---

## Open Questions
- Do we allow live profile apply while running, or require a restart/pause? (Default: pause/reconfigure/resume).
- Where to persist current profile: config file vs dedicated state file?
- Should CP/UI expose profile details (ASR/LLM specifics) or only names/descriptions?
