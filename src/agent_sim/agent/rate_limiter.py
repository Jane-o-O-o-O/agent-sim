"""Token bucket rate limiter for LLM API calls."""
from __future__ import annotations

import asyncio
import time
from typing import Any


class TokenBucketRateLimiter:
    """令牌桶限流器。

    控制 LLM API 调用频率，避免超出速率限制。

    Attributes:
        rate: 每秒补充的令牌数
        max_tokens: 令牌桶最大容量
        tokens: 当前可用令牌数

    Example:
        >>> limiter = TokenBucketRateLimiter(rate=10, max_tokens=20)
        >>> await limiter.acquire()  # 等待直到有可用令牌
    """

    def __init__(self, rate: float = 10.0, max_tokens: int = 20) -> None:
        self.rate = rate
        self.max_tokens = max_tokens
        self.tokens = float(max_tokens)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """补充令牌。"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self, tokens: int = 1) -> float:
        """获取令牌，不够时等待。

        Args:
            tokens: 需要的令牌数

        Returns:
            实际等待时间（秒）
        """
        waited = 0.0
        async with self._lock:
            self._refill()
            while self.tokens < tokens:
                deficit = tokens - self.tokens
                wait_time = deficit / self.rate
                waited += wait_time
                await asyncio.sleep(wait_time)
                self._refill()
            self.tokens -= tokens
        return waited

    @property
    def available(self) -> float:
        """当前可用令牌数（不等待）。"""
        self._refill()
        return self.tokens

    def __str__(self) -> str:
        return f"RateLimiter(rate={self.rate}/s, available={self.available:.1f})"
