"""Tests for evaluation system."""
from __future__ import annotations

import pytest

from agent_sim.metrics.evaluator import (
    AgentParticipationEvaluator,
    CompletionEvaluator,
    EvalReport,
    EvalResult,
    EvalSuite,
    Evaluator,
    LatencyEvaluator,
    MessageVolumeEvaluator,
)


class TestEvalResult:
    """EvalResult 模型测试。"""

    def test_create_result(self) -> None:
        result = EvalResult(name="test", score=0.8, passed=True)
        assert result.name == "test"
        assert result.score == 0.8
        assert result.passed is True
        assert result.details == {}

    def test_result_with_details(self) -> None:
        result = EvalResult(
            name="test",
            score=0.5,
            details={"total": 10, "completed": 5},
        )
        assert result.details["total"] == 10


class TestEvalReport:
    """EvalReport 模型测试。"""

    def test_create_report(self) -> None:
        report = EvalReport(overall_score=0.85, passed=True)
        assert report.overall_score == 0.85
        assert report.passed is True
        assert report.results == []

    def test_report_summary(self) -> None:
        report = EvalReport(
            results=[
                EvalResult(name="a", score=0.9, passed=True),
                EvalResult(name="b", score=0.7, passed=True),
            ],
            overall_score=0.8,
            passed=True,
        )
        summary = report.summary()
        assert summary["overall_score"] == 0.8
        assert summary["passed"] is True
        assert len(summary["evaluators"]) == 2


class TestMessageVolumeEvaluator:
    """消息量评估器测试。"""

    def test_name(self) -> None:
        ev = MessageVolumeEvaluator()
        assert ev.name == "message_volume"

    def test_enough_messages(self) -> None:
        ev = MessageVolumeEvaluator(min_messages=5, threshold=0.5)
        result = ev.evaluate({"total_messages": 10, "steps_completed": 5})
        assert result.passed is True
        assert result.score == 1.0

    def test_few_messages(self) -> None:
        ev = MessageVolumeEvaluator(min_messages=10, threshold=0.5)
        result = ev.evaluate({"total_messages": 2, "steps_completed": 5})
        assert result.passed is False
        assert result.score == pytest.approx(0.2)

    def test_zero_messages(self) -> None:
        ev = MessageVolumeEvaluator(min_messages=1, threshold=0.5)
        result = ev.evaluate({"total_messages": 0, "steps_completed": 1})
        assert result.score == 0.0
        assert result.passed is False


class TestAgentParticipationEvaluator:
    """Agent 参与度评估器测试。"""

    def test_name(self) -> None:
        ev = AgentParticipationEvaluator()
        assert ev.name == "agent_participation"

    def test_all_completed(self) -> None:
        ev = AgentParticipationEvaluator(threshold=0.8)
        result = ev.evaluate({
            "agent_states": {"a": "completed", "b": "completed", "c": "completed"}
        })
        assert result.score == 1.0
        assert result.passed is True

    def test_partial_completion(self) -> None:
        ev = AgentParticipationEvaluator(threshold=0.8)
        result = ev.evaluate({
            "agent_states": {"a": "completed", "b": "completed", "c": "failed"}
        })
        assert result.score == pytest.approx(2 / 3)
        assert result.passed is False

    def test_no_agents(self) -> None:
        ev = AgentParticipationEvaluator()
        result = ev.evaluate({"agent_states": {}})
        assert result.score == 0.0
        assert result.passed is False


class TestCompletionEvaluator:
    """完成度评估器测试。"""

    def test_name(self) -> None:
        ev = CompletionEvaluator()
        assert ev.name == "completion"

    def test_full_completion(self) -> None:
        ev = CompletionEvaluator(threshold=1.0)
        result = ev.evaluate({"steps_completed": 10, "expected_steps": 10})
        assert result.score == 1.0
        assert result.passed is True

    def test_partial_completion(self) -> None:
        ev = CompletionEvaluator(threshold=0.5)
        result = ev.evaluate({"steps_completed": 5, "expected_steps": 10})
        assert result.score == 0.5
        assert result.passed is True


class TestLatencyEvaluator:
    """延迟评估器测试。"""

    def test_name(self) -> None:
        ev = LatencyEvaluator()
        assert ev.name == "latency"

    def test_fast_run(self) -> None:
        ev = LatencyEvaluator(max_duration=60, threshold=0.5)
        result = ev.evaluate({"duration_seconds": 5.0})
        assert result.score > 0.9
        assert result.passed is True

    def test_slow_run(self) -> None:
        ev = LatencyEvaluator(max_duration=10, threshold=0.5)
        result = ev.evaluate({"duration_seconds": 8.0})
        assert result.score < 0.3
        assert result.passed is False


class TestEvalSuite:
    """评估套件测试。"""

    def test_create_suite(self) -> None:
        suite = EvalSuite()
        assert suite.evaluators == []
        assert suite.pass_threshold == 0.6

    def test_add_evaluator(self) -> None:
        suite = EvalSuite()
        suite.add(MessageVolumeEvaluator())
        assert len(suite.evaluators) == 1

    def test_run_suite(self) -> None:
        suite = EvalSuite(pass_threshold=0.5)
        suite.add(MessageVolumeEvaluator(min_messages=1))
        suite.add(AgentParticipationEvaluator())

        report = suite.run({
            "total_messages": 10,
            "steps_completed": 5,
            "agent_states": {"a": "completed", "b": "completed"},
        })

        assert isinstance(report, EvalReport)
        assert report.overall_score > 0
        assert len(report.results) == 2

    def test_default_suite(self) -> None:
        suite = EvalSuite.default()
        assert len(suite.evaluators) == 4

    def test_run_default_suite(self) -> None:
        suite = EvalSuite.default()
        report = suite.run({
            "total_messages": 20,
            "steps_completed": 5,
            "expected_steps": 5,
            "agent_states": {"a": "completed", "b": "completed"},
            "duration_seconds": 1.0,
        })
        assert report.passed is True
        assert report.overall_score > 0.8

    def test_evaluator_error_handling(self) -> None:
        """评估器异常不应导致整个套件崩溃。"""

        class BadEvaluator(Evaluator):
            @property
            def name(self) -> str:
                return "bad"

            def evaluate(self, data: dict) -> EvalResult:
                raise RuntimeError("boom")

        suite = EvalSuite(pass_threshold=0.0)
        suite.add(BadEvaluator())
        suite.add(MessageVolumeEvaluator(min_messages=1))

        report = suite.run({"total_messages": 5, "steps_completed": 1})
        assert len(report.results) == 2
        assert report.results[0].score == 0.0
        assert report.results[0].details.get("error") == "boom"
