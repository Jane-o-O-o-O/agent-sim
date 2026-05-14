"""Communication modules."""
from agent_sim.communication.message import Message, MessageType

# Lazy import to avoid circular dependency with agent.base
from agent_sim.communication.bus import MessageBus  # noqa: E402

from agent_sim.communication.event_bus import AsyncEventBus, Event  # noqa: E402

__all__ = ["AsyncEventBus", "Event", "Message", "MessageBus", "MessageType"]
