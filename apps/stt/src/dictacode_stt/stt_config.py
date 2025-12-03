"""Configuration file loader for dictacode STT."""

import logging
from configparser import ConfigParser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

import yaml


logger = logging.getLogger("dictacode.config")
DEFAULT_CONFIG_PATH = Path("/etc/dictacode/stt.conf")
DROP_IN_DIR = Path("/etc/dictacode/stt.d")


class ValidationPolicy:
    """Config validation behavior."""

    STRICT = "strict"  # Raise ValueError, service won't start
    WARN = "warn"  # Log WARNING, use default
    SILENT = "silent"  # Log DEBUG, use default (not recommended)


DEFAULT_POLICY = ValidationPolicy.WARN


def validate_field(
    name: str,
    value: Any,
    validator: Callable[[Any], bool],
    default: Any,
    policy: str = DEFAULT_POLICY,
) -> Any:
    """Validate config value with explicit failure semantics."""
    if not validator(value):
        msg = f"Config '{name}': invalid value {value!r}"
        if policy == ValidationPolicy.STRICT:
            raise ValueError(msg)
        elif policy == ValidationPolicy.WARN:
            logger.warning("%s, using default %r", msg, default)
            return default
        else:
            logger.debug("%s, using default %r", msg, default)
            return default
    return value


@dataclass
class SttConfig:
    """STT service configuration with validation.

    All fields match CLI args and environment variables from main.py.
    """

    # === Prometheus metrics (main service) ===
    metrics_enabled: bool = False
    metrics_port: int = 9100

    # === API server ===
    api_host: str = "127.0.0.1"  # Secure default
    api_port: int = 8000
    api_config_dir: str = "/etc/dictacode/audio"
    api_metrics_enabled: bool = False
    api_metrics_port: int = 9101

    # === STT settings ===
    model: str = "tiny"
    language: str = "en"
    uart_device: str = "/dev/serial0"
    uart_baud: int = 115200
    chunk_duration: float = 5.0

    # === Transport (v0.3.2) ===
    transport_type: Optional[str] = None  # "uart", "tcp", etc. (--transport)
    hid_device_id: Optional[str] = None  # From HID registry (--hid-device)
    protocol: str = "json"  # DICTACODE_PROTOCOL env

    # === Handshake & Link (v0.3.2) ===
    handshake_timeout: float = 10.0
    link_poll_interval: float = 5.0
    prerequisite_poll_interval: float = 30.0

    # === Audio (v0.3.2) ===
    native_sample_rate: int = 48000
    native_channels: int = 2
    whisper_sample_rate: int = 16000
    audio_config_dir: str = "/etc/dictacode/audio"
    audio_profiles_dir: str = "/etc/dictacode/audio/profiles"
    audio_source: Optional[str] = None  # --audio-source (testing)
    audio_port: Optional[str] = None  # --port
    audio_device: Optional[str] = None  # --device

    # === Whisper paths (v0.3.2) ===
    whisper_binary: Optional[str] = None  # --whisper-binary
    whisper_model: Optional[str] = None  # --whisper-model
    streaming_enabled: bool = False  # --streaming

    # === Supervisor (v0.3.2) ===
    supervisor_enabled: bool = True  # --no-supervisor
    supervisor_timeout: float = 30.0  # --supervisor-timeout
    supervisor_ping_interval: float = 5.0  # --supervisor-ping-interval

    # === Logging (v0.3.2) ===
    log_level: str = "INFO"  # --log-level
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = None  # --log-file

    # === Behavior ===
    dry_run: bool = False  # --dry-run
    run_once: bool = False  # --once

    # === LLM post-processing (v0.2.14) ===
    llm_enabled: bool = False
    llm_provider: str = "ollama"  # "ollama", "openai", "openrouter"
    llm_model: str = "llama3.2"
    llm_profile: str = (
        "passthrough"  # "grammar", "punctuation", "formal", "casual", "code", "passthrough"
    )
    llm_fallback: bool = True  # Return original text on error
    llm_base_url: Optional[str] = None  # Override provider default URL
    llm_api_key: Optional[str] = None  # API key for openai/openrouter

    # === Compatibility (v0.3.2) ===
    compatibility_matrix: Optional[str] = None  # Override search path

    def __post_init__(self):
        """Validate configuration values using WARN policy."""
        # Validate ports
        for field_name in ["metrics_port", "api_port", "api_metrics_port"]:
            port = getattr(self, field_name)
            validated = validate_field(
                field_name,
                port,
                lambda v: isinstance(v, int) and 1 <= v <= 65535,
                9100 if "metrics" in field_name else 8000,
            )
            setattr(self, field_name, validated)

        # Validate UART baud rate
        valid_bauds = [9600, 19200, 38400, 57600, 115200, 230400]
        self.uart_baud = validate_field(
            "uart_baud",
            self.uart_baud,
            lambda v: v in valid_bauds,
            115200,
        )

        # Validate chunk_duration
        self.chunk_duration = validate_field(
            "chunk_duration",
            self.chunk_duration,
            lambda v: isinstance(v, (int, float)) and 0.1 <= v <= 60.0,
            5.0,
        )

        # Validate protocol
        valid_protocols = ["json", "msgpack"]
        self.protocol = validate_field(
            "protocol",
            self.protocol,
            lambda v: v in valid_protocols,
            "json",
        )

        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        self.log_level = validate_field(
            "log_level",
            self.log_level.upper(),
            lambda v: v in valid_levels,
            "INFO",
        )

        # Validate supervisor timeouts (positive numbers)
        self.supervisor_timeout = validate_field(
            "supervisor_timeout",
            self.supervisor_timeout,
            lambda v: isinstance(v, (int, float)) and v > 0,
            30.0,
        )
        self.supervisor_ping_interval = validate_field(
            "supervisor_ping_interval",
            self.supervisor_ping_interval,
            lambda v: isinstance(v, (int, float)) and v > 0,
            5.0,
        )

        # Validate sample rates (positive integers)
        for field_name in ["native_sample_rate", "whisper_sample_rate"]:
            rate = getattr(self, field_name)
            validated = validate_field(
                field_name,
                rate,
                lambda v: isinstance(v, int) and v > 0,
                48000 if "native" in field_name else 16000,
            )
            setattr(self, field_name, validated)

        # Security: warn if API bound to non-localhost
        if self.api_host not in ("127.0.0.1", "localhost", "::1"):
            logger.warning(
                "API host set to %s (not localhost) - ensure this is intentional!",
                self.api_host,
            )


def load_stt_config(
    config_path: Optional[Path] = None,
    drop_in_dir: Optional[Path] = None,
) -> SttConfig:
    """
    Load configuration with drop-in merging.

    Args:
        config_path: Base config file path (default: /etc/dictacode/stt.conf)
        drop_in_dir: Drop-in directory (default: /etc/dictacode/stt.d)

    Returns:
        SttConfig with validated values, or safe defaults if file missing/invalid

    Drop-ins are merged in sorted filename order on top of base config.
    Files without section headers get [DEFAULT] prepended automatically.
    """
    config_path = config_path or DEFAULT_CONFIG_PATH
    drop_in_dir = drop_in_dir or DROP_IN_DIR

    parser = ConfigParser()

    # 1. Load base config (if exists)
    if config_path.exists():
        try:
            content = config_path.read_text()
            # Tolerate missing section header
            if content.strip() and not content.strip().startswith("["):
                content = "[DEFAULT]\n" + content
            parser.read_string(content, source=str(config_path))
            logger.info("Loaded base config: %s", config_path)
        except Exception as e:
            logger.warning("Failed to read base config %s: %s", config_path, e)
    else:
        logger.debug("Base config not found: %s, using defaults", config_path)

    # 2. Merge drop-ins in sorted order
    if drop_in_dir.exists() and drop_in_dir.is_dir():
        for drop_in in sorted(drop_in_dir.glob("*.conf")):
            try:
                content = drop_in.read_text()
                if content.strip() and not content.strip().startswith("["):
                    content = "[DEFAULT]\n" + content
                parser.read_string(content, source=str(drop_in))
                logger.info("Merged drop-in: %s", drop_in)
            except Exception as e:
                logger.warning("Failed to read drop-in %s: %s", drop_in, e)

    # 3. Build config from merged values
    section = "stt" if parser.has_section("stt") else "DEFAULT"

    # Helper functions with validation logging
    def getbool(key: str, default: bool) -> bool:
        try:
            return parser.getboolean(section, key, fallback=default)
        except ValueError as e:
            logger.warning("Invalid boolean for %s: %s, using default %s", key, e, default)
            return default

    def getint(key: str, default: int) -> int:
        try:
            return parser.getint(section, key, fallback=default)
        except ValueError as e:
            logger.warning("Invalid integer for %s: %s, using default %s", key, e, default)
            return default

    def getfloat(key: str, default: float) -> float:
        try:
            return parser.getfloat(section, key, fallback=default)
        except ValueError as e:
            logger.warning("Invalid float for %s: %s, using default %s", key, e, default)
            return default

    def getstr(key: str, default: str) -> str:
        return parser.get(section, key, fallback=default)

    def getstr_optional(key: str) -> Optional[str]:
        val = parser.get(section, key, fallback=None)
        return val if val else None

    try:
        config = SttConfig(
            # Metrics
            metrics_enabled=getbool("metrics_enabled", False),
            metrics_port=getint("metrics_port", 9100),
            # API
            api_host=getstr("api_host", "127.0.0.1"),
            api_port=getint("api_port", 8000),
            api_config_dir=getstr("api_config_dir", "/etc/dictacode/audio"),
            api_metrics_enabled=getbool("api_metrics_enabled", False),
            api_metrics_port=getint("api_metrics_port", 9101),
            # STT
            model=getstr("model", "tiny"),
            language=getstr("language", "en"),
            uart_device=getstr("uart_device", "/dev/serial0"),
            uart_baud=getint("uart_baud", 115200),
            chunk_duration=getfloat("chunk_duration", 5.0),
            # Transport (v0.3.2)
            transport_type=getstr_optional("transport_type"),
            hid_device_id=getstr_optional("hid_device_id"),
            protocol=getstr("protocol", "json"),
            # Handshake & Link (v0.3.2)
            handshake_timeout=getfloat("handshake_timeout", 10.0),
            link_poll_interval=getfloat("link_poll_interval", 5.0),
            prerequisite_poll_interval=getfloat("prerequisite_poll_interval", 30.0),
            # Audio (v0.3.2)
            native_sample_rate=getint("native_sample_rate", 48000),
            native_channels=getint("native_channels", 2),
            whisper_sample_rate=getint("whisper_sample_rate", 16000),
            audio_config_dir=getstr("audio_config_dir", "/etc/dictacode/audio"),
            audio_profiles_dir=getstr("audio_profiles_dir", "/etc/dictacode/audio/profiles"),
            audio_source=getstr_optional("audio_source"),
            audio_port=getstr_optional("audio_port"),
            audio_device=getstr_optional("audio_device"),
            # Whisper (v0.3.2)
            whisper_binary=getstr_optional("whisper_binary"),
            whisper_model=getstr_optional("whisper_model"),
            streaming_enabled=getbool("streaming_enabled", False),
            # Supervisor (v0.3.2)
            supervisor_enabled=getbool("supervisor_enabled", True),
            supervisor_timeout=getfloat("supervisor_timeout", 30.0),
            supervisor_ping_interval=getfloat("supervisor_ping_interval", 5.0),
            # Logging (v0.3.2)
            log_level=getstr("log_level", "INFO"),
            log_format=getstr(
                "log_format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
            log_file=getstr_optional("log_file"),
            # Behavior
            dry_run=getbool("dry_run", False),
            run_once=getbool("run_once", False),
            # LLM post-processing (v0.2.14)
            llm_enabled=getbool("llm_enabled", False),
            llm_provider=getstr("llm_provider", "ollama"),
            llm_model=getstr("llm_model", "llama3.2"),
            llm_profile=getstr("llm_profile", "passthrough"),
            llm_fallback=getbool("llm_fallback", True),
            llm_base_url=getstr_optional("llm_base_url"),
            llm_api_key=getstr_optional("llm_api_key"),
            # Compatibility (v0.3.2)
            compatibility_matrix=getstr_optional("compatibility_matrix"),
        )

        logger.debug("Configuration loaded: %s", config)
        # Validation happens in __post_init__
        return config

    except ValueError as e:
        logger.error("Configuration validation failed: %s", e)
        logger.error("Falling back to safe defaults")
        return SttConfig()
    except Exception as e:
        logger.error("Failed to build config: %s", e)
        logger.error("Falling back to safe defaults")
        return SttConfig()


# =============================================================================
# Pipeline Profiles (v0.3.10)
# =============================================================================

PROFILES_DIR = Path(__file__).parent / "profiles"  # Packaged profiles
USER_PROFILES_DIR = Path("/etc/dictacode/stt.d/profiles")  # User drop-ins


@dataclass
class AudioConfig:
    """Audio source configuration for pipeline profile."""

    source: str = "mic"  # mic | file | directory
    port: str = "auto"  # Audio port ID or "auto"
    path: Optional[Union[List[str], str]] = None  # For file source (list of paths) or directory source (single path)
    pattern: str = "*.wav"  # Glob pattern for directory source


@dataclass
class AsrConfig:
    """ASR (transcription) configuration for pipeline profile."""

    backend: str = "whisper"  # whisper | vosk
    model: str = "tiny"  # tiny | base | small | medium | large
    language: str = "en"
    # Paths: None = auto-detect from common locations
    binary_path: Optional[str] = None  # ~/whisper.cpp/build/bin/whisper-cli
    model_path: Optional[str] = None  # ~/whisper.cpp/models/ggml-{model}.bin
    # Sample rates: None = auto-detect from device/transcriber
    native_sample_rate: Optional[int] = None  # Mic capture rate (auto-detect)
    whisper_sample_rate: Optional[int] = None  # Transcriber rate (default: 16000)
    native_channels: Optional[int] = None  # Mic channels (auto-detect)


@dataclass
class LlmConfig:
    """LLM post-processing configuration for pipeline profile."""

    enabled: bool = False
    provider: Optional[str] = None  # ollama | openai | openrouter
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


@dataclass
class TransportConfig:
    """Transport configuration for pipeline profile."""

    type: str = "uart"  # uart | wifi | null
    device: str = "/dev/serial0"  # For uart
    host: Optional[str] = None  # For wifi
    port: Optional[int] = None  # For wifi


def _find_whisper_binary(custom_path: Optional[str] = None) -> Optional[Path]:
    """Find whisper-cli binary in common locations."""
    if custom_path:
        p = Path(custom_path)
        return p if p.exists() else None

    candidates = [
        Path.home() / "whisper.cpp" / "build" / "bin" / "whisper-cli",
        Path("/opt/whisper/whisper-cli"),
        Path("/usr/local/bin/whisper-cli"),
        Path("/usr/bin/whisper-cli"),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _find_whisper_model(custom_path: Optional[str] = None, model: str = "tiny") -> Optional[Path]:
    """Find whisper model in common locations."""
    if custom_path:
        p = Path(custom_path)
        return p if p.exists() else None

    # Try model-specific names
    model_names = [f"ggml-{model}.bin", f"ggml-{model}.en.bin"]
    search_dirs = [
        Path.home() / "whisper.cpp" / "models",
        Path("/opt/whisper/models"),
        Path("/usr/share/whisper/models"),
    ]

    for d in search_dirs:
        if d.exists():
            for name in model_names:
                p = d / name
                if p.exists():
                    return p
    return None


@dataclass
class PipelineProfile:
    """Complete pipeline configuration profile."""

    name: str
    description: str = ""
    audio: AudioConfig = field(default_factory=AudioConfig)
    asr: AsrConfig = field(default_factory=AsrConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    transport: TransportConfig = field(default_factory=TransportConfig)

    def validate(self) -> List[str]:
        """Validate profile configuration. Returns list of errors."""
        errors = []

        # Validate audio source
        if self.audio.source not in ("mic", "file", "directory"):
            errors.append(f"Invalid audio.source: {self.audio.source}")

        # File/directory sources require path
        if self.audio.source in ("file", "directory") and not self.audio.path:
            errors.append(f"audio.path required for source={self.audio.source}")

        # Validate files exist for file source
        if self.audio.source == "file" and self.audio.path:
            paths = self.audio.path if isinstance(self.audio.path, list) else [self.audio.path]
            for p in paths:
                if not Path(p).exists():
                    errors.append(f"audio.path does not exist: {p}")

        # Validate directory exists for directory source
        if self.audio.source == "directory" and self.audio.path:
            dir_path = self.audio.path if isinstance(self.audio.path, str) else self.audio.path[0]
            if not Path(dir_path).is_dir():
                errors.append(f"audio.path is not a directory: {dir_path}")

        # Validate ASR backend
        if self.asr.backend not in ("whisper", "vosk"):
            errors.append(f"Invalid asr.backend: {self.asr.backend}")

        # Validate whisper paths when backend=whisper
        if self.asr.backend == "whisper":
            binary = _find_whisper_binary(self.asr.binary_path)
            if not binary:
                searched = self.asr.binary_path or "~/whisper.cpp/build/bin/whisper-cli, /opt/whisper/, /usr/local/bin/, /usr/bin/"
                errors.append(f"whisper binary not found (searched: {searched})")

            model = _find_whisper_model(self.asr.model_path, self.asr.model)
            if not model:
                searched = self.asr.model_path or f"~/whisper.cpp/models/ggml-{self.asr.model}.bin, /opt/whisper/models/"
                errors.append(f"whisper model not found (searched: {searched})")

        # Validate transport type
        if self.transport.type not in ("uart", "wifi", "null"):
            errors.append(f"Invalid transport.type: {self.transport.type}")

        return errors


def _load_profile_from_yaml(path: Path) -> Optional[PipelineProfile]:
    """Load a single profile from YAML file."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or not isinstance(data, dict):
            logger.warning("Invalid profile YAML: %s", path)
            return None

        # Build nested dataclasses
        audio = AudioConfig(**data.get("audio", {})) if "audio" in data else AudioConfig()
        asr = AsrConfig(**data.get("asr", {})) if "asr" in data else AsrConfig()
        llm = LlmConfig(**data.get("llm", {})) if "llm" in data else LlmConfig()
        transport = (
            TransportConfig(**data.get("transport", {}))
            if "transport" in data
            else TransportConfig()
        )

        profile = PipelineProfile(
            name=data.get("name", path.stem),
            description=data.get("description", ""),
            audio=audio,
            asr=asr,
            llm=llm,
            transport=transport,
        )

        # Validate
        errors = profile.validate()
        if errors:
            logger.warning("Profile %s has validation errors: %s", path, errors)

        return profile

    except Exception as e:
        logger.warning("Failed to load profile %s: %s", path, e)
        return None


def load_profiles(
    packaged_dir: Optional[Path] = None,
    user_dir: Optional[Path] = None,
) -> Dict[str, PipelineProfile]:
    """
    Load all available profiles from packaged and user directories.

    User profiles override packaged profiles with the same name.

    Returns:
        Dict mapping profile name to PipelineProfile
    """
    packaged_dir = packaged_dir or PROFILES_DIR
    user_dir = user_dir or USER_PROFILES_DIR

    profiles: Dict[str, PipelineProfile] = {}

    # Load packaged profiles first
    if packaged_dir.exists() and packaged_dir.is_dir():
        for yaml_file in sorted(packaged_dir.glob("*.yaml")):
            profile = _load_profile_from_yaml(yaml_file)
            if profile:
                profiles[profile.name] = profile
                logger.debug("Loaded packaged profile: %s", profile.name)

    # Load user profiles (override packaged)
    if user_dir.exists() and user_dir.is_dir():
        for yaml_file in sorted(user_dir.glob("*.yaml")):
            profile = _load_profile_from_yaml(yaml_file)
            if profile:
                if profile.name in profiles:
                    logger.info("User profile overrides packaged: %s", profile.name)
                profiles[profile.name] = profile
                logger.debug("Loaded user profile: %s", profile.name)

    logger.info("Loaded %d profiles", len(profiles))
    return profiles


def get_profile(name: str, profiles: Optional[Dict[str, PipelineProfile]] = None) -> Optional[PipelineProfile]:
    """Get a profile by name, loading profiles if not provided."""
    if profiles is None:
        profiles = load_profiles()
    return profiles.get(name)


def get_default_profile() -> PipelineProfile:
    """Return the default profile (mic + whisper + uart)."""
    return PipelineProfile(
        name="default",
        description="Standard mic input with local whisper transcription via UART",
        audio=AudioConfig(source="mic", port="auto"),
        asr=AsrConfig(backend="whisper", model="tiny", language="en"),
        llm=LlmConfig(enabled=False),
        transport=TransportConfig(type="uart", device="/dev/serial0"),
    )
