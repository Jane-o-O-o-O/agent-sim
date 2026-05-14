"""Async event bus with pub/sub pattern for agent communication."""
from __future__ import annotations

import asyncio
import fnmatch
import logging
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# 事件回调类型
EventCallback = Callable[[str, Any], Awaitable[None] | None]


class Event(BaseModel):
    """事件数据。

    Attributes:
        topic: 事件主题（支持点分隔层级，如 agent.step.start）
        data: 事件数据
        source: 事件来源
        timestamp: 事件时间戳
    """

    topic: str
    data: Any = None
    source: str = ""
    timestamp: float = 0.0


class Subscription(BaseModel):
    """订阅信息。

    Attributes:
        topic_pattern: 主题模式（支持 * 和 ** 通配符）
        callback: 回调函数
        once: 是否只触发一次
    """

    topic_pattern: str
    callback_id: int = 0
    once: bool = False


class AsyncEventBus:
    """异步事件总线 — pub/sub 模式。

    支持主题层级订阅、通配符匹配（* 和 **）、同步/异步回调。

    Features:
        - 点分隔主题层级: agent.step.start, message.delivered
        - 通配符: * 匹配单层, ** 匹配多层
        - 同步和异步回调
        - 一次性订阅
        - 事件历史记录

    Example:
        >>> bus = AsyncEventBus()
        >>> async def handler(topic, data):
        ...     print(f"Received: {topic} -> {data}")
        >>> bus.subscribe("agent.*", handler)
        >>> await bus.publish("agent.step", {"count": 1})
    """

    def __init__(self, max_history: int = 1000) -> None:
        self._subscriptions: list[tuple[Subscription, EventCallback]] = []
        self._history: list[Event] = []
        self._max_history = max_history
        self._publish_count = 0
        self._id_counter = 0

    @property
    def subscription_count(self) -> int:
        """当前订阅数。"""
        return len(self._subscriptions)

    @property
    def history(self) -> list[Event]:
        """事件历史。"""
        return list(self._history)

    @property
    def publish_count(self) -> int:
        """发布事件总数。"""
        return self._publish_count

    def subscribe(
        self, topic_pattern: str, callback: EventCallback, once: bool = False,
    ) -> int:
        """订阅事件。

        Args:
            topic_pattern: 主题模式（支持 * 和 ** 通配符）
            callback: 回调函数 (topic, data) -> None
            once: 是否只触发一次

        Returns:
            订阅 ID，用于取消订阅
        """
        self._id_counter += 1
        sub = Subscription(
            topic_pattern=topic_pattern, callback_id=self._id_counter, once=once,
        )
        self._subscriptions.append((sub, callback))
        logger.debug("订阅: %s (id=%d, once=%s)", topic_pattern, sub.callback_id, once)
        return sub.callback_id

    def unsubscribe(self, subscription_id: int) -> bool:
        """取消订阅。

        Args:
            subscription_id: 订阅 ID

        Returns:
            是否成功取消
        """
        for i, (sub, _) in enumerate(self._subscriptions):
            if sub.callback_id == subscription_id:
                self._subscriptions.pop(i)
                logger.debug("取消订阅: id=%d", subscription_id)
                return True
        return False

    def clear_subscriptions(self) -> int:
        """清除所有订阅。

        Returns:
            清除的订阅数
        """
        count = len(self._subscriptions)
        self._subscriptions.clear()
        return count

    async def publish(self, topic: str, data: Any = None, source: str = "") -> int:
        """发布事件。

        Args:
            topic: 事件主题
            data: 事件数据
            source: 事件来源

        Returns:
            触发的回调数量
        """
        import time

        event = Event(topic=topic, data=data, source=source, timestamp=time.time())
        self._publish_count += 1

        # 记录历史
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        triggered = 0
        to_remove: list[int] = []

        for i, (sub, callback) in enumerate(self._subscriptions):
            if self._match_topic(sub.topic_pattern, topic):
                try:
                    result = callback(topic, data)
                    if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                        await result
                    triggered += 1
                except Exception as e:
                    logger.error("回调执行失败 [%s]: %s", topic, e)

                if sub.once:
                    to_remove.append(i)

        # 移除一次性订阅（从后往前移除避免索引偏移）
        for i in reversed(to_remove):
            self._subscriptions.pop(i)

        logger.debug("发布 [%s] -> %d 个回调触发", topic, triggered)
        return triggered

    @staticmethod
    def _match_topic(pattern: str, topic: str) -> bool:
        """匹配主题模式。

        支持:
            *   匹配单层 (agent.* -> agent.step)
            **  匹配多层 (agent.** -> agent.step.start)

        Args:
            pattern: 主题模式
            topic: 实际主题

        Returns:
            是否匹配
        """
        # 先尝试精确匹配
        if pattern == topic:
            return True

        # 使用 fnmatch 进行通配符匹配
        if fnmatch.fnmatch(topic, pattern):
            return True

        # 处理 ** 通配符（匹配多层）
        if "**" in pattern:
            # 将 ** 替换为能匹配任意字符的模式
            import re
            regex_pattern = pattern.replace(".", r"\.")
            regex_pattern = regex_pattern.replace("**", ".*")
            regex_pattern = regex_pattern.replace("*", r"[^.]*")
            regex_pattern = f"^{regex_pattern}$"
            return bool(re.match(regex_pattern, topic))

        return False

    def get_subscribers(self, topic: str) -> list[int]:
        """获取匹配某个主题的订阅 ID 列表。

        Args:
            topic: 事件主题

        Returns:
            匹配的订阅 ID 列表
        """
        return [
            sub.callback_id
            for sub, _ in self._subscriptions
            if self._match_topic(sub.topic_pattern, topic)
        ]

    def topics(self) -> set[str]:
        """获取所有已发布过的主题。

        Returns:
            主题集合
        """
        return {event.topic for event in self._history}

    def clear_history(self) -> None:
        """清除事件历史。"""
        self._history.clear()

    def __str__(self) -> str:
        return (
            f"AsyncEventBus(subscriptions={self.subscription_count}, "
            f"published={self.publish_count}, history={len(self._history)})"
        )
