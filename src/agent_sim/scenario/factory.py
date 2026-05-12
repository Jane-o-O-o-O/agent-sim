"""Scenario factory -- builds agents and wires up simulation from ScenarioConfig."""
from __future__ import annotations

import importlib
import logging
from typing import Any

from agent_sim.agent.base import Agent
from agent_sim.agent.llm_agent import EchoLLMBackend, LLMAgent
from agent_sim.agent.llm_backend import create_backend
from agent_sim.agent.role import Role
from agent_sim.agent.tool_agent import ToolAgent
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.scenario.config import AgentConfig, ScenarioConfig

logger = logging.getLogger(__name__)


class PingAgent(Agent):
    """Ping Agent: send ping on first step, reply pong to pings."""

    async def step(self) -> list[Message]:
        replies: list[Message] = []
        for msg in self.inbox:
            if msg.content == "ping":
                replies.append(Message(
                    sender=self.name,
                    receiver=msg.sender,
                    content="pong",
                    msg_type=MessageType.RESPONSE,
                ))
        self.inbox.clear()

        if self.step_count == 0:
            for target in self.context.get("targets", []):
                replies.append(Message(
                    sender=self.name,
                    receiver=target,
                    content="ping",
                    msg_type=MessageType.REQUEST,
                ))

        self.increment_step()
        return replies


class EchoAgent(Agent):
    """Echo Agent: echo back received messages."""

    async def step(self) -> list[Message]:
        replies: list[Message] = []
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


# Builtin agent type mapping
_BUILTIN_TYPES: dict[str, type[Agent]] = {
    "echo": EchoAgent,
    "ping": PingAgent,
}


def _build_llm_backend(config: AgentConfig) -> Any:
    """Build LLM backend from AgentConfig.

    Uses create_backend() factory for provider resolution.
    Falls back to EchoLLMBackend when no backend specified.

    Args:
        config: Agent configuration with llm_backend, llm_model, and context

    Returns:
        LLMBackend instance
    """
    backend_name = config.llm_backend or "echo"

    kwargs: dict[str, Any] = {}
    if config.llm_model:
        kwargs["model"] = config.llm_model

    # Extract backend-specific params from context
    ctx = config.context
    for key in ("api_key", "base_url", "temperature", "max_tokens", "timeout"):
        if key in ctx:
            kwargs[key] = ctx[key]

    try:
        return create_backend(backend_name, **kwargs)
    except ValueError:
        logger.warning("Cannot create LLM backend '%s', falling back to EchoLLMBackend", backend_name)
        return EchoLLMBackend()


def _create_agent(config: AgentConfig) -> Agent:
    """Create a single Agent from config.

    Args:
        config: Agent configuration

    Returns:
        Agent instance

    Raises:
        ValueError: Unsupported agent type or config error
    """
    role = Role(name=config.role, goals=config.goals)

    if config.type == "llm":
        backend = _build_llm_backend(config)
        return LLMAgent(
            name=config.name,
            role=role,
            context=config.context,
            system_prompt=config.context.get("system_prompt", ""),
            backend=backend,
        )

    if config.type == "tool":
        return ToolAgent(
            name=config.name,
            role=role,
            context=config.context,
        )

    if config.type == "custom":
        return _load_custom_agent(config)

    agent_cls = _BUILTIN_TYPES.get(config.type)
    if agent_cls is None:
        raise ValueError(
            f"Unsupported agent type: {config.type}, "
            f"available: {list(_BUILTIN_TYPES.keys()) + ['llm', 'tool', 'custom']}"
        )

    return agent_cls(
        name=config.name,
        role=role,
        context=config.context,
    )


def _load_custom_agent(config: AgentConfig) -> Agent:
    """Load custom Agent class from module path.

    Args:
        config: Agent config (requires module and class_name)

    Returns:
        Agent instance

    Raises:
        ValueError: Missing module or class_name
    """
    if not config.module or not config.class_name:
        raise ValueError("Custom agent must specify module and class_name")

    logger.info("Loading custom agent: %s.%s", config.module, config.class_name)
    mod = importlib.import_module(config.module)
    agent_cls = getattr(mod, config.class_name)

    if not (isinstance(agent_cls, type) and issubclass(agent_cls, Agent)):
        raise ValueError(f"{config.module}.{config.class_name} is not an Agent subclass")

    role = Role(name=config.role, goals=config.goals)
    return agent_cls(
        name=config.name,
        role=role,
        context=config.context,
    )


def build_scenario(config: ScenarioConfig) -> tuple[Sandbox, MessageBus]:
    """Build Sandbox and MessageBus from scenario config.

    Args:
        config: Scenario configuration

    Returns:
        (Sandbox, MessageBus) tuple
    """
    logger.info("Building scenario: %s (%d agents)", config.name, len(config.agents))

    agents = [_create_agent(ac) for ac in config.agents]
    sandbox = Sandbox(agents=agents)

    bus = MessageBus()
    for agent in agents:
        bus.register(agent)

    # Process connections: send initial messages
    for conn in config.connections:
        msg = Message(
            sender=conn.from_agent,
            receiver=conn.to_agent,
            content=conn.topic or "hello",
            msg_type=MessageType.DIRECT if conn.to_agent else MessageType.BROADCAST,
        )
        bus.send(msg)
        logger.debug("Sending connection message: %s -> %s", conn.from_agent, conn.to_agent or "ALL")

    return sandbox, bus
