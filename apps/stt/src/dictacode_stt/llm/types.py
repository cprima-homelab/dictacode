"""Data types for LLM post-processing.

This module defines the core types used for LLM-based text post-processing:
- LlmProvider: Enum of supported LLM providers
- LlmMessage: Single message in conversation history
- LlmRequest: Request to LLM for text processing
- LlmResponse: Response from LLM adapter
- LlmConfig: Configuration for LLM adapters
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class LlmProvider(str, Enum):
    """Supported LLM providers.

    Attributes:
        OLLAMA: Local LLM via Ollama API (http://localhost:11434)
        OPENAI: OpenAI's ChatGPT API (api.openai.com)
        OPENROUTER: OpenRouter aggregator (openrouter.ai)
    """

    OLLAMA = "ollama"
    OPENAI = "openai"
    OPENROUTER = "openrouter"


@dataclass(frozen=True)
class LlmMessage:
    """Single message in LLM conversation.

    Attributes:
        role: Message role ("system", "user", "assistant")
        content: Message text content
    """

    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass(frozen=True)
class LlmRequest:
    """Request to LLM for text processing.

    Attributes:
        messages: Conversation history (system prompt + user message)
        model: LLM model identifier (e.g., "llama3.2", "gpt-4o-mini")
        temperature: Sampling temperature (0.0-2.0, lower = more deterministic)
        max_tokens: Maximum tokens in response
    """

    messages: tuple[LlmMessage, ...]
    model: str
    temperature: float = 0.3  # Low for deterministic text correction
    max_tokens: int = 500


@dataclass(frozen=True)
class LlmResponse:
    """Response from LLM adapter.

    Attributes:
        text: Processed text output
        model: Model that generated response
        tokens_used: Total tokens consumed (prompt + completion)
        error: Error message if request failed
    """

    text: str
    model: str
    tokens_used: Optional[int] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if request succeeded."""
        return self.error is None


@dataclass(frozen=True)
class LlmConfig:
    """Configuration for LLM adapter.

    Attributes:
        provider: LLM provider to use
        model: Model identifier (provider-specific)
        base_url: API base URL (None = use provider default)
        api_key: API key for authentication (None = no auth)
        timeout: Request timeout in seconds
        max_retries: Maximum retry attempts on transient failures
    """

    provider: LlmProvider
    model: str
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    timeout: float = 30.0
    max_retries: int = 2

    @classmethod
    def for_ollama(
        cls, model: str = "llama3.2", base_url: str = "http://localhost:11434"
    ) -> "LlmConfig":
        """Create config for Ollama provider.

        Args:
            model: Ollama model name (default: "llama3.2")
            base_url: Ollama API URL (default: "http://localhost:11434")

        Returns:
            LlmConfig configured for Ollama
        """
        return cls(
            provider=LlmProvider.OLLAMA,
            model=model,
            base_url=base_url,
            api_key=None,  # Ollama doesn't require auth
        )

    @classmethod
    def for_openai(cls, model: str = "gpt-4o-mini", api_key: str = "") -> "LlmConfig":
        """Create config for OpenAI provider.

        Args:
            model: OpenAI model name (default: "gpt-4o-mini")
            api_key: OpenAI API key (required)

        Returns:
            LlmConfig configured for OpenAI
        """
        return cls(
            provider=LlmProvider.OPENAI,
            model=model,
            base_url="https://api.openai.com/v1",
            api_key=api_key,
        )

    @classmethod
    def for_openrouter(
        cls, model: str = "anthropic/claude-3.5-sonnet", api_key: str = ""
    ) -> "LlmConfig":
        """Create config for OpenRouter provider.

        Args:
            model: OpenRouter model identifier (default: "anthropic/claude-3.5-sonnet")
            api_key: OpenRouter API key (required)

        Returns:
            LlmConfig configured for OpenRouter
        """
        return cls(
            provider=LlmProvider.OPENROUTER,
            model=model,
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
