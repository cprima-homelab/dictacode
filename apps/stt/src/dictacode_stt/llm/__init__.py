"""LLM post-processing package.

This package provides LLM-based text post-processing capabilities for
improving transcription quality through grammar correction, punctuation,
and formatting adjustments.

Available providers:
- Ollama (local inference)
- OpenAI (ChatGPT)
- OpenRouter (multi-model aggregator)

Example usage:
    from dictacode_stt.llm import LlmConfig, create_llm_adapter

    config = LlmConfig.for_ollama(model="llama3.2")
    adapter = create_llm_adapter(config)
    # Use adapter in PostProcessor
"""

from dictacode_stt.llm.adapter import LlmAdapter
from dictacode_stt.llm.ollama import OllamaAdapter
from dictacode_stt.llm.openai import OpenAiAdapter
from dictacode_stt.llm.openrouter import OpenRouterAdapter
from dictacode_stt.llm.types import (
    LlmConfig,
    LlmMessage,
    LlmProvider,
    LlmRequest,
    LlmResponse,
)


__all__ = [
    "LlmAdapter",
    "LlmConfig",
    "LlmMessage",
    "LlmProvider",
    "LlmRequest",
    "LlmResponse",
    "create_llm_adapter",
]


def create_llm_adapter(config: LlmConfig) -> LlmAdapter:
    """Factory function to create LLM adapter based on provider.

    Args:
        config: LLM configuration specifying provider and settings

    Returns:
        Concrete LlmAdapter instance (OllamaAdapter, OpenAiAdapter, etc.)

    Raises:
        ValueError: If provider is not supported

    Example:
        >>> config = LlmConfig.for_ollama(model="llama3.2")
        >>> adapter = create_llm_adapter(config)
        >>> # Use adapter in PostProcessor
    """
    if config.provider == LlmProvider.OLLAMA:
        return OllamaAdapter(config)
    elif config.provider == LlmProvider.OPENAI:
        return OpenAiAdapter(config)
    elif config.provider == LlmProvider.OPENROUTER:
        return OpenRouterAdapter(config)
    else:
        raise ValueError(f"Unsupported LLM provider: {config.provider}")
