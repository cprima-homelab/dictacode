"""
Configuration loader for audio port abstraction.

Loads and manages device profiles and audio configuration.
"""

import configparser
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional


logger = logging.getLogger(__name__)


@dataclass
class AudioProfile:
    """Audio device profile configuration."""

    # Device matching
    match_name: Optional[str] = None
    match_port_id: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    description: str = ""

    # Audio settings
    buffer_size_seconds: float = 5.0
    overlap_seconds: float = 0.5
    target_sample_rate: int = 16000
    channels: int = 1
    dtype: str = "int16"
    chunk_size: int = 1024

    # Transcription settings
    min_duration: float = 3.0
    language: str = "en"

    # Advanced settings
    streaming_enabled: bool = True
    deduplication_enabled: bool = True
    max_overlap_words: int = 10

    @classmethod
    def from_config(
        cls, config: configparser.ConfigParser, profile_name: str = ""
    ) -> "AudioProfile":
        """Create AudioProfile from ConfigParser."""
        profile = cls()

        # Device section
        if config.has_section("device"):
            if config.has_option("device", "match_name"):
                profile.match_name = config.get("device", "match_name")
            if config.has_option("device", "match_port_id"):
                profile.match_port_id = config.get("device", "match_port_id")
            if config.has_option("device", "vendor"):
                profile.vendor = config.get("device", "vendor")
            if config.has_option("device", "model"):
                profile.model = config.get("device", "model")
            if config.has_option("device", "description"):
                profile.description = config.get("device", "description")

        # Audio section
        if config.has_section("audio"):
            if config.has_option("audio", "buffer_size_seconds"):
                profile.buffer_size_seconds = config.getfloat(
                    "audio", "buffer_size_seconds"
                )
            if config.has_option("audio", "overlap_seconds"):
                profile.overlap_seconds = config.getfloat("audio", "overlap_seconds")
            if config.has_option("audio", "target_sample_rate"):
                profile.target_sample_rate = config.getint(
                    "audio", "target_sample_rate"
                )
            if config.has_option("audio", "channels"):
                profile.channels = config.getint("audio", "channels")
            if config.has_option("audio", "dtype"):
                profile.dtype = config.get("audio", "dtype")
            if config.has_option("audio", "chunk_size"):
                profile.chunk_size = config.getint("audio", "chunk_size")

        # Transcription section
        if config.has_section("transcription"):
            if config.has_option("transcription", "min_duration"):
                profile.min_duration = config.getfloat("transcription", "min_duration")
            if config.has_option("transcription", "language"):
                profile.language = config.get("transcription", "language")

        # Advanced section
        if config.has_section("advanced"):
            if config.has_option("advanced", "streaming_enabled"):
                profile.streaming_enabled = config.getboolean(
                    "advanced", "streaming_enabled"
                )
            if config.has_option("advanced", "deduplication_enabled"):
                profile.deduplication_enabled = config.getboolean(
                    "advanced", "deduplication_enabled"
                )
            if config.has_option("advanced", "max_overlap_words"):
                profile.max_overlap_words = config.getint(
                    "advanced", "max_overlap_words"
                )

        logger.debug(f"Loaded audio profile: {profile_name} ({profile.description})")
        return profile


class AudioConfig:
    """Audio configuration manager."""

    def __init__(self, config_dir: str = "/etc/dictacode/audio"):
        """
        Initialize audio configuration.

        Args:
            config_dir: Directory containing audio.conf and profiles/
        """
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "audio.conf"
        self.profiles_dir = self.config_dir / "profiles"

        # Main configuration
        self.config = configparser.ConfigParser()
        self._loaded = False

        # Cached profiles
        self._profiles: Dict[str, AudioProfile] = {}
        self._generic_profile: Optional[AudioProfile] = None

        # Load configuration
        self.load()

    def load(self) -> bool:
        """
        Load main configuration and profiles.

        Returns:
            True if configuration loaded successfully
        """
        # Load main config if it exists
        if self.config_file.exists():
            try:
                self.config.read(self.config_file)
                logger.info(f"Loaded audio config: {self.config_file}")
                self._loaded = True
            except Exception as e:
                logger.warning(f"Failed to load {self.config_file}: {e}")
                self._loaded = False
        else:
            logger.info(f"No config file at {self.config_file}, using defaults")
            self._loaded = False

        # Load profiles
        self._load_profiles()

        return self._loaded

    def _load_profiles(self) -> None:
        """Load all device profiles from profiles directory."""
        if not self.profiles_dir.exists():
            logger.warning(f"Profiles directory not found: {self.profiles_dir}")
            return

        # Load all .conf files in profiles directory
        for profile_path in self.profiles_dir.glob("*.conf"):
            profile_name = profile_path.stem

            try:
                parser = configparser.ConfigParser()
                parser.read(profile_path)

                profile = AudioProfile.from_config(parser, profile_name)
                self._profiles[profile_name] = profile

                # Store generic profile separately
                if profile_name == "generic":
                    self._generic_profile = profile

                logger.debug(f"Loaded profile: {profile_name}")
            except Exception as e:
                logger.error(f"Failed to load profile {profile_path}: {e}")

        logger.info(f"Loaded {len(self._profiles)} audio profiles")

    def get_profile_for_port(
        self, port_id: str, port_name: str = "", port_type: str = ""
    ) -> AudioProfile:
        """
        Get the best matching profile for a port.

        Matching priority:
        1. Exact port_id match (e.g., rode-videomic-ntg)
        2. Exact device name match
        3. Vendor match (first part of port_id or name)
        4. Generic fallback

        Args:
            port_id: Port ID (e.g., "rode-videomic-ntg", "hw:0")
            port_name: Device name (e.g., "RØDE VideoMic NTG: USB Audio")
            port_type: Port type (e.g., "usb", "jack", "alsa")

        Returns:
            Matching AudioProfile (defaults to generic if no match)
        """
        # Try exact port_id match
        if port_id in self._profiles:
            logger.info(f"Matched profile by port_id: {port_id}")
            return self._profiles[port_id]

        # Try profile matching by match_port_id
        for profile_name, profile in self._profiles.items():
            if profile.match_port_id and profile.match_port_id == port_id:
                logger.info(
                    f"Matched profile {profile_name} by match_port_id: {port_id}"
                )
                return profile

        # Try profile matching by device name
        for profile_name, profile in self._profiles.items():
            if profile.match_name and profile.match_name.lower() in port_name.lower():
                logger.info(
                    f"Matched profile {profile_name} by device name: {port_name}"
                )
                return profile

        # Try vendor match (first part of hyphenated port_id)
        if "-" in port_id:
            vendor = port_id.split("-")[0]
            for profile_name, profile in self._profiles.items():
                if profile.vendor and profile.vendor.lower() == vendor.lower():
                    logger.info(f"Matched profile {profile_name} by vendor: {vendor}")
                    return profile

        # Fallback to generic
        if self._generic_profile:
            logger.info(f"Using generic profile for port: {port_id}")
            return self._generic_profile

        # Ultimate fallback: create default generic profile
        logger.warning(f"No profile found for {port_id}, using hardcoded defaults")
        return AudioProfile()

    def get_profiles(self) -> Dict[str, AudioProfile]:
        """Get all loaded profiles."""
        return self._profiles.copy()

    def get_generic_profile(self) -> AudioProfile:
        """Get the generic fallback profile."""
        if self._generic_profile:
            return self._generic_profile
        return AudioProfile()

    def reload(self) -> bool:
        """Reload configuration and profiles."""
        self._profiles.clear()
        self._generic_profile = None
        return self.load()
