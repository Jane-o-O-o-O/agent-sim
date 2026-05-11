"""Metrics collector for simulation results."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MetricsCollector(BaseModel):
    """仿真指标收集器。

    在仿真运行期间收集各步骤的指标数据。

    Example:
        >>> collector = MetricsCollector()
        >>> collector.record_step(messages_sent=5, agents_active=3)
        >>> collector.summary()
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    step_count: int = 0
    total_messages: int = 0
    agent_states: dict[str, str] = Field(default_factory=dict)
    step_details: list[dict[str, Any]] = Field(default_factory=list)

    def record_step(self, messages_sent: int = 0, agents_active: int = 0) -> None:
        """记录一个步骤的指标。

        Args:
            messages_sent: 本步发送的消息数
            agents_active: 活跃 Agent 数
        """
        self.step_count += 1
        self.total_messages += messages_sent
        self.step_details.append({
            "step": self.step_count,
            "messages_sent": messages_sent,
            "agents_active": agents_active,
        })

    def record_agent_state(self, agent_name: str, state: str) -> None:
        """记录 Agent 最终状态。

        Args:
            agent_name: Agent 名称
            state: 状态值
        """
        self.agent_states[agent_name] = state

    def summary(self) -> dict[str, Any]:
        """生成指标摘要。"""
        return {
            "total_steps": self.step_count,
            "total_messages": self.total_messages,
            "agent_states": dict(self.agent_states),
            "avg_messages_per_step": (
                self.total_messages / self.step_count if self.step_count > 0 else 0
            ),
        }

    def __str__(self) -> str:
        return f"MetricsCollector(steps={self.step_count}, messages={self.total_messages})"
