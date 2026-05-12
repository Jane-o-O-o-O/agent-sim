"""Tests for debate and collaboration agents."""
from __future__ import annotations

import pytest

from agent_sim.agent.debate_agent import CollaborateAgent, DebateAgent
from agent_sim.agent.role import Role
from agent_sim.communication.message import Message, MessageType


# ────────────────────── DebateAgent ──────────────────────


class TestDebateAgent:
    """DebateAgent 测试。"""

    def test_create(self) -> None:
        agent = DebateAgent(
            name="pro",
            role=Role(name="pro_side"),
            context={"stance": "for", "style": "balanced"},
        )
        assert agent.name == "pro"
        assert agent.stance == "for"
        assert agent.argument_style == "balanced"
        assert agent.round_count == 0

    def test_default_stance(self) -> None:
        agent = DebateAgent(name="a")
        assert agent.stance == "for"
        assert agent.argument_style == "balanced"

    async def test_step_initial_argument(self) -> None:
        agent = DebateAgent(
            name="pro",
            context={"stance": "for"},
        )
        agent.receive(Message(sender="opp", content="AI is dangerous"))
        replies = await agent.step()
        assert len(replies) == 1
        assert "支持" in replies[0].content
        assert agent.round_count == 1

    async def test_step_rebuttal(self) -> None:
        agent = DebateAgent(name="pro", context={"stance": "for"})
        # Round 0
        agent.receive(Message(sender="opp", content="AI is dangerous"))
        await agent.step()
        # Round 1 (rebuttal)
        agent.receive(Message(sender="opp", content="AI will take jobs"))
        replies = await agent.step()
        assert len(replies) == 1
        assert agent.round_count == 2

    async def test_step_aggressive_style(self) -> None:
        agent = DebateAgent(
            name="a",
            context={"style": "aggressive"},
        )
        agent.receive(Message(sender="b", content="point"))
        await agent.step()  # round 0
        agent.receive(Message(sender="b", content="counter"))
        replies = await agent.step()
        assert "强烈反驳" in replies[0].content

    async def test_step_defensive_style(self) -> None:
        agent = DebateAgent(name="a", context={"style": "defensive"})
        agent.receive(Message(sender="b", content="point"))
        await agent.step()
        agent.receive(Message(sender="b", content="counter"))
        replies = await agent.step()
        assert "谨慎回应" in replies[0].content

    async def test_step_metadata(self) -> None:
        agent = DebateAgent(name="a", context={"stance": "against"})
        agent.receive(Message(sender="b", content="test"))
        replies = await agent.step()
        assert replies[0].metadata["stance"] == "against"
        assert replies[0].metadata["round"] == 0

    async def test_step_clears_inbox(self) -> None:
        agent = DebateAgent(name="a")
        agent.receive(Message(sender="b", content="test"))
        await agent.step()
        assert len(agent.inbox) == 0

    def test_total_arguments(self) -> None:
        agent = DebateAgent(name="a")
        assert agent.total_arguments == 0


# ────────────────────── CollaborateAgent ──────────────────────


class TestCollaborateAgent:
    """CollaborateAgent 测试。"""

    def test_create_coordinator(self) -> None:
        agent = CollaborateAgent(
            name="coord",
            context={"role_type": "coordinator", "workers": ["w1"], "subtasks": ["t1"]},
        )
        assert agent.role_type == "coordinator"
        assert len(agent._pending_tasks) == 1

    def test_create_worker(self) -> None:
        agent = CollaborateAgent(name="w1", context={"role_type": "worker"})
        assert agent.role_type == "worker"

    def test_create_reviewer(self) -> None:
        agent = CollaborateAgent(name="rev", context={"role_type": "reviewer"})
        assert agent.role_type == "reviewer"

    def test_default_role(self) -> None:
        agent = CollaborateAgent(name="a")
        assert agent.role_type == "worker"

    async def test_coordinator_dispatch(self) -> None:
        coord = CollaborateAgent(
            name="coord",
            context={
                "role_type": "coordinator",
                "workers": ["w1", "w2"],
                "subtasks": ["task_a", "task_b"],
            },
        )
        # First step: dispatches first task even without inbox
        replies = await coord.step()
        assert len(replies) == 2  # dispatched to both workers
        assert replies[0].receiver == "w1"
        assert replies[1].receiver == "w2"

    async def test_coordinator_with_inbox_dispatch(self) -> None:
        coord = CollaborateAgent(
            name="coord",
            context={
                "role_type": "coordinator",
                "workers": ["w1"],
                "subtasks": ["task_a"],
            },
        )
        # Give it an inbox message to trigger dispatch
        coord.receive(Message(sender="w1", content="ready"))
        replies = await coord.step()
        assert len(replies) == 1
        assert replies[0].receiver == "w1"
        assert replies[0].content["task"] == "task_a"

    async def test_worker_process_task(self) -> None:
        worker = CollaborateAgent(name="w1", context={"role_type": "worker"})
        worker.receive(Message(
            sender="coord",
            content={"task": "compute 1+1", "task_id": "t1"},
        ))
        replies = await worker.step()
        assert len(replies) == 1
        assert replies[0].content["task_id"] == "t1"
        assert "已完成" in replies[0].content["result"]

    async def test_worker_normal_message(self) -> None:
        worker = CollaborateAgent(name="w1", context={"role_type": "worker"})
        worker.receive(Message(sender="a", content="hello"))
        replies = await worker.step()
        assert len(replies) == 1
        assert "收到" in replies[0].content

    async def test_reviewer_approve(self) -> None:
        reviewer = CollaborateAgent(name="rev", context={"role_type": "reviewer"})
        reviewer.receive(Message(
            sender="w1",
            content={"result": "42", "task_id": "t1"},
        ))
        replies = await reviewer.step()
        assert len(replies) == 1
        assert replies[0].content["approved"] is True

    async def test_step_clears_inbox(self) -> None:
        agent = CollaborateAgent(name="w1", context={"role_type": "worker"})
        agent.receive(Message(sender="a", content="test"))
        await agent.step()
        assert len(agent.inbox) == 0

    async def test_step_increments_count(self) -> None:
        agent = CollaborateAgent(name="a", context={"role_type": "worker"})
        agent.receive(Message(sender="a", content="test"))
        await agent.step()
        assert agent.step_count == 1
