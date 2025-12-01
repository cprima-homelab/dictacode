# dictacode Backlog

Items discovered during development that could improve the project but are not critical blockers.

## Development Workflow

### Device Setup Automation
**Gap**: After `git pull` on ephemeral devices, venv needs manual reconfiguration
**Nice-to-have**: Post-pull hook or wrapper script that auto-runs `tools/dev-setup.sh`
```bash
# Proposed: tools/deploy-to-device.sh
# - SSH to device
# - git pull
# - Run dev-setup.sh
# - Restart services
```
**Related**: v0.2.12 Phase 7 (partial - script exists, automation missing)

### Pre-commit Hooks
**Gap**: No pre-commit configuration yet
**Nice-to-have**: Auto-format, lint, type-check before commits
**Related**: v0.2.12 Phase 7 (unchecked item)

### CONTRIBUTING.md Documentation
**Gap**: No developer onboarding documentation
**Nice-to-have**:
- How to set up development environment
- How to run tests
- Code style guidelines
- PR process
**Related**: v0.2.12 Phase 7 (unchecked item)

## Architecture & Planning

### Architecture Plan Index
**Gap**: 11+ architecture plan files (v0.2.4-v0.2.14, v0.2.99) with no master index
**Nice-to-have**: `docs/architecture-index.md` or `docs/roadmap.md` showing:
- Dependency graph between plans
- Which plans are complete/in-progress/not-started
- Version progression rationale

### Version Number Confusion
**Gap**: Debian packages at v0.2.4, but completed work is v0.2.3
**Observation**: Package versions ahead of feature versions causes confusion
**Nice-to-have**: Clarify versioning strategy in RELEASING.md or architecture docs

## Testing

### Test Runner Configuration
**Gap**: Tests exist but no documented test strategy
**Nice-to-have**:
- pytest.ini or pyproject.toml test config
- CI/CD test automation (mentioned in v0.2.12 Phase 6)
- Test coverage reporting

### Integration Test Suite
**Gap**: Unit tests exist, but integration tests between components unclear
**Nice-to-have**:
- End-to-end test: STT → HID → keyboard input
- UART handshake integration test
- Device failure simulation tests

## Operations

### Background Process Cleanup
**Observation**: Many long-running background SSH processes accumulate
**Nice-to-have**: `tools/cleanup-shells.sh` to kill stale background processes
```bash
# List active background processes
# Kill by ID or pattern
# Auto-cleanup on session end
```

### Device Health Dashboard
**Gap**: No centralized view of device status
**Nice-to-have**:
- `tools/device-status.sh` - Query all devices for service status, logs, versions
- Shows: service state, last log entries, git commit, package version

### Log Aggregation
**Gap**: Checking logs requires SSH to each device
**Nice-to-have**:
- Central log collection (syslog forwarding?)
- `tools/tail-all-logs.sh` - Tail logs from multiple devices simultaneously

## Documentation

### Hardware Setup Documentation
**Gap**: Hardware wiring diagram exists, but assembly instructions unclear
**Nice-to-have**:
- Step-by-step assembly guide with photos
- Bill of materials (BOM) with purchase links
- Troubleshooting common hardware issues

### API Documentation
**Gap**: Backend API endpoints planned (v0.2.4 Phase 6) but not documented
**Nice-to-have**: OpenAPI/Swagger spec when API implemented

## Nice-to-Have Features

### Audio Device Hot-Plug Detection
**Scope**: Out of scope for v0.2.4
**Nice-to-have**: Automatic detection when USB mic plugged/unplugged
**Use case**: User swaps microphones without restarting service

### Whisper Model Auto-Download
**Gap**: Current setup requires manual Whisper model installation
**Nice-to-have**: Service auto-downloads model on first run if missing
**Consideration**: Large download size, may want user confirmation

### Diagnostics Mode
**Gap**: No built-in diagnostics for troubleshooting
**Nice-to-have**: `dictacode-stt diagnose` command that:
- Checks UART connectivity
- Tests audio input
- Verifies Whisper model
- Reports system resources (CPU, memory, disk)

### Multi-Language Support
**Gap**: Currently English-only transcription
**Nice-to-have**: Language selection via config or CLI flag
**Consideration**: Whisper supports 99 languages

## Infrastructure

### Automated Device Provisioning
**Gap**: Device setup is manual (flash SD card, run scripts)
**Nice-to-have**:
- Ansible playbook for full device setup
- Custom SD card image with pre-installed packages
**Related**: Tools exist (flash_pi5.md, flash_zero2.md) but not automated

### Backup & Recovery
**Gap**: No documented backup strategy for device configurations
**Nice-to-have**:
- Script to backup `/etc/dictacode/` configs
- Script to restore device state from backup

---

## Prioritization Notes

**Critical Path**: Items blocking main features (none currently)
**High Value**: Development workflow improvements (pre-commit, CONTRIBUTING.md)
**Medium Value**: Operations tooling (device status, log aggregation)
**Low Value / Future**: Nice-to-have features (hot-plug, multi-language)

---

Last updated: 2025-12-01
