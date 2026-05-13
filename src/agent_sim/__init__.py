"""Agent Sim - Multi-agent simulation framework."""
from __future__ import annotations

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.debate_agent import CollaborateAgent, DebateAgent
from agent_sim.agent.llm_agent import EchoLLMBackend, LLMAgent, LLMBackend
from agent_sim.agent.memory_agent import MemoryAgent
from agent_sim.agent.openai_backend import OpenAIBackend
from agent_sim.agent.rate_limiter import TokenBucketRateLimiter
from agent_sim.agent.retry import RetryConfig, RetryManager
from agent_sim.agent.role import Role
from agent_sim.agent.tool_agent import Tool, ToolAgent
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.correlation import ResponseTracker
from agent_sim.communication.message import Message, MessageType
from agent_sim.communication.middleware import (
    DeduplicationMiddleware,
    FilterMiddleware,
    LoggingMiddleware,
    MessageMiddleware,
    RateLimitMiddleware,
    TransformMiddleware,
)
from agent_sim.environment.sandbox import Sandbox
from agent_sim.environment.state import EnvironmentState
from agent_sim.export import (
    export_messages_to_csv,
    export_messages_to_json,
    export_messages_to_markdown,
    format_conversation_table,
)
from agent_sim.log import get_logger, setup_logging
from agent_sim.memory.buffer import ConversationBuffer, SlidingWindowBuffer
from agent_sim.memory.facts import KeyFactMemory
from agent_sim.metrics.collector import MetricsCollector
from agent_sim.metrics.evaluator import (
    AgentParticipationEvaluator,
    CompletionEvaluator,
    ConversationFlowEvaluator,
    EvalReport,
    EvalResult,
    EvalSuite,
    Evaluator,
    LatencyEvaluator,
    MessageVolumeEvaluator,
    NetworkHealthEvaluator,
)
from agent_sim.scenario.checkpoint import Checkpoint, CheckpointManager
from agent_sim.scenario.config import AgentConfig, ConnectionConfig, ScenarioConfig, load_scenario
from agent_sim.scenario.factory import build_scenario
from agent_sim.scenario.hooks import LifecycleHooks
from agent_sim.scenario.runner import RunResult, ScenarioRunner
from agent_sim.topology.topology import (
    NetworkTopology,
    TopologyType,
    build_topology,
)
from agent_sim.viz.charts import bar_chart, line_chart, metrics_table, sparkline

__version__ = "0.5.0"

__all__ = [
    "Agent",
    "AgentConfig",
    "AgentParticipationEvaluator",
    "AgentState",
    "Checkpoint",
    "CheckpointManager",
    "CollaborateAgent",
    "CompletionEvaluator",
    "ConnectionConfig",
    "ConversationBuffer",
    "ConversationFlowEvaluator",
    "DebateAgent",
    "DeduplicationMiddleware",
    "EchoLLMBackend",
    "EnvironmentState",
    "EvalReport",
    "EvalResult",
    "EvalSuite",
    "Evaluator",
    "FilterMiddleware",
    "KeyFactMemory",
    "LatencyEvaluator",
    "LifecycleHooks",
    "LLMAgent",
    "LLMBackend",
    "LoggingMiddleware",
    "MemoryAgent",
    "Message",
    "MessageBus",
    "MessageMiddleware",
    "MessageType",
    "MessageVolumeEvaluator",
    "MetricsCollector",
    "NetworkHealthEvaluator",
    "NetworkTopology",
    "OpenAIBackend",
    "RateLimitMiddleware",
    "ResponseTracker",
    "RetryConfig",
    "RetryManager",
    "Role",
    "RunResult",
    "Sandbox",
    "ScenarioConfig",
    "ScenarioRunner",
    "SlidingWindowBuffer",
    "TokenBucketRateLimiter",
    "Tool",
    "ToolAgent",
    "TopologyType",
    "TransformMiddleware",
    "bar_chart",
    "build_scenario",
    "build_topology",
    "export_messages_to_csv",
    "export_messages_to_json",
    "export_messages_to_markdown",
    "format_conversation_table",
    "get_logger",
    "line_chart",
    "load_scenario",
    "metrics_table",
    "setup_logging",
    "sparkline",
]
