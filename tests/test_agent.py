"""Tests for Agent base class."""
import asyncio

import pytest

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.role import Role
from agent_sim.communication.message import Message, MessageType


class TestRole:
    """Test Role definition."""

    def test_create_role(self) -> None:
        """创建基本角色。"""
        role = Role(name="researcher", description="负责信息搜集")
        assert role.name == "researcher"
        assert role.description == "负责信息搜集"

    def test_role_with_goals(self) -> None:
        """角色带目标列表。"""
        role = Role(name="planner", goals=["create_plan", "assign_tasks"])
        assert len(role.goals) == 2
        assert "create_plan" in role.goals

    def test_role_empty_defaults(self) -> None:
        """角色默认值。"""
        role = Role(name="test")
        assert role.goals == []
        assert role.description == ""

    def test_role_str(self) -> None:
        """角色字符串表示。"""
        role = Role(name="worker")
        assert "worker" in str(role)


class TestAgent:
    """Test Agent base class."""

    def test_create_agent(self) -> None:
        """创建基本 Agent。"""
        agent = Agent(name="agent_a")
        assert agent.name == "agent_a"
        assert agent.state == AgentState.IDLE

    def test_create_agent_with_role(self) -> None:
        """带角色创建 Agent。"""
        role = Role(name="researcher", goals=["find_info"])
        agent = Agent(name="researcher_1", role=role)
        assert agent.role.name == "researcher"
        assert agent.state == AgentState.IDLE

    def test_agent_default_role(self) -> None:
        """Agent 默认角色。"""
        agent = Agent(name="test")
        assert agent.role.name == "default"

    def test_agent_inbox(self) -> None:
        """Agent 收件箱。"""
        agent = Agent(name="a")
        assert agent.inbox == []
        msg = Message(sender="b", receiver="a", content="hello")
        agent.receive(msg)
        assert len(agent.inbox) == 1
        assert agent.inbox[0].content == "hello"

    def test_agent_state_transitions(self) -> None:
        """Agent 状态转换。"""
        agent = Agent(name="a")
        assert agent.state == AgentState.IDLE
        agent.set_state(AgentState.RUNNING)
        assert agent.state == AgentState.RUNNING
        agent.set_state(AgentState.COMPLETED)
        assert agent.state == AgentState.COMPLETED

    def test_agent_state_str(self) -> None:
        """AgentState 字符串值。"""
        assert AgentState.IDLE.value == "idle"
        assert AgentState.RUNNING.value == "running"
        assert AgentState.COMPLETED.value == "completed"
        assert AgentState.FAILED.value == "failed"

    @pytest.mark.asyncio
    async def test_agent_step_returns_messages(self) -> None:
        """Agent step 方法返回消息列表。"""
        agent = Agent(name="a")
        messages = await agent.step()
        assert isinstance(messages, list)

    @pytest.mark.asyncio
    async def test_agent_step_processes_inbox(self) -> None:
        """Agent step 处理收件箱消息。"""

        class EchoAgent(Agent):
            """回显 Agent：收到消息后原样回复。"""

            async def step(self) -> list[Message]:
                replies = []
                for msg in self.inbox:
                    reply = Message(
                        sender=self.name,
                        receiver=msg.sender,
                        content=f"echo: {msg.content}",
                        msg_type=MessageType.RESPONSE,
                    )
                    replies.append(reply)
                self.inbox.clear()
                return replies

        agent = EchoAgent(name="echo")
        agent.receive(Message(sender="user", receiver="echo", content="hi"))
        replies = await agent.step()
        assert len(replies) == 1
        assert replies[0].content == "echo: hi"
        assert replies[0].receiver == "user"
        assert agent.inbox == []

    @pytest.mark.asyncio
    async def test_agent_step_with_empty_inbox(self) -> None:
        """空收件箱时 step 返回空列表。"""
        agent = Agent(name="a")
        result = await agent.step()
        assert result == []

    def test_agent_properties(self) -> None:
        """Agent 属性。"""
        agent = Agent(name="test_agent")
        assert agent.name == "test_agent"
        assert agent.state == AgentState.IDLE
        assert agent.step_count == 0

    def test_agent_increment_step(self) -> None:
        """Agent 步骤计数。"""
        agent = Agent(name="a")
        agent.increment_step()
        agent.increment_step()
        assert agent.step_count == 2

    def test_agent_context(self) -> None:
        """Agent 上下文存储。"""
        agent = Agent(name="a")
        assert agent.context == {}
        agent.context["key"] = "value"
        assert agent.context["key"] == "value"
