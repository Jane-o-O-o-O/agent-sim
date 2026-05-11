"""Agent base class for the simulation framework."""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_sim.agent.role import Role
from agent_sim.communication.message import Message


class AgentState(str, Enum):
    """Agent 生命周期状态。"""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Agent(BaseModel):
    """Agent 基类。

    所有仿真 Agent 的基础抽象。子类应重写 step() 方法定义具体行为。

    Attributes:
        name: Agent 唯一名称
        role: Agent 角色
        state: 当前状态
        inbox: 收件箱
        step_count: 已执行步数
        context: 运行时上下文存储

    Example:
        >>> class MyAgent(Agent):
        ...     async def step(self):
        ...         for msg in self.inbox:
        ...             ...  # 处理消息
        ...         self.inbox.clear()
        ...         return [Message(sender=self.name, content="done")]
    """

    name: str
    role: Role = Field(default_factory=lambda: Role(name="default"))
    state: AgentState = AgentState.IDLE
    inbox: list[Message] = Field(default_factory=list)
    step_count: int = 0
    context: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(use_enum_values=True)

    def receive(self, message: Message) -> None:
        """接收消息到收件箱。

        Args:
            message: 要接收的消息
        """
        self.inbox.append(message)

    def set_state(self, state: AgentState) -> None:
        """设置 Agent 状态。

        Args:
            state: 目标状态
        """
        self.state = state

    def increment_step(self) -> None:
        """步数计数器 +1。"""
        self.step_count += 1

    async def step(self) -> list[Message]:
        """执行一步仿真逻辑。

        子类应重写此方法实现具体行为。默认实现清空收件箱并返回空列表。

        Returns:
            本次 step 产生的出站消息列表
        """
        self.inbox.clear()
        return []
