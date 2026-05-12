"""Conversation buffer implementations for agent memory."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class MemoryBuffer(ABC):
    """记忆缓冲区抽象基类。"""

    @abstractmethod
    def add(self, role: str, content: str, **metadata: Any) -> None:
        """添加一条消息到缓冲区。"""
        ...

    @abstractmethod
    def get_messages(self) -> list[dict[str, Any]]:
        """获取所有消息（格式化为 LLM 对话格式）。"""
        ...

    @abstractmethod
    def clear(self) -> None:
        """清空缓冲区。"""
        ...

    @property
    @abstractmethod
    def size(self) -> int:
        """当前缓冲区消息数。"""
        ...


class ConversationBuffer(MemoryBuffer):
    """全量对话缓冲区。

    保存所有对话历史，适合短对话场景。

    Attributes:
        max_size: 最大消息数限制（0 表示无限）

    Example:
        >>> buf = ConversationBuffer(max_size=100)
        >>> buf.add("user", "hello")
        >>> buf.add("assistant", "hi there")
        >>> buf.get_messages()
        [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi there"}]
    """

    def __init__(self, max_size: int = 0) -> None:
        self.max_size = max_size
        self._messages: list[dict[str, Any]] = []

    def add(self, role: str, content: str, **metadata: Any) -> None:
        """添加消息到缓冲区末尾。

        如果超出 max_size，自动移除最早的消息。

        Args:
            role: 消息角色 (user/assistant/system)
            content: 消息内容
            **metadata: 附加元数据
        """
        msg: dict[str, Any] = {"role": role, "content": content}
        if metadata:
            msg["metadata"] = metadata
        self._messages.append(msg)

        # 超出限制时移除最早的非 system 消息
        if self.max_size > 0 and len(self._messages) > self.max_size:
            for i, m in enumerate(self._messages):
                if m["role"] != "system":
                    self._messages.pop(i)
                    break

    def get_messages(self) -> list[dict[str, Any]]:
        """返回所有消息的副本。"""
        return list(self._messages)

    def clear(self) -> None:
        """保留 system 消息，清除其他。"""
        self._messages = [m for m in self._messages if m["role"] == "system"]

    @property
    def size(self) -> int:
        """当前消息数。"""
        return len(self._messages)

    def __str__(self) -> str:
        return f"ConversationBuffer(size={self.size}, max={self.max_size})"


class SlidingWindowBuffer(MemoryBuffer):
    """滑动窗口缓冲区。

    保留最近 N 条消息，始终保留 system 消息。适合需要控制上下文长度的 LLM 对话。

    Attributes:
        window_size: 窗口大小（保留最近多少条非 system 消息）

    Example:
        >>> buf = SlidingWindowBuffer(window_size=3)
        >>> buf.add("system", "You are helpful")
        >>> buf.add("user", "msg1")
        >>> buf.add("assistant", "reply1")
        >>> buf.add("user", "msg2")
        >>> buf.add("assistant", "reply2")
        >>> len(buf.get_messages())  # system + last 3 non-system
        4
    """

    def __init__(self, window_size: int = 10) -> None:
        if window_size < 1:
            raise ValueError("window_size 必须 >= 1")
        self.window_size = window_size
        self._system: list[dict[str, Any]] = []
        self._recent: list[dict[str, Any]] = []

    def add(self, role: str, content: str, **metadata: Any) -> None:
        """添加消息。

        system 消息单独保存，其他消息进入滑动窗口。

        Args:
            role: 消息角色
            content: 消息内容
            **metadata: 附加元数据
        """
        msg: dict[str, Any] = {"role": role, "content": content}
        if metadata:
            msg["metadata"] = metadata

        if role == "system":
            self._system.append(msg)
        else:
            self._recent.append(msg)
            if len(self._recent) > self.window_size:
                self._recent.pop(0)

    def get_messages(self) -> list[dict[str, Any]]:
        """返回 system 消息 + 窗口内的消息。"""
        return list(self._system) + list(self._recent)

    def clear(self) -> None:
        """清除窗口内消息，保留 system 消息。"""
        self._recent.clear()

    @property
    def size(self) -> int:
        """当前总消息数（含 system）。"""
        return len(self._system) + len(self._recent)

    def __str__(self) -> str:
        return f"SlidingWindowBuffer(size={self.size}, window={self.window_size})"
