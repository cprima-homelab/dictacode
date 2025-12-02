# Configurability Findings (apps/stt)

Items below are currently hard-coded or only exposed via CLI/env flags. They should be configurable via files under `/etc/dictacode.d/` (e.g., `/etc/dictacode/stt.conf`, `/etc/dictacode/audio`, `/etc/dictacode/hid`) so deployments can be tuned without code changes.

## Transport & Protocol
- UART device path and baud rate (`main.py`: args `--uart`, `--baud`; `service.py`: defaults `/dev/serial0`, `115200`).
- Protocol selection (`DICTACODE_PROTOCOL`, defaults to `json`).
- Transport type (`--transport` / `service.py` default `None`) and HID device selection (`--hid-device`, `hid/registry.py` uses `/etc/dictacode/hid/devices.d/*.conf`).
- Handshake and link timings (`service.py`: `handshake_timeout=10.0`, `link_poll_interval=5.0`).
- Supervisor controls (`main.py`: `--no-supervisor`, `--supervisor-timeout`, `--supervisor-ping-interval`; `service.py`: `prerequisite_poll_interval=30.0`, `link_poll_interval=5.0`, `supervisor_enabled=True`).

## Audio Capture
- Audio config directory (`audio/manager.py`, `api.py`, `api_server.py`: default `/etc/dictacode/audio`).
- Recording duration and chunk/windowing (`main.py`: `--duration`; `service.py`: `recording_duration=5.0`).
- Device/port selection (`--port`, `--device`; `AudioPortManager` enumeration).
- Native/target sample rates and channel count (`service.py`: `native_sample_rate=48000`, `native_channels=2`, `whisper_sample_rate=16000`; `audio_config.py`: defaults).
- Audio source injection for testing (`--audio-source`, `service.py`: `audio_source=None`).

## Transcription / Whisper
- Whisper binary and model paths (`main.py`: `--whisper-binary`, `--whisper-model`; `service.py` fallback to `~/whisper.cpp/build/bin/whisper-cli` and `~/whisper.cpp/models/ggml-tiny.bin`).
- Transcriber selection (`service.py`: `transcriber_name="whisper"`; streaming toggle `--streaming`).
- Language/model selection (`main.py`: `--language`; `stt_config.py`: `model`, `language`).

## LLM Post-Processing
- Enable/disable and provider/model/profile (`main.py`: `--llm`, `--no-llm`, provider/model/profile flags; `stt_config.py`: `llm_*` defaults).
- Fallback behavior and provider endpoints/keys (`stt_config.py`: `llm_fallback`, `llm_base_url`, `llm_api_key`).

## Logging & Metrics
- Log level/format/output file (`main.py`: `--log-level`, `--log-format`, `--log-file`; `logging_config.py`).
- Metrics enable/port for main service (`main.py`: `--metrics`, `--metrics-port`; `stt_config.py`: `metrics_*`).
- API host/port and API metrics settings (`stt_config.py`: `api_host`, `api_port`, `api_metrics_enabled`, `api_metrics_port`; `api_server.py`).
- Log control (SIGUSR1 debug toggle) and journald vs console (`log_control.py`, `logging_config.py`).

## API/Web Panel
- Template/static roots are fixed in source tree (`api.py`); if relocatable, should be configurable.
- WebSocket settings (endpoint `/api/ws` is fixed; reconnection/backoff values are hard-coded in JS).

## HID Registry (STT-side)
- HID device configs path and active device selection (`hid/registry.py`: `/etc/dictacode/hid/devices.d`).

## Compatibility & Diagnostics
- Compatibility matrix search paths (`compatibility.py`: `/opt/dictacode/shared/compatibility.json`, repo root fallback, `/etc/dictacode/compatibility.json`).
- Diagnostics/bugreport config root (`diagnostics/bugreport.py`: `/etc/dictacode`).

## Other Timers & Behaviors
- Supervisor watchdog timeouts and ping intervals (env + CLI, not persisted).
- Handshake/poll intervals (`service.py`: `prerequisite_poll_interval`, `link_poll_interval`).
- Dry-run behavior (`--dry-run`) and `once` vs continuous run (`--once`) currently only via CLI.

## Suggested Config Coverage
- Consolidate service-level tunables (transport, UART, audio durations/rates, language/model, supervisor timings, handshake timeouts) into a managed config file.
- Include LLM settings, metrics/logging, and API bind/metrics config in the same or adjacent config file(s).
- Keep per-component config roots discoverable (audio profiles dir, HID registry dir, compatibility matrix path).

---

# Additional Configurability Findings (apps/hid)

HID-side tunables are mostly CLI/env-driven; they should be configurable via `/etc/dictacode.d/` (e.g., `/etc/dictacode/hid.conf`, `/etc/dictacode/hid/devices.d`, `/etc/dictacode/keymap.conf`).

## Transport & Protocol
- UART device and baud (`main.py`: `--uart`, `--baud`; `service.py` defaults `/dev/serial0`, `115200`).
- HID gadget device path (`main.py`: `--hid`; `service.py` default `/dev/hidg0`).
- Protocol selection (`DICTACODE_PROTOCOL`, default `json`; `protocol.py` for msgpack).
- Supervisor timings (`--supervisor-timeout`, `--supervisor-ping-interval`, `--no-supervisor`; `service.py` uses `LinkSupervisor(timeout=30, ping_interval=5)`).

## Keymaps & Input Behavior
- Initial keymap (`DICTACODE_KEYMAP`, default `en_us`; `main.py` initial_keymap; `keymaps/base.py` config file `/etc/dictacode/keymap.conf`).
- Keymap definitions and overrides (`keymaps/`, but runtime config path fixed to `/etc/dictacode/keymap.conf`).
- Device mode defaults (`DICTACODE_MODE`, CLI `--maintenance`; `DeviceMode` supports NORMAL/MAINTENANCE/PAUSED).

## Diagnostics & Compatibility
- Compatibility matrix search paths (`compatibility.py`: `/opt/dictacode/shared/compatibility.json`, repo fallback, `/etc/dictacode/compatibility.json`).
- Diagnostics hardware checks assume system paths (`/etc/modules`, `/etc/modules-load.d`)—if alternate module load paths are used, they’re not configurable.

## Logging & Metrics
- Logging is basic (`setup_logging` in `main.py`); no config file for log level/format/output.
- No metrics toggles on HID side; if added, should be configurable similarly to STT.

## HID Registry / Device Selection
- HID device registry/configs (`hid/registry.py`): path fixed to `/etc/dictacode/hid/devices.d/*.conf`. Active device selection is not persisted; could be configurable.
- Transport selection for HID devices (uart vs. others) is read from device conf; registry path should be configurable.

## Other Behaviors
- Dry-run and maintenance mode only via CLI/env (`--dry-run`, `--maintenance`).
- Watchdog/systemd notify is automatic; no config to toggle.

## Suggested Config Coverage (HID)
- Centralize UART/HID paths, baud, protocol, supervisor timings, and initial mode/keymap into a config file.
- Allow configurable paths for keymap config (`/etc/dictacode/keymap.conf`) and HID device registry (`/etc/dictacode/hid/devices.d`).
- Add logging config (level/format/output) to avoid hard-coded `logging.basicConfig`.
- Keep compatibility matrix path configurable (align with STT).

---

# Current Config Handling (As-Is)

## STT App
- **Config file**: `/etc/dictacode/stt.conf` via `stt_config.py`; supports a single section (DEFAULT or [stt]). Covers metrics, API bind/metrics, model/language, UART device/baud, chunk duration, LLM settings. Validation present; missing section headers cause load failure (ConfigParser rules).
- **Other config roots**:
  - Audio profiles: `/etc/dictacode/audio/` (`AudioPortManager`, `api.py`, `api_server.py`).
  - HID registry: `/etc/dictacode/hid/devices.d/*.conf` (used when selecting HID device/transport).
  - Compatibility matrix: `/opt/dictacode/shared/compatibility.json` (core package), fallback to repo root or `/etc/dictacode/compatibility.json`.
  - Keymaps: referenced via HID side (not directly configured here).
  - Diagnostics/bugreport: `/etc/dictacode` root used for collection.
- **CLI/env precedence**: Many knobs are CLI-only (UART, baud, duration, language, streaming, dry-run, once/continuous, transport, hid-device, audio-source, supervisor toggles/timeouts). Metrics and LLM pull from config/env/CLI. Protocol and mode are env-driven (`DICTACODE_PROTOCOL`, `DICTACODE_MODE`).
- **Logging**: Configured via CLI (level/format/file) and systemd detection; no file-based logging config.
- **API**: Bind/ports configurable via `stt.conf`; metrics for API also configurable there.
- **Packaging**: Config shipped as conffile; templates/static shipped with API. Separate compatibility matrix in core package.

## HID App
- **Config file**: None central; relies on CLI/env for UART/HID paths, baud, protocol, mode, keymap, supervisor timings, dry-run/maintenance.
- **Other config roots**:
  - Keymap config: `/etc/dictacode/keymap.conf` (`keymaps/base.py`) plus keymap data files.
  - HID device registry: `/etc/dictacode/hid/devices.d/*.conf` (HidDeviceRegistry).
  - Compatibility matrix: `/opt/dictacode/shared/compatibility.json` (core package) with fallbacks.
  - Diagnostics assume system paths (`/etc/modules`, `/etc/modules-load.d`).
- **CLI/env precedence**: Primary control via CLI and env (`DICTACODE_PROTOCOL`, `DICTACODE_MODE`, `DICTACODE_KEYMAP`, supervisor envs). No persistent service config file for HID.
- **Logging**: Basic `logging.basicConfig` at DEBUG/INFO based on `--verbose`; no file/config-driven logging.
- **Metrics/API**: Not present on HID side (no configurable API/metrics).

## Role Separation
- STT and HID are installed on different devices with exclusive roles; config handling is asymmetric: STT has a dedicated config loader/file; HID does not. Shared assets (compatibility matrix, HID registry, keymaps) live under `/etc/dictacode` but are consumed differently by each role.

---

# Solution Design Draft (Config Consolidation with Cascading)

**Precedence (highest → lowest)**
1) CLI flags  
2) Environment variables  
3) Drop-ins: `/etc/dictacode/stt.d/*.conf` or `/etc/dictacode/hid.d/*.conf`  
4) Base file: `/etc/dictacode/stt.conf` or `/etc/dictacode/hid.conf`  
5) Code defaults

**Package responsibilities**
- Create dirs: `/etc/dictacode`, `/etc/dictacode/stt.d`, `/etc/dictacode/hid.d`, `/etc/dictacode/audio`, `/etc/dictacode/hid/devices.d`, `/etc/dictacode/keymap.conf`, `/opt/dictacode/shared/compatibility.json`.
- Install template `stt.conf` and `hid.conf` as conffiles (commented defaults). Leave drop-in dirs empty; runtime never writes to /etc.
- Ship shared data (compatibility.json) via core; checksums match repo.

**STT config scope**
- Transport/protocol: UART path/baud, protocol, transport type, HID device ID, handshake/link/supervisor timeouts.
- Audio: profile dir, recording duration, sample rates/channels, test audio source.
- Transcription/LLM: model/language, transcriber choice, whisper paths, LLM enable/provider/model/profile/base_url/api_key/fallback.
- Logging/metrics/API: log level/format/output, metrics enable/port (main/API), API host/port.
- Compatibility matrix path (optional override).

**HID config scope**
- Transport/protocol: UART path/baud, HID gadget path, protocol.
- Mode/keymap: initial mode/keymap, keymap config path, HID registry path.
- Supervisor: timeouts/ping interval/enable.
- Logging: level/format/output; (future) metrics toggle/port.
- Compatibility matrix path (optional override).

**Code changes**
- Add `hid_config.py` loader mirroring STT, merging base + drop-ins + env + CLI with validation (tolerate missing section header by prepending `[DEFAULT]`).
- Refactor `main.py` (both roles) to use loaders and shared precedence; centralize path constants.
- API/server uses same loader; default bind localhost; warn on non-localhost.
- Remove hard-coded paths; read from config.

**Validation/tests**
- CI schema checks for base and drop-in files; unit tests for loaders (defaults, overrides, invalid values, precedence).
- Artifact checks: conffiles present in debs; drop-in dirs created; shared files installed with matching checksums.

# Implementation Instructions (for this codebase)

1) Add `apps/hid/src/dictacode_hid/hid_config.py` modeled on `stt_config.py`: defaults, validation, prepend `[DEFAULT]` if missing, merge base `/etc/dictacode/hid.conf` + drop-ins `/etc/dictacode/hid.d/*.conf` + env + CLI.
2) Refactor `apps/stt/src/dictacode_stt/main.py` and `apps/hid/src/dictacode_hid/main.py` to use loaders and precedence (CLI > env > drop-ins > base > defaults); replace hard-coded UART/baud/protocol/supervisor/logging/metrics/API/LLM/audio values with config-backed values when CLI/env not set.
3) Centralize path constants per role (config file, drop-in dir, audio profiles dir, HID registry dir, keymap config, compatibility matrix) and reuse in `api.py`, `api_server.py`, `audio/manager.py`, `hid/registry.py`, etc.
4) Ensure shared assets honor config: compatibility search order override → `/opt/dictacode/shared/compatibility.json` → `/etc/dictacode/compatibility.json` → repo (dev); pass audio config dir to `AudioPortManager`; allow HID registry dir override.
5) Logging/metrics: add HID logging config (level/format/output) similar to STT; if HID metrics are added, mirror STT pattern.
6) Packaging: create empty `etc/dictacode/stt.d` and `etc/dictacode/hid.d` in core package; install template `stt.conf`/`hid.conf` as conffiles (commented defaults); keep `opt/dictacode/shared/compatibility.json` with checksum validation.
7) Tests/validation: unit tests for loaders (defaults, base, drop-in, env/CLI precedence, invalid values); CI checks for conffiles/drop-in dirs in debs; compatibility.json checksum alignment; optional schema lint.
8) Docs: update README/UPGRADING to document precedence and locations; note drop-ins are user/front-end owned (packages never write to them).

# Testing Plan (config consolidation)

- **Loader unit tests (STT/HID)**: Defaults-only; base file only; base+single drop-in; multiple drop-ins (sorted order); env overrides; CLI overrides; invalid values (ports/baud/protocol) -> warn/fail policy; missing section header prepend `[DEFAULT]`.
- **Path resolution tests**: Ensure paths modules return expected defaults and honor env overrides for config files, drop-in dirs, audio config, HID registry, keymap, compatibility matrix search order.
- **Precedence integration (lightweight)**: Run main entrypoints with temp config + drop-ins + env + CLI and assert effective settings (e.g., uart_baud precedence chain). Expose a `--show-config` debug flag for test-only dumps.
- **Compatibility matrix search**: Stub files in temp dirs to verify override → env → `/opt/dictacode/shared` → `/etc/dictacode` → repo fallback order in both apps.
- **Packaging validation**: CI script to inspect built debs for conffiles (`stt.conf`, `hid.conf`), empty drop-in dirs (`stt.d`, `hid.d`), correct shared `compatibility.json` checksum and expected `/etc/dictacode/...` paths.
- **Runtime smoke**: Start services with config files only (no CLI) in a temp env, ensure they read configs and exit cleanly in dry-run mode.

# Packaging/Layout Considerations (single template, multiple platforms)

- Single source for templates: keep authoritative `stt.conf` and `hid.conf` templates under source control (e.g., `ops/packaging/templates/`). Both deb builds and future macOS packages should consume the same files.
- Platform-specific install roots: default install paths come from `paths.py` with OS branching (e.g., Linux: `/etc/dictacode/*.conf`, `/etc/dictacode/*.d`; macOS: `/Library/Application Support/dictacode/*.conf`, `.../*.d`). Packaging scripts copy the same templates into the appropriate root.
- Drop-in dirs: create per platform (Linux `/etc/dictacode/{stt.d,hid.d}`, macOS `/Library/Application Support/dictacode/{stt.d,hid.d}`), initially empty; code only reads.
- Shared assets (compatibility.json): single canonical copy in repo; installer places it in platform-specific shared dir (Linux `/opt/dictacode/shared/`, macOS `/Library/Application Support/dictacode/shared/`); `/etc` as legacy fallback only.
- Pytest/dev usage: tests should read templates directly from the repo templates directory (not system paths) to avoid platform coupling; use `paths.py` repo fallback in finders.
- Packaging scripts: factor out a common step to copy templates from the repo template directory into the package-specific destination; ensure checksums match the source template across platforms.

# Platform Template Strategy

- Maintain a single set of authoritative templates under `ops/packaging/templates/` (stt.conf, hid.conf, keymap.conf).
- For each platform/package, generate the installed templates from the canonical versions. If platform-specific adjustments are needed, keep them as minimal diffs and automate them (e.g., sed/patch during packaging) rather than hand-maintaining separate files.
- If a diff is required, store it as a patch file under `ops/packaging/{platform}/patches/` and apply during build; avoid duplicating full templates per platform.
- Keep checksums of installed templates in CI to ensure they remain faithful to the canonical source + platform patch; fail builds if divergence occurs.
- For testing/dev (pytest), consume the canonical templates directly from `ops/packaging/templates/` to avoid platform coupling.
