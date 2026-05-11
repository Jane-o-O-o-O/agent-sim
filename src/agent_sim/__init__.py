"""Agent Sim - Multi-agent simulation framework."""
from __future__ import annotations

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.role import Role
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.environment.state import EnvironmentState
from agent_sim.metrics.collector import MetricsCollector
from agent_sim.scenario.runner import RunResult, ScenarioRunner

__version__ = "0.1.0"

__all__ = [
    "Agent",
    "AgentState",
    "EnvironmentState",
    "Message",
    "MessageBus",
    "MessageType",
    "MetricsCollector",
    "Role",
    "RunResult",
    "Sandbox",
    "ScenarioRunner",
]
