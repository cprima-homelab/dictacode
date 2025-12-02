"""Processing profiles for LLM text post-processing.

Profiles define system prompts and templates for different text processing goals:
- Grammar correction
- Punctuation enhancement
- Formal/casual tone adjustment
- Code formatting
- Passthrough (no processing)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProcessingProfile:
    """Profile defining how LLM should process text.

    Attributes:
        name: Profile identifier (e.g., "grammar", "formal")
        description: Human-readable description
        system_prompt: System message defining LLM behavior
        user_template: Template for user message (use {text} placeholder)
        temperature: Override LLM temperature (None = use default)
    """

    name: str
    description: str
    system_prompt: str
    user_template: str = "Process this text:\n\n{text}"
    temperature: Optional[float] = None


# Builtin processing profiles
BUILTIN_PROFILES = {
    "grammar": ProcessingProfile(
        name="grammar",
        description="Fix grammar and spelling errors while preserving meaning",
        system_prompt="""You are a grammar and spelling correction assistant.

Your task:
- Fix grammar errors (subject-verb agreement, tenses, articles)
- Correct spelling mistakes
- Preserve the original meaning and tone
- Keep technical terms and proper nouns unchanged
- Return ONLY the corrected text, no explanations

Do not add punctuation, change capitalization, or alter sentence structure beyond fixing errors.""",
        user_template="Correct grammar and spelling:\n\n{text}",
        temperature=0.1,  # Very deterministic for grammar
    ),
    "punctuation": ProcessingProfile(
        name="punctuation",
        description="Add appropriate punctuation and capitalization",
        system_prompt="""You are a punctuation and capitalization assistant.

Your task:
- Add appropriate punctuation (periods, commas, question marks, etc.)
- Capitalize sentence beginnings and proper nouns
- Preserve the original words and meaning
- Keep technical terms unchanged
- Return ONLY the punctuated text, no explanations

Do not fix grammar, spelling, or change word order.""",
        user_template="Add punctuation and capitalization:\n\n{text}",
        temperature=0.1,
    ),
    "formal": ProcessingProfile(
        name="formal",
        description="Rewrite in formal, professional tone",
        system_prompt="""You are a professional writing assistant.

Your task:
- Rewrite text in formal, professional tone
- Use complete sentences and proper grammar
- Avoid contractions, slang, and colloquialisms
- Maintain the original meaning and key points
- Return ONLY the rewritten text, no explanations

Suitable for business emails, reports, and formal documents.""",
        user_template="Rewrite in formal tone:\n\n{text}",
        temperature=0.3,
    ),
    "casual": ProcessingProfile(
        name="casual",
        description="Rewrite in casual, conversational tone",
        system_prompt="""You are a casual writing assistant.

Your task:
- Rewrite text in casual, conversational tone
- Use contractions and natural speech patterns
- Keep it friendly and approachable
- Maintain the original meaning and key points
- Return ONLY the rewritten text, no explanations

Suitable for casual messages, social media, and informal communication.""",
        user_template="Rewrite in casual tone:\n\n{text}",
        temperature=0.4,
    ),
    "code": ProcessingProfile(
        name="code",
        description="Format code comments and documentation",
        system_prompt="""You are a code documentation assistant.

Your task:
- Fix grammar and punctuation in code comments
- Ensure proper capitalization in documentation
- Preserve code formatting, indentation, and syntax
- Keep variable names, function names, and keywords unchanged
- Return ONLY the corrected text, no explanations

Do not modify actual code, only comments and documentation.""",
        user_template="Fix code comments and docs:\n\n{text}",
        temperature=0.1,
    ),
    "passthrough": ProcessingProfile(
        name="passthrough",
        description="Return text unchanged (no LLM processing)",
        system_prompt="Return the input text exactly as provided, without any modifications.",
        user_template="{text}",
        temperature=0.0,
    ),
}


class ProfileManager:
    """Manages processing profiles (builtin + custom).

    Responsibilities:
    - Provide access to builtin profiles
    - Load custom profiles from YAML files
    - Validate profile definitions
    - Handle profile not found errors
    """

    def __init__(self, custom_profile_dir: Optional[Path] = None):
        """Initialize profile manager.

        Args:
            custom_profile_dir: Directory containing custom profile YAML files
                              (None = only use builtin profiles)
        """
        self.custom_profile_dir = custom_profile_dir
        self._custom_profiles: dict[str, ProcessingProfile] = {}

        if custom_profile_dir and custom_profile_dir.exists():
            self._load_custom_profiles()

    def get_profile(self, name: str) -> ProcessingProfile:
        """Get profile by name.

        Args:
            name: Profile name (e.g., "grammar", "formal")

        Returns:
            ProcessingProfile instance

        Raises:
            ValueError: If profile not found
        """
        # Check custom profiles first (override builtins)
        if name in self._custom_profiles:
            return self._custom_profiles[name]

        # Check builtin profiles
        if name in BUILTIN_PROFILES:
            return BUILTIN_PROFILES[name]

        # Not found
        available = list(BUILTIN_PROFILES.keys()) + list(self._custom_profiles.keys())
        raise ValueError(
            f"Profile '{name}' not found. Available: {', '.join(available)}"
        )

    def list_profiles(self) -> list[str]:
        """List all available profile names.

        Returns:
            List of profile names (builtin + custom)
        """
        return list(BUILTIN_PROFILES.keys()) + list(self._custom_profiles.keys())

    def get_builtin_profiles(self) -> dict[str, ProcessingProfile]:
        """Get all builtin profiles.

        Returns:
            Dict of builtin profiles
        """
        return BUILTIN_PROFILES.copy()

    def _load_custom_profiles(self) -> None:
        """Load custom profiles from YAML files.

        Scans custom_profile_dir for *.yaml files and loads them as profiles.
        Invalid profiles are logged and skipped.
        """
        if not self.custom_profile_dir:
            return

        if yaml is None:
            logger.warning(
                "PyYAML not installed, custom profiles disabled. "
                "Install with: pip install pyyaml"
            )
            return

        yaml_files = list(self.custom_profile_dir.glob("*.yaml")) + list(
            self.custom_profile_dir.glob("*.yml")
        )

        for yaml_file in yaml_files:
            try:
                with yaml_file.open() as f:
                    data = yaml.safe_load(f)

                if not isinstance(data, dict):
                    logger.warning(f"Invalid profile file {yaml_file}: not a dict")
                    continue

                # Validate required fields
                required = ["name", "description", "system_prompt"]
                if not all(field in data for field in required):
                    logger.warning(
                        f"Invalid profile {yaml_file}: missing required fields"
                    )
                    continue

                # Create profile
                profile = ProcessingProfile(
                    name=data["name"],
                    description=data["description"],
                    system_prompt=data["system_prompt"],
                    user_template=data.get(
                        "user_template", "Process this text:\n\n{text}"
                    ),
                    temperature=data.get("temperature"),
                )

                self._custom_profiles[profile.name] = profile
                logger.info(f"Loaded custom profile: {profile.name}")

            except Exception as e:
                logger.error(f"Failed to load profile {yaml_file}: {e}")
                continue
