"""Tests for LLM types and configuration (v0.3.1)."""

import pytest

from dictacode_stt.llm.types import (
    LlmConfig,
    LlmMessage,
    LlmProvider,
    LlmRequest,
    LlmResponse,
)


class TestLlmProvider:
    """Test LlmProvider enum."""

    def test_provider_values(self):
        """Test provider enum values."""
        assert LlmProvider.OLLAMA.value == "ollama"
        assert LlmProvider.OPENAI.value == "openai"
        assert LlmProvider.OPENROUTER.value == "openrouter"

    def test_provider_from_string(self):
        """Test creating provider from string."""
        assert LlmProvider("ollama") == LlmProvider.OLLAMA
        assert LlmProvider("openai") == LlmProvider.OPENAI
        assert LlmProvider("openrouter") == LlmProvider.OPENROUTER


class TestLlmMessage:
    """Test LlmMessage dataclass."""

    def test_message_creation(self):
        """Test creating a message."""
        msg = LlmMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_roles(self):
        """Test different message roles."""
        system = LlmMessage(role="system", content="You are a helpful assistant")
        user = LlmMessage(role="user", content="Hello")
        assistant = LlmMessage(role="assistant", content="Hi there!")

        assert system.role == "system"
        assert user.role == "user"
        assert assistant.role == "assistant"


class TestLlmRequest:
    """Test LlmRequest dataclass."""

    def test_request_creation(self):
        """Test creating a request with defaults."""
        messages = (LlmMessage(role="user", content="Test"),)
        request = LlmRequest(messages=messages, model="gpt-4o-mini")

        assert request.messages == messages
        assert request.model == "gpt-4o-mini"
        assert request.temperature == 0.3  # default
        assert request.max_tokens == 500  # default

    def test_request_with_custom_params(self):
        """Test creating a request with custom parameters."""
        messages = (LlmMessage(role="user", content="Test"),)
        request = LlmRequest(
            messages=messages,
            model="llama3.2",
            temperature=0.7,
            max_tokens=1000,
        )

        assert request.temperature == 0.7
        assert request.max_tokens == 1000

    def test_request_with_multiple_messages(self):
        """Test request with message sequence."""
        messages = (
            LlmMessage(role="system", content="You are helpful"),
            LlmMessage(role="user", content="Hello"),
            LlmMessage(role="assistant", content="Hi!"),
            LlmMessage(role="user", content="How are you?"),
        )
        request = LlmRequest(messages=messages, model="gpt-4o-mini")

        assert len(request.messages) == 4
        assert request.messages[0].role == "system"
        assert request.messages[-1].content == "How are you?"


class TestLlmResponse:
    """Test LlmResponse dataclass."""

    def test_successful_response(self):
        """Test successful response."""
        response = LlmResponse(
            text="Generated text",
            model="gpt-4o-mini",
            tokens_used=42,
            latency_ms=150,
        )

        assert response.text == "Generated text"
        assert response.model == "gpt-4o-mini"
        assert response.tokens_used == 42
        assert response.latency_ms == 150
        assert response.error is None
        assert response.success is True

    def test_error_response(self):
        """Test error response."""
        response = LlmResponse(
            text="",
            model="gpt-4o-mini",
            error="API key invalid",
        )

        assert response.text == ""
        assert response.error == "API key invalid"
        assert response.success is False

    def test_empty_text_response(self):
        """Test response with empty text."""
        response = LlmResponse(
            text="",
            model="gpt-4o-mini",
        )

        # Empty text with no error should still be considered failed
        assert response.success is False

    def test_response_with_usage_dict(self):
        """Test response with token usage dictionary."""
        response = LlmResponse(
            text="Result",
            model="llama3.2",
            tokens_used=100,
        )

        assert response.tokens_used == 100


class TestLlmConfig:
    """Test LlmConfig dataclass."""

    def test_config_creation(self):
        """Test creating a config."""
        config = LlmConfig(
            provider=LlmProvider.OLLAMA,
            model="llama3.2",
        )

        assert config.provider == LlmProvider.OLLAMA
        assert config.model == "llama3.2"
        assert config.base_url is None
        assert config.api_key is None

    def test_config_with_api_key(self):
        """Test config with API key."""
        config = LlmConfig(
            provider=LlmProvider.OPENAI,
            model="gpt-4o-mini",
            api_key="sk-test-key",
        )

        assert config.provider == LlmProvider.OPENAI
        assert config.api_key == "sk-test-key"

    def test_config_with_custom_url(self):
        """Test config with custom base URL."""
        config = LlmConfig(
            provider=LlmProvider.OLLAMA,
            model="llama3.2",
            base_url="http://192.168.1.100:11434",
        )

        assert config.base_url == "http://192.168.1.100:11434"

    def test_config_factory_ollama(self):
        """Test for_ollama factory method."""
        config = LlmConfig.for_ollama(model="llama3.2:3b")

        assert config.provider == LlmProvider.OLLAMA
        assert config.model == "llama3.2:3b"
        assert config.base_url == "http://localhost:11434"

    def test_config_factory_ollama_custom_url(self):
        """Test for_ollama with custom URL."""
        config = LlmConfig.for_ollama(
            model="llama3.2",
            base_url="http://server:11434",
        )

        assert config.base_url == "http://server:11434"

    def test_config_factory_openai(self):
        """Test for_openai factory method."""
        config = LlmConfig.for_openai(api_key="sk-test")

        assert config.provider == LlmProvider.OPENAI
        assert config.model == "gpt-4o-mini"  # default
        assert config.api_key == "sk-test"
        assert config.base_url == "https://api.openai.com/v1"

    def test_config_factory_openai_custom_model(self):
        """Test for_openai with custom model."""
        config = LlmConfig.for_openai(
            model="gpt-4o",
            api_key="sk-test",
        )

        assert config.model == "gpt-4o"

    def test_config_factory_openrouter(self):
        """Test for_openrouter factory method."""
        config = LlmConfig.for_openrouter(api_key="sk-or-test")

        assert config.provider == LlmProvider.OPENROUTER
        assert config.model == "meta-llama/llama-3.2-3b-instruct"  # default
        assert config.api_key == "sk-or-test"
        assert config.base_url == "https://openrouter.ai/api/v1"

    def test_config_immutability(self):
        """Test that config is frozen (immutable)."""
        config = LlmConfig(
            provider=LlmProvider.OLLAMA,
            model="llama3.2",
        )

        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            config.model = "different-model"
