"""Tests for OpenAI backend and rate limiter."""
from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agent_sim.agent.llm_agent import LLMBackend
from agent_sim.agent.rate_limiter import TokenBucketRateLimiter


# ──────────────────────────────────────────────
# Rate Limiter Tests
# ──────────────────────────────────────────────

class TestTokenBucketRateLimiter:
    """令牌桶限流器测试。"""

    def test_create_limiter(self) -> None:
        limiter = TokenBucketRateLimiter(rate=10, max_tokens=20)
        assert limiter.rate == 10
        assert limiter.max_tokens == 20
        assert limiter.available == 20

    def test_acquire_reduces_tokens(self) -> None:
        limiter = TokenBucketRateLimiter(rate=100, max_tokens=10)
        asyncio.get_event_loop().run_until_complete(limiter.acquire(3))
        assert limiter.available <= 7.1  # some refill

    def test_acquire_multiple_times(self) -> None:
        limiter = TokenBucketRateLimiter(rate=1000, max_tokens=10)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(limiter.acquire(5))
        loop.run_until_complete(limiter.acquire(3))
        assert limiter.available <= 2.1
        loop.close()

    def test_str_repr(self) -> None:
        limiter = TokenBucketRateLimiter(rate=5, max_tokens=10)
        s = str(limiter)
        assert "RateLimiter" in s
        assert "rate=5/s" in s

    @pytest.mark.asyncio
    async def test_acquire_refills_over_time(self) -> None:
        limiter = TokenBucketRateLimiter(rate=1000, max_tokens=5)
        await limiter.acquire(5)
        assert limiter.available <= 0.1
        await asyncio.sleep(0.01)
        # After 10ms at 1000/s, should have ~10 tokens
        assert limiter.available >= 5  # capped at max


# ──────────────────────────────────────────────
# OpenAI Backend Tests (mocked)
# ──────────────────────────────────────────────

class TestOpenAIBackend:
    """OpenAI 后端测试（使用 mock）。"""

    def test_import_openai_backend(self) -> None:
        from agent_sim.agent.openai_backend import OpenAIBackend
        backend = OpenAIBackend(model="test-model", api_key="test-key")
        assert backend.model == "test-model"
        assert backend.api_key == "test-key"

    def test_backend_is_llm_backend(self) -> None:
        from agent_sim.agent.openai_backend import OpenAIBackend
        backend = OpenAIBackend()
        assert isinstance(backend, LLMBackend)

    def test_default_values(self) -> None:
        from agent_sim.agent.openai_backend import OpenAIBackend
        backend = OpenAIBackend()
        assert backend.model == "gpt-4o-mini"
        assert backend.temperature == 0.7
        assert backend.max_tokens == 1024
        assert backend.timeout == 60.0

    def test_custom_base_url(self) -> None:
        from agent_sim.agent.openai_backend import OpenAIBackend
        backend = OpenAIBackend(base_url="http://localhost:8000/v1")
        assert backend.base_url == "http://localhost:8000/v1"

    @pytest.mark.asyncio
    async def test_generate_with_mock(self) -> None:
        from agent_sim.agent.openai_backend import OpenAIBackend

        # Create mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "Hello, world!"
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.model = "gpt-4o-mini"
        mock_response.usage.total_tokens = 50

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        backend = OpenAIBackend(api_key="test-key")
        backend._client = mock_client

        result = await backend.generate([{"role": "user", "content": "hi"}])
        assert result == "Hello, world!"
        mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_api_error(self) -> None:
        from agent_sim.agent.openai_backend import OpenAIBackend

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            side_effect=Exception("API Error")
        )

        backend = OpenAIBackend(api_key="test-key")
        backend._client = mock_client

        with pytest.raises(RuntimeError, match="OpenAI API 调用失败"):
            await backend.generate([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        from agent_sim.agent.openai_backend import OpenAIBackend

        mock_client = AsyncMock()
        backend = OpenAIBackend(api_key="test-key")
        backend._client = mock_client

        await backend.close()
        mock_client.close.assert_called_once()
        assert backend._client is None
