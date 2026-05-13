"""Response correlation tracking for request-response message pairs."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from agent_sim.communication.message import Message

logger = logging.getLogger(__name__)


class CorrelationEntry(BaseModel):
    """关联条目。"""

    correlation_id: str
    request: dict[str, Any] = Field(default_factory=dict)
    response: dict[str, Any] | None = None
    request_time: float = 0.0
    response_time: float = 0.0
    completed: bool = False


class ResponseTracker:
    """请求-响应关联追踪器。

    通过 correlation_id 将请求消息和响应消息配对。
    支持超时检测和统计。

    Example:
        >>> tracker = ResponseTracker()
        >>> # 发送请求时标记
        >>> request = Message(sender="a", receiver="b", content="query")
        >>> cid = tracker.track_request(request)
        >>> # 收到响应时关联
        >>> response = Message(sender="b", receiver="a", content="answer", correlation_id=cid)
        >>> tracker.track_response(response)
        >>> entry = tracker.get_entry(cid)
        >>> assert entry.completed
    """

    def __init__(self) -> None:
        self._entries: dict[str, CorrelationEntry] = {}

    def generate_id(self) -> str:
        """生成唯一关联 ID。"""
        return str(uuid.uuid4())[:8]

    def track_request(self, message: Message) -> str:
        """追踪请求消息。

        如果消息没有 correlation_id，自动生成一个。

        Args:
            message: 请求消息

        Returns:
            关联 ID
        """
        import time

        cid = message.correlation_id or self.generate_id()
        self._entries[cid] = CorrelationEntry(
            correlation_id=cid,
            request=message.model_dump(),
            request_time=time.time(),
        )
        logger.debug("追踪请求: cid=%s, sender=%s", cid, message.sender)
        return cid

    def track_response(self, message: Message) -> bool:
        """追踪响应消息。

        Args:
            message: 响应消息（需要包含 correlation_id）

        Returns:
            是否成功关联到请求
        """
        import time

        cid = message.correlation_id
        if not cid or cid not in self._entries:
            logger.debug("未找到关联: cid=%s", cid)
            return False

        entry = self._entries[cid]
        entry.response = message.model_dump()
        entry.response_time = time.time()
        entry.completed = True
        logger.debug("关联完成: cid=%s, latency=%.3fs", cid, entry.response_time - entry.request_time)
        return True

    def get_entry(self, correlation_id: str) -> CorrelationEntry | None:
        """获取关联条目。"""
        return self._entries.get(correlation_id)

    def get_pending(self) -> list[CorrelationEntry]:
        """获取所有未完成的请求。"""
        return [e for e in self._entries.values() if not e.completed]

    def get_completed(self) -> list[CorrelationEntry]:
        """获取所有已完成的请求-响应对。"""
        return [e for e in self._entries.values() if e.completed]

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息。"""
        completed = self.get_completed()
        pending = self.get_pending()
        latencies = [e.response_time - e.request_time for e in completed if e.response_time > 0]
        return {
            "total": len(self._entries),
            "completed": len(completed),
            "pending": len(pending),
            "avg_latency": sum(latencies) / len(latencies) if latencies else 0.0,
            "max_latency": max(latencies) if latencies else 0.0,
        }

    def clear(self) -> None:
        """清空所有追踪条目。"""
        self._entries.clear()
