"""OpenRouter LLM adapter implementation.

OpenRouter aggregates multiple LLM providers into one API (https://openrouter.ai).
Access to Claude, GPT, Llama, Mistral, Gemini, and more through single interface.
"""

import logging
from typing import Any

import httpx

from dictacode_stt.llm.adapter import LlmAdapter
from dictacode_stt.llm.types import LlmRequest, LlmResponse


logger = logging.getLogger(__name__)


class OpenRouterAdapter(LlmAdapter):
    """OpenRouter multi-model aggregator adapter.

    Connects to OpenRouter API for access to multiple LLM providers.
    Requires: OpenRouter API key from openrouter.ai

    Example models:
    - anthropic/claude-3.5-sonnet (recommended quality)
    - openai/gpt-4o-mini (fast, cheap)
    - meta-llama/llama-3.1-70b-instruct
    - mistralai/mistral-small
    - google/gemini-pro-1.5

    Full model list: https://openrouter.ai/models
    """

    def get_name(self) -> str:
        """Return provider name."""
        return "openrouter"

    async def process(self, request: LlmRequest) -> LlmResponse:
        """Process text via OpenRouter API.

        Args:
            request: LLM request with messages and parameters

        Returns:
            LlmResponse with processed text or error
        """
        if not self.config.api_key:
            return LlmResponse(
                text="",
                model=request.model,
                error="OpenRouter API key not configured",
            )

        try:
            # Build OpenRouter chat request
            # https://openrouter.ai/docs#chat-completions
            payload = self._build_request(request)

            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    f"{self.config.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.config.api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://github.com/cprima-homelab/dictacode",
                        "X-Title": "DictaCode STT",
                    },
                    json=payload,
                )
                response.raise_for_status()

            # Parse OpenRouter response (OpenAI-compatible format)
            data = response.json()
            return self._parse_response(data)

        except httpx.TimeoutException as e:
            logger.error(f"OpenRouter timeout: {e}")
            return LlmResponse(
                text="",
                model=request.model,
                error=f"Timeout after {self.config.timeout}s",
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"OpenRouter HTTP error: {e.response.status_code} - {e}")
            error_text = self._parse_error_response(e.response)
            return LlmResponse(
                text="",
                model=request.model,
                error=f"HTTP {e.response.status_code}: {error_text}",
            )

        except Exception as e:
            logger.error(f"OpenRouter error: {e}")
            return LlmResponse(text="", model=request.model, error=str(e))

    def is_available(self) -> bool:
        """Check if OpenRouter API key is configured.

        Returns:
            True if API key is set (does not validate key)

        Note:
            We don't make a test API call to avoid costs.
            Invalid keys will fail at first process() call.
        """
        return bool(self.config.api_key)

    def get_default_model(self) -> str:
        """Return recommended OpenRouter model."""
        return "anthropic/claude-3.5-sonnet"

    def _build_request(self, request: LlmRequest) -> dict[str, Any]:
        """Build OpenRouter API request payload.

        Args:
            request: LLM request

        Returns:
            Dict for OpenRouter /chat/completions endpoint
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
        """Parse OpenRouter API response.

        Args:
            data: JSON response from OpenRouter

        Returns:
            LlmResponse with extracted text and metadata
        """
        # OpenRouter uses OpenAI-compatible response format:
        # {
        #   "id": "gen-...",
        #   "model": "anthropic/claude-3.5-sonnet",
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
        """Parse OpenRouter error response.

        Args:
            response: HTTP error response

        Returns:
            Error message string
        """
        try:
            error_data = response.json()
            # OpenRouter error format can be:
            # {"error": {"message": "...", "code": "..."}}
            # or
            # {"error": "..."}
            error_info = error_data.get("error", {})
            if isinstance(error_info, dict):
                return error_info.get("message", response.text)
            else:
                return str(error_info)
        except Exception:
            return response.text
