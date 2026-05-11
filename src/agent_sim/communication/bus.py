"""Message bus for agent communication routing."""
from __future__ import annotations

from typing import TYPE_CHECKING

from agent_sim.communication.message import Message, MessageType

if TYPE_CHECKING:
    from agent_sim.agent.base import Agent


class MessageBus:
    """Agent 间通信总线。

    负责消息路由：定向消息投递到目标 Agent，广播消息投递给除发送者外的所有 Agent。

    Example:
        >>> bus = MessageBus()
        >>> bus.register(Agent(name="a"))
        >>> bus.register(Agent(name="b"))
        >>> bus.send(Message(sender="a", receiver="b", content="hello"))
    """

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._history: list[Message] = []
        self._dead_letters: list[Message] = []

    @property
    def agent_count(self) -> int:
        """已注册 Agent 数量。"""
        return len(self._agents)

    @property
    def message_count(self) -> int:
        """已处理消息总数。"""
        return len(self._history)

    @property
    def dead_letter_count(self) -> int:
        """无法投递的消息数。"""
        return len(self._dead_letters)

    @property
    def history(self) -> list[Message]:
        """完整消息历史。"""
        return list(self._history)

    def has_agent(self, name: str) -> bool:
        """检查 Agent 是否已注册。"""
        return name in self._agents

    def register(self, agent: Agent) -> None:
        """注册 Agent 到总线。

        Raises:
            ValueError: 同名 Agent 已注册
        """
        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' 已注册")
        self._agents[agent.name] = agent

    def unregister(self, name: str) -> None:
        """注销 Agent。

        Raises:
            KeyError: Agent 不存在
        """
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' 未注册")
        del self._agents[name]

    def send(self, message: Message) -> None:
        """发送消息。

        定向消息投递给 receiver；广播消息投递给除 sender 外的所有 Agent。
        """
        self._history.append(message)

        if message.msg_type == MessageType.BROADCAST:
            self._broadcast(message)
        else:
            self._deliver(message)

    def _broadcast(self, message: Message) -> None:
        """广播消息给除发送者外的所有 Agent。"""
        for name, agent in self._agents.items():
            if name != message.sender:
                agent.receive(message)

    def _deliver(self, message: Message) -> None:
        """投递定向消息。"""
        target = self._agents.get(message.receiver)
        if target is None:
            self._dead_letters.append(message)
        else:
            target.receive(message)

    def get_history(self, agent_name: str) -> list[Message]:
        """获取与某 Agent 相关的消息历史。"""
        return [
            msg
            for msg in self._history
            if msg.sender == agent_name or msg.receiver == agent_name
        ]

    def clear_history(self) -> None:
        """清空消息历史和死信。"""
        self._history.clear()
        self._dead_letters.clear()

    def __str__(self) -> str:
        return f"MessageBus(agents={self.agent_count}, messages={self.message_count})"
