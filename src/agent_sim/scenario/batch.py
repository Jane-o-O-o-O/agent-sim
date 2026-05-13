"""Batch simulation runner for statistical analysis of multiple runs."""
from __future__ import annotations

import asyncio
import logging
import statistics
from typing import Any, Callable

from pydantic import BaseModel, Field

from agent_sim.agent.base import Agent
from agent_sim.communication.bus import MessageBus
from agent_sim.environment.sandbox import Sandbox
from agent_sim.scenario.config import ScenarioConfig
from agent_sim.scenario.factory import build_scenario
from agent_sim.scenario.runner import RunResult, ScenarioRunner

logger = logging.getLogger(__name__)


class BatchResult(BaseModel):
    """批量运行结果。

    Attributes:
        results: 每次运行的 RunResult 列表
    """

    results: list[RunResult] = Field(default_factory=list)

    @property
    def statistics(self) -> dict[str, Any]:
        """计算聚合统计。

        Returns:
            统计字典，含平均值、标准差、最小值、最大值
        """
        if not self.results:
            return {"total_runs": 0}

        messages = [r.total_messages for r in self.results]
        durations = [r.duration for r in self.results]
        steps = [r.steps_completed for r in self.results]
        timed_out_count = sum(1 for r in self.results if r.timed_out)

        def _stats(values: list[float]) -> dict[str, float]:
            if len(values) < 2:
                return {
                    "avg": values[0] if values else 0.0,
                    "min": values[0] if values else 0.0,
                    "max": values[0] if values else 0.0,
                    "stdev": 0.0,
                }
            return {
                "avg": round(statistics.mean(values), 4),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "stdev": round(statistics.stdev(values), 4),
            }

        return {
            "total_runs": len(self.results),
            "timed_out_count": timed_out_count,
            "messages": _stats(messages),
            "durations": _stats(durations),
            "steps": _stats(steps),
            "avg_messages": round(statistics.mean(messages), 2) if messages else 0,
            "avg_duration": round(statistics.mean(durations), 4) if durations else 0,
            "avg_steps": round(statistics.mean(steps), 2) if steps else 0,
            "success_rate": round(
                sum(1 for r in self.results if not r.timed_out) / len(self.results), 3
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        """导出为字典。"""
        return {
            "total_runs": len(self.results),
            "statistics": self.statistics,
            "runs": [
                {
                    "steps_completed": r.steps_completed,
                    "total_messages": r.total_messages,
                    "duration": round(r.duration, 4),
                    "timed_out": r.timed_out,
                }
                for r in self.results
            ],
        }


class BatchRunner:
    """批量仿真运行器。

    运行 N 次仿真并收集统计结果。每次运行使用独立的 Sandbox 和 MessageBus。

    Attributes:
        runs: 运行次数

    Example:
        >>> runner = BatchRunner(runs=10)
        >>> result = await runner.run(
        ...     sandbox_factory=lambda: Sandbox(agents=[...]),
        ...     bus_factory=lambda: MessageBus(),
        ...     steps=5,
        ... )
        >>> print(result.statistics)
    """

    def __init__(self, runs: int = 5) -> None:
        if runs < 1:
            raise ValueError("runs 必须 >= 1")
        self.runs = runs

    async def run(
        self,
        sandbox_factory: Callable[[], Sandbox],
        bus_factory: Callable[[], MessageBus],
        steps: int = 10,
        timeout_seconds: float = 0,
    ) -> BatchResult:
        """运行批量仿真。

        Args:
            sandbox_factory: 创建 Sandbox 的工厂函数
            bus_factory: 创建 MessageBus 的工厂函数
            steps: 每次运行的步数
            timeout_seconds: 超时秒数

        Returns:
            BatchResult 批量运行结果
        """
        results: list[RunResult] = []
        logger.info("开始批量运行: %d 次, %d 步/次", self.runs, steps)

        for i in range(self.runs):
            logger.debug("运行第 %d/%d 次", i + 1, self.runs)

            # 每次运行使用独立的实例
            sandbox = sandbox_factory()
            bus = bus_factory()

            # 注册所有 Agent 到 bus
            for agent in sandbox.agents.values():
                if not bus.has_agent(agent.name):
                    bus.register(agent)

            runner = ScenarioRunner(
                sandbox=sandbox,
                bus=bus,
                timeout_seconds=timeout_seconds,
            )
            result = await runner.run(steps=steps)
            results.append(result)

            logger.debug(
                "第 %d 次完成: %d 消息, %.3fs",
                i + 1, result.total_messages, result.duration,
            )

        batch = BatchResult(results=results)
        logger.info(
            "批量运行完成: 平均 %.1f 消息, 平均 %.3fs",
            batch.statistics["avg_messages"],
            batch.statistics["avg_duration"],
        )
        return batch

    async def run_from_config(
        self,
        config: ScenarioConfig,
        runs: int | None = None,
        timeout_seconds: float = 0,
    ) -> BatchResult:
        """从场景配置运行批量仿真。

        Args:
            config: 场景配置
            runs: 运行次数（覆盖构造函数设置）
            timeout_seconds: 超时秒数

        Returns:
            BatchResult 批量运行结果
        """
        n_runs = runs or self.runs

        def _make_sandbox() -> Sandbox:
            sandbox, _ = build_scenario(config)
            return sandbox

        def _make_bus() -> MessageBus:
            _, bus = build_scenario(config)
            return bus

        # 优化：只创建一次配置，然后复用
        original_runs = self.runs
        self.runs = n_runs
        try:
            return await self.run(
                sandbox_factory=_make_sandbox,
                bus_factory=_make_bus,
                steps=config.steps,
                timeout_seconds=timeout_seconds,
            )
        finally:
            self.runs = original_runs
