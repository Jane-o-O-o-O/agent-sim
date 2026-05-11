"""Message model and MessageBus for inter-agent communication."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A message exchanged between agents."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    sender: str
    receiver: str  # agent id or "*" for broadcast
    content: Any
    topic: str = "default"


class MessageBus:
    """In-memory message bus supporting direct and broadcast delivery."""

    def __init__(self) -> None:
        self._agents: dict[str, Any] = {}  # agent_id -> agent
        self._log: list[Message] = []

    def register(self, agent: Any) -> None:
        """Register an agent so it can receive messages."""
        self._agents[agent.id] = agent

    def unregister(self, agent_id: str) -> None:
        """Remove an agent from the bus."""
        self._agents.pop(agent_id, None)

    def send(self, message: Message) -> int:
        """Deliver a message.  Returns count of recipients.

        If ``receiver`` is ``"*"``, broadcast to all agents *except* sender.
        """
        self._log.append(message)

        if message.receiver == "*":
            delivered = 0
            for aid, agent in self._agents.items():
                if aid != message.sender:
                    agent.receive_message(message)
                    delivered += 1
            return delivered

        target = self._agents.get(message.receiver)
        if target is None:
            return 0
        target.receive_message(message)
        return 1

    @property
    def history(self) -> list[Message]:
        """Return all messages ever sent (read-only view)."""
        return list(self._log)

    def clear(self) -> None:
        """Clear message log."""
        self._log.clear()
