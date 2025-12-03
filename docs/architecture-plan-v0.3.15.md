# v0.3.15 - ALSA Mixer Auto-Setup and Diagnostics

## Problem Statement

USB audio devices often reset mixer levels to 0% (muted) on:
- Device reconnection
- System reboot
- Driver reload

This caused silent transcriptions (all ASR results were empty) because the microphone capture gain was at 0%.

## Root Cause

ALSA mixer settings don't persist by default. Without running `alsactl store`, USB audio devices reset to their defaults on reconnect/reboot. The RODE VideoMic NTG defaults to 0% capture gain.

## Changes

### 1. Debian Package: Auto-Configure ALSA Mixer

**File:** `ops/packaging/debian/dictacode-stt/DEBIAN/postinst`

On package install/upgrade, the postinst script now:
1. Scans ALSA cards 0-2 for a 'Mic' control
2. Sets capture level to 80%
3. Persists settings via `alsactl store`

```bash
for card in 0 1 2; do
    if amixer -c "$card" sget 'Mic' >/dev/null 2>&1; then
        amixer -c "$card" sset 'Mic' 80% || true
        alsactl store "$card" 2>/dev/null || true
        break
    fi
done
```

### 2. Diagnostics: Mixer Level Checks

**File:** `apps/stt/src/dictacode_stt/diagnostics/audio.py`

New diagnostic functions:
- `get_mixer_capture_level(card)` - Read current mic capture %
- `check_alsa_state_persisted()` - Check if `/var/lib/alsa/asound.state` exists
- `run_mixer_checks(card)` - Run all mixer diagnostics

Integrated into `run_audio_checks()` to provide:
- **FAIL** if mic capture is 0% (muted)
- **WARN** if mic capture is < 50%
- **WARN** if ALSA state file is missing (settings won't persist)

### 3. Dependencies

The `alsa-utils` package (already a dependency) provides:
- `amixer` - Mixer control
- `alsactl` - State storage

No new dependencies required.

## Files Modified

| File | Change |
|------|--------|
| `ops/packaging/debian/dictacode-stt/DEBIAN/postinst` | Added ALSA mixer auto-configuration |
| `apps/stt/src/dictacode_stt/diagnostics/audio.py` | Added mixer level and state persistence checks |

## Testing

1. Build new package: `./build-package.sh stt`
2. Install on device: `sudo apt install /tmp/dictacode-stt_*.deb`
3. Verify postinst output shows mixer configuration
4. Run diagnostics: `dictacode-stt diagnose`
5. Verify `mixer_capture_level` and `alsa_state` checks pass

## Manual Workaround

If settings reset before upgrading:

```bash
# Set mic gain
amixer -c 0 sset 'Mic' 80%

# Persist across reboots
alsactl store 0
```

## Future Considerations (v0.3.99)

The broader diagnostics overhaul should include:
- Audio device enumeration in diagnostics API
- Mixer level monitoring in live status
- Platform-specific tool detection (alsactl availability)
- Automated remediation suggestions in CP
