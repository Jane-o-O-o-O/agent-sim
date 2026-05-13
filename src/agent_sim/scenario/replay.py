"""Event replay engine for stepping through recorded simulation events."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from agent_sim.scenario.recorder import EventRecorder, SimulationEvent

logger = logging.getLogger(__name__)


class ReplayEngine:
    """事件回放引擎。

    加载 EventRecorder 记录的事件数据，支持按步回放、过滤、导出。
    用于调试和分析仿真过程。

    Attributes:
        _events: 所有事件列表
        _total_steps: 总步数

    Example:
        >>> recorder = EventRecorder()
        >>> # ... record events ...
        >>> engine = ReplayEngine.from_recorder(recorder)
        >>> for step_events in engine.iter_steps():
        ...     print(f"Step has {len(step_events)} events")
    """

    def __init__(self, events: list[SimulationEvent]) -> None:
        self._events = list(events)
        self._total_steps = max((e.step for e in self._events), default=0)

    @classmethod
    def from_recorder(cls, recorder: EventRecorder) -> ReplayEngine:
        """从 EventRecorder 创建回放引擎。

        Args:
            recorder: 已记录事件的 EventRecorder 实例

        Returns:
            ReplayEngine 实例
        """
        return cls(recorder.events)

    @classmethod
    def from_json(cls, path: str | Path) -> ReplayEngine:
        """从 JSON 文件加载回放数据。

        Args:
            path: JSON 文件路径（EventRecorder.export_json 导出的格式）

        Returns:
            ReplayEngine 实例

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: JSON 格式错误
        """
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"回放文件不存在: {filepath}")

        data = json.loads(filepath.read_text(encoding="utf-8"))
        events_data = data.get("events", [])
        events = [SimulationEvent(**e) for e in events_data]
        logger.info("加载回放数据: %d 事件 from %s", len(events), filepath)
        return cls(events)

    @property
    def total_steps(self) -> int:
        """总步数。"""
        return self._total_steps

    @property
    def event_count(self) -> int:
        """事件总数。"""
        return len(self._events)

    def get_step(self, step: int) -> list[SimulationEvent]:
        """获取指定步数的所有事件。

        Args:
            step: 步数

        Returns:
            该步的所有事件列表
        """
        return [e for e in self._events if e.step == step]

    def filter_by_type(self, event_type: str) -> list[SimulationEvent]:
        """按事件类型过滤。

        Args:
            event_type: 事件类型字符串

        Returns:
            匹配的事件列表
        """
        return [e for e in self._events if e.event_type == event_type]

    def iter_steps(self) -> list[list[SimulationEvent]]:
        """按步迭代所有事件。

        Returns:
            每步事件的列表
        """
        steps: dict[int, list[SimulationEvent]] = {}
        for event in self._events:
            steps.setdefault(event.step, []).append(event)
        return [steps[s] for s in sorted(steps.keys())]

    def timeline(self) -> list[dict[str, Any]]:
        """获取事件时间线（按时间顺序）。

        Returns:
            事件字典列表，每项包含 event_type, timestamp, step, data
        """
        return [
            {
                "event_type": e.event_type,
                "timestamp": e.timestamp,
                "step": e.step,
                "data": e.data,
                "time_iso": e.time_iso,
            }
            for e in self._events
        ]

    def to_dict(self) -> dict[str, Any]:
        """导出回放数据为字典。

        Returns:
            包含回放摘要和事件数据的字典
        """
        steps_data: dict[int, list[dict[str, Any]]] = {}
        for event in self._events:
            step_list = steps_data.setdefault(event.step, [])
            step_list.append({
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "data": event.data,
            })

        return {
            "total_steps": self._total_steps,
            "event_count": len(self._events),
            "summary": self.summary(),
            "steps": {
                str(k): v for k, v in sorted(steps_data.items())
            },
        }

    def summary(self) -> dict[str, Any]:
        """生成回放摘要。

        Returns:
            摘要字典，含事件类型统计、步数等
        """
        counts: dict[str, int] = {}
        for event in self._events:
            counts[event.event_type] = counts.get(event.event_type, 0) + 1

        return {
            "total_events": len(self._events),
            "total_steps": self._total_steps,
            "event_counts": counts,
        }

    def __str__(self) -> str:
        return f"ReplayEngine(events={len(self._events)}, steps={self._total_steps})"
