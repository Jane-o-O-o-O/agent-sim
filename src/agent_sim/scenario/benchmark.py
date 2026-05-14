"""Performance benchmark runner for large-scale agent simulations."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from pydantic import BaseModel, Field

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.role import Role
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.scenario.runner import ScenarioRunner

logger = logging.getLogger(__name__)


class BenchmarkResult(BaseModel):
    """基准测试结果。

    Attributes:
        agent_count: Agent 数量
        steps: 仿真步数
        total_messages: 总消息数
        duration: 运行耗时（秒）
        throughput: 吞吐量（消息/秒）
        steps_per_second: 每秒步数
        peak_memory_hint: 峰值内存估计
        timed_out: 是否超时
    """

    agent_count: int = 0
    steps: int = 0
    total_messages: int = 0
    duration: float = 0.0
    throughput: float = 0.0
    steps_per_second: float = 0.0
    peak_memory_hint: int = 0
    timed_out: bool = False


class BenchmarkSuite(BaseModel):
    """基准测试套件结果。

    Attributes:
        results: 各规模测试结果
        scale_agents: 测试的 Agent 规模列表
    """

    results: list[BenchmarkResult] = Field(default_factory=list)
    scale_agents: list[int] = Field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        """生成摘要。"""
        if not self.results:
            return {"error": "no results"}
        return {
            "total_runs": len(self.results),
            "max_agents": max(r.agent_count for r in self.results),
            "max_throughput": max(r.throughput for r in self.results),
            "results": [
                {
                    "agents": r.agent_count,
                    "messages": r.total_messages,
                    "duration": round(r.duration, 4),
                    "throughput": round(r.throughput, 1),
                    "steps_per_second": round(r.steps_per_second, 1),
                }
                for r in self.results
            ],
        }


class EchoBenchmarkAgent(Agent):
    """基准测试用 Echo Agent。

    回复收到的每条消息，模拟基本的通信模式。
    """

    async def step(self) -> list[Message]:
        """回声收到的消息。"""
        replies: list[Message] = []
        for msg in self.inbox:
            replies.append(Message(
                sender=self.name, receiver=msg.sender,
                content=f"echo:{msg.content}",
                msg_type=MessageType.RESPONSE,
            ))
        self.inbox.clear()
        self.increment_step()
        return replies


class BenchmarkRunner:
    """性能基准测试运行器。

    创建大量 Agent 进行并发仿真，测量吞吐量、延迟等性能指标。

    Features:
        - 可配置 Agent 数量（10-1000+）
        - 多规模梯度测试
        - 吞吐量和延迟统计
        - 超时保护

    Example:
        >>> runner = BenchmarkRunner()
        >>> suite = await runner.run_scale_test(
        ...     agent_counts=[10, 50, 100],
        ...     steps=10,
        ... )
        >>> print(suite.summary())
    """

    def __init__(self, timeout_seconds: float = 60.0) -> None:
        self._timeout = timeout_seconds

    async def run_single(
        self,
        agent_count: int,
        steps: int = 10,
        topology: str = "mesh",
    ) -> BenchmarkResult:
        """运行单次基准测试。

        Args:
            agent_count: Agent 数量
            steps: 仿真步数
            topology: 拓扑类型 (mesh/star/ring)

        Returns:
            测试结果
        """
        agents = self._create_agents(agent_count)
        sandbox = Sandbox(agents=agents)
        bus = MessageBus()
        for agent in agents:
            bus.register(agent)

        # 发送初始消息激发通信
        if agent_count >= 2:
            bus.send(Message(
                sender=agents[0].name, receiver=agents[1].name,
                content="benchmark_start", msg_type=MessageType.REQUEST,
            ))

        runner = ScenarioRunner(
            sandbox=sandbox, bus=bus, timeout_seconds=self._timeout,
        )

        start = time.perf_counter()
        result = await runner.run(steps=steps)
        duration = time.perf_counter() - start

        throughput = result.total_messages / duration if duration > 0 else 0
        steps_per_sec = result.steps_completed / duration if duration > 0 else 0

        return BenchmarkResult(
            agent_count=agent_count,
            steps=result.steps_completed,
            total_messages=result.total_messages,
            duration=duration,
            throughput=throughput,
            steps_per_second=steps_per_sec,
            timed_out=result.timed_out,
        )

    async def run_scale_test(
        self,
        agent_counts: list[int] | None = None,
        steps: int = 10,
        topology: str = "mesh",
    ) -> BenchmarkSuite:
        """运行多规模梯度测试。

        Args:
            agent_counts: Agent 数量梯度列表
            steps: 每次测试的仿真步数
            topology: 拓扑类型

        Returns:
            测试套件结果
        """
        if agent_counts is None:
            agent_counts = [5, 10, 25, 50, 100]

        suite = BenchmarkSuite(scale_agents=agent_counts)

        for count in agent_counts:
            logger.info("基准测试: %d agents, %d steps", count, steps)
            result = await self.run_single(count, steps, topology)
            suite.results.append(result)
            logger.info(
                "  结果: %.3fs, %d msgs, %.1f msgs/s",
                result.duration, result.total_messages, result.throughput,
            )

        return suite

    @staticmethod
    def _create_agents(count: int) -> list[Agent]:
        """创建测试 Agent 列表。

        Args:
            count: Agent 数量

        Returns:
            Agent 列表
        """
        agents = []
        for i in range(count):
            agent = EchoBenchmarkAgent(
                name=f"bench_agent_{i}",
                role=Role(name="benchmark", goals=["echo messages"]),
            )
            agents.append(agent)
        return agents
