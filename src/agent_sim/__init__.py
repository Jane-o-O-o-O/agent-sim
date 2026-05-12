"""Agent Sim - Multi-agent simulation framework."""
from __future__ import annotations

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.llm_agent import EchoLLMBackend, LLMAgent, LLMBackend
from agent_sim.agent.openai_backend import OpenAIBackend
from agent_sim.agent.rate_limiter import TokenBucketRateLimiter
from agent_sim.agent.role import Role
from agent_sim.agent.tool_agent import Tool, ToolAgent
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.environment.state import EnvironmentState
from agent_sim.export import (
    export_messages_to_json,
    export_messages_to_markdown,
    format_conversation_table,
)
from agent_sim.log import get_logger, setup_logging
from agent_sim.metrics.collector import MetricsCollector
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
from agent_sim.scenario.config import AgentConfig, ConnectionConfig, ScenarioConfig, load_scenario
from agent_sim.scenario.factory import build_scenario
from agent_sim.scenario.hooks import LifecycleHooks
from agent_sim.scenario.runner import RunResult, ScenarioRunner

__version__ = "0.3.0"

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentParticipationEvaluator",
    "AgentState",
    "CompletionEvaluator",
    "ConnectionConfig",
    "EchoLLMBackend",
    "EnvironmentState",
    "EvalReport",
    "EvalResult",
    "EvalSuite",
    "Evaluator",
    "LatencyEvaluator",
    "LifecycleHooks",
    "LLMAgent",
    "LLMBackend",
    "Message",
    "MessageBus",
    "MessageType",
    "MessageVolumeEvaluator",
    "MetricsCollector",
    "Role",
    "RunResult",
    "Sandbox",
    "ScenarioConfig",
    "ScenarioRunner",
    "TokenBucketRateLimiter",
    "Tool",
    "ToolAgent",
    "build_scenario",
    "export_messages_to_json",
    "export_messages_to_markdown",
    "format_conversation_table",
    "get_logger",
    "load_scenario",
    "setup_logging",
]
