"""Communication modules."""
from agent_sim.communication.message import Message, MessageType

# Lazy import to avoid circular dependency with agent.base
from agent_sim.communication.bus import MessageBus  # noqa: E402

__all__ = ["Message", "MessageBus", "MessageType"]
