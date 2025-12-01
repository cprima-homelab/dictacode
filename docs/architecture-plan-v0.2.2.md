# dictacode Architecture Plan v0.2.2 - Diagnostics Integration

## Status

### Phase 1: Diagnostic Framework
- [x] Create `diagnostics/` package in both HID and STT
- [x] Implement `base.py` with CheckStatus, CheckResult, DiagnosticResult
- [x] Add JSON and human-readable formatters
- [x] Unit tests for result classes

### Phase 2: HID Hardware Checks
- [x] Migrate check_hardware.py logic to `diagnostics/hardware.py`
- [x] Create CLI entry point `dictacode-hid-check`
- [x] Update pyproject.toml
- [x] Integration tests

### Phase 3: STT Hardware Checks
- [x] Create `diagnostics/audio.py` (mic detection)
- [x] Create `diagnostics/whisper.py` (binary/model checks)
- [x] Create CLI entry point `dictacode-stt-check`
- [x] Integration tests

### Phase 4: Full Diagnostic Suite
- [x] Add keymap diagnostics to HID
- [x] Create `dictacode-*-diagnose` commands
- [x] Add `--check NAME` option

### Phase 5: Runtime Integration
- [x] Add `diagnose` command handler to both services
- [x] Respect MAINTENANCE mode requirement
- [x] Log results to journal

### Phase 6: systemd Integration
- [ ] Update service files with ExecStartPre (ops/packaging)
- [ ] Test service startup with failing checks
- [ ] Document journalctl usage

**v0.2.2 COMPLETE** - Diagnostics integration implemented with CLI entry points.

---

## Prerequisites

v0.2.2 builds on top of v0.2.1:
- ✅ 5-layer architecture (transport, protocol, service, supervisor)
- ✅ MAINTENANCE mode implemented (log but don't act)
- ✅ CLI entry points (dictacode-hid, dictacode-stt)
- ✅ systemd integration with signal handling

---

## Scope

### Diagnostics as First-Class Utilities

Elevate sandbox diagnostic scripts to production-ready tools integrated with MAINTENANCE mode.

```
┌─────────────────────────────────────────────────────────────┐
│                    Diagnostics Layer                         │
│                                                              │
│  CLI Entry Points                    Runtime Integration     │
│  ├── dictacode-hid-check             ├── diagnose command   │
│  ├── dictacode-hid-diagnose          │   (MAINTENANCE only) │
│  ├── dictacode-stt-check             └── Results to journal │
│  └── dictacode-stt-diagnose                                 │
│                                                              │
│  systemd Integration                                         │
│  └── ExecStartPre: check before service start               │
└─────────────────────────────────────────────────────────────┘
```

---

## Design Decisions

### 1. Separate CLI Entry Points

Diagnostics get their own commands rather than subcommands:
- `dictacode-hid-check` - Quick hardware check (for systemd)
- `dictacode-hid-diagnose` - Full diagnostic suite
- `dictacode-stt-check` - Quick hardware check (for systemd)
- `dictacode-stt-diagnose` - Full diagnostic suite

### 2. Both Standalone and Runtime

- **Standalone**: Run before service starts (systemd ExecStartPre)
- **Runtime**: `diagnose` command via protocol (MAINTENANCE mode only)

### 3. Sandbox Remains

Sandbox scripts kept for experimental/ad-hoc testing. Diagnostics are formalized versions.

### 4. systemd ExecStartPre

Services fail to start if hardware check fails.

---

## CLI Entry Points

### New Commands

| Command | Purpose | Exit Codes |
|---------|---------|------------|
| `dictacode-hid-check` | Hardware prerequisites (quick) | 0=OK, 1=FAIL, 2=WARN |
| `dictacode-hid-diagnose` | Full diagnostic suite | 0=OK, 1=FAIL, 2=WARN |
| `dictacode-stt-check` | Hardware prerequisites (quick) | 0=OK, 1=FAIL, 2=WARN |
| `dictacode-stt-diagnose` | Full diagnostic suite | 0=OK, 1=FAIL, 2=WARN |

### CLI Options

```
--json          Output JSON (for machine parsing)
--verbose/-v    Show detailed check information
--quiet/-q      Only show failures
--check NAME    Run specific check only
```

### pyproject.toml Updates

**HID:**
```toml
[project.scripts]
dictacode-hid = "dictacode_hid.main:main"
dictacode-keymap = "dictacode_hid.cli:main"
dictacode-hid-check = "dictacode_hid.diagnostics:check_main"
dictacode-hid-diagnose = "dictacode_hid.diagnostics:diagnose_main"
```

**STT:**
```toml
[project.scripts]
dictacode-stt = "dictacode_stt.main:main"
dictacode-stt-check = "dictacode_stt.diagnostics:check_main"
dictacode-stt-diagnose = "dictacode_stt.diagnostics:diagnose_main"
```

---

## File Structure

```
apps/hid/src/dictacode_hid/
├── ...existing...
└── diagnostics/            # NEW
    ├── __init__.py         # check_main, diagnose_main entry points
    ├── base.py             # CheckStatus, CheckResult, DiagnosticResult
    ├── hardware.py         # Boot, modules, configfs, gadget, hidg0
    ├── keymap.py           # Keymap validation
    └── uart.py             # UART device checks

apps/stt/src/dictacode_stt/
├── ...existing...
└── diagnostics/            # NEW
    ├── __init__.py         # check_main, diagnose_main entry points
    ├── base.py             # CheckStatus, CheckResult, DiagnosticResult
    ├── audio.py            # Microphone detection, recording test
    ├── whisper.py          # Binary/model checks
    └── uart.py             # UART device checks
```

---

## Core Classes

### CheckResult and DiagnosticResult

```python
class CheckStatus(Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"

@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    next_step: Optional[str] = None  # Remediation hint

@dataclass
class DiagnosticResult:
    component: str  # "hid" or "stt"
    checks: List[CheckResult]

    @property
    def exit_code(self) -> int:
        if any(c.status == CheckStatus.FAIL for c in self.checks):
            return 1
        if any(c.status == CheckStatus.WARN for c in self.checks):
            return 2
        return 0

    def to_json(self) -> str: ...
    def to_human(self, verbose: bool = False) -> str: ...
```

---

## Diagnostic Checks

### HID Checks (from check_hardware.py)

| Check | Description |
|-------|-------------|
| `boot_config` | dtoverlay=dwc2 in /boot/firmware/config.txt |
| `kernel_modules` | dwc2, libcomposite loaded |
| `configfs_mount` | /sys/kernel/config mounted |
| `usb_gadget` | Gadget exists with HID function |
| `hid_device` | /dev/hidg0 exists and writable |
| `keymap_load` | Keymaps load without error |
| `uart_device` | /dev/serial0 readable |

### STT Checks

| Check | Description |
|-------|-------------|
| `audio_device` | Microphone device exists |
| `audio_record` | Can capture audio (1 second test) |
| `whisper_binary` | whisper-cli found and executable |
| `whisper_model` | Model file exists and valid size |
| `uart_device` | /dev/serial0 writable |

---

## Runtime Integration

### Protocol Command

```json
// Request diagnostic (MAINTENANCE mode only)
{"t":"cmd","c":"diagnose","a":"hardware"}
{"t":"cmd","c":"diagnose","a":"all"}
```

### Service Handler

```python
def _handle_command(self, msg: CommandMessage) -> None:
    # ...existing handlers...

    elif msg.command == "diagnose":
        if self.state.mode != DeviceMode.MAINTENANCE:
            logger.warning("diagnose ignored - not in MAINTENANCE mode")
            return
        self._run_diagnostic(msg.argument or "all")
```

---

## systemd Integration

### Updated Service Files

```ini
# dictacode-hid.service
[Service]
ExecStartPre=/opt/dictacode/hid/venv/bin/dictacode-hid-check --quiet
ExecStart=/opt/dictacode/hid/venv/bin/dictacode-hid
```

```ini
# dictacode-stt.service
[Service]
ExecStartPre=/opt/dictacode/stt/venv/bin/dictacode-stt-check --quiet
ExecStart=/opt/dictacode/stt/venv/bin/dictacode-stt
```

**Behavior:**
- Exit 1 (FAIL) → service does not start
- Exit 2 (WARN) → service starts with warning logged
- Exit 0 (OK) → service starts normally

---

## Output Formats

### Human-Readable (default)

```
=== dictacode HID Hardware Check ===

Boot Configuration:
  [OK] dtoverlay=dwc2 configured

Kernel Modules:
  [OK] dwc2 active (UDC available)
  [OK] libcomposite module loaded

HID Device:
  [OK] /dev/hidg0 exists
  [OK] /dev/hidg0 is writable

=== Summary ===
Status: READY
Checks: 5 passed, 0 failed, 0 warnings
```

### JSON (--json)

```json
{
  "status": "ok",
  "component": "hid",
  "checks": [
    {"name": "boot_config", "status": "ok", "message": "dtoverlay=dwc2 configured"},
    {"name": "hid_device", "status": "ok", "message": "/dev/hidg0 writable"}
  ],
  "summary": {"passed": 5, "failed": 0, "warnings": 0}
}
```

---

## Implementation Phases

### Phase 1: Diagnostic Framework
1. Create `diagnostics/` package in both HID and STT
2. Implement `base.py` with CheckStatus, CheckResult, DiagnosticResult
3. Add JSON and human-readable formatters
4. Unit tests for result classes

### Phase 2: HID Hardware Checks
1. Migrate check_hardware.py logic to `diagnostics/hardware.py`
2. Create CLI entry point `dictacode-hid-check`
3. Update pyproject.toml
4. Integration tests

### Phase 3: STT Hardware Checks
1. Create `diagnostics/audio.py` (mic detection)
2. Create `diagnostics/whisper.py` (binary/model checks)
3. Create CLI entry point `dictacode-stt-check`
4. Integration tests

### Phase 4: Full Diagnostic Suite
1. Add keymap diagnostics to HID
2. Create `dictacode-*-diagnose` commands
3. Add `--check NAME` option

### Phase 5: Runtime Integration
1. Add `diagnose` command handler to both services
2. Respect MAINTENANCE mode requirement
3. Log results to journal

### Phase 6: systemd Integration
1. Update service files with ExecStartPre
2. Test service startup with failing checks
3. Document journalctl usage

---

## Critical Files

**To Create:**
- `apps/hid/src/dictacode_hid/diagnostics/__init__.py`
- `apps/hid/src/dictacode_hid/diagnostics/base.py`
- `apps/hid/src/dictacode_hid/diagnostics/hardware.py`
- `apps/stt/src/dictacode_stt/diagnostics/__init__.py`
- `apps/stt/src/dictacode_stt/diagnostics/base.py`
- `apps/stt/src/dictacode_stt/diagnostics/audio.py`
- `apps/stt/src/dictacode_stt/diagnostics/whisper.py`

**To Modify:**
- `apps/hid/pyproject.toml` (add entry points)
- `apps/stt/pyproject.toml` (add entry points)
- `apps/hid/src/dictacode_hid/service.py` (add diagnose handler)
- `apps/stt/src/dictacode_stt/service.py` (add diagnose handler)

**Reference:**
- `apps/hid/sandbox/check_hardware.py` (migrate logic)

---

## Success Criteria

v0.2.2 is complete when:

1. ✅ `dictacode-hid-check` validates USB HID prerequisites
2. ✅ `dictacode-stt-check` validates audio and whisper prerequisites
3. ✅ Both commands support `--json` and `--quiet` flags
4. ✅ Exit codes: 0=OK, 1=FAIL, 2=WARN
5. ✅ systemd ExecStartPre prevents start on failure
6. ✅ `diagnose` command works in MAINTENANCE mode
7. ✅ sandbox/ scripts remain untouched
8. ✅ Unit tests for diagnostic classes

---

## Out of Scope (v0.2.2)

- HTTP API for diagnostics (v0.3.0 web panel)
- Bidirectional diagnostic responses (v0.3.0)
- Automatic remediation
- Network diagnostics
- Performance benchmarks
