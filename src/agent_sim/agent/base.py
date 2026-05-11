"""Agent base classes and models."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class AgentConfig(BaseModel):
    """Configuration for creating an agent."""

    name: str
    description: str = ""
    max_steps: int = 100


class AgentState(BaseModel):
    """Runtime state of an agent."""

    step_count: int = 0
    status: str = "idle"  # idle | running | done | error
    data: dict[str, Any] = Field(default_factory=dict)


class Agent(ABC):
    """Base class for all simulation agents.

    Lifecycle: observe() -> act() -> step() (convenience wrapper).
    Subclasses MUST implement ``act``.
    """

    def __init__(self, config: AgentConfig, agent_id: str | None = None):
        self.id: str = agent_id or uuid.uuid4().hex[:8]
        self.config = config
        self.state = AgentState()
        self._inbox: list[Any] = []

    # ---- abstract -------------------------------------------------

    @abstractmethod
    def act(self) -> dict[str, Any] | None:
        """Decide on an action.  Must be implemented by subclasses."""
        ...

    # ---- concrete -------------------------------------------------

    def observe(self, env_state: dict[str, Any]) -> None:
        """Observe the current environment state."""
        self.state.data["last_observation"] = env_state

    def receive_message(self, message: Any) -> None:
        """Enqueue a message from the communication bus."""
        self._inbox.append(message)

    def step(self, env_state: dict[str, Any] | None = None) -> dict[str, Any] | None:
        """Execute one simulation tick: observe → act."""
        if env_state is not None:
            self.observe(env_state)
        self.state.step_count += 1
        self.state.status = "running"
        result = self.act()
        if self.state.step_count >= self.config.max_steps:
            self.state.status = "done"
        return result

    def reset(self) -> None:
        """Reset agent to initial state."""
        self.state = AgentState()
        self._inbox.clear()
