"""Environment state management."""
from __future__ import annotations

import copy
import time
from typing import Any

from pydantic import BaseModel, Field


class EnvironmentState(BaseModel):
    """仿真环境状态。

    管理共享数据和事件日志。

    Attributes:
        step: 当前步骤
        data: 键值存储
        events: 事件日志
    """

    step: int = 0
    data: dict[str, Any] = Field(default_factory=dict)
    events: list[dict[str, Any]] = Field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        """获取状态值。

        Args:
            key: 键名
            default: 默认值

        Returns:
            键对应的值，不存在则返回 default
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置状态值。

        Args:
            key: 键名
            value: 值
        """
        self.data[key] = value

    def snapshot(self) -> dict[str, Any]:
        """返回当前数据的深拷贝快照。"""
        return copy.deepcopy(self.data)

    def add_event(self, event_type: str, details: dict[str, Any] | None = None) -> None:
        """记录环境事件。

        Args:
            event_type: 事件类型
            details: 事件详情
        """
        self.events.append({
            "type": event_type,
            "step": self.step,
            "timestamp": time.time(),
            "details": details or {},
        })

    def __str__(self) -> str:
        return f"EnvironmentState(step={self.step}, keys={list(self.data.keys())})"
