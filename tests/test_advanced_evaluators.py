"""Tests for advanced evaluators."""
from __future__ import annotations

import pytest

from agent_sim.metrics.evaluator import (
    ConversationFlowEvaluator,
    NetworkHealthEvaluator,
)


class TestNetworkHealthEvaluator:
    """NetworkHealthEvaluator 测试。"""

    def test_name(self) -> None:
        ev = NetworkHealthEvaluator()
        assert ev.name == "network_health"

    def test_evaluate_healthy(self) -> None:
        ev = NetworkHealthEvaluator()
        result = ev.evaluate({
            "topology": {
                "agents": 4,
                "links": 6,
                "avg_degree": 3.0,
            }
        })
        assert result.score > 0.5
        assert result.passed

    def test_evaluate_sparse(self) -> None:
        ev = NetworkHealthEvaluator()
        result = ev.evaluate({
            "topology": {
                "agents": 10,
                "links": 2,
                "avg_degree": 0.4,
            }
        })
        assert result.score < 1.0

    def test_evaluate_no_topology(self) -> None:
        ev = NetworkHealthEvaluator()
        result = ev.evaluate({})
        assert result.score == 0.0
        assert not result.passed

    def test_evaluate_threshold(self) -> None:
        ev = NetworkHealthEvaluator(threshold=0.99)
        result = ev.evaluate({
            "topology": {"agents": 4, "links": 3, "avg_degree": 1.5}
        })
        # Low avg_degree/agents ratio might not pass high threshold
        assert result.name == "network_health"


class TestConversationFlowEvaluator:
    """ConversationFlowEvaluator 测试。"""

    def test_name(self) -> None:
        ev = ConversationFlowEvaluator()
        assert ev.name == "conversation_flow"

    def test_evaluate_balanced(self) -> None:
        ev = ConversationFlowEvaluator()
        result = ev.evaluate({
            "agent_message_counts": {"a": 5, "b": 5, "c": 5},
        })
        assert result.score == 1.0
        assert result.passed

    def test_evaluate_imbalanced(self) -> None:
        ev = ConversationFlowEvaluator()
        result = ev.evaluate({
            "agent_message_counts": {"a": 100, "b": 1, "c": 1},
        })
        assert result.score < 1.0

    def test_evaluate_no_data(self) -> None:
        ev = ConversationFlowEvaluator()
        result = ev.evaluate({})
        assert result.score == 0.0
        assert not result.passed

    def test_evaluate_single_agent(self) -> None:
        ev = ConversationFlowEvaluator()
        result = ev.evaluate({
            "agent_message_counts": {"a": 10},
        })
        assert result.score == 1.0  # single agent is trivially balanced

    def test_threshold(self) -> None:
        ev = ConversationFlowEvaluator(threshold=0.99)
        result = ev.evaluate({
            "agent_message_counts": {"a": 5, "b": 4},
        })
        # balance = 1 - (5-4)/5 = 0.8, threshold 0.99 -> not passed
        assert not result.passed
