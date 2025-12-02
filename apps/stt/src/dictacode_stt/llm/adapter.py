"""LLM adapter abstract base class.

Follows the Adapter pattern like TranscriptionAdapter, allowing swapping
between Ollama, OpenAI, OpenRouter, and future providers.
"""

from abc import ABC, abstractmethod

from dictacode_stt.llm.types import LlmConfig, LlmRequest, LlmResponse


class LlmAdapter(ABC):
    """Abstract LLM provider interface.

    Provides a unified interface for text post-processing via different
    LLM providers (Ollama, OpenAI, OpenRouter, etc.).

    Implementations must handle:
    - Provider-specific API calls
    - Request/response format conversion
    - Error handling and retries
    - Timeout management
    """

    def __init__(self, config: LlmConfig):
        """Initialize adapter with configuration.

        Args:
            config: LLM configuration (model, API key, etc.)
        """
        self.config = config

    @abstractmethod
    def get_name(self) -> str:
        """Return provider name (e.g., 'ollama', 'openai', 'openrouter')."""
        pass

    @abstractmethod
    async def process(self, request: LlmRequest) -> LlmResponse:
        """Process text via LLM.

        Args:
            request: LLM request with messages, model, temperature

        Returns:
            LlmResponse with processed text or error

        Note:
            This is an async method because all LLM APIs are HTTP-based.
            The service will use asyncio.run() to call this from sync code.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available.

        Returns:
            True if provider is reachable (API key valid, server running, etc.)

        Note:
            For local providers (Ollama), check if server is running.
            For cloud providers (OpenAI/OpenRouter), check if API key is set.
        """
        pass

    def supports_streaming(self) -> bool:
        """Return True if adapter supports streaming responses.

        Returns:
            False by default (streaming not implemented in v0.2.14)

        Note:
            Streaming support may be added in future versions for real-time
            text correction as user dictates.
        """
        return False

    def get_default_model(self) -> str:
        """Return provider's recommended default model.

        Returns:
            Model identifier string

        Note:
            Subclasses can override this to provide sensible defaults.
        """
        return self.config.model
