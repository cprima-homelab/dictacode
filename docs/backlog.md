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

### Streaming Pipeline Backpressure & Flow Control
**Gap**: Streaming pipeline + ring buffer + WebSocket preview lacks backpressure/flow control to HID
**Concerns**:
- No plan for chunk coalescing
- No queue limits defined
- No slow-client handling
- Partial transcriptions could pile up or race with final results
**Action needed**: Define buffering policy, ordering rules, and drop/flush behavior before adding streaming/UI
**Related**: v0.2.4 Phase 2 (ring buffer), future WebSocket implementation
**Impact**: High - affects reliability and correctness of transcription output

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

### Streaming Adapter Unit Tests
**Gap**: v0.2.7 streaming adapters (VoskAdapter, WhisperAdapter streaming methods) lack unit tests
**Technical Debt**: All streaming tests deferred during implementation
**Nice-to-have**:
- Mock Vosk model and test streaming callbacks
- Test WhisperAdapter chunked batch buffering
- Test StreamingTranscriptionAdapter protocol compliance
**Related**: v0.2.7 Phase 1-3 (tests deferred)

### Streaming Pipeline Integration Tests
**Gap**: No integration tests for streaming transcription pipeline
**Nice-to-have**:
- Test ring buffer → streaming adapter → callbacks flow
- Test streaming mode vs batch mode behavior
- Test graceful fallback when streaming unsupported
**Related**: v0.2.7 Phase 4 (tests deferred)

### Audio Source Unit Tests
**Gap**: v0.2.11 created integration tests but incomplete unit test coverage
**Technical Debt**: Tests deferred during implementation
**Nice-to-have**:
- Unit tests for AudioSource protocol compliance
- Unit tests for SyntheticSource patterns (tone, noise, click, sweep)
- Edge case tests for source lifecycle (double-open, stop-before-start, etc.)
- Audio resampling accuracy tests
**Related**: v0.2.11 Phases 1-3 (unchecked unit test items)

### Real Speech Audio Fixtures
**Gap**: Test infrastructure complete but only synthetic silence fixture exists
**Nice-to-have**:
- Create hello_world.wav fixture (actual speech sample)
- Create numbers_1_to_5.wav fixture for number recognition
- Create short_phrase.wav for looping tests
- Record/generate fixtures with known transcriptions for validation
**Impact**: Without real speech fixtures, integration tests can't verify actual transcription accuracy
**Related**: v0.2.11 Phase 5 (audio fixtures marked optional)

### CI/CD Pipeline for Audio Tests
**Gap**: Audio source tests exist but not integrated into CI/CD
**Nice-to-have**:
- GitHub Actions workflow to run audio source tests
- Pytest configuration for CI (pytest.ini or pyproject.toml)
- Test with file sources in fast mode for speed
- Coverage reporting for audio module
**Related**: v0.2.11 Phase 6 (CI pipeline integration deferred)

### Audio Fixture Creation Tooling
**Gap**: No streamlined tool for creating valid test fixtures
**Nice-to-have**: `dictacode-stt-audio create-fixture` command that:
- Records audio from microphone
- Automatically converts to 16kHz mono WAV
- Validates format requirements
- Saves with documented expected transcription
- Optionally transcribes immediately to verify accuracy
**Use case**: Developers can easily create test fixtures without manual audio processing
**Related**: v0.2.11 (fixtures documented but creation is manual)

### Reusable Mock Transcriber
**Gap**: MockTranscriber created in test file but not exported as reusable utility
**Nice-to-have**:
- Move MockTranscriber to `dictacode_stt.testing` module
- Support configurable transcription text
- Support simulated delays/errors
- Make available for all integration tests
**Related**: v0.2.11 Phase 5 (test utilities)

### Audio Source Performance Benchmarks
**Gap**: No metrics comparing fast mode vs real-time mode performance
**Nice-to-have**:
- Benchmark file source playback speeds (fast vs realtime)
- Measure overhead of audio resampling
- CI performance regression detection
- Document optimal test configuration for CI
**Use case**: Optimize CI test execution time
**Related**: v0.2.11 (fast mode implemented but not benchmarked)

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

## Release Process (v0.2.12 Learnings)

### GitHub Secrets Configuration
**Gap**: GitHub Actions workflow requires `PYPI_TOKEN` and `TEST_PYPI_TOKEN` secrets
**Action needed**: Document how to configure GitHub repository secrets for automated releases
**Related**: v0.2.12 Phase 6 - workflow created but secrets not configured
**Impact**: Blocks automated releases via GitHub Actions

### Changelog Generation Automation
**Gap**: CHANGELOG.md must be manually updated before releases
**Nice-to-have**: Auto-generate changelog from git commits or conventional commits
**Consideration**: Could use tools like `git-cliff`, `conventional-changelog`, or GitHub Releases
**Related**: v0.2.12 Phase 4 - marked as "out of scope" but creates manual work
**Workaround**: Currently developers must manually update CHANGELOG.md

### Release Verification Testing
**Gap**: No post-release verification that packages actually work
**Nice-to-have**: Automated verification script that:
- Installs package from PyPI in clean environment
- Runs basic smoke tests
- Verifies version numbers match
- Checks .deb package installs without errors
**Use case**: Catch broken releases before users do
**Related**: v0.2.12 Phase 5 - post-release verification mentioned but not implemented

### Version Consistency Validation
**Gap**: No automated check that component versions are compatible
**Nice-to-have**: Pre-release validation that checks:
- STT and HID versions are compatible per compatibility matrix
- Version numbers follow semantic versioning
- New version is higher than last release
- No duplicate version tags exist
**Use case**: Prevent releasing incompatible component combinations
**Related**: v0.2.12 - version bumping works but no cross-component validation

### Multi-Component Coordinated Releases
**Gap**: Releasing multiple components together requires running scripts multiple times
**Nice-to-have**: `./tools/release.sh --all --version 0.2.13 --full` to:
- Bump all component versions to same number
- Release all components in dependency order
- Create coordinated tag (e.g., `v0.2.13` for monorepo-wide release)
**Use case**: Major releases that update all components together
**Related**: v0.2.12 - individual releases work well, coordinated releases cumbersome

### Release Rollback Capability
**Gap**: No rollback scripts if release goes wrong
**Nice-to-have**: `tools/rollback-release.sh` that:
- Deletes git tag (local and remote)
- Yanks PyPI package release
- Documents rollback in CHANGELOG
**Use case**: Quick recovery from broken releases
**Impact**: Without rollback, broken releases stay published

### Package Signing
**Scope**: Marked out-of-scope for v0.2.12
**Gap**: Debian packages and PyPI uploads not cryptographically signed
**Nice-to-have**:
- GPG signing for .deb packages
- Signed PyPI uploads (Twine supports GPG)
- Document signing key setup for maintainers
**Security**: Prevents package tampering
**Related**: v0.2.12 success criteria - signing explicitly excluded

### Debian Package Repository
**Gap**: Users must manually download and install .deb files
**Nice-to-have**: Host apt repository so users can:
```bash
echo "deb https://dictacode.example.com/apt stable main" | sudo tee /etc/apt/sources.list.d/dictacode.list
sudo apt update && sudo apt install dictacode-stt
```
**Consideration**: Requires hosting infrastructure and package signing
**Benefit**: Professional distribution, automatic updates via apt

### Build Reproducibility
**Gap**: No guarantees that builds are reproducible (same source → same binary)
**Nice-to-have**:
- Pin all build dependencies (Python, uv, dpkg-deb versions)
- Use reproducible build flags
- Verify checksums match across builds
**Use case**: Security auditing, supply chain verification
**Related**: v0.2.12 - builds work but reproducibility not tested

### GitHub Actions Workflow Testing
**Gap**: Release workflow hasn't been tested end-to-end (can't push tags from dev environment)
**Action needed**: Test actual tag-triggered release in GitHub:
- Push test tag to trigger workflow
- Verify PyPI upload works
- Verify .deb artifact is created
- Verify GitHub Release is created correctly
**Related**: v0.2.12 Phase 6 - workflow created but untested in practice

### TestPyPI Release Testing
**Gap**: TestPyPI releases haven't been tested in practice
**Nice-to-have**: Before first production release to PyPI:
- Test full release to TestPyPI
- Verify package installs from TestPyPI
- Document any differences between Test and production PyPI
**Use case**: Practice release process safely before production

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

### MicrophoneSource Implementation
**Gap**: v0.2.11 Phase 1 deferred MicrophoneSource implementation
**Current**: Microphone code still uses legacy sounddevice directly in SttService
**Nice-to-have**:
- Implement MicrophoneSource using AudioSource protocol
- Wrap existing sounddevice/port manager logic
- Unified interface for all audio sources (mic, file, synthetic)
- Simplifies testing (can mock MicrophoneSource like any other source)
**Benefit**: Consistent abstraction, easier to test microphone path
**Related**: v0.2.11 Phase 1 (MicrophoneSource marked as deferred)

### Audio Device Hot-Plug Detection
**Scope**: Out of scope for v0.2.4
**Nice-to-have**: Automatic detection when USB mic plugged/unplugged
**Use case**: User swaps microphones without restarting service

### Audio Format Validation
**Gap**: No validation that audio files meet requirements before use
**Nice-to-have**:
- Validate WAV format, sample rate, channels before playback
- Helpful error messages for invalid files
- Support for auto-conversion (e.g., 48kHz → 16kHz)
**Use case**: Prevent confusing errors when using wrong audio formats in tests
**Related**: v0.2.11 (FileSource accepts any WAV but may fail unexpectedly)

### Whisper Model Auto-Download
**Gap**: Current setup requires manual Whisper model installation
**Nice-to-have**: Service auto-downloads model on first run if missing
**Consideration**: Large download size, may want user confirmation

### Vosk Model Management
**Gap**: VoskAdapter (v0.2.7) searches for models but provides no download/management
**Nice-to-have**:
- Auto-download Vosk model on first use if missing
- Support multiple language models
- Model selection via CLI flag or config
**Consideration**: Vosk models range from 50MB (small) to 1.8GB (large)
**Related**: v0.2.7 Phase 2 (VoskAdapter implementation)

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

### mDNS Service Discovery
**Scope**: v0.2.8 Phase 7 (deferred)
**Gap**: WiFi HID devices must be manually configured with IP addresses
**Nice-to-have**:
- Register HID devices via mDNS (Avahi) on network
- Auto-discover WiFi HID devices using Zeroconf
- Update device registry from discovery
- mDNS service browser in STT service
**Use case**: WiFi HID devices announce themselves, STT service finds them automatically
**Consideration**: Requires avahi-daemon on HID devices and zeroconf Python package
**Related**: v0.2.8 architecture plan - Phase 7 marked as optional enhancement

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


# transport

evaluate bluetooth transport

---


### Phase 5: Streaming (Optional)
- [ ] Evaluate whisper.cpp streaming support
- [ ] Or evaluate Vosk for streaming STT
- [ ] Implement partial result handling
- [ ] Update web panel for partial display


---

the diagrams in @docs/diagrams.md are horribly outdated.
  generate 24 mermaid diagrams of your choice

---

 Command Detection (Stub)
- [ ] Define `CommandDetector` interface
- [ ] Implement wake word detection stub
- [ ] Define `Command` types (wake, action, cancel)
- [ ] Prepare hooks for future voice command system
- [ ] Document extension points

---

  - Ownership/permissions: chmod 666 on /dev/serial0 is risky; if not reset, it masks permission problems rather than validating proper group
    membership.


---

cors

---


