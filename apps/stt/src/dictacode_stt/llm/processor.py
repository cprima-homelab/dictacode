"""PostProcessor for LLM-based text processing.

Combines LlmAdapter + ProcessingProfile to transform transcribed text.
"""

import asyncio
import logging

from dictacode_stt.llm.adapter import LlmAdapter
from dictacode_stt.llm.profiles import ProcessingProfile
from dictacode_stt.llm.types import LlmMessage, LlmRequest, LlmResponse


logger = logging.getLogger(__name__)


class PostProcessor:
    """LLM-based text post-processor.

    Combines an LLM adapter with a processing profile to transform text
    according to specific goals (grammar, punctuation, tone, etc.).

    This class bridges sync and async code:
    - The service calls process() synchronously
    - PostProcessor uses asyncio.run() to call adapter.process() asynchronously
    """

    def __init__(
        self,
        adapter: LlmAdapter,
        profile: ProcessingProfile,
        fallback_on_error: bool = True,
    ):
        """Initialize post-processor.

        Args:
            adapter: LLM adapter to use for processing
            profile: Processing profile defining behavior
            fallback_on_error: If True, return original text on error.
                              If False, return empty string on error.
        """
        self.adapter = adapter
        self.profile = profile
        self.fallback_on_error = fallback_on_error

        logger.info(f"PostProcessor initialized: {adapter.get_name()} + {profile.name}")

    def process(self, text: str) -> str:
        """Process text via LLM.

        This is a synchronous method that internally calls async adapter.

        Args:
            text: Input text to process

        Returns:
            Processed text (or original text if error + fallback enabled)
        """
        if not text or not text.strip():
            logger.debug("Empty input text, skipping processing")
            return text

        # Special case: passthrough profile
        if self.profile.name == "passthrough":
            logger.debug("Passthrough profile, returning original text")
            return text

        # Check adapter availability
        if not self.adapter.is_available():
            logger.warning(
                f"LLM adapter '{self.adapter.get_name()}' not available, "
                f"fallback={'enabled' if self.fallback_on_error else 'disabled'}"
            )
            return text if self.fallback_on_error else ""

        try:
            # Build LLM request
            request = self._build_request(text)

            # Call async adapter via asyncio.run()
            # This bridges sync service code with async HTTP calls
            response = asyncio.run(self.adapter.process(request))

            # Handle response
            return self._handle_response(response, text)

        except Exception as e:
            logger.error(f"PostProcessor error: {e}", exc_info=True)
            return text if self.fallback_on_error else ""

    def _build_request(self, text: str) -> LlmRequest:
        """Build LLM request from profile and input text.

        Args:
            text: Input text

        Returns:
            LlmRequest ready to send to adapter
        """
        # Format user message using profile template
        user_content = self.profile.user_template.format(text=text)

        # Create message sequence: system + user
        messages = (
            LlmMessage(role="system", content=self.profile.system_prompt),
            LlmMessage(role="user", content=user_content),
        )

        # Use profile temperature if set, otherwise use adapter default
        temperature = (
            self.profile.temperature if self.profile.temperature is not None else 0.3
        )

        return LlmRequest(
            messages=messages,
            model=self.adapter.config.model,
            temperature=temperature,
            max_tokens=500,  # Reasonable for text correction
        )

    def _handle_response(self, response: LlmResponse, original_text: str) -> str:
        """Handle LLM response.

        Args:
            response: Response from LLM adapter
            original_text: Original input text (for fallback)

        Returns:
            Processed text or fallback text
        """
        if response.success:
            processed = response.text.strip()

            # Log token usage for monitoring
            if response.tokens_used:
                logger.info(
                    f"LLM processing: {len(original_text)} chars -> {len(processed)} chars, "
                    f"{response.tokens_used} tokens, model={response.model}"
                )
            else:
                logger.info(
                    f"LLM processing: {len(original_text)} chars -> {len(processed)} chars, "
                    f"model={response.model}"
                )

            return processed

        else:
            # Error occurred
            logger.error(f"LLM processing failed: {response.error}")

            if self.fallback_on_error:
                logger.info("Fallback enabled, returning original text")
                return original_text
            else:
                logger.info("Fallback disabled, returning empty string")
                return ""

    def get_info(self) -> dict[str, str]:
        """Get processor information for debugging/monitoring.

        Returns:
            Dict with adapter, profile, and config info
        """
        return {
            "adapter": self.adapter.get_name(),
            "profile": self.profile.name,
            "profile_description": self.profile.description,
            "model": self.adapter.config.model,
            "fallback_on_error": str(self.fallback_on_error),
            "adapter_available": str(self.adapter.is_available()),
        }


def create_processor(
    adapter: LlmAdapter,
    profile: ProcessingProfile,
    fallback_on_error: bool = True,
) -> PostProcessor:
    """Factory function to create PostProcessor.

    Args:
        adapter: LLM adapter to use
        profile: Processing profile to use
        fallback_on_error: Whether to fallback to original text on error

    Returns:
        Configured PostProcessor instance

    Example:
        >>> from dictacode_stt.llm import create_llm_adapter, LlmConfig
        >>> from dictacode_stt.llm.profiles import BUILTIN_PROFILES
        >>> from dictacode_stt.llm.processor import create_processor
        >>>
        >>> config = LlmConfig.for_ollama()
        >>> adapter = create_llm_adapter(config)
        >>> profile = BUILTIN_PROFILES["grammar"]
        >>> processor = create_processor(adapter, profile)
        >>>
        >>> result = processor.process("this are test")
        >>> print(result)  # "This is a test"
    """
    return PostProcessor(
        adapter=adapter,
        profile=profile,
        fallback_on_error=fallback_on_error,
    )
