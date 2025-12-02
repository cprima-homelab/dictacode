"""Ollama LLM adapter implementation.

Ollama provides local LLM inference via HTTP API (http://localhost:11434).
No API key required, supports models like llama3.2, mistral, phi3, etc.
"""

import logging
from typing import Any

import httpx

from dictacode_stt.llm.adapter import LlmAdapter
from dictacode_stt.llm.types import LlmRequest, LlmResponse


logger = logging.getLogger(__name__)


class OllamaAdapter(LlmAdapter):
    """Ollama local LLM adapter.

    Connects to Ollama API running locally or on specified host.
    Default: http://localhost:11434

    Example models:
    - llama3.2 (Meta's latest)
    - mistral (Mistral AI)
    - phi3 (Microsoft)
    - gemma2 (Google)
    """

    def get_name(self) -> str:
        """Return provider name."""
        return "ollama"

    async def process(self, request: LlmRequest) -> LlmResponse:
        """Process text via Ollama API.

        Args:
            request: LLM request with messages and parameters

        Returns:
            LlmResponse with processed text or error
        """
        try:
            # Build Ollama chat request
            # https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion
            payload = self._build_request(request)

            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    f"{self.config.base_url}/api/chat",
                    json=payload,
                )
                response.raise_for_status()

            # Parse Ollama response
            data = response.json()
            return self._parse_response(data)

        except httpx.TimeoutException as e:
            logger.error(f"Ollama timeout: {e}")
            return LlmResponse(
                text="",
                model=request.model,
                error=f"Timeout after {self.config.timeout}s",
            )

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama HTTP error: {e.response.status_code} - {e}")
            return LlmResponse(
                text="",
                model=request.model,
                error=f"HTTP {e.response.status_code}: {e.response.text}",
            )

        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return LlmResponse(text="", model=request.model, error=str(e))

    def is_available(self) -> bool:
        """Check if Ollama server is running.

        Returns:
            True if Ollama API responds to /api/tags
        """
        try:
            response = httpx.get(
                f"{self.config.base_url}/api/tags",
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Ollama not available: {e}")
            return False

    def get_default_model(self) -> str:
        """Return recommended Ollama model."""
        return "llama3.2"

    def _build_request(self, request: LlmRequest) -> dict[str, Any]:
        """Build Ollama API request payload.

        Args:
            request: LLM request

        Returns:
            Dict for Ollama /api/chat endpoint
        """
        return {
            "model": request.model,
            "messages": [
                {"role": msg.role, "content": msg.content} for msg in request.messages
            ],
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
            "stream": False,  # No streaming in v0.2.14
        }

    def _parse_response(self, data: dict[str, Any]) -> LlmResponse:
        """Parse Ollama API response.

        Args:
            data: JSON response from Ollama

        Returns:
            LlmResponse with extracted text and metadata
        """
        # Ollama response format:
        # {
        #   "model": "llama3.2",
        #   "message": {"role": "assistant", "content": "..."},
        #   "done": true,
        #   "total_duration": 1234567890,
        #   "prompt_eval_count": 10,
        #   "eval_count": 50
        # }

        message = data.get("message", {})
        text = message.get("content", "")

        # Calculate total tokens (prompt + completion)
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        total_tokens = prompt_tokens + completion_tokens if prompt_tokens > 0 else None

        return LlmResponse(
            text=text,
            model=data.get("model", "unknown"),
            tokens_used=total_tokens,
            error=None,
        )
