"""Event recorder for structured simulation event logging."""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """仿真事件类型。"""

    SIM_START = "simulation_start"
    SIM_END = "simulation_end"
    STEP_START = "step_start"
    STEP_END = "step_end"
    MESSAGE = "message"
    AGENT_ERROR = "agent_error"
    AGENT_STATE_CHANGE = "agent_state_change"


class SimulationEvent(BaseModel):
    """单个仿真事件记录。

    Attributes:
        event_type: 事件类型
        timestamp: 事件时间戳 (unix)
        step: 当前仿真步数
        data: 事件数据
    """

    event_type: str
    timestamp: float = Field(default_factory=time.time)
    step: int = 0
    data: dict[str, Any] = Field(default_factory=dict)

    @property
    def time_iso(self) -> str:
        """ISO 格式时间。"""
        return datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat()


class EventRecorder:
    """仿真事件记录器。

    自动记录仿真过程中的所有关键事件，支持导出为 JSON/CSV。

    可以作为 LifecycleHooks 的回调使用，也可以手动记录。

    Example:
        >>> recorder = EventRecorder()
        >>> hooks = LifecycleHooks()
        >>> recorder.attach_to(hooks)  # 自动绑定所有事件
        >>> # 或者手动记录
        >>> recorder.record(EventType.STEP_START, step=1)
        >>> events = recorder.get_events()
    """

    def __init__(self) -> None:
        self._events: list[SimulationEvent] = []
        self._start_time: float = 0.0

    def record(
        self,
        event_type: EventType | str,
        step: int = 0,
        **data: Any,
    ) -> SimulationEvent:
        """记录一个事件。

        Args:
            event_type: 事件类型
            step: 当前步数
            **data: 事件数据

        Returns:
            创建的事件对象
        """
        event = SimulationEvent(
            event_type=event_type if isinstance(event_type, str) else event_type.value,
            step=step,
            data=data,
        )
        self._events.append(event)
        return event

    def attach_to(self, hooks: Any) -> None:
        """将记录器绑定到 LifecycleHooks。

        自动注册所有事件类型的回调。

        Args:
            hooks: LifecycleHooks 实例
        """
        hooks.on_simulation_start(self._on_sim_start)
        hooks.on_simulation_end(self._on_sim_end)
        hooks.on_step_start(self._on_step_start)
        hooks.on_step_end(self._on_step_end)
        hooks.on_message(self._on_message)
        hooks.on_agent_error(self._on_agent_error)
        hooks.on_agent_state_change(self._on_agent_state_change)

    def _on_sim_start(self, steps: int, agent_count: int, **kw: Any) -> None:
        self._start_time = time.time()
        self.record(EventType.SIM_START, steps=steps, agent_count=agent_count)

    def _on_sim_end(self, result: Any = None, duration: float = 0.0, **kw: Any) -> None:
        data: dict[str, Any] = {"duration": duration}
        if result is not None:
            data["total_messages"] = getattr(result, "total_messages", 0)
            data["steps_completed"] = getattr(result, "steps_completed", 0)
        self.record(EventType.SIM_END, **data)

    def _on_step_start(self, step: int = 0, **kw: Any) -> None:
        self.record(EventType.STEP_START, step=step)

    def _on_step_end(self, step: int = 0, messages_sent: int = 0, **kw: Any) -> None:
        self.record(EventType.STEP_END, step=step, messages_sent=messages_sent)

    def _on_message(self, message: Any = None, step: int = 0, **kw: Any) -> None:
        data: dict[str, Any] = {}
        if message is not None:
            data["sender"] = getattr(message, "sender", "unknown")
            data["receiver"] = getattr(message, "receiver", None)
            data["msg_type"] = getattr(message, "msg_type", "direct")
            content = getattr(message, "content", "")
            data["content_preview"] = str(content)[:100]
        self.record(EventType.MESSAGE, step=step, **data)

    def _on_agent_error(
        self, agent_name: str = "", error: str = "", step: int = 0, **kw: Any,
    ) -> None:
        self.record(EventType.AGENT_ERROR, step=step, agent=agent_name, error=error)

    def _on_agent_state_change(
        self,
        agent_name: str = "",
        old_state: str = "",
        new_state: str = "",
        **kw: Any,
    ) -> None:
        self.record(
            EventType.AGENT_STATE_CHANGE,
            agent=agent_name,
            old_state=old_state,
            new_state=new_state,
        )

    @property
    def events(self) -> list[SimulationEvent]:
        """所有记录的事件。"""
        return list(self._events)

    def get_events(
        self,
        event_type: EventType | str | None = None,
        step: int | None = None,
    ) -> list[SimulationEvent]:
        """获取事件，支持过滤。

        Args:
            event_type: 按事件类型过滤
            step: 按步数过滤

        Returns:
            过滤后的事件列表
        """
        result = self._events
        if event_type is not None:
            et = event_type if isinstance(event_type, str) else event_type.value
            result = [e for e in result if e.event_type == et]
        if step is not None:
            result = [e for e in result if e.step == step]
        return result

    @property
    def event_count(self) -> int:
        """事件总数。"""
        return len(self._events)

    def clear(self) -> None:
        """清除所有事件。"""
        self._events.clear()

    def summary(self) -> dict[str, Any]:
        """生成事件摘要统计。"""
        counts: dict[str, int] = {}
        for event in self._events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1

        return {
            "total_events": len(self._events),
            "event_counts": counts,
            "duration": (
                self._events[-1].timestamp - self._events[0].timestamp
                if len(self._events) >= 2
                else 0.0
            ),
        }

    def export_json(self, path: str | Path) -> Path:
        """导出事件为 JSON 文件。

        Args:
            path: 输出文件路径

        Returns:
            输出文件路径
        """
        output = Path(path)
        data = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.summary(),
            "events": [e.model_dump() for e in self._events],
        }
        output.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8",
        )
        return output

    def export_csv(self, path: str | Path) -> Path:
        """导出事件为 CSV 文件。

        Args:
            path: 输出文件路径

        Returns:
            输出文件路径
        """
        import csv

        output = Path(path)
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "event_type", "step", "data"])
            for event in self._events:
                writer.writerow([
                    event.time_iso,
                    event.event_type,
                    event.step,
                    json.dumps(event.data, ensure_ascii=False),
                ])
        return output

    def __str__(self) -> str:
        return f"EventRecorder(events={len(self._events)})"
