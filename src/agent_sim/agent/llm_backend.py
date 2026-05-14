"""LLM backend implementations for real API integrations.

Provides:
- OpenAIBackend: OpenAI-compatible API (OpenAI, Azure, vLLM, etc.)
- OllamaBackend: Ollama local model server
- create_backend(): Factory function for config-driven backend selection
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from agent_sim.agent.llm_agent import EchoLLMBackend, LLMBackend
from agent_sim.exceptions import LLMError

logger = logging.getLogger(__name__)

# Default timeouts (seconds)
_DEFAULT_TIMEOUT = 60.0


class OpenAIBackend(LLMBackend):
    """OpenAI-compatible API backend.

    Works with OpenAI, Azure OpenAI, vLLM, LiteLLM, and any
    service implementing the OpenAI Chat Completions API.

    Args:
        api_key: API key (falls back to OPENAI_API_KEY env var)
        base_url: API base URL (default: https://api.openai.com/v1)
        model: Model name (default: gpt-4o-mini)
        temperature: Sampling temperature (0.0-2.0)
        max_tokens: Maximum tokens to generate
        timeout: HTTP request timeout in seconds
        extra_headers: Additional HTTP headers
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        temperature: float = 1.0,
        max_tokens: int | None = None,
        timeout: float = _DEFAULT_TIMEOUT,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.extra_headers = extra_headers or {}

        if not self.api_key:
            raise LLMError(
                "OpenAI API key required. Pass api_key or set OPENAI_API_KEY env var."
            )

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Call OpenAI Chat Completions API.

        Args:
            messages: Conversation messages [{\"role\": \"user\", \"content\": \"...\"}]
            **kwargs: Override model parameters (model, temperature, max_tokens)

        Returns:
            Generated text response

        Raises:
            httpx.HTTPStatusError: On HTTP errors (4xx, 5xx)
            httpx.ConnectError: On connection failures
            httpx.TimeoutException: On request timeout
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.extra_headers,
        }

        body: dict[str, Any] = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.temperature),
        }
        max_tok = kwargs.get("max_tokens", self.max_tokens)
        if max_tok is not None:
            body["max_tokens"] = max_tok

        logger.debug(
            "OpenAI request: model=%s, messages=%d",
            body["model"],
            len(messages),
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            logger.warning("OpenAI returned empty choices")
            return ""

        content = choices[0].get("message", {}).get("content", "")
        usage = data.get("usage")
        if usage:
            logger.debug(
                "OpenAI usage: prompt=%d, completion=%d",
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
            )

        return content


class OllamaBackend(LLMBackend):
    """Ollama local model server backend.

    Connects to a running Ollama instance via its chat API.

    Args:
        base_url: Ollama server URL (default: http://localhost:11434)
        model: Model name (default: llama3)
        temperature: Sampling temperature
        num_predict: Maximum tokens to predict (equivalent to max_tokens)
        timeout: HTTP request timeout in seconds
        extra_options: Additional Ollama options
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "llama3",
        temperature: float = 0.8,
        num_predict: int | None = None,
        timeout: float = 120.0,
        extra_options: dict[str, Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.num_predict = num_predict
        self.timeout = timeout
        self.extra_options = extra_options or {}

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Call Ollama chat API.

        Args:
            messages: Conversation messages
            **kwargs: Override parameters

        Returns:
            Generated text response

        Raises:
            httpx.ConnectError: Ollama server not reachable
            httpx.TimeoutException: On request timeout
        """
        url = f"{self.base_url}/api/chat"

        options: dict[str, Any] = {
            "temperature": kwargs.get("temperature", self.temperature),
            **self.extra_options,
        }
        num_pred = kwargs.get("num_predict", self.num_predict)
        if num_pred is not None:
            options["num_predict"] = num_pred

        body = {
            "model": kwargs.get("model", self.model),
            "messages": messages,
            "stream": False,
            "options": options,
        }

        logger.debug(
            "Ollama request: model=%s, messages=%d",
            body["model"],
            len(messages),
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()

        data = resp.json()
        content = data.get("message", {}).get("content", "")
        return content


def create_backend(provider: str, **kwargs: Any) -> LLMBackend:
    """Factory function to create an LLM backend by provider name.

    Args:
        provider: Backend provider name ("echo", "openai", "ollama")
        **kwargs: Provider-specific configuration

    Returns:
        LLMBackend instance

    Raises:
        ValueError: Unknown provider name

    Example:
        >>> backend = create_backend("openai", api_key="sk-...", model="gpt-4")
        >>> backend = create_backend("ollama", model="mistral")
        >>> backend = create_backend("echo")
    """
    providers = {
        "echo": lambda **kw: EchoLLMBackend(),
        "openai": lambda **kw: OpenAIBackend(**kw),
        "ollama": lambda **kw: OllamaBackend(**kw),
    }

    if provider not in providers:
        raise LLMError(
            f"Unknown LLM backend: '{provider}'. "
            f"Available: {list(providers.keys())}"
        )

    return providers[provider](**kwargs)
