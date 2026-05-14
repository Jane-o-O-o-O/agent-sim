"""Tests for v0.9.0 features — monitor, topology scheduler, protocols, templates, conversation graph."""
from __future__ import annotations

import asyncio
import io
import json
from pathlib import Path

import pytest
import yaml

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.role import Role
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.scenario.monitor import MonitorConfig, SimulationMonitor, StepSnapshot
from agent_sim.scenario.topology_scheduler import TopologyRule, TopologyScheduler
from agent_sim.scenario.protocol import (
    BroadcastCollectProtocol,
    CommunicationProtocol,
    ConsensusProtocol,
    FreeFormProtocol,
    ProtocolResult,
    ProtocolType,
    RoundRobinProtocol,
    create_protocol,
)
from agent_sim.scenario.templates import (
    get_template,
    list_templates,
    save_template_to_yaml,
    template_info,
)
from agent_sim.topology.dynamic import DynamicTopology
from agent_sim.topology.topology import TopologyType, build_topology
from agent_sim.viz.conversation_graph import ConversationGraph


# ── Helpers ──────────────────────────────────────────────────


class EchoAgent(Agent):
    """Test agent that echoes received messages."""

    async def step(self) -> list[Message]:
        replies = []
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


class SenderAgent(Agent):
    """Test agent that sends a message each step."""

    async def step(self) -> list[Message]:
        replies = []
        for target in self.context.get("targets", []):
            replies.append(Message(
                sender=self.name,
                receiver=target,
                content=f"msg_step_{self.step_count}",
                msg_type=MessageType.DIRECT,
            ))
        self.increment_step()
        return replies


def _make_agents(names: list[str]) -> list[Agent]:
    """Create echo agents with given names."""
    return [EchoAgent(name=n, role=Role(name=n)) for n in names]


def _make_bus_and_sandbox(names: list[str]) -> tuple[MessageBus, Sandbox, dict[str, Agent]]:
    """Create bus and sandbox with echo agents."""
    agents = _make_agents(names)
    sandbox = Sandbox(agents=agents)
    bus = MessageBus()
    agent_map = {}
    for a in agents:
        bus.register(a)
        agent_map[a.name] = a
    return bus, sandbox, agent_map


# ── SimulationMonitor tests ──────────────────────────────────


class TestSimulationMonitor:
    """Tests for SimulationMonitor."""

    def test_monitor_creation(self) -> None:
        monitor = SimulationMonitor(total_steps=10)
        assert monitor.total_messages == 0
        assert monitor.snapshots == []
        assert monitor.get_progress() == 0.0

    def test_monitor_step_tracking(self) -> None:
        output = io.StringIO()
        config = MonitorConfig(output=output, compact=True)
        monitor = SimulationMonitor(total_steps=3, config=config)

        monitor.on_simulation_start(steps=3, agent_count=2)
        monitor.on_step_start(step=1)
        monitor.on_message(sender="a", receiver="b", content="hello")
        monitor.on_step_end(step=1, messages_sent=1)

        assert monitor.total_messages == 1
        assert len(monitor.snapshots) == 1
        assert monitor.snapshots[0].step == 1
        assert monitor.snapshots[0].messages_sent == 1
        assert monitor.get_progress() == pytest.approx(1 / 3)

    def test_monitor_message_flow(self) -> None:
        monitor = SimulationMonitor(total_steps=2)

        monitor.on_step_start(step=1)
        monitor.on_message(sender="a", receiver="b", content="hello")
        monitor.on_message(sender="b", receiver="a", content="world")
        monitor.on_step_end(step=1, messages_sent=2)

        flow = monitor.message_flow
        assert len(flow) == 2
        assert flow[0]["sender"] == "a"
        assert flow[1]["sender"] == "b"

    def test_monitor_message_counts(self) -> None:
        monitor = SimulationMonitor(total_steps=2)
        monitor.on_step_start(step=1)
        monitor.on_message(sender="a", receiver="b", content="1")
        monitor.on_message(sender="a", receiver="b", content="2")
        monitor.on_message(sender="b", receiver="a", content="3")
        monitor.on_step_end(step=1, messages_sent=3)

        counts = monitor.get_message_counts()
        assert counts == {"a": 2, "b": 1}

    def test_monitor_communication_matrix(self) -> None:
        monitor = SimulationMonitor(total_steps=1)
        monitor.on_step_start(step=1)
        monitor.on_message(sender="a", receiver="b", content="1")
        monitor.on_message(sender="a", receiver="b", content="2")
        monitor.on_message(sender="b", receiver="c", content="3")
        monitor.on_step_end(step=1, messages_sent=3)

        matrix = monitor.get_communication_matrix()
        assert matrix["a"]["b"] == 2
        assert matrix["b"]["c"] == 1

    def test_monitor_progress_bar(self) -> None:
        monitor = SimulationMonitor(total_steps=4)
        monitor.on_step_start(1)
        monitor.on_step_end(1, 0)

        bar = monitor.progress_bar(width=20)
        assert "25%" in bar
        assert "█" in bar
        assert "░" in bar

    def test_monitor_summary(self) -> None:
        monitor = SimulationMonitor(total_steps=2)
        monitor.on_simulation_start(steps=2, agent_count=2)
        monitor.on_step_start(1)
        monitor.on_message(sender="a", receiver="b", content="hi")
        monitor.on_step_end(1, 1)
        monitor.on_step_start(2)
        monitor.on_message(sender="b", receiver="a", content="yo")
        monitor.on_step_end(2, 1)
        monitor.on_simulation_end(duration=0.1, total_messages=2)

        summary = monitor.summary()
        assert summary["total_steps"] == 2
        assert summary["total_messages"] == 2
        assert summary["avg_messages_per_step"] == 1.0

    def test_monitor_callbacks(self) -> None:
        snapshots_received = []
        monitor = SimulationMonitor(total_steps=2)
        monitor.add_callback(lambda s: snapshots_received.append(s))

        monitor.on_step_start(1)
        monitor.on_step_end(1, 5)

        assert len(snapshots_received) == 1
        assert snapshots_received[0].messages_sent == 5

    def test_monitor_output_stream(self) -> None:
        output = io.StringIO()
        config = MonitorConfig(output=output, show_messages=True, compact=True)
        monitor = SimulationMonitor(total_steps=1, config=config)

        monitor.on_simulation_start(steps=1, agent_count=2)
        monitor.on_step_start(1)
        monitor.on_message(sender="a", receiver="b", content="test")
        monitor.on_step_end(1, 1)
        monitor.on_simulation_end(duration=0.01, total_messages=1)

        text = output.getvalue()
        assert "仿真开始" in text
        assert "a→b" in text
        assert "仿真完成" in text

    def test_step_snapshot_dataclass(self) -> None:
        snap = StepSnapshot(step=5, messages_sent=3, elapsed=1.5)
        assert snap.step == 5
        assert snap.messages_sent == 3
        assert snap.messages == []
        assert snap.agent_states == {}


# ── TopologyScheduler tests ──────────────────────────────────


class TestTopologyScheduler:
    """Tests for TopologyScheduler."""

    def test_scheduler_creation(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        scheduler = TopologyScheduler(dyn)
        assert scheduler.rules == []
        assert scheduler.applied_steps == []

    def test_add_rule(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        scheduler = TopologyScheduler(dyn)

        rule = TopologyRule(step=3, topology_type=TopologyType.STAR, center="a")
        scheduler.add_rule(rule)
        assert len(scheduler.rules) == 1

    def test_rules_sorted_by_step(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        scheduler = TopologyScheduler(dyn)

        scheduler.add_rule(TopologyRule(step=5, topology_type=TopologyType.STAR))
        scheduler.add_rule(TopologyRule(step=2, topology_type=TopologyType.RING))
        scheduler.add_rule(TopologyRule(step=1, topology_type=TopologyType.CHAIN))

        steps = [r.step for r in scheduler.rules]
        assert steps == [1, 2, 5]

    def test_on_step_triggers_rule(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        scheduler = TopologyScheduler(dyn)

        scheduler.add_rule(TopologyRule(step=3, topology_type=TopologyType.STAR, center="a"))

        assert scheduler.on_step(1) is False
        assert scheduler.on_step(2) is False
        assert scheduler.on_step(3) is True
        assert 3 in scheduler.applied_steps
        assert dyn.topology.topology_type == TopologyType.STAR

    def test_conditional_rule(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        scheduler = TopologyScheduler(dyn)

        # Trigger on even steps
        scheduler.add_conditional_rule(
            condition=lambda step: step % 2 == 0,
            topology_type=TopologyType.STAR,
            center="a",
        )

        assert scheduler.on_step(1) is False
        assert scheduler.on_step(2) is True
        assert scheduler.on_step(3) is False
        assert scheduler.on_step(4) is True
        assert len(scheduler.applied_steps) == 2

    def test_multiple_rules_same_step(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        scheduler = TopologyScheduler(dyn)

        scheduler.add_rule(TopologyRule(step=2, topology_type=TopologyType.STAR, center="a"))
        scheduler.add_rule(TopologyRule(step=2, topology_type=TopologyType.RING))

        changed = scheduler.on_step(2)
        assert changed is True
        # Last rule wins
        assert dyn.topology.topology_type == TopologyType.RING

    def test_scheduler_summary(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        scheduler = TopologyScheduler(dyn)

        scheduler.add_rule(TopologyRule(step=2, topology_type=TopologyType.STAR, center="a", description="切换到星型"))
        scheduler.on_step(2)

        summary = scheduler.summary()
        assert summary["total_rules"] == 1
        assert summary["applied_count"] == 1
        assert 2 in summary["applied_steps"]

    def test_topology_rule_pydantic(self) -> None:
        rule = TopologyRule(step=5, topology_type=TopologyType.STAR, center="leader", description="test")
        assert rule.step == 5
        assert rule.center == "leader"

        # Validation: step >= 1
        with pytest.raises(Exception):
            TopologyRule(step=0, topology_type=TopologyType.MESH)


# ── CommunicationProtocol tests ──────────────────────────────


class TestRoundRobinProtocol:
    """Tests for RoundRobinProtocol."""

    def test_current_speaker(self) -> None:
        protocol = RoundRobinProtocol(["a", "b", "c"])
        assert protocol.current_speaker == "a"
        protocol._step = 1
        assert protocol.current_speaker == "b"
        protocol._step = 2
        assert protocol.current_speaker == "c"
        protocol._step = 3
        assert protocol.current_speaker == "a"  # wraps around

    @pytest.mark.asyncio
    async def test_round_robin_step(self) -> None:
        bus, sandbox, agents = _make_bus_and_sandbox(["a", "b", "c"])
        # Give agent 'a' something to process
        agents["a"].receive(Message(sender="b", receiver="a", content="hello"))

        protocol = RoundRobinProtocol(["a", "b", "c"])
        result = await protocol.execute_step(bus, agents)

        assert result.protocol == ProtocolType.ROUND_ROBIN
        assert result.step == 1
        assert "a" in result.participants
        assert result.completed is False  # 3 agents, step 1

    @pytest.mark.asyncio
    async def test_round_robin_cycle_completes(self) -> None:
        bus, sandbox, agents = _make_bus_and_sandbox(["a", "b"])
        protocol = RoundRobinProtocol(["a", "b"])

        await protocol.execute_step(bus, agents)  # a speaks
        result = await protocol.execute_step(bus, agents)  # b speaks

        assert result.completed is True  # cycle complete (2/2)


class TestBroadcastCollectProtocol:
    """Tests for BroadcastCollectProtocol."""

    @pytest.mark.asyncio
    async def test_broadcast_phase(self) -> None:
        bus, sandbox, agents = _make_bus_and_sandbox(["coord", "w1", "w2"])
        protocol = BroadcastCollectProtocol(coordinator="coord", workers=["w1", "w2"])

        assert protocol.current_phase == "broadcast"
        result = await protocol.execute_step(bus, agents)

        assert result.protocol == ProtocolType.BROADCAST_COLLECT
        assert "broadcast" in result.phase
        assert protocol.current_phase == "collect"
        assert len(result.messages) == 2  # sent to 2 workers

    @pytest.mark.asyncio
    async def test_collect_phase(self) -> None:
        bus, sandbox, agents = _make_bus_and_sandbox(["coord", "w1", "w2"])
        protocol = BroadcastCollectProtocol(coordinator="coord", workers=["w1", "w2"])

        # Broadcast phase
        await protocol.execute_step(bus, agents)

        # Workers should have received messages
        result = await protocol.execute_step(bus, agents)  # collect phase
        assert "collect" in result.phase
        assert result.completed is True

    @pytest.mark.asyncio
    async def test_custom_request_template(self) -> None:
        bus, sandbox, agents = _make_bus_and_sandbox(["mgr", "dev"])
        protocol = BroadcastCollectProtocol(
            coordinator="mgr",
            workers=["dev"],
            request_template="implement_feature_{step}",
        )

        result = await protocol.execute_step(bus, agents)
        assert result.messages[0]["content"] == "implement_feature_1"


class TestConsensusProtocol:
    """Tests for ConsensusProtocol."""

    @pytest.mark.asyncio
    async def test_discussion_rounds(self) -> None:
        bus, sandbox, agents = _make_bus_and_sandbox(["v1", "v2", "v3"])
        protocol = ConsensusProtocol(["v1", "v2", "v3"], rounds=3)

        # Round 1
        result = await protocol.execute_step(bus, agents)
        assert result.protocol == ProtocolType.CONSENSUS
        assert "round 1/3" in result.phase
        assert result.completed is False
        assert protocol.current_round == 1

        # Round 2
        result = await protocol.execute_step(bus, agents)
        assert "round 2/3" in result.phase

        # Round 3
        result = await protocol.execute_step(bus, agents)
        assert "round 3/3" in result.phase
        assert result.completed is True

    @pytest.mark.asyncio
    async def test_consensus_positions(self) -> None:
        bus, sandbox, agents = _make_bus_and_sandbox(["a", "b"])
        protocol = ConsensusProtocol(["a", "b"], rounds=2)

        await protocol.execute_step(bus, agents)
        positions = protocol.positions
        assert "a" in positions
        assert "b" in positions

    @pytest.mark.asyncio
    async def test_consensus_reset(self) -> None:
        bus, sandbox, agents = _make_bus_and_sandbox(["a", "b"])
        protocol = ConsensusProtocol(["a", "b"], rounds=2)

        await protocol.execute_step(bus, agents)
        protocol.reset()
        assert protocol.current_round == 0
        assert protocol.step == 0


class TestFreeFormProtocol:
    """Tests for FreeFormProtocol."""

    @pytest.mark.asyncio
    async def test_free_form_step(self) -> None:
        bus, sandbox, agents = _make_bus_and_sandbox(["a", "b"])
        protocol = FreeFormProtocol(["a", "b"])

        result = await protocol.execute_step(bus, agents)
        assert result.protocol == ProtocolType.FREE_FORM
        assert result.completed is True
        assert len(result.participants) == 2


class TestCreateProtocol:
    """Tests for create_protocol factory."""

    def test_create_round_robin(self) -> None:
        p = create_protocol("round_robin", ["a", "b"])
        assert isinstance(p, RoundRobinProtocol)

    def test_create_broadcast_collect(self) -> None:
        p = create_protocol("broadcast_collect", ["a", "b", "c"], coordinator="a")
        assert isinstance(p, BroadcastCollectProtocol)

    def test_create_consensus(self) -> None:
        p = create_protocol("consensus", ["a", "b"], rounds=5)
        assert isinstance(p, ConsensusProtocol)

    def test_create_free_form(self) -> None:
        p = create_protocol("free_form", ["a", "b"])
        assert isinstance(p, FreeFormProtocol)

    def test_create_by_enum(self) -> None:
        p = create_protocol(ProtocolType.ROUND_ROBIN, ["a", "b"])
        assert isinstance(p, RoundRobinProtocol)

    def test_create_unknown_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown protocol"):
            create_protocol("unknown", ["a"])


class TestProtocolResult:
    """Tests for ProtocolResult model."""

    def test_default_values(self) -> None:
        result = ProtocolResult()
        assert result.protocol == ProtocolType.FREE_FORM
        assert result.step == 0
        assert result.messages == []
        assert result.completed is False

    def test_custom_values(self) -> None:
        result = ProtocolResult(
            protocol=ProtocolType.ROUND_ROBIN,
            step=3,
            messages=[{"sender": "a", "receiver": "b", "content": "hi"}],
            participants=["a"],
            phase="a speaking",
            completed=True,
        )
        assert result.step == 3
        assert len(result.messages) == 1


# ── Template tests ──────────────────────────────────────────


class TestScenarioTemplates:
    """Tests for scenario templates."""

    def test_list_templates(self) -> None:
        templates = list_templates()
        assert "ping_pong" in templates
        assert "debate" in templates
        assert "brainstorm" in templates
        assert "code_review" in templates
        assert "task_delegation" in templates
        assert "multi_round_discussion" in templates
        assert len(templates) >= 6

    def test_get_template(self) -> None:
        template = get_template("ping_pong")
        assert template["name"] == "ping-pong"
        assert "agents" in template
        assert len(template["agents"]) == 2

    def test_get_template_not_found(self) -> None:
        with pytest.raises(KeyError, match="not found"):
            get_template("nonexistent")

    def test_template_info(self) -> None:
        info = template_info("debate")
        assert "name" in info
        assert "description" in info
        assert "agents" in info
        assert "steps" in info

    def test_template_isolation(self) -> None:
        """Getting a template twice returns independent copies."""
        t1 = get_template("ping_pong")
        t2 = get_template("ping_pong")
        t1["name"] = "modified"
        assert t2["name"] == "ping-pong"

    def test_save_template_to_yaml(self, tmp_path: Path) -> None:
        output = tmp_path / "test_scenario.yaml"
        result = save_template_to_yaml("debate", output)
        assert result == output
        assert output.exists()

        with open(output) as f:
            data = yaml.safe_load(f)
        assert data["name"] == "debate"
        assert len(data["agents"]) == 3

    def test_all_templates_valid_yaml(self, tmp_path: Path) -> None:
        """All templates can be serialized to valid YAML."""
        for name in list_templates():
            output = tmp_path / f"{name}.yaml"
            save_template_to_yaml(name, output)
            with open(output) as f:
                data = yaml.safe_load(f)
            assert "name" in data
            assert "agents" in data

    def test_debate_template_structure(self) -> None:
        t = get_template("debate")
        agent_names = [a["name"] for a in t["agents"]]
        assert "moderator" in agent_names
        assert "proponent" in agent_names
        assert "opponent" in agent_names

    def test_task_delegation_template(self) -> None:
        t = get_template("task_delegation")
        assert t["steps"] == 6
        assert len(t["agents"]) == 4


# ── ConversationGraph tests ──────────────────────────────────


class TestConversationGraph:
    """Tests for ConversationGraph."""

    def test_graph_creation(self) -> None:
        graph = ConversationGraph()
        assert graph.agents == []
        assert graph.message_count == 0

    def test_add_message(self) -> None:
        graph = ConversationGraph()
        graph.add_message("a", "b", "hello")
        assert graph.message_count == 1
        assert "a" in graph.agents
        assert "b" in graph.agents

    def test_add_messages_bulk(self) -> None:
        graph = ConversationGraph()
        messages = [
            {"sender": "a", "receiver": "b", "content": "hi"},
            {"sender": "b", "receiver": "a", "content": "hey"},
        ]
        graph.add_messages(messages)
        assert graph.message_count == 2

    def test_from_history(self) -> None:
        messages = [
            {"sender": "x", "receiver": "y", "content": "1"},
            {"sender": "y", "receiver": "x", "content": "2"},
        ]
        graph = ConversationGraph.from_history(messages)
        assert graph.message_count == 2
        assert "x" in graph.agents

    def test_to_mermaid(self) -> None:
        graph = ConversationGraph()
        graph.add_message("alice", "bob", "hello")
        graph.add_message("bob", "alice", "hi there")

        mermaid = graph.to_mermaid(title="Test")
        assert "sequenceDiagram" in mermaid
        assert "alice" in mermaid
        assert "bob" in mermaid
        assert "hello" in mermaid
        assert "hi there" in mermaid

    def test_to_mermaid_content_truncation(self) -> None:
        graph = ConversationGraph()
        graph.add_message("a", "b", "x" * 100)
        mermaid = graph.to_mermaid(max_content_len=10)
        # Content should be truncated
        assert "xxxxxxxxxx" in mermaid

    def test_to_mermaid_special_chars(self) -> None:
        graph = ConversationGraph()
        graph.add_message("a", 'b', 'hello "world"')
        mermaid = graph.to_mermaid()
        # Quotes should be escaped
        assert '"' not in mermaid.split(":")[-1]

    def test_to_ascii_matrix(self) -> None:
        graph = ConversationGraph()
        graph.add_message("a", "b", "1")
        graph.add_message("a", "b", "2")
        graph.add_message("b", "a", "3")

        matrix = graph.to_ascii_matrix()
        assert "a" in matrix
        assert "b" in matrix
        # Should contain counts
        assert "2" in matrix
        assert "1" in matrix

    def test_ascii_matrix_empty(self) -> None:
        graph = ConversationGraph()
        assert graph.to_ascii_matrix() == "(no messages)"

    def test_get_stats(self) -> None:
        graph = ConversationGraph()
        graph.add_message("a", "b", "1")
        graph.add_message("a", "b", "2")
        graph.add_message("b", "a", "3")

        stats = graph.get_stats()
        assert stats["total_messages"] == 3
        assert stats["agents"] == 2
        assert stats["send_counts"]["a"] == 2
        assert stats["send_counts"]["b"] == 1
        assert stats["recv_counts"]["b"] == 2
        assert stats["recv_counts"]["a"] == 1
        assert stats["most_active_pair"]["sender"] == "a"
        assert stats["most_active_pair"]["count"] == 2

    def test_get_stats_empty(self) -> None:
        graph = ConversationGraph()
        stats = graph.get_stats()
        assert stats["total_messages"] == 0

    def test_to_flow_summary(self) -> None:
        graph = ConversationGraph()
        graph.add_message("a", "b", "1")
        graph.add_message("a", "b", "2")
        graph.add_message("b", "c", "3")

        summary = graph.to_flow_summary()
        assert "消息流摘要" in summary
        assert "发送统计" in summary
        assert "接收统计" in summary
        assert "最活跃通信对" in summary

    def test_flow_summary_empty(self) -> None:
        graph = ConversationGraph()
        assert graph.to_flow_summary() == "(no messages)"
