"""Scenario runner for executing simulations with lifecycle hooks."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from agent_sim.agent.base import Agent, AgentState
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message
from agent_sim.environment.sandbox import Sandbox
from agent_sim.metrics.collector import MetricsCollector
from agent_sim.scenario.hooks import LifecycleHooks

logger = logging.getLogger(__name__)


class RunResult(BaseModel):
    """仿真运行结果。

    Attributes:
        steps_completed: 完成的步骤数
        total_messages: 总消息数
        agent_states: 各 Agent 最终状态
        duration: 运行耗时（秒）
        metrics: 指标摘要
        message_history: 所有消息历史
    """

    steps_completed: int = 0
    total_messages: int = 0
    agent_states: dict[str, str] = Field(default_factory=dict)
    duration: float = 0.0
    metrics: dict[str, Any] = Field(default_factory=dict)
    message_history: list[dict[str, Any]] = Field(default_factory=list)


class ScenarioRunner:
    """场景运行器。

    协调 Sandbox、MessageBus 和 Agent，执行 N 步仿真循环。
    支持生命周期钩子，可在仿真各阶段注入自定义逻辑。

    每步流程：
    1. 触发 on_step_start 钩子
    2. 推进沙箱步数
    3. 对每个 Agent 调用 step()
    4. 通过 MessageBus 路由产生的消息
    5. 触发 on_message 钩子
    6. 记录指标
    7. 触发 on_step_end 钩子

    Attributes:
        sandbox: 仿真沙箱
        bus: 通信总线
        max_steps: 最大步数限制
        metrics: 指标收集器
        hooks: 生命周期钩子管理器

    Example:
        >>> runner = ScenarioRunner(sandbox=sandbox, bus=bus, max_steps=10)
        >>> runner.hooks.on_step_end(lambda step, msgs: print(f"Step {step}"))
        >>> result = await runner.run(steps=5)
    """

    def __init__(
        self,
        sandbox: Sandbox,
        bus: MessageBus,
        max_steps: int = 10,
        hooks: LifecycleHooks | None = None,
        concurrent: bool = False,
    ) -> None:
        self.sandbox = sandbox
        self.bus = bus
        self.max_steps = max_steps
        self.metrics = MetricsCollector()
        self.hooks = hooks or LifecycleHooks()
        self.concurrent = concurrent

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
            old_state = agent.state
            agent.set_state(AgentState.RUNNING)
            await self.hooks.trigger(
                "on_agent_state_change",
                agent_name=agent.name,
                old_state=old_state,
                new_state=AgentState.RUNNING.value,
            )

        await self.hooks.trigger(
            "on_simulation_start",
            steps=n_steps,
            agent_count=self.sandbox.agent_count,
        )

        total_messages = 0

        for step in range(n_steps):
            await self.hooks.trigger("on_step_start", step=step + 1)
            self.sandbox.advance()
            step_messages = await self._run_step()
            total_messages += step_messages
            self.metrics.record_step(
                messages_sent=step_messages,
                agents_active=self.sandbox.agent_count,
            )
            await self.hooks.trigger(
                "on_step_end",
                step=step + 1,
                messages_sent=step_messages,
            )

        # 完成后更新状态
        for name, agent in self.sandbox.agents.items():
            if agent.state == AgentState.RUNNING.value:
                old_state = agent.state
                agent.set_state(AgentState.COMPLETED)
                await self.hooks.trigger(
                    "on_agent_state_change",
                    agent_name=name,
                    old_state=old_state,
                    new_state=AgentState.COMPLETED.value,
                )
            self.metrics.record_agent_state(name, agent.state)

        duration = time.time() - start_time

        result = RunResult(
            steps_completed=n_steps,
            total_messages=total_messages,
            agent_states=dict(self.metrics.agent_states),
            duration=duration,
            metrics=self.metrics.summary(),
            message_history=[
                {
                    "sender": msg.sender,
                    "receiver": msg.receiver,
                    "content": msg.content,
                    "type": msg.msg_type,
                    "timestamp": msg.timestamp,
                }
                for msg in self.bus.history
            ],
        )

        await self.hooks.trigger(
            "on_simulation_end",
            result=result,
            duration=duration,
        )

        return result

    async def _run_step(self) -> int:
        """执行单步仿真。

        根据 concurrent 配置选择顺序或并发执行。

        Returns:
            本步产生的消息数
        """
        if self.concurrent:
            return await self._run_step_concurrent()
        return await self._run_step_sequential()

    async def _run_step_sequential(self) -> int:
        """顺序执行单步仿真。"""
        step_messages = 0

        for agent in self.sandbox.agents.values():
            try:
                messages = await agent.step()
                for msg in messages:
                    self.bus.send(msg)
                    step_messages += 1
                    await self.hooks.trigger(
                        "on_message",
                        message=msg,
                        step=self.sandbox.current_step,
                    )
            except Exception as e:
                agent.set_state(AgentState.FAILED)
                self.sandbox.state.add_event(
                    "agent_error",
                    {"agent": agent.name, "step": self.sandbox.current_step},
                )
                await self.hooks.trigger(
                    "on_agent_error",
                    agent_name=agent.name,
                    error=str(e),
                    step=self.sandbox.current_step,
                )

        return step_messages

    async def _run_step_concurrent(self) -> int:
        """并发执行单步仿真 — 所有 Agent 同时 step()。

        使用 asyncio.gather 并行运行所有 Agent，提高 I/O 密集型场景性能。

        Returns:
            本步产生的消息数
        """
        agents = list(self.sandbox.agents.values())

        async def _step_agent(agent: Agent) -> list[Message]:
            """单个 Agent 的 step 包装，捕获异常。"""
            try:
                return await agent.step()
            except Exception as e:
                agent.set_state(AgentState.FAILED)
                self.sandbox.state.add_event(
                    "agent_error",
                    {"agent": agent.name, "step": self.sandbox.current_step},
                )
                await self.hooks.trigger(
                    "on_agent_error",
                    agent_name=agent.name,
                    error=str(e),
                    step=self.sandbox.current_step,
                )
                return []

        # 并发执行所有 Agent step
        results = await asyncio.gather(*[_step_agent(a) for a in agents])

        # 收集并路由消息
        step_messages = 0
        for messages in results:
            for msg in messages:
                self.bus.send(msg)
                step_messages += 1
                await self.hooks.trigger(
                    "on_message",
                    message=msg,
                    step=self.sandbox.current_step,
                )

        return step_messages
