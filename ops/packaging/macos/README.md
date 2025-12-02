# macOS Packaging

## Purpose

The macOS packages are for **configuration/code inspection and development only**, not for functional UART/HID runtime. The hardware-dependent features (USB gadget mode, UART serial) are Linux-specific.

## What Gets Installed

| Package | Install Location | Contents |
|---------|-----------------|----------|
| `dictacode-core` | `/Library/Application Support/dictacode/shared/` | `compatibility.json` |
| `dictacode-stt` | `/Library/Application Support/dictacode/` | `stt.conf`, `stt.d/`, `audio/` |
| `dictacode-hid` | `/Library/Application Support/dictacode/` | `hid.conf`, `keymap.conf`, `hid.d/`, `hid/devices.d/` |

## What Is NOT Included

- **launchd plists** - No background services (macOS doesn't use systemd)
- **System users/groups** - Not needed for config-only packages
- **Hardware-dependent binaries** - UART/HID gadget requires Linux

## Building

### On macOS (produces .pkg files)

```bash
./build-pkg.sh                    # Build all packages
./build-pkg.sh dictacode-stt      # Build specific package
./build-pkg.sh --combined         # Build combined installer
```

Requires Xcode Command Line Tools (`xcode-select --install`).

### On Linux (produces payload tarballs)

```bash
./build-pkg.sh                    # Creates .tar.gz payloads for inspection
```

The tarballs can be used to verify contents match paths.py expectations.

## Permissions

- Ownership: `root:wheel` (standard for macOS system configs)
- Directories: `755`
- Config files: `644`

The postinstall script sets these permissions automatically.

## Hardware Expectations

The Python code has platform guards for hardware-dependent paths:

```python
# In paths.py
def _is_macos() -> bool:
    return sys.platform == "darwin"

def _get_config_base() -> Path:
    if _is_macos():
        return Path("/Library/Application Support/dictacode")
    return Path("/etc/dictacode")
```

On macOS, attempting to use UART or HID gadget features will fail gracefully with appropriate error messages (device not found).

## Validation

Run the validation script to verify:

```bash
../validate-artifacts.sh
```

This checks:
- Payload paths match paths.py macOS defaults
- Templates sourced from `ops/packaging/templates/`
- compatibility.json checksum matches repo and Linux packages

## Directory Structure

```
macos/
├── build-pkg.sh           # Build script
├── dist/                  # Output directory
│   ├── *.pkg              # macOS installer packages (on macOS)
│   └── *-macos-payload.tar.gz  # Payload tarballs (on Linux)
└── README.md              # This file
```

## Templates

All config files are sourced from `ops/packaging/templates/`:
- `stt.conf`
- `hid.conf`
- `keymap.conf`

This ensures a single source of truth across Linux and macOS packages.
