"""Scenario factory — builds agents and wires up simulation from ScenarioConfig."""
from __future__ import annotations

import importlib
import logging
from typing import Any, Callable

from agent_sim.agent.base import Agent
from agent_sim.agent.debate_agent import CollaborateAgent, DebateAgent
from agent_sim.agent.llm_agent import EchoLLMBackend, LLMAgent
from agent_sim.agent.memory_agent import MemoryAgent
from agent_sim.agent.role import Role
from agent_sim.agent.tool_agent import ToolAgent
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.scenario.config import AgentConfig, ScenarioConfig

logger = logging.getLogger(__name__)


class PingAgent(Agent):
    """Ping Agent：第一步发送 ping，收到 ping 回复 pong。"""

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
    """Echo Agent：回显收到的消息。"""

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


# Type alias for agent factory functions
AgentFactory = Callable[[AgentConfig], Agent]

# Agent type registry — maps type name to factory function
_AGENT_REGISTRY: dict[str, AgentFactory] = {}


def register_agent_type(type_name: str, factory: AgentFactory) -> None:
    """注册自定义 Agent 类型到工厂注册表。

    Args:
        type_name: 类型名称（用于 YAML 配置中的 type 字段）
        factory: 工厂函数，接受 AgentConfig 返回 Agent 实例

    Raises:
        ValueError: 类型名已被注册

    Example:
        >>> register_agent_type("my_agent", lambda cfg: MyAgent(name=cfg.name))
    """
    if type_name in _AGENT_REGISTRY:
        raise ValueError(f"Agent 类型 '{type_name}' 已注册")
    _AGENT_REGISTRY[type_name] = factory
    logger.info("注册 Agent 类型: %s", type_name)


def unregister_agent_type(type_name: str) -> None:
    """注销 Agent 类型。

    Args:
        type_name: 类型名称

    Raises:
        KeyError: 类型不存在
    """
    if type_name not in _AGENT_REGISTRY:
        raise KeyError(f"Agent 类型 '{type_name}' 未注册")
    del _AGENT_REGISTRY[type_name]


def get_registered_types() -> list[str]:
    """获取所有已注册的 Agent 类型名。"""
    return list(_AGENT_REGISTRY.keys())


def _create_echo(config: AgentConfig) -> Agent:
    """创建 EchoAgent。"""
    return EchoAgent(
        name=config.name,
        role=Role(name=config.role, goals=config.goals),
        context=config.context,
    )


def _create_ping(config: AgentConfig) -> Agent:
    """创建 PingAgent。"""
    return PingAgent(
        name=config.name,
        role=Role(name=config.role, goals=config.goals),
        context=config.context,
    )


def _create_llm(config: AgentConfig) -> Agent:
    """创建 LLMAgent。"""
    backend = _create_llm_backend(config)
    return LLMAgent(
        name=config.name,
        role=Role(name=config.role, goals=config.goals),
        context=config.context,
        system_prompt=config.context.get("system_prompt", ""),
        backend=backend,
    )


def _create_memory(config: AgentConfig) -> Agent:
    """创建 MemoryAgent。"""
    backend = _create_llm_backend(config)
    return MemoryAgent(
        name=config.name,
        role=Role(name=config.role, goals=config.goals),
        context=config.context,
        system_prompt=config.context.get("system_prompt", ""),
        backend=backend,
        memory_window=config.context.get("memory_window", 10),
        include_facts=config.context.get("include_facts", True),
    )


def _create_tool(config: AgentConfig) -> Agent:
    """创建 ToolAgent。"""
    return ToolAgent(
        name=config.name,
        role=Role(name=config.role, goals=config.goals),
        context=config.context,
    )


def _create_debate(config: AgentConfig) -> Agent:
    """创建 DebateAgent。"""
    return DebateAgent(
        name=config.name,
        role=Role(name=config.role, goals=config.goals),
        context=config.context,
    )


def _create_collaborate(config: AgentConfig) -> Agent:
    """创建 CollaborateAgent。"""
    return CollaborateAgent(
        name=config.name,
        role=Role(name=config.role, goals=config.goals),
        context=config.context,
    )


def _create_custom(config: AgentConfig) -> Agent:
    """从模块路径加载自定义 Agent 类。"""
    return _load_custom_agent(config)


# Register all built-in types
_AGENT_REGISTRY["echo"] = _create_echo
_AGENT_REGISTRY["ping"] = _create_ping
_AGENT_REGISTRY["llm"] = _create_llm
_AGENT_REGISTRY["memory"] = _create_memory
_AGENT_REGISTRY["tool"] = _create_tool
_AGENT_REGISTRY["debate"] = _create_debate
_AGENT_REGISTRY["collaborate"] = _create_collaborate
_AGENT_REGISTRY["custom"] = _create_custom


def _create_llm_backend(config: AgentConfig) -> Any:
    """根据 AgentConfig 创建 LLM 后端。

    Args:
        config: Agent 配置，包含 llm_backend 和 llm_model 字段

    Returns:
        LLMBackend 实例
    """
    from agent_sim.agent.llm_backend import create_backend

    provider = config.llm_backend or "echo"
    kwargs: dict[str, Any] = {}

    if config.llm_model:
        kwargs["model"] = config.llm_model

    ctx = config.context
    if provider == "openai":
        for key in ("api_key", "base_url", "temperature", "max_tokens", "timeout"):
            if key in ctx:
                kwargs[key] = ctx[key]
        if "extra_headers" in ctx:
            kwargs["extra_headers"] = ctx["extra_headers"]
    elif provider == "ollama":
        for key in ("base_url", "temperature", "num_predict", "timeout"):
            if key in ctx:
                kwargs[key] = ctx[key]
        if "extra_options" in ctx:
            kwargs["extra_options"] = ctx["extra_options"]

    return create_backend(provider, **kwargs)


def _create_agent(config: AgentConfig) -> Agent:
    """从配置创建单个 Agent（使用注册表）。

    Args:
        config: Agent 配置

    Returns:
        Agent 实例

    Raises:
        ValueError: 不支持的 Agent 类型
    """
    factory = _AGENT_REGISTRY.get(config.type)
    if factory is None:
        raise ValueError(
            f"不支持的 Agent 类型: {config.type}，"
            f"可选: {list(_AGENT_REGISTRY.keys())}"
        )
    return factory(config)


def _load_custom_agent(config: AgentConfig) -> Agent:
    """从模块路径加载自定义 Agent 类。

    Args:
        config: Agent 配置 (需要 module 和 class_name)

    Returns:
        Agent 实例

    Raises:
        ValueError: 配置缺少 module 或 class_name
    """
    if not config.module or not config.class_name:
        raise ValueError("自定义 Agent 必须指定 module 和 class_name")

    logger.info("加载自定义 Agent: %s.%s", config.module, config.class_name)
    mod = importlib.import_module(config.module)
    agent_cls = getattr(mod, config.class_name)

    if not (isinstance(agent_cls, type) and issubclass(agent_cls, Agent)):
        raise ValueError(f"{config.module}.{config.class_name} 不是 Agent 子类")

    role = Role(name=config.role, goals=config.goals)
    return agent_cls(
        name=config.name,
        role=role,
        context=config.context,
    )


def build_scenario(config: ScenarioConfig) -> tuple[Sandbox, MessageBus]:
    """从场景配置构建 Sandbox 和 MessageBus。

    Args:
        config: 场景配置

    Returns:
        (Sandbox, MessageBus) 元组
    """
    logger.info("构建场景: %s (%d agents)", config.name, len(config.agents))

    agents = [_create_agent(ac) for ac in config.agents]
    sandbox = Sandbox(agents=agents)

    bus = MessageBus()
    for agent in agents:
        bus.register(agent)

    for conn in config.connections:
        msg = Message(
            sender=conn.from_agent,
            receiver=conn.to_agent,
            content=conn.topic or "hello",
            msg_type=MessageType.DIRECT if conn.to_agent else MessageType.BROADCAST,
        )
        bus.send(msg)
        logger.debug("发送连接消息: %s -> %s", conn.from_agent, conn.to_agent or "ALL")

    return sandbox, bus
