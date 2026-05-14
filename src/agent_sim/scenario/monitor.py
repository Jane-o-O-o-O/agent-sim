"""Real-time simulation monitor for live output during simulation runs."""
from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Callable, TextIO

logger = logging.getLogger(__name__)


@dataclass
class StepSnapshot:
    """Snapshot of a single simulation step.

    Attributes:
        step: Step number (1-indexed)
        timestamp: Time when step was recorded
        messages_sent: Messages sent in this step
        messages: List of message dicts (sender, receiver, content)
        agent_states: Agent states at this step
        elapsed: Seconds since simulation start
    """

    step: int = 0
    timestamp: float = 0.0
    messages_sent: int = 0
    messages: list[dict[str, str]] = field(default_factory=list)
    agent_states: dict[str, str] = field(default_factory=dict)
    elapsed: float = 0.0


@dataclass
class MonitorConfig:
    """Configuration for simulation monitor.

    Attributes:
        show_progress: Show progress bar
        show_messages: Show individual messages
        show_agent_states: Show agent state changes
        show_step_summary: Show per-step summary
        output: Output stream (default: stderr)
        compact: Use compact output format
    """

    show_progress: bool = True
    show_messages: bool = True
    show_agent_states: bool = False
    show_step_summary: bool = True
    output: TextIO = field(default_factory=lambda: sys.stderr)
    compact: bool = False


class SimulationMonitor:
    """Real-time simulation monitor.

    Captures step-by-step snapshots and provides live output during
    simulation runs. Can be attached to ScenarioRunner via hooks.

    Features:
        - Step-by-step progress tracking
        - Message flow visualization
        - Agent state monitoring
        - Customizable output stream
        - Snapshot history for post-analysis

    Example:
        >>> monitor = SimulationMonitor(total_steps=10)
        >>> monitor.on_step_start(step=1)
        >>> monitor.on_message(sender="a", receiver="b", content="hello")
        >>> monitor.on_step_end(step=1, messages_sent=1)
        >>> print(monitor.summary())
    """

    def __init__(
        self,
        total_steps: int = 0,
        config: MonitorConfig | None = None,
    ) -> None:
        self._total_steps = total_steps
        self._config = config or MonitorConfig()
        self._snapshots: list[StepSnapshot] = []
        self._current_snapshot: StepSnapshot | None = None
        self._start_time: float = 0.0
        self._total_messages: int = 0
        self._message_flow: list[dict[str, Any]] = []
        self._callbacks: list[Callable[[StepSnapshot], None]] = []

    @property
    def snapshots(self) -> list[StepSnapshot]:
        """All recorded step snapshots."""
        return list(self._snapshots)

    @property
    def total_messages(self) -> int:
        """Total messages observed."""
        return self._total_messages

    @property
    def message_flow(self) -> list[dict[str, Any]]:
        """Complete message flow history."""
        return list(self._message_flow)

    @property
    def elapsed(self) -> float:
        """Elapsed time since monitoring started."""
        if self._start_time == 0:
            return 0.0
        return time.time() - self._start_time

    def add_callback(self, callback: Callable[[StepSnapshot], None]) -> None:
        """Add a callback invoked after each step completes.

        Args:
            callback: Function receiving StepSnapshot
        """
        self._callbacks.append(callback)

    def on_simulation_start(self, steps: int, agent_count: int) -> None:
        """Called when simulation starts.

        Args:
            steps: Total steps to run
            agent_count: Number of agents
        """
        self._total_steps = steps
        self._start_time = time.time()
        if self._config.show_progress:
            self._write(f"🚀 仿真开始: {agent_count} agents, {steps} steps\n")

    def on_step_start(self, step: int) -> None:
        """Called at the start of each step.

        Args:
            step: Step number (1-indexed)
        """
        self._current_snapshot = StepSnapshot(
            step=step,
            timestamp=time.time(),
        )

    def on_message(
        self,
        sender: str,
        receiver: str,
        content: str,
        msg_type: str = "direct",
    ) -> None:
        """Called when a message is sent.

        Args:
            sender: Sender agent name
            receiver: Receiver agent name
            content: Message content
            msg_type: Message type
        """
        self._total_messages += 1
        msg_data = {
            "step": self._current_snapshot.step if self._current_snapshot else 0,
            "sender": sender,
            "receiver": receiver,
            "content": content,
            "type": msg_type,
            "timestamp": time.time(),
        }
        self._message_flow.append(msg_data)

        if self._current_snapshot:
            self._current_snapshot.messages_sent += 1
            self._current_snapshot.messages.append({
                "sender": sender,
                "receiver": receiver,
                "content": content[:50] + ("..." if len(content) > 50 else ""),
            })

        if self._config.show_messages:
            if self._config.compact:
                self._write(f"  📨 {sender}→{receiver}: {content[:40]}\n")
            else:
                self._write(f"  📨 [{sender}] → [{receiver}]: {content[:60]}\n")

    def on_step_end(
        self,
        step: int,
        messages_sent: int = 0,
        agent_states: dict[str, str] | None = None,
    ) -> None:
        """Called at the end of each step.

        Args:
            step: Step number (1-indexed)
            messages_sent: Messages sent in this step
            agent_states: Current agent states
        """
        if self._current_snapshot:
            self._current_snapshot.messages_sent = messages_sent
            self._current_snapshot.agent_states = agent_states or {}
            self._current_snapshot.elapsed = time.time() - self._start_time
            self._snapshots.append(self._current_snapshot)

            for cb in self._callbacks:
                try:
                    cb(self._current_snapshot)
                except Exception as e:
                    logger.warning("监控回调异常: %s", e)

        if self._config.show_step_summary:
            elapsed = time.time() - self._start_time if self._start_time else 0
            if self._config.compact:
                self._write(f"  ✓ step {step}/{self._total_steps} ({messages_sent} msgs, {elapsed:.2f}s)\n")
            else:
                self._write(
                    f"  ✓ Step {step}/{self._total_steps} — "
                    f"{messages_sent} messages, {elapsed:.3f}s elapsed\n"
                )

        self._current_snapshot = None

    def on_simulation_end(self, duration: float, total_messages: int) -> None:
        """Called when simulation ends.

        Args:
            duration: Total duration in seconds
            total_messages: Total messages sent
        """
        if self._config.show_progress:
            self._write(
                f"✅ 仿真完成: {total_messages} messages in {duration:.3f}s\n"
            )

    def get_progress(self) -> float:
        """Get progress as a fraction (0.0 to 1.0)."""
        if self._total_steps == 0:
            return 0.0
        return len(self._snapshots) / self._total_steps

    def get_message_counts(self) -> dict[str, int]:
        """Get message count per sender.

        Returns:
            Dict mapping agent name to message count
        """
        counts: dict[str, int] = {}
        for msg in self._message_flow:
            sender = msg["sender"]
            counts[sender] = counts.get(sender, 0) + 1
        return counts

    def get_communication_matrix(self) -> dict[str, dict[str, int]]:
        """Get communication matrix between agents.

        Returns:
            Nested dict: {sender: {receiver: count}}
        """
        matrix: dict[str, dict[str, int]] = {}
        for msg in self._message_flow:
            sender = msg["sender"]
            receiver = msg["receiver"]
            if sender not in matrix:
                matrix[sender] = {}
            matrix[sender][receiver] = matrix[sender].get(receiver, 0) + 1
        return matrix

    def summary(self) -> dict[str, Any]:
        """Get a summary of the monitoring data.

        Returns:
            Summary dict with stats
        """
        return {
            "total_steps": len(self._snapshots),
            "total_messages": self._total_messages,
            "elapsed": self.elapsed,
            "message_counts": self.get_message_counts(),
            "avg_messages_per_step": (
                self._total_messages / len(self._snapshots)
                if self._snapshots
                else 0
            ),
        }

    def progress_bar(self, width: int = 40) -> str:
        """Generate an ASCII progress bar.

        Args:
            width: Bar width in characters

        Returns:
            Progress bar string
        """
        progress = self.get_progress()
        filled = int(width * progress)
        bar = "█" * filled + "░" * (width - filled)
        pct = progress * 100
        return f"[{bar}] {pct:.0f}% ({len(self._snapshots)}/{self._total_steps})"

    def _write(self, text: str) -> None:
        """Write to output stream."""
        try:
            self._config.output.write(text)
            self._config.output.flush()
        except Exception:
            pass
