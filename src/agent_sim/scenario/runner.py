"""Scenario runner for executing simulations."""
from __future__ import annotations

import time
from typing import Any

from pydantic import BaseModel, Field

from agent_sim.agent.base import Agent, AgentState
from agent_sim.communication.bus import MessageBus
from agent_sim.environment.sandbox import Sandbox
from agent_sim.metrics.collector import MetricsCollector


class RunResult(BaseModel):
    """仿真运行结果。

    Attributes:
        steps_completed: 完成的步骤数
        total_messages: 总消息数
        agent_states: 各 Agent 最终状态
        duration: 运行耗时（秒）
        metrics: 指标摘要
    """

    steps_completed: int = 0
    total_messages: int = 0
    agent_states: dict[str, str] = Field(default_factory=dict)
    duration: float = 0.0
    metrics: dict[str, Any] = Field(default_factory=dict)


class ScenarioRunner:
    """场景运行器。

    协调 Sandbox、MessageBus 和 Agent，执行 N 步仿真循环。

    每步流程：
    1. 推进沙箱步数
    2. 对每个 Agent 调用 step()
    3. 通过 MessageBus 路由产生的消息
    4. 记录指标

    Attributes:
        sandbox: 仿真沙箱
        bus: 通信总线
        max_steps: 最大步数限制
        metrics: 指标收集器

    Example:
        >>> runner = ScenarioRunner(sandbox=sandbox, bus=bus, max_steps=10)
        >>> result = await runner.run(steps=5)
        >>> print(result.total_messages)
    """

    def __init__(
        self,
        sandbox: Sandbox,
        bus: MessageBus,
        max_steps: int = 10,
    ) -> None:
        self.sandbox = sandbox
        self.bus = bus
        self.max_steps = max_steps
        self.metrics = MetricsCollector()

    async def run(self, steps: int | None = None) -> RunResult:
        """运行仿真。

        Args:
            steps: 运行步数，默认使用 max_steps

        Returns:
            RunResult 仿真结果
        """
        n_steps = steps or self.max_steps
        start_time = time.time()

        # 设置所有 Agent 为 RUNNING
        for agent in self.sandbox.agents.values():
            agent.set_state(AgentState.RUNNING)

        total_messages = 0

        for step in range(n_steps):
            self.sandbox.advance()
            step_messages = await self._run_step()
            total_messages += step_messages
            self.metrics.record_step(
                messages_sent=step_messages,
                agents_active=self.sandbox.agent_count,
            )

        # 完成后更新状态
        for name, agent in self.sandbox.agents.items():
            if agent.state == AgentState.RUNNING.value:
                agent.set_state(AgentState.COMPLETED)
            self.metrics.record_agent_state(name, agent.state)

        duration = time.time() - start_time

        return RunResult(
            steps_completed=n_steps,
            total_messages=total_messages,
            agent_states=dict(self.metrics.agent_states),
            duration=duration,
            metrics=self.metrics.summary(),
        )

    async def _run_step(self) -> int:
        """执行单步仿真。

        Returns:
            本步产生的消息数
        """
        step_messages = 0

        for agent in self.sandbox.agents.values():
            try:
                messages = await agent.step()
                for msg in messages:
                    self.bus.send(msg)
                    step_messages += 1
            except Exception:
                agent.set_state(AgentState.FAILED)
                self.sandbox.state.add_event(
                    "agent_error",
                    {"agent": agent.name, "step": self.sandbox.current_step},
                )

        return step_messages
