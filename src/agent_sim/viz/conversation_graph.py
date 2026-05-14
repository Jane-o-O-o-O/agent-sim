"""Conversation graph visualization — Mermaid and ASCII diagrams of agent message flow."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class ConversationGraph:
    """Generates visual representations of agent communication flow.

    Creates Mermaid sequence diagrams and ASCII representations
    from message history data.

    Features:
        - Mermaid sequence diagram generation
        - ASCII communication matrix
        - Message flow statistics
        - Agent interaction summary

    Example:
        >>> graph = ConversationGraph()
        >>> graph.add_message("alice", "bob", "hello")
        >>> graph.add_message("bob", "alice", "hi there")
        >>> print(graph.to_mermaid())
        >>> print(graph.to_ascii_matrix())
    """

    def __init__(self) -> None:
        self._messages: list[dict[str, Any]] = []
        self._agents: set[str] = set()

    def add_message(
        self,
        sender: str,
        receiver: str,
        content: str,
        step: int = 0,
        msg_type: str = "direct",
    ) -> None:
        """Record a message.

        Args:
            sender: Sender agent name
            receiver: Receiver agent name
            content: Message content
            step: Simulation step
            msg_type: Message type
        """
        self._messages.append({
            "sender": sender,
            "receiver": receiver,
            "content": content,
            "step": step,
            "type": msg_type,
        })
        self._agents.add(sender)
        self._agents.add(receiver)

    def add_messages(self, messages: list[dict[str, Any]]) -> None:
        """Bulk-add messages from history.

        Args:
            messages: List of message dicts with sender, receiver, content keys
        """
        for msg in messages:
            self.add_message(
                sender=msg.get("sender", "unknown"),
                receiver=msg.get("receiver", "unknown"),
                content=msg.get("content", ""),
                step=msg.get("step", 0),
                msg_type=msg.get("type", "direct"),
            )

    @classmethod
    def from_history(cls, messages: list[dict[str, Any]]) -> ConversationGraph:
        """Create graph from message history.

        Args:
            messages: List of message dicts

        Returns:
            ConversationGraph instance
        """
        graph = cls()
        graph.add_messages(messages)
        return graph

    @property
    def agents(self) -> list[str]:
        """Sorted list of all agents."""
        return sorted(self._agents)

    @property
    def message_count(self) -> int:
        """Total messages recorded."""
        return len(self._messages)

    def to_mermaid(self, max_content_len: int = 30, title: str = "") -> str:
        """Generate a Mermaid sequence diagram.

        Args:
            max_content_len: Max content length per message
            title: Optional diagram title

        Returns:
            Mermaid diagram string
        """
        lines = ["sequenceDiagram"]

        if title:
            lines.append(f"    %% {title}")

        # Declare participants in sorted order
        for agent in self.agents:
            safe = _sanitize_id(agent)
            lines.append(f"    participant {safe}")

        # Add messages
        for msg in self._messages:
            sender = _sanitize_id(msg["sender"])
            receiver = _sanitize_id(msg["receiver"])
            content = msg["content"][:max_content_len]
            # Escape special chars for Mermaid
            content = content.replace('"', "'").replace("\n", " ")
            lines.append(f'    {sender}->>{receiver}: {content}')

        return "\n".join(lines)

    def to_ascii_matrix(self) -> str:
        """Generate an ASCII communication matrix.

        Shows message counts between each pair of agents.

        Returns:
            ASCII matrix string
        """
        agents = self.agents
        if not agents:
            return "(no messages)"

        # Build count matrix
        matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for msg in self._messages:
            matrix[msg["sender"]][msg["receiver"]] += 1

        # Calculate column widths
        name_width = max(len(a) for a in agents)
        cell_width = max(name_width, 5)

        # Header
        header = " " * (name_width + 2)
        header += " ".join(f"{a:>{cell_width}}" for a in agents)
        lines = [header, "-" * len(header)]

        # Rows
        for sender in agents:
            row = f"{sender:>{name_width}} │"
            cells = []
            for receiver in agents:
                count = matrix[sender][receiver]
                cells.append(f"{count:>{cell_width}}")
            row += " ".join(cells)
            lines.append(row)

        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """Get communication statistics.

        Returns:
            Stats dict with counts, flows, etc.
        """
        if not self._messages:
            return {"total_messages": 0, "agents": 0}

        # Per-agent send/receive counts
        send_counts: dict[str, int] = defaultdict(int)
        recv_counts: dict[str, int] = defaultdict(int)
        pair_counts: dict[tuple[str, str], int] = defaultdict(int)

        for msg in self._messages:
            send_counts[msg["sender"]] += 1
            recv_counts[msg["receiver"]] += 1
            pair_counts[(msg["sender"], msg["receiver"])] += 1

        # Find most active pair
        most_active_pair = max(pair_counts.items(), key=lambda x: x[1]) if pair_counts else None

        return {
            "total_messages": len(self._messages),
            "agents": len(self._agents),
            "send_counts": dict(send_counts),
            "recv_counts": dict(recv_counts),
            "most_active_pair": (
                {"sender": most_active_pair[0][0], "receiver": most_active_pair[0][1], "count": most_active_pair[1]}
                if most_active_pair
                else None
            ),
            "unique_pairs": len(pair_counts),
        }

    def to_flow_summary(self) -> str:
        """Generate a human-readable flow summary.

        Returns:
            Summary string
        """
        stats = self.get_stats()
        if stats["total_messages"] == 0:
            return "(no messages)"

        lines = [f"消息流摘要: {stats['total_messages']} 条消息, {stats['agents']} 个 Agent"]
        lines.append("")

        lines.append("发送统计:")
        for agent, count in sorted(stats["send_counts"].items(), key=lambda x: -x[1]):
            bar = "█" * min(count, 30)
            lines.append(f"  {agent:<15} {bar} {count}")

        lines.append("")
        lines.append("接收统计:")
        for agent, count in sorted(stats["recv_counts"].items(), key=lambda x: -x[1]):
            bar = "█" * min(count, 30)
            lines.append(f"  {agent:<15} {bar} {count}")

        if stats["most_active_pair"]:
            pair = stats["most_active_pair"]
            lines.append("")
            lines.append(
                f"最活跃通信对: {pair['sender']} ↔ {pair['receiver']} ({pair['count']} messages)"
            )

        return "\n".join(lines)


def _sanitize_id(name: str) -> str:
    """Sanitize agent name for Mermaid participant ID."""
    return name.replace(" ", "_").replace("-", "_").replace(".", "_")
