"""Evaluation system for simulation results."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EvalResult(BaseModel):
    """单个评估器的评估结果。

    Attributes:
        name: 评估器名称
        score: 分数 (0.0-1.0)
        details: 详细信息
        passed: 是否通过阈值
    """

    name: str
    score: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)
    passed: bool = False


class EvalReport(BaseModel):
    """评估报告。

    包含所有评估器的结果和汇总信息。

    Attributes:
        results: 各评估器结果
        overall_score: 综合分数 (0.0-1.0)
        passed: 是否整体通过
    """

    results: list[EvalResult] = Field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False

    def summary(self) -> dict[str, Any]:
        """生成摘要。"""
        return {
            "overall_score": round(self.overall_score, 3),
            "passed": self.passed,
            "evaluators": [
                {"name": r.name, "score": round(r.score, 3), "passed": r.passed}
                for r in self.results
            ],
        }


class Evaluator(ABC):
    """评估器抽象基类。

    子类实现 evaluate() 方法定义具体的评估逻辑。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """评估器名称。"""
        ...

    @abstractmethod
    def evaluate(self, data: dict[str, Any]) -> EvalResult:
        """评估仿真结果。

        Args:
            data: 仿真运行结果数据

        Returns:
            EvalResult 评估结果
        """
        ...


class MessageVolumeEvaluator(Evaluator):
    """消息量评估器。

    评估仿真中消息通信的活跃度。
    """

    @property
    def name(self) -> str:
        return "message_volume"

    def __init__(self, min_messages: int = 1, threshold: float = 0.5) -> None:
        self.min_messages = min_messages
        self.threshold = threshold

    def evaluate(self, data: dict[str, Any]) -> EvalResult:
        """评估消息量是否达标。"""
        total = data.get("total_messages", 0)
        steps = data.get("steps_completed", 1)
        avg_per_step = total / steps if steps > 0 else 0

        score = min(1.0, total / max(self.min_messages, 1))
        passed = score >= self.threshold

        return EvalResult(
            name=self.name,
            score=score,
            passed=passed,
            details={
                "total_messages": total,
                "avg_per_step": round(avg_per_step, 2),
                "min_required": self.min_messages,
            },
        )


class AgentParticipationEvaluator(Evaluator):
    """Agent 参与度评估器。

    评估所有 Agent 是否都参与了仿真。
    """

    @property
    def name(self) -> str:
        return "agent_participation"

    def __init__(self, threshold: float = 0.8) -> None:
        self.threshold = threshold

    def evaluate(self, data: dict[str, Any]) -> EvalResult:
        """评估 Agent 参与度。"""
        states = data.get("agent_states", {})
        if not states:
            return EvalResult(
                name=self.name,
                score=0.0,
                passed=False,
                details={"reason": "no agent states"},
            )

        total = len(states)
        completed = sum(1 for s in states.values() if s == "completed")
        score = completed / total if total > 0 else 0
        passed = score >= self.threshold

        return EvalResult(
            name=self.name,
            score=score,
            passed=passed,
            details={
                "total_agents": total,
                "completed": completed,
                "failed": sum(1 for s in states.values() if s == "failed"),
            },
        )


class CompletionEvaluator(Evaluator):
    """完成度评估器。

    评估仿真是否按预期步数完成。
    """

    @property
    def name(self) -> str:
        return "completion"

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold

    def evaluate(self, data: dict[str, Any]) -> EvalResult:
        """评估完成度。"""
        steps = data.get("steps_completed", 0)
        expected = data.get("expected_steps", steps)
        score = min(1.0, steps / expected) if expected > 0 else 0.0
        passed = score >= self.threshold

        return EvalResult(
            name=self.name,
            score=score,
            passed=passed,
            details={
                "steps_completed": steps,
                "expected_steps": expected,
            },
        )


class LatencyEvaluator(Evaluator):
    """延迟评估器。

    评估仿真运行时间是否在可接受范围内。
    """

    @property
    def name(self) -> str:
        return "latency"

    def __init__(self, max_duration: float = 60.0, threshold: float = 0.5) -> None:
        self.max_duration = max_duration
        self.threshold = threshold

    def evaluate(self, data: dict[str, Any]) -> EvalResult:
        """评估运行延迟。"""
        duration = data.get("duration_seconds", 0)
        score = max(0.0, 1.0 - (duration / self.max_duration))
        passed = score >= self.threshold

        return EvalResult(
            name=self.name,
            score=score,
            passed=passed,
            details={
                "duration_seconds": round(duration, 4),
                "max_allowed": self.max_duration,
            },
        )


class NetworkHealthEvaluator(Evaluator):
    """网络健康度评估器。

    评估仿真中 Agent 通信网络的连接密度和健康度。
    """

    @property
    def name(self) -> str:
        return "network_health"

    def __init__(self, threshold: float = 0.3) -> None:
        self.threshold = threshold

    def evaluate(self, data: dict[str, Any]) -> EvalResult:
        """评估网络拓扑健康度。"""
        topo = data.get("topology", {})
        if not topo:
            return EvalResult(
                name=self.name,
                score=0.0,
                passed=False,
                details={"reason": "no topology data"},
            )

        agents = topo.get("agents", 0)
        links = topo.get("links", 0)
        avg_degree = topo.get("avg_degree", 0)

        if agents <= 1:
            score = 1.0
        else:
            # 健康度 = min(1, avg_degree / (agents - 1))
            # 全连接时 avg_degree = agents-1，score = 1.0
            score = min(1.0, avg_degree / max(agents - 1, 1))

        passed = score >= self.threshold
        return EvalResult(
            name=self.name,
            score=score,
            passed=passed,
            details={
                "agents": agents,
                "links": links,
                "avg_degree": round(avg_degree, 2),
            },
        )


class ConversationFlowEvaluator(Evaluator):
    """对话流均衡度评估器。

    评估各 Agent 参与对话的均衡程度。
    """

    @property
    def name(self) -> str:
        return "conversation_flow"

    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = threshold

    def evaluate(self, data: dict[str, Any]) -> EvalResult:
        """评估对话均衡度。"""
        counts = data.get("agent_message_counts", {})
        if not counts:
            return EvalResult(
                name=self.name,
                score=0.0,
                passed=False,
                details={"reason": "no agent message counts"},
            )

        if len(counts) == 1:
            return EvalResult(
                name=self.name,
                score=1.0,
                passed=True,
                details={"agents": 1, "balance": 1.0},
            )

        values = list(counts.values())
        max_count = max(values)
        min_count = min(values)

        # 均衡度 = 1 - (max-min)/max
        balance = 1.0 - ((max_count - min_count) / max_count) if max_count > 0 else 0.0
        score = balance
        passed = score >= self.threshold

        return EvalResult(
            name=self.name,
            score=score,
            passed=passed,
            details={
                "agents": len(counts),
                "balance": round(balance, 3),
                "max_messages": max_count,
                "min_messages": min_count,
            },
        )


class EvalSuite:
    """评估套件。

    管理多个评估器，运行综合评估。

    Attributes:
        evaluators: 评估器列表
        pass_threshold: 综合通过阈值

    Example:
        >>> suite = EvalSuite()
        >>> suite.add(MessageVolumeEvaluator(min_messages=5))
        >>> suite.add(AgentParticipationEvaluator())
        >>> report = suite.run(result_dict)
    """

    def __init__(self, pass_threshold: float = 0.6) -> None:
        self.evaluators: list[Evaluator] = []
        self.pass_threshold = pass_threshold

    def add(self, evaluator: Evaluator) -> None:
        """添加评估器。"""
        self.evaluators.append(evaluator)

    def run(self, data: dict[str, Any]) -> EvalReport:
        """运行所有评估器。

        Args:
            data: 仿真结果数据

        Returns:
            EvalReport 综合评估报告
        """
        results: list[EvalResult] = []
        for evaluator in self.evaluators:
            try:
                result = evaluator.evaluate(data)
                results.append(result)
                logger.debug("评估 %s: score=%.3f passed=%s", result.name, result.score, result.passed)
            except Exception as e:
                logger.error("评估器 %s 失败: %s", evaluator.name, e)
                results.append(EvalResult(
                    name=evaluator.name,
                    score=0.0,
                    passed=False,
                    details={"error": str(e)},
                ))

        overall = sum(r.score for r in results) / len(results) if results else 0.0
        all_passed = all(r.passed for r in results) if results else False

        return EvalReport(
            results=results,
            overall_score=overall,
            passed=overall >= self.pass_threshold and all_passed,
        )

    @classmethod
    def default(cls) -> EvalSuite:
        """创建默认评估套件。"""
        suite = cls()
        suite.add(MessageVolumeEvaluator(min_messages=1))
        suite.add(AgentParticipationEvaluator())
        suite.add(CompletionEvaluator())
        suite.add(LatencyEvaluator())
        return suite
