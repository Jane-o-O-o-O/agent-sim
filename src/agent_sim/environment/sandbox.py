"""Sandbox simulation environment."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_sim.agent.base import Agent
from agent_sim.environment.state import EnvironmentState


class Sandbox(BaseModel):
    """仿真沙箱环境。

    管理 Agent 集合和环境状态，提供仿真生命周期管理。

    Attributes:
        agents: Agent 字典 (name -> Agent)
        state: 环境状态
        current_step: 当前仿真步数

    Example:
        >>> sandbox = Sandbox(agents=[Agent(name="a"), Agent(name="b")])
        >>> sandbox.advance()
        >>> sandbox.current_step
        1
    """

    agents: dict[str, Agent] = Field(default_factory=dict)
    state: EnvironmentState = Field(default_factory=EnvironmentState)
    current_step: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, agents: list[Agent] | None = None, **kwargs: Any) -> None:
        agent_dict = {a.name: a for a in (agents or [])}
        super().__init__(agents=agent_dict, **kwargs)

    @property
    def agent_count(self) -> int:
        """Agent 数量。"""
        return len(self.agents)

    def add_agent(self, agent: Agent) -> None:
        """添加 Agent 到沙箱。

        Args:
            agent: 要添加的 Agent

        Raises:
            ValueError: 同名 Agent 已存在
        """
        if agent.name in self.agents:
            raise ValueError(f"Agent '{agent.name}' 已存在")
        self.agents[agent.name] = agent

    def get_agent(self, name: str) -> Agent | None:
        """获取 Agent。

        Args:
            name: Agent 名称

        Returns:
            Agent 实例，不存在返回 None
        """
        return self.agents.get(name)

    def remove_agent(self, name: str) -> None:
        """移除 Agent。

        Args:
            name: Agent 名称

        Raises:
            KeyError: Agent 不存在
        """
        if name not in self.agents:
            raise KeyError(f"Agent '{name}' 不存在")
        del self.agents[name]

    def advance(self) -> None:
        """推进仿真一步。"""
        self.current_step += 1
        self.state.step = self.current_step

    def __str__(self) -> str:
        return f"Sandbox(agents={self.agent_count}, step={self.current_step})"
