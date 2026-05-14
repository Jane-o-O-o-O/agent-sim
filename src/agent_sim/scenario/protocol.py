"""Structured communication protocols for multi-agent scenarios.

Provides predefined communication patterns that control message flow
between agents, such as round-robin, broadcast-collect, and consensus.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from agent_sim.agent.base import Agent
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.exceptions import ProtocolError

logger = logging.getLogger(__name__)


class ProtocolType(str, Enum):
    """Communication protocol types."""

    ROUND_ROBIN = "round_robin"
    BROADCAST_COLLECT = "broadcast_collect"
    CONSENSUS = "consensus"
    FREE_FORM = "free_form"


class ProtocolResult(BaseModel):
    """Result of a protocol step.

    Attributes:
        protocol: Protocol type
        step: Step number
        messages: Messages generated in this step
        participants: Agents that participated
        phase: Current protocol phase description
        completed: Whether the protocol cycle completed
    """

    protocol: ProtocolType = ProtocolType.FREE_FORM
    step: int = 0
    messages: list[dict[str, Any]] = Field(default_factory=list)
    participants: list[str] = Field(default_factory=list)
    phase: str = ""
    completed: bool = False


class CommunicationProtocol(ABC):
    """Abstract base class for communication protocols.

    A protocol controls how agents communicate by determining
    message routing, ordering, and phases.
    """

    def __init__(self, agents: list[str]) -> None:
        self._agents = list(agents)
        self._step = 0

    @property
    def agents(self) -> list[str]:
        """Agent names in this protocol."""
        return list(self._agents)

    @property
    def step(self) -> int:
        """Current protocol step."""
        return self._step

    @abstractmethod
    async def execute_step(
        self, bus: MessageBus, agents: dict[str, Agent]
    ) -> ProtocolResult:
        """Execute one step of the protocol.

        Args:
            bus: Message bus for routing
            agents: Dict of agent name to Agent instance

        Returns:
            ProtocolResult for this step
        """
        ...

    def reset(self) -> None:
        """Reset protocol state."""
        self._step = 0


class RoundRobinProtocol(CommunicationProtocol):
    """Round-robin communication protocol.

    Each turn, one agent speaks and all others listen. The speaking
    agent rotates each step: step 1 → agent[0], step 2 → agent[1], etc.

    Useful for structured discussions where each participant gets
    an equal opportunity to contribute.

    Example:
        >>> protocol = RoundRobinProtocol(["alice", "bob", "charlie"])
        >>> # step 1: alice speaks
        >>> # step 2: bob speaks
        >>> # step 3: charlie speaks
        >>> # step 4: alice speaks again
    """

    def __init__(self, agents: list[str], topic: str = "") -> None:
        super().__init__(agents)
        self._topic = topic

    @property
    def current_speaker(self) -> str:
        """Get the current speaker's name."""
        if not self._agents:
            return ""
        return self._agents[self._step % len(self._agents)]

    async def execute_step(
        self, bus: MessageBus, agents: dict[str, Agent]
    ) -> ProtocolResult:
        """Execute one round-robin step.

        The current speaker processes their inbox and broadcasts
        a response to all other agents.
        """
        speaker_name = self.current_speaker
        self._step += 1
        speaker = agents.get(speaker_name)

        if speaker is None:
            return ProtocolResult(
                protocol=ProtocolType.ROUND_ROBIN,
                step=self._step,
                phase=f"speaker {speaker_name} not found",
            )

        # Let the speaker process inbox
        messages = await speaker.step()
        sent_messages = []

        for msg in messages:
            # Broadcast to all other agents
            for name in self._agents:
                if name != speaker_name:
                    broadcast_msg = Message(
                        sender=speaker_name,
                        receiver=name,
                        content=msg.content,
                        msg_type=MessageType.DIRECT,
                    )
                    bus.send(broadcast_msg)
                    sent_messages.append({
                        "sender": speaker_name,
                        "receiver": name,
                        "content": msg.content,
                    })

        return ProtocolResult(
            protocol=ProtocolType.ROUND_ROBIN,
            step=self._step,
            messages=sent_messages,
            participants=[speaker_name],
            phase=f"{speaker_name} speaking (round {(self._step - 1) // len(self._agents) + 1})",
            completed=self._step % len(self._agents) == 0,
        )


class BroadcastCollectProtocol(CommunicationProtocol):
    """Broadcast-collect communication protocol.

    Phase 1 (broadcast): One coordinator broadcasts a request to all workers.
    Phase 2 (collect): Workers respond, coordinator collects results.
    Alternates between phases each step.

    Useful for task delegation patterns.

    Example:
        >>> protocol = BroadcastCollectProtocol(
        ...     coordinator="manager",
        ...     workers=["worker_1", "worker_2"],
        ... )
    """

    def __init__(
        self,
        coordinator: str,
        workers: list[str],
        request_template: str = "task_{step}",
    ) -> None:
        all_agents = [coordinator] + list(workers)
        super().__init__(all_agents)
        self._coordinator = coordinator
        self._workers = list(workers)
        self._request_template = request_template
        self._phase = "broadcast"  # broadcast or collect

    @property
    def coordinator(self) -> str:
        """Coordinator agent name."""
        return self._coordinator

    @property
    def workers(self) -> list[str]:
        """Worker agent names."""
        return list(self._workers)

    @property
    def current_phase(self) -> str:
        """Current protocol phase."""
        return self._phase

    async def execute_step(
        self, bus: MessageBus, agents: dict[str, Agent]
    ) -> ProtocolResult:
        """Execute one broadcast-collect step."""
        self._step += 1
        sent_messages = []

        if self._phase == "broadcast":
            # Coordinator sends task to all workers
            coordinator_agent = agents.get(self._coordinator)
            if coordinator_agent:
                request = self._request_template.format(step=self._step)
                for worker_name in self._workers:
                    msg = Message(
                        sender=self._coordinator,
                        receiver=worker_name,
                        content=request,
                        msg_type=MessageType.REQUEST,
                    )
                    bus.send(msg)
                    sent_messages.append({
                        "sender": self._coordinator,
                        "receiver": worker_name,
                        "content": request,
                    })
            self._phase = "collect"
            phase_desc = f"broadcast: {self._coordinator} → {self._workers}"

        else:
            # Workers process and respond to coordinator
            for worker_name in self._workers:
                worker = agents.get(worker_name)
                if worker:
                    messages = await worker.step()
                    for msg in messages:
                        response = Message(
                            sender=worker_name,
                            receiver=self._coordinator,
                            content=msg.content,
                            msg_type=MessageType.RESPONSE,
                        )
                        bus.send(response)
                        sent_messages.append({
                            "sender": worker_name,
                            "receiver": self._coordinator,
                            "content": msg.content,
                        })
            self._phase = "broadcast"
            phase_desc = f"collect: {self._workers} → {self._coordinator}"

        return ProtocolResult(
            protocol=ProtocolType.BROADCAST_COLLECT,
            step=self._step,
            messages=sent_messages,
            participants=[self._coordinator] if self._phase == "collect" else self._workers,
            phase=phase_desc,
            completed=self._phase == "broadcast",  # just finished collect
        )


class ConsensusProtocol(CommunicationProtocol):
    """Consensus-building communication protocol.

    All agents discuss in rounds. Each round:
    1. All agents share their current position
    2. All agents see all positions
    3. After N rounds, a vote is held

    Useful for decision-making scenarios.

    Example:
        >>> protocol = ConsensusProtocol(
        ...     agents=["voter_1", "voter_2", "voter_3"],
        ...     rounds=3,
        ... )
    """

    def __init__(self, agents: list[str], rounds: int = 3) -> None:
        super().__init__(agents)
        self._max_rounds = rounds
        self._current_round = 0
        self._positions: dict[str, list[str]] = {a: [] for a in agents}

    @property
    def current_round(self) -> int:
        """Current discussion round."""
        return self._current_round

    @property
    def positions(self) -> dict[str, list[str]]:
        """All stated positions per agent."""
        return {k: list(v) for k, v in self._positions.items()}

    async def execute_step(
        self, bus: MessageBus, agents: dict[str, Agent]
    ) -> ProtocolResult:
        """Execute one consensus step."""
        self._step += 1
        sent_messages = []
        participants = []

        if self._current_round < self._max_rounds:
            # Discussion phase: each agent states position to all others
            self._current_round += 1
            for agent_name in self._agents:
                agent = agents.get(agent_name)
                if agent:
                    messages = await agent.step()
                    for msg in messages:
                        self._positions[agent_name].append(msg.content)
                        # Share with all other agents
                        for other in self._agents:
                            if other != agent_name:
                                share_msg = Message(
                                    sender=agent_name,
                                    receiver=other,
                                    content=msg.content,
                                    msg_type=MessageType.DIRECT,
                                )
                                bus.send(share_msg)
                                sent_messages.append({
                                    "sender": agent_name,
                                    "receiver": other,
                                    "content": msg.content,
                                })
                    participants.append(agent_name)

            phase = f"discussion round {self._current_round}/{self._max_rounds}"
            completed = self._current_round >= self._max_rounds
        else:
            # Vote phase: all agents cast final vote
            for agent_name in self._agents:
                agent = agents.get(agent_name)
                if agent:
                    messages = await agent.step()
                    for msg in messages:
                        self._positions[agent_name].append(f"VOTE:{msg.content}")
                        sent_messages.append({
                            "sender": agent_name,
                            "receiver": "consensus",
                            "content": f"VOTE: {msg.content}",
                        })
                    participants.append(agent_name)

            phase = "voting"
            completed = True
            self._current_round = 0  # reset for next cycle

        return ProtocolResult(
            protocol=ProtocolType.CONSENSUS,
            step=self._step,
            messages=sent_messages,
            participants=participants,
            phase=phase,
            completed=completed,
        )

    def reset(self) -> None:
        """Reset protocol state."""
        super().reset()
        self._current_round = 0
        self._positions = {a: [] for a in self._agents}


def create_protocol(
    protocol_type: ProtocolType | str,
    agents: list[str],
    **kwargs: Any,
) -> CommunicationProtocol:
    """Factory function to create a communication protocol.

    Args:
        protocol_type: Protocol type to create
        agents: List of agent names
        **kwargs: Additional protocol-specific arguments

    Returns:
        CommunicationProtocol instance

    Raises:
        ValueError: Unknown protocol type
    """
    try:
        if isinstance(protocol_type, str):
            protocol_type = ProtocolType(protocol_type)
    except ValueError:
        raise ProtocolError(f"Unknown protocol type: {protocol_type}") from None

    if protocol_type == ProtocolType.ROUND_ROBIN:
        return RoundRobinProtocol(agents, topic=kwargs.get("topic", ""))
    elif protocol_type == ProtocolType.BROADCAST_COLLECT:
        coordinator = kwargs.get("coordinator", agents[0] if agents else "")
        workers = kwargs.get("workers", [a for a in agents if a != coordinator])
        return BroadcastCollectProtocol(
            coordinator=coordinator,
            workers=workers,
            request_template=kwargs.get("request_template", "task_{step}"),
        )
    elif protocol_type == ProtocolType.CONSENSUS:
        return ConsensusProtocol(agents, rounds=kwargs.get("rounds", 3))
    elif protocol_type == ProtocolType.FREE_FORM:
        return FreeFormProtocol(agents)
    else:
        raise ProtocolError(f"Unknown protocol type: {protocol_type}")


class FreeFormProtocol(CommunicationProtocol):
    """Free-form communication — all agents step() with no ordering constraints.

    This is the default behavior matching ScenarioRunner without protocols.
    """

    async def execute_step(
        self, bus: MessageBus, agents: dict[str, Agent]
    ) -> ProtocolResult:
        """Execute one free-form step — all agents step()."""
        self._step += 1
        sent_messages = []
        participants = []

        for agent_name in self._agents:
            agent = agents.get(agent_name)
            if agent:
                messages = await agent.step()
                for msg in messages:
                    bus.send(msg)
                    sent_messages.append({
                        "sender": msg.sender,
                        "receiver": msg.receiver,
                        "content": msg.content,
                    })
                participants.append(agent_name)

        return ProtocolResult(
            protocol=ProtocolType.FREE_FORM,
            step=self._step,
            messages=sent_messages,
            participants=participants,
            phase="free_form",
            completed=True,
        )
