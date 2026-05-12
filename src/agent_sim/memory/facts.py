"""Key fact memory — store and retrieve important facts."""
from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field


class Fact(BaseModel):
    """单条记忆事实。

    Attributes:
        key: 事实标识（如 "user_name", "preference_color"）
        value: 事实内容
        source: 来源标识
        confidence: 置信度 0.0-1.0
        created_at: 创建时间戳
        last_accessed: 最近访问时间
        access_count: 访问次数
    """

    key: str
    value: str
    source: str = ""
    confidence: float = 1.0
    created_at: float = Field(default_factory=time.time)
    last_accessed: float = Field(default_factory=time.time)
    access_count: int = 0


class KeyFactMemory:
    """键值事实记忆存储。

    存储 Agent 在对话中获取的关键事实，支持置信度过滤和 LRU 淘汰。

    Attributes:
        max_facts: 最大事实数量（0 无限）

    Example:
        >>> mem = KeyFactMemory(max_facts=100)
        >>> mem.remember("user_name", "Alice", source="dialogue")
        >>> mem.recall("user_name")
        "Alice"
        >>> mem.search("user")
        [("user_name", "Alice")]
    """

    def __init__(self, max_facts: int = 0) -> None:
        self.max_facts = max_facts
        self._facts: dict[str, Fact] = {}

    def remember(
        self,
        key: str,
        value: str,
        source: str = "",
        confidence: float = 1.0,
    ) -> None:
        """存储或更新一条事实。

        如果 key 已存在且新 confidence >= 旧值，则更新；否则跳过。

        Args:
            key: 事实标识
            value: 事实内容
            source: 来源标识
            confidence: 置信度 0.0-1.0
        """
        existing = self._facts.get(key)
        if existing and confidence < existing.confidence:
            return  # 低置信度不覆盖

        self._facts[key] = Fact(
            key=key,
            value=value,
            source=source,
            confidence=confidence,
        )

        # LRU 淘汰
        if self.max_facts > 0 and len(self._facts) > self.max_facts:
            oldest_key = min(self._facts, key=lambda k: self._facts[k].last_accessed)
            del self._facts[oldest_key]

    def recall(self, key: str) -> str | None:
        """回忆一条事实。

        Args:
            key: 事实标识

        Returns:
            事实内容，不存在返回 None
        """
        fact = self._facts.get(key)
        if fact:
            fact.last_accessed = time.time()
            fact.access_count += 1
            return fact.value
        return None

    def forget(self, key: str) -> bool:
        """删除一条事实。

        Args:
            key: 事实标识

        Returns:
            是否成功删除
        """
        if key in self._facts:
            del self._facts[key]
            return True
        return False

    def search(self, query: str, min_confidence: float = 0.0) -> list[tuple[str, str]]:
        """搜索包含 query 的事实。

        在 key 和 value 中搜索子串匹配。

        Args:
            query: 搜索词
            min_confidence: 最低置信度过滤

        Returns:
            匹配的 (key, value) 列表
        """
        results = []
        query_lower = query.lower()
        for fact in self._facts.values():
            if fact.confidence < min_confidence:
                continue
            if query_lower in fact.key.lower() or query_lower in fact.value.lower():
                results.append((fact.key, fact.value))
        return results

    def get_all(self, min_confidence: float = 0.0) -> dict[str, str]:
        """获取所有事实。

        Args:
            min_confidence: 最低置信度过滤

        Returns:
            key -> value 字典
        """
        return {
            k: f.value
            for k, f in self._facts.items()
            if f.confidence >= min_confidence
        }

    def clear(self) -> None:
        """清空所有事实。"""
        self._facts.clear()

    @property
    def size(self) -> int:
        """当前事实数量。"""
        return len(self._facts)

    @property
    def keys(self) -> list[str]:
        """所有事实的 key 列表。"""
        return list(self._facts.keys())

    def stats(self) -> dict[str, Any]:
        """返回记忆统计信息。"""
        if not self._facts:
            return {"count": 0, "avg_confidence": 0.0, "total_accesses": 0}
        confidences = [f.confidence for f in self._facts.values()]
        accesses = [f.access_count for f in self._facts.values()]
        return {
            "count": len(self._facts),
            "avg_confidence": sum(confidences) / len(confidences),
            "total_accesses": sum(accesses),
            "most_accessed": max(self._facts, key=lambda k: self._facts[k].access_count)
            if self._facts
            else None,
        }

    def __str__(self) -> str:
        return f"KeyFactMemory(facts={self.size}, max={self.max_facts})"

    def __len__(self) -> int:
        return len(self._facts)
