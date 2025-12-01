# Repository Guidelines

## Project Structure & Module Organization
- `apps/stt/` (Pi 5 STT engine) and `apps/hid/` (Pi Zero HID gadget) hold Python sources under `src/` with matching `tests/`; `sandbox/` contains UART/audio/HID exploratory scripts.
- `ops/packaging/` defines Debian package roots and `build-deb.sh`; outputs land in `ops/packaging/dist/`.
- `tools/bootstrap.sh` bootstraps fresh DietPi installs; `config/inventory.example.yaml` documents host metadata; `docs/` captures architecture, testing workflows, and wiring notes.

## Build, Test, and Development Commands
- Install deps with uv: `cd apps/stt && uv sync`; repeat in `apps/hid` when needed.
- Run unit tests: `cd apps/stt && uv run pytest tests/`; HID: `cd apps/hid && uv run pytest tests/`.
- Manual pipeline run: `cd apps/stt && uv run sandbox/pipeline_stream.py` (UART to HID). Sandbox tools for HID live in `apps/hid/sandbox/`.
- Build packages (system changes): `cd ops/packaging && ./build-deb.sh dictacode-stt` (or `dictacode-hid`; omit arg for all). Deploy from `ops/packaging/dist/` to devices, install via `sudo dpkg -i`.

## Coding Style & Naming Conventions
- Python 3.9+, 4-space indentation; `snake_case` for modules/functions, `CamelCase` classes, `UPPER_SNAKE_CASE` constants.
- Keep state-machine and protocol code explicit and deterministic; fail fast over silent recovery. Log UART/audio/HID context when behavior changes.
- Tests mirror modules (`tests/test_*.py`); keep CLI entry points thin and isolate hardware-touching code.

## Testing Guidelines
- Pytest is standard; add regression tests alongside changes in `apps/*/tests/` using `test_<unit>.py` and `test_*` functions.
- Canonical workflows live in `docs/testing.md`. Follow “Quick Development” when only Python changes: run the app suite(s) with `uv run pytest`, push/pull, restart `dictacode-{stt|hid}`, and inspect `journalctl -u dictacode-{stt|hid} -n 50 --no-pager`.
- For system/service/config edits, follow the “System Changes” path in `docs/testing.md`: update package versions, `./build-deb.sh` the affected packages, `scp` to devices, install with `dpkg -i`, restart via `systemctl daemon-reload && systemctl restart dictacode-{stt|hid}`, then verify UART/HID availability (`/dev/serial0`, `/dev/hidg0`) and logs.

## Commit & Pull Request Guidelines
- Use short, imperative commits with component context (e.g., `Add v0.2.3 handshake support to HID`, `Remove manual start() calls`). Keep concerns grouped.
- PRs should state what changed, why, and how it was tested (commands, devices touched). Link issues/releases; include log snippets or screenshots for diagnostics when useful.
- When modifying packaging or config, note version bumps and required device actions (service restarts, package rebuilds).
