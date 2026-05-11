"""Shared test fixtures for Agent Sim."""

import pytest

from agent_sim.agent import Agent, AgentConfig
from agent_sim.communication import MessageBus


class EchoAgent(Agent):
    """Minimal agent that echoes observations in its action."""

    def act(self) -> dict | None:
        obs = self.state.data.get("last_observation", {})
        return {"echo": obs}


class CountingAgent(Agent):
    """Agent that counts steps in its data state."""

    def act(self) -> dict | None:
        count = self.state.data.get("count", 0) + 1
        self.state.data["count"] = count
        return {"count": count}


@pytest.fixture
def echo_agent():
    return EchoAgent(AgentConfig(name="echo-1", max_steps=5))


@pytest.fixture
def counting_agent():
    return CountingAgent(AgentConfig(name="counter-1", max_steps=5))


@pytest.fixture
def bus():
    return MessageBus()
