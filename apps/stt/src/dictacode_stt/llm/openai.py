"""OpenAI LLM adapter implementation.

OpenAI ChatGPT API (https://api.openai.com/v1).
Requires API key from platform.openai.com.
"""

import logging
from typing import Any

import httpx

from dictacode_stt.llm.adapter import LlmAdapter
from dictacode_stt.llm.types import LlmRequest, LlmResponse


logger = logging.getLogger(__name__)


class OpenAiAdapter(LlmAdapter):
    """OpenAI ChatGPT adapter.

    Connects to OpenAI's Chat Completions API.
    Requires: OPENAI_API_KEY environment variable or config.api_key

    Example models:
    - gpt-4o-mini (recommended for cost/quality)
    - gpt-4o (most capable)
    - gpt-4-turbo
    - gpt-3.5-turbo (cheapest)
    """

    def get_name(self) -> str:
        """Return provider name."""
        return "openai"

    async def process(self, request: LlmRequest) -> LlmResponse:
        """Process text via OpenAI API.

        Args:
            request: LLM request with messages and parameters

        Returns:
            LlmResponse with processed text or error
        """
        if not self.config.api_key:
            return LlmResponse(
                text="",
                model=request.model,
                error="OpenAI API key not configured",
            )

        try:
            # Build OpenAI chat request
            # https://platform.openai.com/docs/api-reference/chat/create
            payload = self._build_request(request)

            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    f"{self.config.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()

            # Parse OpenAI response
            data = response.json()
            return self._parse_response(data)

        except httpx.TimeoutException as e:
            logger.error(f"OpenAI timeout: {e}")
            return LlmResponse(
                text="",
                model=request.model,
                error=f"Timeout after {self.config.timeout}s",
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI HTTP error: {e.response.status_code} - {e}")
            error_text = self._parse_error_response(e.response)
            return LlmResponse(
                text="",
                model=request.model,
                error=f"HTTP {e.response.status_code}: {error_text}",
            )

        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return LlmResponse(text="", model=request.model, error=str(e))

    def is_available(self) -> bool:
        """Check if OpenAI API key is configured.

        Returns:
            True if API key is set (does not validate key)

        Note:
            We don't make a test API call to avoid costs.
            Invalid keys will fail at first process() call.
        """
        return bool(self.config.api_key)

    def get_default_model(self) -> str:
        """Return recommended OpenAI model."""
        return "gpt-4o-mini"

    def _build_request(self, request: LlmRequest) -> dict[str, Any]:
        """Build OpenAI API request payload.

        Args:
            request: LLM request

        Returns:
            Dict for OpenAI /chat/completions endpoint
        """
        return {
            "model": request.model,
            "messages": [
                {"role": msg.role, "content": msg.content} for msg in request.messages
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,  # No streaming in v0.2.14
        }

    def _parse_response(self, data: dict[str, Any]) -> LlmResponse:
        """Parse OpenAI API response.

        Args:
            data: JSON response from OpenAI

        Returns:
            LlmResponse with extracted text and metadata
        """
        # OpenAI response format:
        # {
        #   "id": "chatcmpl-...",
        #   "object": "chat.completion",
        #   "model": "gpt-4o-mini",
        #   "choices": [
        #     {
        #       "index": 0,
        #       "message": {"role": "assistant", "content": "..."},
        #       "finish_reason": "stop"
        #     }
        #   ],
        #   "usage": {
        #     "prompt_tokens": 10,
        #     "completion_tokens": 50,
        #     "total_tokens": 60
        #   }
        # }

        choices = data.get("choices", [])
        if not choices:
            return LlmResponse(
                text="",
                model=data.get("model", "unknown"),
                error="No response choices returned",
            )

        message = choices[0].get("message", {})
        text = message.get("content", "")

        # Extract token usage
        usage = data.get("usage", {})
        total_tokens = usage.get("total_tokens")

        return LlmResponse(
            text=text,
            model=data.get("model", "unknown"),
            tokens_used=total_tokens,
            error=None,
        )

    def _parse_error_response(self, response: httpx.Response) -> str:
        """Parse OpenAI error response.

        Args:
            response: HTTP error response

        Returns:
            Error message string
        """
        try:
            error_data = response.json()
            error_info = error_data.get("error", {})
            return error_info.get("message", response.text)
        except Exception:
            return response.text
