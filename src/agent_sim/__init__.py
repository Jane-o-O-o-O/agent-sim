"""Agent Sim - Multi-agent simulation framework."""

__version__ = "0.1.0"

from agent_sim.agent import Agent, AgentConfig, AgentState
from agent_sim.communication import Message, MessageBus

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentState",
    "Message",
    "MessageBus",
]
