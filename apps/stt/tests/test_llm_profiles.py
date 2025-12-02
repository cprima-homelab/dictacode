"""Tests for LLM processing profiles (v0.3.1)."""

import pytest
from pathlib import Path
from dictacode_stt.llm.profiles import (
    BUILTIN_PROFILES,
    ProcessingProfile,
    ProfileManager,
)


class TestProcessingProfile:
    """Test ProcessingProfile dataclass."""

    def test_profile_creation(self):
        """Test creating a processing profile."""
        profile = ProcessingProfile(
            name="test",
            description="Test profile",
            system_prompt="You are a test assistant",
            user_template="Process: {text}",
            temperature=0.5,
        )

        assert profile.name == "test"
        assert profile.description == "Test profile"
        assert profile.system_prompt == "You are a test assistant"
        assert profile.user_template == "Process: {text}"
        assert profile.temperature == 0.5

    def test_profile_immutability(self):
        """Test that profiles are frozen (immutable)."""
        profile = ProcessingProfile(
            name="test",
            description="Test",
            system_prompt="Test",
        )

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            profile.name = "modified"


class TestBuiltinProfiles:
    """Test builtin processing profiles."""

    def test_builtin_profiles_exist(self):
        """Test that all expected builtin profiles exist."""
        expected_profiles = [
            "grammar",
            "punctuation",
            "formal",
            "casual",
            "code",
            "passthrough",
        ]

        for profile_name in expected_profiles:
            assert profile_name in BUILTIN_PROFILES

    def test_grammar_profile(self):
        """Test grammar correction profile."""
        profile = BUILTIN_PROFILES["grammar"]

        assert profile.name == "grammar"
        assert "grammar" in profile.description.lower()
        assert len(profile.system_prompt) > 0
        assert "{text}" in profile.user_template
        assert profile.temperature == 0.1  # Very deterministic

    def test_punctuation_profile(self):
        """Test punctuation profile."""
        profile = BUILTIN_PROFILES["punctuation"]

        assert profile.name == "punctuation"
        assert "punctuation" in profile.description.lower()
        assert profile.temperature == 0.1

    def test_formal_profile(self):
        """Test formal writing profile."""
        profile = BUILTIN_PROFILES["formal"]

        assert profile.name == "formal"
        assert "formal" in profile.description.lower()
        assert profile.temperature == 0.3

    def test_casual_profile(self):
        """Test casual writing profile."""
        profile = BUILTIN_PROFILES["casual"]

        assert profile.name == "casual"
        assert "casual" in profile.description.lower()
        assert profile.temperature == 0.4

    def test_code_profile(self):
        """Test code formatting profile."""
        profile = BUILTIN_PROFILES["code"]

        assert profile.name == "code"
        assert "code" in profile.description.lower()
        assert profile.temperature == 0.1

    def test_passthrough_profile(self):
        """Test passthrough (no processing) profile."""
        profile = BUILTIN_PROFILES["passthrough"]

        assert profile.name == "passthrough"
        assert profile.user_template == "{text}"
        assert profile.temperature == 0.0


class TestProfileManager:
    """Test ProfileManager."""

    def test_manager_initialization(self):
        """Test creating a profile manager."""
        manager = ProfileManager()

        assert manager is not None

    def test_manager_with_custom_dir(self):
        """Test manager with custom profile directory."""
        manager = ProfileManager(custom_profile_dir=Path("/tmp/profiles"))

        # Should not fail even if directory doesn't exist
        assert manager is not None

    def test_get_builtin_profile(self):
        """Test getting builtin profile."""
        manager = ProfileManager()

        profile = manager.get_profile("grammar")

        assert profile.name == "grammar"
        assert profile == BUILTIN_PROFILES["grammar"]

    def test_get_all_builtin_profiles(self):
        """Test getting all builtin profiles."""
        manager = ProfileManager()

        profiles = ["grammar", "punctuation", "formal", "casual", "code", "passthrough"]

        for profile_name in profiles:
            profile = manager.get_profile(profile_name)
            assert profile.name == profile_name

    def test_get_nonexistent_profile(self):
        """Test getting a profile that doesn't exist."""
        manager = ProfileManager()

        with pytest.raises(ValueError) as exc_info:
            manager.get_profile("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert "Available" in str(exc_info.value)

    def test_list_profiles(self):
        """Test listing available profiles."""
        manager = ProfileManager()

        profiles = manager.list_profiles()

        assert "grammar" in profiles
        assert "punctuation" in profiles
        assert "formal" in profiles
        assert "casual" in profiles
        assert "code" in profiles
        assert "passthrough" in profiles

    def test_get_builtin_profiles(self):
        """Test getting all builtin profiles."""
        manager = ProfileManager()

        builtins = manager.get_builtin_profiles()

        assert "grammar" in builtins
        assert len(builtins) == len(BUILTIN_PROFILES)

    def test_profile_manager_without_yaml(self, tmp_path, monkeypatch):
        """Test profile manager when PyYAML is not available."""
        # Create a temp dir with a YAML file
        profile_dir = tmp_path / "profiles"
        profile_dir.mkdir()

        yaml_file = profile_dir / "test.yaml"
        yaml_file.write_text("name: test\ndescription: Test\nsystem_prompt: Test")

        # Mock yaml to be None (simulating PyYAML not installed)
        import dictacode_stt.llm.profiles as profiles_module
        original_yaml = profiles_module.yaml
        profiles_module.yaml = None

        try:
            manager = ProfileManager(custom_profile_dir=profile_dir)
            # Should still work, just not load custom profiles
            profiles = manager.list_profiles()
            # Should only have builtin profiles
            assert all(p in BUILTIN_PROFILES for p in profiles)
        finally:
            # Restore yaml
            profiles_module.yaml = original_yaml
