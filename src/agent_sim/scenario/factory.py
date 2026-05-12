"""Scenario factory — builds agents and wires up simulation from ScenarioConfig."""
from __future__ import annotations

import importlib
import logging
from typing import Any

from agent_sim.agent.base import Agent
from agent_sim.agent.debate_agent import CollaborateAgent, DebateAgent
from agent_sim.agent.llm_agent import EchoLLMBackend, LLMAgent
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


# 内置 Agent 类型映射
_BUILTIN_TYPES: dict[str, type[Agent]] = {
    "echo": EchoAgent,
    "ping": PingAgent,
}


def _create_agent(config: AgentConfig) -> Agent:
    """从配置创建单个 Agent。

    Args:
        config: Agent 配置

    Returns:
        Agent 实例

    Raises:
        ValueError: 不支持的 Agent 类型或配置错误
    """
    role = Role(name=config.role, goals=config.goals)

    if config.type == "llm":
        return LLMAgent(
            name=config.name,
            role=role,
            context=config.context,
            system_prompt=config.context.get("system_prompt", ""),
            backend=EchoLLMBackend(),
        )

    if config.type == "tool":
        return ToolAgent(
            name=config.name,
            role=role,
            context=config.context,
        )

    if config.type == "debate":
        return DebateAgent(
            name=config.name,
            role=role,
            context=config.context,
        )

    if config.type == "collaborate":
        return CollaborateAgent(
            name=config.name,
            role=role,
            context=config.context,
        )

    if config.type == "custom":
        return _load_custom_agent(config)

    agent_cls = _BUILTIN_TYPES.get(config.type)
    if agent_cls is None:
        raise ValueError(
            f"不支持的 Agent 类型: {config.type}，"
            f"可选: {list(_BUILTIN_TYPES.keys()) + ['llm', 'tool', 'debate', 'collaborate', 'custom']}"
        )

    return agent_cls(
        name=config.name,
        role=role,
        context=config.context,
    )


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

    # 处理连接配置: 发送初始消息
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
