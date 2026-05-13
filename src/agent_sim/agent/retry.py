"""Agent error recovery with exponential backoff retry."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, TypeVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RetryConfig(BaseModel):
    """重试配置。

    Attributes:
        max_retries: 最大重试次数
        base_delay: 基础延迟（秒）
        max_delay: 最大延迟（秒）
        backoff_factor: 退避因子
        retryable_errors: 可重试的异常类型名称列表（空列表表示全部重试）
    """

    max_retries: int = 3
    base_delay: float = 0.1
    max_delay: float = 10.0
    backoff_factor: float = 2.0
    retryable_errors: list[str] = Field(default_factory=list)


class RetryStats(BaseModel):
    """重试统计。

    Attributes:
        total_calls: 总调用次数
        total_retries: 总重试次数
        total_failures: 总失败次数
        total_successes: 总成功次数
    """

    total_calls: int = 0
    total_retries: int = 0
    total_failures: int = 0
    total_successes: int = 0


class RetryManager:
    """重试管理器 — 为 Agent step 提供指数退避重试。

    Example:
        >>> manager = RetryManager(RetryConfig(max_retries=3, base_delay=0.1))
        >>> result = await manager.retry_async(agent.step)
    """

    def __init__(self, config: RetryConfig | None = None) -> None:
        self.config = config or RetryConfig()
        self.stats = RetryStats()

    def _should_retry(self, error: Exception) -> bool:
        """判断错误是否可重试。"""
        if not self.config.retryable_errors:
            return True
        return type(error).__name__ in self.config.retryable_errors

    def _get_delay(self, attempt: int) -> float:
        """计算退避延迟。"""
        delay = self.config.base_delay * (self.config.backoff_factor ** attempt)
        return min(delay, self.config.max_delay)

    async def retry_async(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """异步重试执行。

        Args:
            func: 异步函数
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            函数返回值

        Raises:
            Exception: 超过最大重试次数后抛出最后一个异常
        """
        self.stats.total_calls += 1
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            try:
                result = await func(*args, **kwargs)
                self.stats.total_successes += 1
                return result
            except Exception as e:
                last_error = e
                if not self._should_retry(e) or attempt >= self.config.max_retries:
                    self.stats.total_failures += 1
                    raise

                self.stats.total_retries += 1
                delay = self._get_delay(attempt)
                logger.warning(
                    "重试 %d/%d (延迟 %.2fs): %s",
                    attempt + 1,
                    self.config.max_retries,
                    delay,
                    e,
                )
                await asyncio.sleep(delay)

        # 不应到达这里，但安全起见
        self.stats.total_failures += 1
        if last_error:
            raise last_error

    def reset_stats(self) -> None:
        """重置统计。"""
        self.stats = RetryStats()
