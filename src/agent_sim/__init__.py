"""Agent Sim - Multi-agent simulation framework."""
from __future__ import annotations

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.debate_agent import CollaborateAgent, DebateAgent
from agent_sim.agent.health_monitor import (
    AgentHealth,
    AgentHealthMonitor,
    HealthReport,
    HealthStatus,
)
from agent_sim.agent.llm_agent import EchoLLMBackend, LLMAgent, LLMBackend
from agent_sim.agent.memory_agent import MemoryAgent
from agent_sim.agent.openai_backend import OpenAIBackend
from agent_sim.agent.rate_limiter import TokenBucketRateLimiter
from agent_sim.agent.retry import RetryConfig, RetryManager
from agent_sim.agent.role import Role
from agent_sim.agent.tool_agent import Tool, ToolAgent
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.correlation import ResponseTracker
from agent_sim.communication.event_bus import AsyncEventBus, Event
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
from agent_sim.exceptions import (
    AgentAlreadyExistsError,
    AgentError,
    AgentNotFoundError,
    AgentNotRegisteredError,
    AgentSimError,
    AgentTypeError,
    CommunicationError,
    ConfigError,
    ConfigValidationError,
    LLMError,
    ProtocolError,
    SandboxError,
    ScenarioFileNotFoundError,
    SimulationError,
    SimulationTimeout,
    TemplateError,
    TopologyError,
)
from agent_sim.export import (
    HTMLReport,
    export_messages_to_csv,
    export_messages_to_json,
    export_messages_to_markdown,
    format_conversation_table,
)
from agent_sim.log import get_logger, setup_logging
from agent_sim.memory.buffer import ConversationBuffer, SlidingWindowBuffer
from agent_sim.memory.facts import KeyFactMemory
from agent_sim.metrics.aggregator import (
    HistogramBin,
    MetricAggregator,
    PercentileResult,
    TrendDirection,
)
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
from agent_sim.scenario.batch import BatchResult, BatchRunner
from agent_sim.scenario.benchmark import BenchmarkResult, BenchmarkRunner, BenchmarkSuite
from agent_sim.scenario.checkpoint import Checkpoint, CheckpointManager
from agent_sim.scenario.config import AgentConfig, ConnectionConfig, ScenarioConfig, load_scenario
from agent_sim.scenario.factory import (
    build_scenario,
    get_registered_types,
    register_agent_type,
    unregister_agent_type,
)
from agent_sim.scenario.hooks import LifecycleHooks
from agent_sim.scenario.plugins import PluginRegistry
from agent_sim.scenario.recorder import EventRecorder, EventType, SimulationEvent
from agent_sim.scenario.replay import ReplayEngine
from agent_sim.scenario.runner import RunResult, ScenarioRunner, SimulationTimeout
from agent_sim.scenario.monitor import MonitorConfig, SimulationMonitor, StepSnapshot
from agent_sim.scenario.protocol import (
    BroadcastCollectProtocol,
    CommunicationProtocol,
    ConsensusProtocol,
    FreeFormProtocol,
    ProtocolResult,
    ProtocolType,
    RoundRobinProtocol,
    create_protocol,
)
from agent_sim.scenario.topology_scheduler import TopologyRule, TopologyScheduler
from agent_sim.scenario.templates import get_template, list_templates, save_template_to_yaml, template_info
from agent_sim.topology.dynamic import DynamicTopology, TopologySnapshot
from agent_sim.topology.topology import (
    NetworkTopology,
    TopologyType,
    build_topology,
)
from agent_sim.viz.charts import bar_chart, line_chart, metrics_table, sparkline
from agent_sim.viz.conversation_graph import ConversationGraph

__version__ = "1.0.0"

__all__ = [
    "Agent",
    "AgentAlreadyExistsError",
    "AgentConfig",
    "AgentError",
    "AgentHealth",
    "AgentHealthMonitor",
    "AgentNotFoundError",
    "AgentNotRegisteredError",
    "AgentParticipationEvaluator",
    "AgentSimError",
    "AgentState",
    "AgentTypeError",
    "AsyncEventBus",
    "BatchResult",
    "BatchRunner",
    "BenchmarkResult",
    "BenchmarkRunner",
    "BenchmarkSuite",
    "Checkpoint",
    "CheckpointManager",
    "CollaborateAgent",
    "CommunicationError",
    "CompletionEvaluator",
    "ConfigError",
    "ConfigValidationError",
    "ConnectionConfig",
    "ConversationBuffer",
    "ConversationFlowEvaluator",
    "DebateAgent",
    "DeduplicationMiddleware",
    "DynamicTopology",
    "EchoLLMBackend",
    "EnvironmentState",
    "Event",
    "EvalReport",
    "EvalResult",
    "EvalSuite",
    "Evaluator",
    "EventRecorder",
    "EventType",
    "FilterMiddleware",
    "HTMLReport",
    "HealthReport",
    "HealthStatus",
    "HistogramBin",
    "KeyFactMemory",
    "LatencyEvaluator",
    "LifecycleHooks",
    "LLMAgent",
    "LLMBackend",
    "LLMError",
    "LoggingMiddleware",
    "MemoryAgent",
    "Message",
    "MessageBus",
    "MessageMiddleware",
    "MessageType",
    "MessageVolumeEvaluator",
    "MetricAggregator",
    "MetricsCollector",
    "NetworkHealthEvaluator",
    "NetworkTopology",
    "OpenAIBackend",
    "PercentileResult",
    "PluginRegistry",
    "ProtocolError",
    "RateLimitMiddleware",
    "ReplayEngine",
    "ResponseTracker",
    "RetryConfig",
    "RetryManager",
    "Role",
    "RunResult",
    "Sandbox",
    "SandboxError",
    "ScenarioConfig",
    "ScenarioFileNotFoundError",
    "ScenarioRunner",
    "SimulationError",
    "SimulationEvent",
    "SimulationTimeout",
    "SlidingWindowBuffer",
    "TokenBucketRateLimiter",
    "Tool",
    "ToolAgent",
    "TopologySnapshot",
    "TopologyType",
    "TopologyError",
    "TopologyScheduler",
    "TemplateError",
    "TransformMiddleware",
    "TrendDirection",
    "bar_chart",
    "build_scenario",
    "build_topology",
    "export_messages_to_csv",
    "export_messages_to_json",
    "export_messages_to_markdown",
    "format_conversation_table",
    "get_logger",
    "get_registered_types",
    "line_chart",
    "load_scenario",
    "metrics_table",
    "register_agent_type",
    "setup_logging",
    "sparkline",
    "unregister_agent_type",
    "SimulationMonitor",
    "MonitorConfig",
    "StepSnapshot",
    "RoundRobinProtocol",
    "BroadcastCollectProtocol",
    "ConsensusProtocol",
    "FreeFormProtocol",
    "CommunicationProtocol",
    "ProtocolResult",
    "ProtocolType",
    "create_protocol",
    "TopologyScheduler",
    "TopologyRule",
    "ConversationGraph",
    "get_template",
    "list_templates",
    "template_info",
    "save_template_to_yaml",
]
