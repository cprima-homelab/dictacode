# dictacode Architecture Plan v0.3.2 - Configuration Consolidation

## Summary

Implement unified configuration handling across STT and HID components with cascading precedence, drop-in directories, and centralized path constants. This enables deployment tuning without code changes.

**Precedence (highest → lowest):**
1. CLI flags
2. Environment variables
3. Drop-ins: `/etc/dictacode/stt.d/*.conf` or `/etc/dictacode/hid.d/*.conf`
4. Base file: `/etc/dictacode/stt.conf` or `/etc/dictacode/hid.conf`
5. Code defaults

---

## Status

**Completed: 2025-12-02**

### Phase 1: HID Config Loader
- [x] Create `apps/hid/src/dictacode_hid/hid_config.py`
- [x] Define `HidConfig` dataclass with defaults
- [x] Implement `load_hid_config()` with drop-in merging
- [x] Add validation (ports, baud rates, paths)
- [x] Unit tests for loader (`apps/hid/tests/test_hid_config.py` - 23 tests)

### Phase 2: STT Config Enhancements
- [x] Add drop-in support to `stt_config.py`
- [x] Add missing tunables (supervisor, handshake, audio rates)
- [x] Prepend `[DEFAULT]` if section header missing
- [x] Unit tests for drop-in merging (`apps/stt/tests/test_stt_config.py`)

### Phase 3: Path Constants & Centralization
- [x] Define path constants module for each app (`paths.py` with platform support)
- [x] Refactor hardcoded paths in service.py, main.py, api.py
- [x] Support environment variable overrides for all paths
- [x] Update AudioPortManager to accept config dir parameter
- [x] Platform-aware paths (Linux: `/etc/dictacode/`, macOS: `/Library/Application Support/dictacode/`)

### Phase 4: CLI/Main Integration
- [x] Refactor `stt/main.py` to use loader with precedence
- [x] Refactor `hid/main.py` to use loader with precedence
- [x] Replace CLI defaults with config-backed values
- [x] Add logging config (level/format/output) to HID (`--log-level`, `--log-format`, `--log-file`)

### Phase 5: Packaging Updates
- [x] Create `/etc/dictacode/stt.d/` and `/etc/dictacode/hid.d/` dirs
- [x] Install template `stt.conf` and `hid.conf` as conffiles
- [x] Keep `/opt/dictacode/shared/compatibility.json` with checksum
- [x] Update postinst scripts
- [x] Create `ops/packaging/templates/` with canonical configs (single source of truth)
- [x] Wire templates into `build-deb.sh` via `copy_templates()` function

### Phase 6: Tests & Validation
- [x] Unit tests for loaders (defaults, base, drop-in, env/CLI precedence)
- [ ] CI checks for conffiles/drop-in dirs in debs (deferred)
- [x] Compatibility.json checksum alignment

---

## Problem Statement

### Current State

**STT App:**
- Config file: `/etc/dictacode/stt.conf` via `stt_config.py`
- Supports single section (DEFAULT or [stt])
- Many knobs are CLI-only (UART, baud, duration, supervisor, streaming, etc.)
- No drop-in support
- Logging configured via CLI, not file

**HID App:**
- No central config file - relies entirely on CLI/env
- Keymap config: `/etc/dictacode/keymap.conf`
- HID device registry: `/etc/dictacode/hid/devices.d/*.conf`
- Logging via `logging.basicConfig`, no file/config-driven

**Shared:**
- Compatibility matrix: `/opt/dictacode/shared/compatibility.json` with fallbacks
- Audio profiles: `/etc/dictacode/audio/` (STT only)
- 40+ hardcoded references to `/etc/dictacode/` paths

---

## Design

### Config Loader Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Config Resolution Pipeline                       │
│                                                                      │
│  1. CLI flags (argparse)                                             │
│        ↓                                                             │
│  2. Environment variables (os.getenv)                                │
│        ↓                                                             │
│  3. Drop-in files (/etc/dictacode/{stt,hid}.d/*.conf)               │
│        ↓ (merged in sorted order)                                    │
│  4. Base config (/etc/dictacode/{stt,hid}.conf)                     │
│        ↓                                                             │
│  5. Code defaults (dataclass defaults)                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### HID Config Dataclass

```python
# apps/hid/src/dictacode_hid/hid_config.py

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from configparser import ConfigParser
import logging

logger = logging.getLogger("dictacode.hid.config")
DEFAULT_CONFIG_PATH = Path("/etc/dictacode/hid.conf")
DROP_IN_DIR = Path("/etc/dictacode/hid.d")

@dataclass
class HidConfig:
    """HID service configuration with validation."""

    # Transport
    uart_device: str = "/dev/serial0"
    uart_baud: int = 115200
    hid_device: str = "/dev/hidg0"
    protocol: str = "json"  # "json" or "msgpack"

    # Mode & Keymap
    initial_mode: str = "normal"  # "normal", "maintenance", "paused"
    initial_keymap: str = "en_us"
    keymap_config: str = "/etc/dictacode/keymap.conf"
    hid_registry_dir: str = "/etc/dictacode/hid/devices.d"

    # Supervisor
    supervisor_enabled: bool = True
    supervisor_timeout: float = 30.0
    supervisor_ping_interval: float = 5.0

    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None  # None = stderr/journald

    # Compatibility
    compatibility_matrix: Optional[str] = None  # Override search path

    # Dry-run (default False, typically CLI-only)
    dry_run: bool = False

    def __post_init__(self):
        """Validate configuration values."""
        valid_bauds = [9600, 19200, 38400, 57600, 115200, 230400]
        if self.uart_baud not in valid_bauds:
            raise ValueError(f"Invalid uart_baud: {self.uart_baud}")

        valid_modes = ["normal", "maintenance", "paused"]
        if self.initial_mode not in valid_modes:
            raise ValueError(f"Invalid initial_mode: {self.initial_mode}")

        valid_protocols = ["json", "msgpack"]
        if self.protocol not in valid_protocols:
            raise ValueError(f"Invalid protocol: {self.protocol}")
```

### Drop-in Merging Logic

```python
def load_hid_config(
    config_path: Optional[Path] = None,
    drop_in_dir: Optional[Path] = None,
) -> HidConfig:
    """
    Load configuration with drop-in merging.

    Drop-ins are merged in sorted filename order on top of base config.
    """
    config_path = config_path or DEFAULT_CONFIG_PATH
    drop_in_dir = drop_in_dir or DROP_IN_DIR

    parser = ConfigParser()

    # 1. Load base config (if exists)
    if config_path.exists():
        content = config_path.read_text()
        # Tolerate missing section header
        if not content.strip().startswith("["):
            content = "[DEFAULT]\n" + content
        parser.read_string(content, source=str(config_path))
        logger.info("Loaded base config: %s", config_path)

    # 2. Merge drop-ins in sorted order
    if drop_in_dir.exists():
        for drop_in in sorted(drop_in_dir.glob("*.conf")):
            content = drop_in.read_text()
            if not content.strip().startswith("["):
                content = "[DEFAULT]\n" + content
            parser.read_string(content, source=str(drop_in))
            logger.info("Merged drop-in: %s", drop_in)

    # 3. Build config from merged values
    section = "hid" if parser.has_section("hid") else "DEFAULT"

    # ... helper functions getbool, getint, getfloat, getstr ...

    return HidConfig(
        uart_device=getstr("uart_device", "/dev/serial0"),
        uart_baud=getint("uart_baud", 115200),
        # ... etc ...
    )
```

### STT Config Enhancements

Add to existing `stt_config.py`:

```python
# New tunables to add:
@dataclass
class SttConfig:
    # ... existing fields ...

    # Transport (missing from current config)
    transport_type: Optional[str] = None  # "uart", "tcp", etc.
    hid_device_id: Optional[str] = None  # From HID registry

    # Handshake & Link
    handshake_timeout: float = 10.0
    link_poll_interval: float = 5.0
    prerequisite_poll_interval: float = 30.0

    # Audio (missing from current config)
    native_sample_rate: int = 48000
    native_channels: int = 2
    whisper_sample_rate: int = 16000
    audio_config_dir: str = "/etc/dictacode/audio"
    audio_profiles_dir: str = "/etc/dictacode/audio/profiles"

    # Whisper paths
    whisper_binary: Optional[str] = None
    whisper_model: Optional[str] = None

    # Logging (file-based, complement to CLI)
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None

    # Supervisor (missing from current config)
    supervisor_enabled: bool = True
    supervisor_timeout: float = 30.0
    supervisor_ping_interval: float = 5.0

    # Compatibility
    compatibility_matrix: Optional[str] = None
```

### Path Constants Module

```python
# apps/stt/src/dictacode_stt/paths.py

import os
from pathlib import Path

# Config files
STT_CONFIG_FILE = Path(os.getenv(
    "DICTACODE_STT_CONFIG",
    "/etc/dictacode/stt.conf"
))
STT_DROP_IN_DIR = Path(os.getenv(
    "DICTACODE_STT_DROP_IN_DIR",
    "/etc/dictacode/stt.d"
))

# Audio
AUDIO_CONFIG_DIR = Path(os.getenv(
    "DICTACODE_AUDIO_CONFIG_DIR",
    "/etc/dictacode/audio"
))
AUDIO_PROFILES_DIR = Path(os.getenv(
    "DICTACODE_AUDIO_PROFILES_DIR",
    "/etc/dictacode/audio/profiles"
))

# HID registry (STT side)
HID_REGISTRY_DIR = Path(os.getenv(
    "DICTACODE_HID_REGISTRY_DIR",
    "/etc/dictacode/hid/devices.d"
))

# Compatibility matrix (search order)
COMPATIBILITY_MATRIX_PATHS = [
    os.getenv("DICTACODE_COMPATIBILITY_MATRIX"),
    "/opt/dictacode/shared/compatibility.json",
    "/etc/dictacode/compatibility.json",
    # Repo fallback for development
    Path(__file__).parents[4] / "compatibility.json",
]

# Similar module for HID: apps/hid/src/dictacode_hid/paths.py
```

### Main.py Integration

```python
# apps/stt/src/dictacode_stt/main.py (refactored)

def main() -> int:
    args = parse_args()

    # 1. Load config (base + drop-ins)
    config = load_stt_config()

    # 2. Override with env vars
    if os.getenv("DICTACODE_PROTOCOL"):
        config.protocol = os.getenv("DICTACODE_PROTOCOL")

    # 3. Override with CLI (highest precedence)
    if args.uart is not None:
        config.uart_device = args.uart
    if args.baud is not None:
        config.uart_baud = args.baud
    if args.log_level is not None:
        config.log_level = args.log_level
    # ... etc ...

    # 4. Setup logging from config
    setup_logging(
        level=config.log_level,
        format=config.log_format,
        output_file=config.log_file,
    )

    # 5. Create service with config values
    service = SttService(
        uart_device=config.uart_device,
        baud_rate=config.uart_baud,
        protocol_name=config.protocol,
        supervisor_timeout=config.supervisor_timeout,
        # ... etc ...
    )
```

---

## Package Changes

### Directory Structure

```
/etc/dictacode/                    # Created by dictacode-core
├── stt.conf                       # Conffile (STT package)
├── stt.d/                         # Drop-in dir (empty, STT package)
│   └── .gitkeep
├── hid.conf                       # Conffile (HID package)
├── hid.d/                         # Drop-in dir (empty, HID package)
│   └── .gitkeep
├── audio/                         # Audio config (STT package)
│   ├── audio.conf
│   └── profiles/
├── hid/                           # HID registry (HID package)
│   └── devices.d/
├── keymap.conf                    # Conffile (HID package)
└── compatibility.json             # Shared (core package, optional)

/opt/dictacode/shared/
└── compatibility.json             # Primary location (core package)
```

### Template Configs

**`/etc/dictacode/stt.conf`** (commented defaults):

```ini
# STT Service Configuration
# Uncomment and modify values as needed

[stt]
# Transport
# uart_device = /dev/serial0
# uart_baud = 115200
# protocol = json

# Audio
# native_sample_rate = 48000
# native_channels = 2
# whisper_sample_rate = 16000
# audio_config_dir = /etc/dictacode/audio

# Transcription
# model = tiny
# language = en
# whisper_binary =
# whisper_model =

# LLM Post-Processing
# llm_enabled = false
# llm_provider = ollama
# llm_model = llama3.2
# llm_profile = passthrough
# llm_fallback = true

# Supervisor
# supervisor_enabled = true
# supervisor_timeout = 30.0
# supervisor_ping_interval = 5.0
# handshake_timeout = 10.0

# Metrics (main service)
# metrics_enabled = false
# metrics_port = 9100

# API
# api_host = 127.0.0.1
# api_port = 8000
# api_metrics_enabled = false
# api_metrics_port = 9101

# Logging
# log_level = INFO
# log_format = %(asctime)s - %(name)s - %(levelname)s - %(message)s
# log_file =
```

**`/etc/dictacode/hid.conf`** (commented defaults):

```ini
# HID Service Configuration
# Uncomment and modify values as needed

[hid]
# Transport
# uart_device = /dev/serial0
# uart_baud = 115200
# hid_device = /dev/hidg0
# protocol = json

# Mode & Keymap
# initial_mode = normal
# initial_keymap = en_us
# keymap_config = /etc/dictacode/keymap.conf
# hid_registry_dir = /etc/dictacode/hid/devices.d

# Supervisor
# supervisor_enabled = true
# supervisor_timeout = 30.0
# supervisor_ping_interval = 5.0

# Logging
# log_level = INFO
# log_format = %(asctime)s - %(name)s - %(levelname)s - %(message)s
# log_file =
```

---

## Files to Create/Modify

### New Files (7)

1. `apps/hid/src/dictacode_hid/hid_config.py` - HID config loader
2. `apps/hid/src/dictacode_hid/paths.py` - HID path constants
3. `apps/stt/src/dictacode_stt/paths.py` - STT path constants
4. `apps/hid/tests/test_hid_config.py` - Config loader tests
5. `apps/stt/tests/test_stt_config_dropin.py` - Drop-in tests
6. `ops/packaging/debian/dictacode-stt/etc/dictacode/stt.d/.gitkeep`
7. `ops/packaging/debian/dictacode-hid/etc/dictacode/hid.d/.gitkeep`

### Modified Files (12)

1. `apps/stt/src/dictacode_stt/stt_config.py` - Add drop-in support, new fields
2. `apps/stt/src/dictacode_stt/main.py` - Use config loader with precedence
3. `apps/stt/src/dictacode_stt/service.py` - Accept config values, remove hardcoded
4. `apps/stt/src/dictacode_stt/api.py` - Use paths module
5. `apps/stt/src/dictacode_stt/api_server.py` - Use paths module
6. `apps/stt/src/dictacode_stt/audio/manager.py` - Accept config_dir parameter
7. `apps/hid/src/dictacode_hid/main.py` - Use config loader with precedence
8. `apps/hid/src/dictacode_hid/service.py` - Accept config values
9. `apps/hid/src/dictacode_hid/keymaps/base.py` - Use configurable path
10. `apps/hid/src/dictacode_hid/compatibility.py` - Use configurable search path
11. `apps/stt/src/dictacode_stt/compatibility.py` - Use configurable search path
12. `ops/packaging/build-deb.sh` - Create drop-in directories

---

## Implementation Steps

### Step 1: Create HID Config Loader

```bash
# Create hid_config.py modeled on stt_config.py
# - HidConfig dataclass with all tunables
# - load_hid_config() with drop-in merging
# - Prepend [DEFAULT] if missing section header
# - Validation in __post_init__
```

### Step 2: Add Drop-in Support to STT

```bash
# Update stt_config.py
# - Add DROP_IN_DIR constant
# - Merge drop-ins in load_stt_config()
# - Add new tunables (supervisor, audio rates, etc.)
```

### Step 3: Create Paths Modules

```bash
# Create paths.py in both apps
# - Environment variable overrides
# - Search order for compatibility matrix
# - All configurable paths
```

### Step 4: Refactor main.py (Both Apps)

```bash
# Implement precedence: CLI > env > drop-ins > base > defaults
# - Load config first
# - Apply env overrides
# - Apply CLI overrides (highest precedence)
# - Pass to service/components
```

### Step 5: Update Services

```bash
# Replace hardcoded values with config parameters
# - service.py in both apps
# - Remove magic numbers, use config.*
```

### Step 6: Update Shared Components

```bash
# AudioPortManager, API, compatibility.py
# - Accept config dir parameters
# - Use paths module constants
```

### Step 7: Packaging

```bash
# Create drop-in directories
# - /etc/dictacode/stt.d/
# - /etc/dictacode/hid.d/
# Install template configs as conffiles
```

### Step 8: Tests

```bash
# Unit tests for both loaders
# - defaults only (no file)
# - base config only
# - base + drop-ins
# - env/CLI precedence
# - invalid values (validation)
```

---

## Targeted Changes (File-by-File)

This section provides specific line references for each change. Focus on wiring precedence in main.py and loaders, centralizing paths, and eliminating hard-coded `/etc/...` in code paths.

### STT App

**`apps/stt/src/dictacode_stt/stt_config.py`**
- Lines ~10–20: Add `DROP_IN_DIR = Path("/etc/dictacode/stt.d")`
- Lines ~20–70 (SttConfig): Add missing fields:
  - `transport_type`, `hid_device_id`
  - `handshake_timeout`, `link_poll_interval`, `prerequisite_poll_interval`
  - `native_sample_rate`, `native_channels`, `whisper_sample_rate`
  - `audio_config_dir`, `audio_profiles_dir`
  - `whisper_binary`, `whisper_model`
  - `supervisor_enabled`, `supervisor_timeout`, `supervisor_ping_interval`
  - `compatibility_matrix`
  - Logging fields (`log_level`, `log_format`, `log_file`)
- Lines ~90–140 (load_stt_config): Before `parser.read`:
  - Merge drop-ins by prepending `[DEFAULT]` when needed
  - After base file, iterate `sorted(DROP_IN_DIR.glob("*.conf"))` and `read_string` each
  - Support env overrides for all fields

**`apps/stt/src/dictacode_stt/main.py`**
- Line ~180 (after argument parsing): Build `ENV_TO_CONFIG_MAP` / `CLI_TO_CONFIG_MAP` and apply overrides to loaded SttConfig (replace current ad-hoc metrics/LLM logic)
- Line ~320 (SttService construction): Replace direct uses of `args.uart`, `args.baud`, etc. with config fields
- Add optional `--log-level`/`--log-format`/`--log-file` handling via config (HID parity)

**`apps/stt/src/dictacode_stt/audio/manager.py`**
- Line ~18 (`__init__` signature): Keep `config_dir` but pull default from paths module instead of hard-coded `/etc/dictacode/audio`. Pass from main/API.

**`apps/stt/src/dictacode_stt/api.py` and `api_server.py`**
- Replace hard-coded `/etc/dictacode/audio` with constant from paths module
- If API uses AudioPortManager, pass `config_dir` from config/paths

**`apps/stt/src/dictacode_stt/compatibility.py`**
- Replace fixed list of search paths with shared search order function:
  1. override
  2. `DICTACODE_COMPATIBILITY_MATRIX` env
  3. `/opt/dictacode/shared/compatibility.json`
  4. `/etc/dictacode/compatibility.json`
  5. repo fallback

### HID App

**`apps/hid/src/dictacode_hid/hid_config.py`** (NEW FILE)
- Create `HidConfig` dataclass with ALL fields:
  - `uart_device`, `uart_baud`, `hid_device`, `protocol`
  - `initial_mode`, `initial_keymap`, `keymap_config`, `hid_registry_dir`
  - `supervisor_enabled`, `supervisor_timeout`, `supervisor_ping_interval`
  - Logging fields (`log_level`, `log_format`, `log_file`)
  - `compatibility_matrix`, `dry_run`
- Add `DEFAULT_CONFIG_PATH = Path("/etc/dictacode/hid.conf")`
- Add `DROP_IN_DIR = Path("/etc/dictacode/hid.d")`
- Implement `load_hid_config()` with `[DEFAULT]` prepend when missing and drop-in merge (sorted glob)
- Include explicit mapping tables (see below)

**`apps/hid/src/dictacode_hid/main.py`**
- Line ~60 (after parsing args): Call `load_hid_config()`, apply env/CLI overrides via explicit mapping, feed HidService constructor with config fields instead of direct args/env
- Add logging CLI flags (symmetry with STT):
```python
parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    help="Logging level")
parser.add_argument("--log-format", help="Log format string")
parser.add_argument("--log-file", help="Log to file (in addition to stderr)")
```
- Configure logging from config (replace `logging.basicConfig`):
```python
from dictacode_hid.logging_config import setup_logging
setup_logging(level=config.log_level, format=config.log_format, output_file=config.log_file)
```

**`apps/hid/src/dictacode_hid/keymaps/base.py`**
- Replace hard-coded `CONFIG_FILE = Path("/etc/dictacode/keymap.conf")` with constant from paths module

**`apps/hid/src/dictacode_hid/compatibility.py`**
- Replace fixed list of search paths with shared search order function (same as STT)

### Paths Modules (NEW FILES)

**`apps/stt/src/dictacode_stt/paths.py`** and **`apps/hid/src/dictacode_hid/paths.py`**
- Define canonical paths:
  - Config files and drop-in dirs
  - Audio config/profiles (STT)
  - HID registry (both)
  - Keymap config (HID)
  - Compatibility matrix search list
- Support env overrides for all paths
- Use these constants in files above

### Packaging

**`ops/packaging/debian/dictacode-core/`**
- Create empty `etc/dictacode/stt.d/` and `etc/dictacode/hid.d/`
- Ensure template `stt.conf`/`hid.conf` are conffiles
- Keep `opt/dictacode/shared/compatibility.json` aligned with repo checksum

---

## Concrete Specifications

### 1. Explicit Mapping Tables (Required in Both Apps)

**STT (`apps/stt/src/dictacode_stt/main.py`)**:
```python
# EXHAUSTIVE: Every CLI arg must appear here
CLI_TO_CONFIG_MAP = {
    "uart": "uart_device",
    "baud": "uart_baud",
    "transport": "transport_type",
    "hid_device": "hid_device_id",
    "duration": "chunk_duration",
    "port": "audio_port",
    "device": "audio_device",
    "audio_source": "audio_source",
    "language": "language",
    "whisper_binary": "whisper_binary",
    "whisper_model": "whisper_model",
    "streaming": "streaming_enabled",
    "no_supervisor": "supervisor_enabled",  # inverted
    "supervisor_timeout": "supervisor_timeout",
    "supervisor_ping_interval": "supervisor_ping_interval",
    "llm": "llm_provider",
    "llm_model": "llm_model",
    "profile": "llm_profile",
    "no_llm": "llm_enabled",  # inverted
    "log_level": "log_level",
    "log_format": "log_format",
    "log_file": "log_file",
    "metrics": "metrics_enabled",
    "metrics_port": "metrics_port",
    "dry_run": "dry_run",
    "once": "run_once",
}

# EXHAUSTIVE: Every env var must appear here
ENV_TO_CONFIG_MAP = {
    "DICTACODE_PROTOCOL": "protocol",
    "DICTACODE_UART_DEVICE": "uart_device",
    "DICTACODE_BAUD": "uart_baud",
    "DICTACODE_LOG_LEVEL": "log_level",
}
```

**HID (`apps/hid/src/dictacode_hid/main.py`)**:
```python
CLI_TO_CONFIG_MAP = {
    "uart": "uart_device",
    "baud": "uart_baud",
    "hid": "hid_device",
    "maintenance": "initial_mode",  # sets to "maintenance"
    "no_supervisor": "supervisor_enabled",  # inverted
    "supervisor_timeout": "supervisor_timeout",
    "supervisor_ping_interval": "supervisor_ping_interval",
    "log_level": "log_level",
    "log_format": "log_format",
    "log_file": "log_file",
    "verbose": "verbose",
    "dry_run": "dry_run",
}

ENV_TO_CONFIG_MAP = {
    "DICTACODE_PROTOCOL": "protocol",
    "DICTACODE_MODE": "initial_mode",
    "DICTACODE_KEYMAP": "initial_keymap",
}
```

### 2. Validation Policy (WARN by Default)

**Decision**: Invalid config values log WARNING and use defaults. Services start but operators see misconfigs in logs.

```python
# In both stt_config.py and hid_config.py

class ValidationPolicy:
    STRICT = "strict"   # ValueError, service won't start
    WARN = "warn"       # WARNING log, use default
    SILENT = "silent"   # DEBUG log, use default (not recommended)

DEFAULT_POLICY = ValidationPolicy.WARN

def validate_field(name: str, value: Any, validator: Callable, default: Any) -> Any:
    """Validate with explicit failure semantics."""
    if not validator(value):
        if DEFAULT_POLICY == ValidationPolicy.STRICT:
            raise ValueError(f"Invalid {name}: {value!r}")
        logger.warning("Config '%s': invalid value %r, using default %r", name, value, default)
        return default
    return value

# Usage in __post_init__:
self.uart_baud = validate_field(
    "uart_baud", self.uart_baud,
    lambda v: v in [9600, 19200, 38400, 57600, 115200, 230400],
    115200
)
```

### 3. Shared Search Order Function (Single Implementation)

**Location**: `apps/stt/src/dictacode_stt/paths.py` and `apps/hid/src/dictacode_hid/paths.py` (identical)

```python
def find_asset(
    asset_name: str,
    override: Optional[str],
    env_var: str,
    search_paths: list[str],
) -> Path:
    """
    Authoritative search order for shared assets.

    Used by: compatibility matrix, audio config, HID registry.
    """
    candidates = [
        override,
        os.getenv(env_var),
        *search_paths,
    ]
    for path in candidates:
        if path and Path(path).exists():
            logger.debug("Found %s at %s", asset_name, path)
            return Path(path)
    raise FileNotFoundError(f"{asset_name} not found. Searched: {candidates}")

# Specific asset finders
def find_compatibility_matrix(override: Optional[str] = None) -> Path:
    return find_asset(
        "compatibility matrix",
        override,
        "DICTACODE_COMPATIBILITY_MATRIX",
        [
            "/opt/dictacode/shared/compatibility.json",
            "/etc/dictacode/compatibility.json",
            str(Path(__file__).parents[4] / "compatibility.json"),  # repo
        ],
    )

def find_audio_config_dir(override: Optional[str] = None) -> Path:
    return find_asset(
        "audio config",
        override,
        "DICTACODE_AUDIO_CONFIG_DIR",
        ["/etc/dictacode/audio"],
    )

def find_hid_registry_dir(override: Optional[str] = None) -> Path:
    return find_asset(
        "HID registry",
        override,
        "DICTACODE_HID_REGISTRY_DIR",
        ["/etc/dictacode/hid/devices.d"],
    )
```

### 4. Packaging Path Alignment Check

**CI test (`tests/test_paths_match_packaging.py`)**:
```python
import subprocess
from pathlib import Path

def test_code_paths_match_deb_layout():
    """Verify paths.py constants match packaging layout."""
    from dictacode_stt.paths import CANONICAL_PATHS

    deb_layout = Path("ops/packaging/debian")

    for name, code_path in CANONICAL_PATHS.items():
        # /etc/dictacode/stt.conf → ops/packaging/debian/.../etc/dictacode/stt.conf
        if code_path.startswith("/etc/"):
            rel = code_path[1:]  # etc/dictacode/...
            # Check exists in at least one package
            found = any(
                (deb_layout / pkg / rel).exists() or
                (deb_layout / pkg / rel).is_dir()
                for pkg in ["dictacode-core", "dictacode-stt", "dictacode-hid"]
            )
            assert found, f"Path {code_path} not in deb layout"
```

**`ops/packaging/validate-artifacts.sh`** (add check):
```bash
# Verify drop-in dirs exist in built packages
for pkg in dictacode-stt dictacode-hid; do
    dpkg -c dist/${pkg}*.deb | grep -q "etc/dictacode/${pkg#dictacode-}.d/" \
        || die "Missing drop-in dir in $pkg"
done
```

---

## Implementation Priorities

**Phase 1 (Loader Refactor)**:
1. Create `hid_config.py` with full knob coverage
2. Add drop-in support to `stt_config.py`
3. Create paths modules

**Phase 2 (Path Centralization)**:
4. Replace ALL hard-coded `/etc/dictacode/...` paths with paths module constants
5. Update compatibility.py in both apps

**Phase 3 (Main Integration)**:
6. Wire precedence in both main.py files
7. Add logging config to HID

**Phase 4 (Packaging & Tests)**:
8. Update packaging for drop-in dirs
9. Minimal integration tests to prove precedence

---

## Success Criteria

All criteria met as of 2025-12-02:

1. ✅ `HidConfig` dataclass matches STT pattern
2. ✅ `load_hid_config()` supports base + drop-ins
3. ✅ `load_stt_config()` supports drop-ins
4. ✅ Both apps honor CLI > env > drop-ins > base > defaults
5. ✅ All hardcoded paths use paths.py constants
6. ✅ Environment overrides work for all paths
7. ✅ Drop-in dirs created in packages (empty)
8. ✅ Template configs installed as conffiles
9. ✅ Logging configurable from file (HID)
10. ✅ Unit tests pass for loaders (HID: 23 tests passing)
11. ⏳ CI checks conffiles present in debs (deferred)
12. ✅ Services start with config file only (no CLI required)

---

## Out of Scope (v0.3.2)

- GUI/web config editor
- Runtime config reload (requires restart)
- Config file encryption/secrets management
- Remote config fetch
- Config versioning/migration
- Schema validation beyond basic types

---

## Risk Mitigations

### 1. Runtime Wiring: Explicit CLI→Config Mapping

**Risk**: Hidden hard-codes persist if CLI/env aren't explicitly mapped to config fields.

**Mitigation**: Define exhaustive mapping tables in `main.py` for both apps.

```python
# apps/stt/src/dictacode_stt/main.py

# EXHAUSTIVE mapping: CLI arg name → config field name
CLI_TO_CONFIG_MAP = {
    # Transport
    "uart": "uart_device",
    "baud": "uart_baud",
    "transport": "transport_type",
    "hid_device": "hid_device_id",
    "protocol": "protocol",  # Also via DICTACODE_PROTOCOL env

    # Audio
    "duration": "chunk_duration",
    "port": "audio_port",
    "device": "audio_device",
    "audio_source": "audio_source",

    # Transcription
    "language": "language",
    "model": "model",
    "whisper_binary": "whisper_binary",
    "whisper_model": "whisper_model",
    "streaming": "streaming_enabled",

    # Supervisor
    "no_supervisor": "supervisor_enabled",  # Inverted
    "supervisor_timeout": "supervisor_timeout",
    "supervisor_ping_interval": "supervisor_ping_interval",

    # LLM
    "llm": "llm_provider",
    "llm_model": "llm_model",
    "profile": "llm_profile",
    "no_llm": "llm_enabled",  # Inverted
    "llm_fallback": "llm_fallback",

    # Logging
    "log_level": "log_level",
    "log_format": "log_format",
    "log_file": "log_file",

    # Metrics
    "metrics": "metrics_enabled",
    "metrics_port": "metrics_port",

    # Behavior
    "dry_run": "dry_run",
    "once": "run_once",
}

# EXHAUSTIVE mapping: env var name → config field name
ENV_TO_CONFIG_MAP = {
    "DICTACODE_PROTOCOL": "protocol",
    "DICTACODE_MODE": "initial_mode",
    "DICTACODE_KEYMAP": "initial_keymap",
    "DICTACODE_UART_DEVICE": "uart_device",
    "DICTACODE_HID_DEVICE": "hid_device",
    "DICTACODE_BAUD": "uart_baud",
    "DICTACODE_LOG_LEVEL": "log_level",
    # ... all others ...
}

def apply_overrides(config: SttConfig, args: Namespace) -> SttConfig:
    """Apply CLI and env overrides with explicit mapping."""

    # 1. Apply env overrides (lower precedence)
    for env_var, config_field in ENV_TO_CONFIG_MAP.items():
        value = os.getenv(env_var)
        if value is not None:
            setattr(config, config_field, _coerce_type(config, config_field, value))
            logger.debug("Config override from env: %s=%s", config_field, value)

    # 2. Apply CLI overrides (highest precedence)
    for cli_arg, config_field in CLI_TO_CONFIG_MAP.items():
        value = getattr(args, cli_arg, None)
        if value is not None:
            # Handle inverted flags
            if cli_arg in ("no_supervisor", "no_llm"):
                value = not value
            setattr(config, config_field, value)
            logger.debug("Config override from CLI: %s=%s", config_field, value)

    return config
```

**Validation**: CI test that asserts every CLI arg and env var appears in the mapping tables.

### 2. HID Config Coverage: Complete Knob Inventory

**Risk**: Missing CLI/env knobs leaves split control paths.

**Mitigation**: Audit current HID `main.py` and service.py to capture ALL knobs.

```python
# Complete HidConfig - ALL current CLI/env knobs covered

@dataclass
class HidConfig:
    """HID service configuration - COMPLETE knob coverage."""

    # === Transport (from main.py args) ===
    uart_device: str = "/dev/serial0"      # --uart
    uart_baud: int = 115200                 # --baud
    hid_device: str = "/dev/hidg0"          # --hid
    protocol: str = "json"                  # DICTACODE_PROTOCOL env

    # === Mode & Keymap (from main.py args + env) ===
    initial_mode: str = "normal"            # DICTACODE_MODE env, --maintenance
    initial_keymap: str = "en_us"           # DICTACODE_KEYMAP env
    keymap_config: str = "/etc/dictacode/keymap.conf"  # keymaps/base.py
    hid_registry_dir: str = "/etc/dictacode/hid/devices.d"

    # === Supervisor (from main.py args + env) ===
    supervisor_enabled: bool = True         # --no-supervisor
    supervisor_timeout: float = 30.0        # --supervisor-timeout
    supervisor_ping_interval: float = 5.0   # --supervisor-ping-interval

    # === Logging (NEW - currently not configurable) ===
    log_level: str = "INFO"                 # --log-level (add)
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None          # --log-file (add)
    verbose: bool = False                   # --verbose

    # === Behavior (from main.py args) ===
    dry_run: bool = False                   # --dry-run

    # === Compatibility ===
    compatibility_matrix: Optional[str] = None
```

**Validation**: CI test that greps HID `main.py` for `add_argument` and `os.getenv`, verifies each appears in HidConfig.

### 3. Path Consistency: Single Source of Truth

**Risk**: Path divergence between code and packaging causes runtime failures.

**Mitigation**: Shared `dictacode_common.paths` module (or identical paths.py in each app).

```python
# Canonical path definitions - IDENTICAL in both apps

# These paths MUST match:
# 1. Code defaults in paths.py
# 2. Packaging in ops/packaging/debian/*/etc/
# 3. postinst scripts
# 4. Documentation

CANONICAL_PATHS = {
    # Config files
    "stt_config": "/etc/dictacode/stt.conf",
    "hid_config": "/etc/dictacode/hid.conf",
    "stt_drop_in": "/etc/dictacode/stt.d",
    "hid_drop_in": "/etc/dictacode/hid.d",

    # Audio
    "audio_config_dir": "/etc/dictacode/audio",
    "audio_profiles_dir": "/etc/dictacode/audio/profiles",

    # HID
    "keymap_config": "/etc/dictacode/keymap.conf",
    "hid_registry_dir": "/etc/dictacode/hid/devices.d",

    # Shared
    "compatibility_matrix_primary": "/opt/dictacode/shared/compatibility.json",
    "compatibility_matrix_fallback": "/etc/dictacode/compatibility.json",
}
```

**Validation**: CI test that:
1. Greps all Python files for `/etc/dictacode` - must use paths.py constants
2. Compares paths.py values against `ops/packaging/debian/*/etc/` tree
3. Fails if any mismatch

### 4. Validation Behavior: Fail-Fast with Loud Warnings

**Risk**: Silent fallback masks misconfigurations.

**Mitigation**: Explicit validation policy with configurable strictness.

```python
class ValidationPolicy:
    """Config validation behavior."""
    STRICT = "strict"    # Raise ValueError, service won't start
    WARN = "warn"        # Log WARNING, use default
    SILENT = "silent"    # Log DEBUG, use default (NOT RECOMMENDED)

# Default policy
DEFAULT_VALIDATION_POLICY = ValidationPolicy.WARN

def validate_and_coerce(
    field_name: str,
    value: Any,
    expected_type: type,
    validator: Callable[[Any], bool],
    default: Any,
    policy: str = DEFAULT_VALIDATION_POLICY,
) -> Any:
    """Validate config value with explicit failure semantics."""

    # Type coercion
    try:
        coerced = expected_type(value)
    except (ValueError, TypeError) as e:
        msg = f"Config '{field_name}': cannot convert {value!r} to {expected_type.__name__}"
        if policy == ValidationPolicy.STRICT:
            raise ValueError(msg) from e
        elif policy == ValidationPolicy.WARN:
            logger.warning("%s - using default: %s", msg, default)
            return default
        else:
            logger.debug("%s - using default: %s", msg, default)
            return default

    # Value validation
    if not validator(coerced):
        msg = f"Config '{field_name}': invalid value {coerced!r}"
        if policy == ValidationPolicy.STRICT:
            raise ValueError(msg)
        elif policy == ValidationPolicy.WARN:
            logger.warning("%s - using default: %s", msg, default)
            return default
        else:
            logger.debug("%s - using default: %s", msg, default)
            return default

    return coerced

# Usage in __post_init__:
def __post_init__(self):
    self.uart_baud = validate_and_coerce(
        "uart_baud",
        self.uart_baud,
        int,
        lambda v: v in [9600, 19200, 38400, 57600, 115200, 230400],
        115200,
    )
```

**Policy**: Default to WARN. Services log warnings but start. Operators see misconfigs in logs.

### 5. Shared Assets: Authoritative Search Order

**Risk**: STT and HID use different search orders → version mismatches.

**Mitigation**: Single search order function, used by both apps.

```python
# dictacode_common/paths.py OR identical in both apps' paths.py

def find_compatibility_matrix(override_path: Optional[str] = None) -> Path:
    """
    Find compatibility matrix with authoritative search order.

    Order (first found wins):
    1. Explicit override (from config or CLI)
    2. DICTACODE_COMPATIBILITY_MATRIX env var
    3. /opt/dictacode/shared/compatibility.json (package install)
    4. /etc/dictacode/compatibility.json (legacy/manual)
    5. {repo}/compatibility.json (development)

    Raises:
        FileNotFoundError: If no matrix found
    """
    search_paths = [
        override_path,
        os.getenv("DICTACODE_COMPATIBILITY_MATRIX"),
        "/opt/dictacode/shared/compatibility.json",
        "/etc/dictacode/compatibility.json",
        _find_repo_root() / "compatibility.json",
    ]

    for path in search_paths:
        if path and Path(path).exists():
            logger.info("Using compatibility matrix: %s", path)
            return Path(path)

    raise FileNotFoundError(
        "Compatibility matrix not found. Searched:\n" +
        "\n".join(f"  - {p}" for p in search_paths if p)
    )
```

**Validation**: Both apps import same function OR have identical implementation with CI test.

### 6. Logging Config Symmetry

**Risk**: HID logging remains basic while STT is configurable.

**Mitigation**: HID gets identical logging config support.

```python
# apps/hid/src/dictacode_hid/logging_config.py (NEW)

import logging
import sys
from typing import Optional

def setup_logging(
    level: str = "INFO",
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    output_file: Optional[str] = None,
) -> None:
    """Configure logging for HID service (mirrors STT pattern)."""

    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers
    root_logger.handlers.clear()

    formatter = logging.Formatter(format)

    # Console/stderr handler (for journald)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Optional file handler
    if output_file:
        file_handler = logging.FileHandler(output_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
```

**CLI additions for HID**:
```python
parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
parser.add_argument("--log-format", help="Log format string")
parser.add_argument("--log-file", help="Log to file (in addition to stderr)")
```

### 7. Tests: Minimal Precedence Verification

**Risk**: Subtle precedence bugs slip through unit tests.

**Mitigation**: Keep integration tests minimal - prove precedence works, don't exercise whole service.

```python
# apps/stt/tests/test_config_loader.py

def test_precedence_chain(tmp_path):
    """Verify CLI > env > drop-in > base > defaults."""

    # Setup: base=9600, drop-in=19200, env=38400
    base_conf = tmp_path / "stt.conf"
    base_conf.write_text("[stt]\nuart_baud = 9600")

    drop_in_dir = tmp_path / "stt.d"
    drop_in_dir.mkdir()
    (drop_in_dir / "10-test.conf").write_text("uart_baud = 19200")

    # Test 1: base only
    config = load_stt_config(config_path=base_conf, drop_in_dir=Path("/nonexistent"))
    assert config.uart_baud == 9600

    # Test 2: base + drop-in
    config = load_stt_config(config_path=base_conf, drop_in_dir=drop_in_dir)
    assert config.uart_baud == 19200  # drop-in wins

    # Test 3: with env override (via monkeypatch or direct loader support)
    # apply_env_overrides(config, {"DICTACODE_BAUD": "38400"})
    # assert config.uart_baud == 38400

def test_missing_config_uses_defaults(tmp_path):
    """No config file → code defaults."""
    config = load_stt_config(config_path=tmp_path / "missing.conf")
    assert config.uart_baud == 115200  # default

def test_invalid_value_warns(tmp_path, caplog):
    """Invalid value logs WARNING, uses default."""
    bad_conf = tmp_path / "bad.conf"
    bad_conf.write_text("[stt]\nuart_baud = 99999")

    config = load_stt_config(config_path=bad_conf)
    assert config.uart_baud == 115200  # fell back
    assert "WARNING" in caplog.text
```

**Scope limit**: Unit tests for loaders only. Full service integration tests deferred.

---

## Related Documents

- `docs/FINDINGS-configurability.md` - Source analysis
- `apps/stt/src/dictacode_stt/stt_config.py` - Existing STT loader
- `docs/architecture-plan-v0.3.1.md` - LLM features (LLM config lives here)
