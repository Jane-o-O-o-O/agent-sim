"""Message middleware pipeline for the MessageBus.

Supports intercepting, filtering, and transforming messages before delivery.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from agent_sim.communication.message import Message

logger = logging.getLogger(__name__)


class MessageMiddleware(ABC):
    """消息中间件抽象基类。

    子类实现 process() 方法来拦截、过滤或变换消息。
    返回 None 表示消息被过滤（不继续传递）。
    """

    @abstractmethod
    def process(self, message: Message) -> Message | None:
        """处理消息。

        Args:
            message: 输入消息

        Returns:
            处理后的消息，或 None 表示过滤掉
        """
        ...


class LoggingMiddleware(MessageMiddleware):
    """日志中间件 — 记录所有经过的消息。"""

    def __init__(self, level: int = logging.DEBUG) -> None:
        self.level = level
        self.logged: list[Message] = []

    def process(self, message: Message) -> Message:
        """记录消息日志并放行。"""
        logger.log(
            self.level,
            "Message: %s -> %s [%s] %s",
            message.sender,
            message.receiver or "ALL",
            message.msg_type,
            message.content[:100],
        )
        self.logged.append(message)
        return message


class FilterMiddleware(MessageMiddleware):
    """过滤中间件 — 根据条件过滤消息。

    支持按 sender、receiver、msg_type 过滤。

    Example:
        >>> # 过滤掉来自 "spam_agent" 的消息
        >>> middleware = FilterMiddleware(blocked_senders={"spam_agent"})
        >>> # 只允许 REQUEST 类型消息
        >>> middleware = FilterMiddleware(allowed_types={MessageType.REQUEST})
    """

    def __init__(
        self,
        blocked_senders: set[str] | None = None,
        blocked_receivers: set[str] | None = None,
        allowed_types: set[str] | None = None,
        max_content_length: int | None = None,
    ) -> None:
        self.blocked_senders = blocked_senders or set()
        self.blocked_receivers = blocked_receivers or set()
        self.allowed_types = allowed_types or set()
        self.max_content_length = max_content_length

    def process(self, message: Message) -> Message | None:
        """检查消息是否通过过滤条件。"""
        if message.sender in self.blocked_senders:
            logger.debug("Filtered: blocked sender %s", message.sender)
            return None
        if message.receiver and message.receiver in self.blocked_receivers:
            logger.debug("Filtered: blocked receiver %s", message.receiver)
            return None
        if self.allowed_types and message.msg_type not in self.allowed_types:
            logger.debug("Filtered: disallowed type %s", message.msg_type)
            return None
        if self.max_content_length and len(message.content) > self.max_content_length:
            logger.debug("Filtered: content too long (%d chars)", len(message.content))
            return None
        return message


class TransformMiddleware(MessageMiddleware):
    """变换中间件 — 修改消息内容。

    支持自定义变换函数。

    Example:
        >>> # 给所有消息添加前缀
        >>> middleware = TransformMiddleware(
        ...     transform=lambda m: m.model_copy(update={"content": f"[LOGGED] {m.content}"})
        ... )
    """

    def __init__(self, transform: Any = None) -> None:
        self._transform = transform

    def process(self, message: Message) -> Message:
        """应用变换函数。"""
        if self._transform:
            return self._transform(message)
        return message


class RateLimitMiddleware(MessageMiddleware):
    """限流中间件 — 限制每个 sender 的消息速率。

    Args:
        max_per_second: 每个 sender 每秒最大消息数
    """

    def __init__(self, max_per_second: float = 10.0) -> None:
        self.max_per_second = max_per_second
        self._timestamps: dict[str, list[float]] = {}

    def process(self, message: Message) -> Message | None:
        """检查速率限制。"""
        now = time.monotonic()
        sender = message.sender
        timestamps = self._timestamps.setdefault(sender, [])

        # 清理过期时间戳
        cutoff = now - 1.0
        timestamps[:] = [t for t in timestamps if t > cutoff]

        if len(timestamps) >= self.max_per_second:
            logger.debug("Rate limited: %s (%.0f/s)", sender, self.max_per_second)
            return None

        timestamps.append(now)
        return message


class DeduplicationMiddleware(MessageMiddleware):
    """去重中间件 — 过滤短时间内相同内容的消息。

    Args:
        window_seconds: 去重窗口（秒）
    """

    def __init__(self, window_seconds: float = 1.0) -> None:
        self.window_seconds = window_seconds
        self._seen: dict[str, float] = {}  # content_hash -> timestamp

    def _message_key(self, message: Message) -> str:
        """生成消息去重键。"""
        return f"{message.sender}:{message.receiver}:{message.content}"

    def process(self, message: Message) -> Message | None:
        """检查是否重复消息。"""
        now = time.monotonic()
        key = self._message_key(message)

        # 清理过期条目
        cutoff = now - self.window_seconds
        self._seen = {k: v for k, v in self._seen.items() if v > cutoff}

        if key in self._seen:
            logger.debug("Dedup: duplicate message from %s", message.sender)
            return None

        self._seen[key] = now
        return message
