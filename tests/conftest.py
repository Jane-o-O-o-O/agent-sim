"""Shared test fixtures for agent-sim."""
import pytest

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.role import Role
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.scenario.runner import ScenarioRunner


@pytest.fixture
def bus() -> MessageBus:
    """空通信总线。"""
    return MessageBus()


@pytest.fixture
def sandbox() -> Sandbox:
    """空沙箱。"""
    return Sandbox()


@pytest.fixture
def two_agents() -> tuple[Agent, Agent]:
    """两个基础 Agent。"""
    return Agent(name="a"), Agent(name="b")


@pytest.fixture
def registered_bus(two_agents: tuple[Agent, Agent]) -> MessageBus:
    """带两个已注册 Agent 的总线。"""
    a, b = two_agents
    bus = MessageBus()
    bus.register(a)
    bus.register(b)
    return bus


class EchoAgent(Agent):
    """测试用 Echo Agent：回显所有收到的消息。"""

    async def step(self) -> list[Message]:
        replies = []
        for msg in self.inbox:
            replies.append(Message(
                sender=self.name,
                receiver=msg.sender,
                content=f"echo:{msg.content}",
                msg_type=MessageType.RESPONSE,
            ))
        self.inbox.clear()
        self.increment_step()
        return replies


@pytest.fixture
def echo_agent() -> EchoAgent:
    """Echo Agent 实例。"""
    return EchoAgent(name="echo")
