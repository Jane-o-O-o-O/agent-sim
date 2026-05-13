"""Tests for v0.7.0 features: replay, HTML report, batch runner, scenario inheritance."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.role import Role
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.scenario.checkpoint import CheckpointManager
from agent_sim.scenario.config import (
    AgentConfig,
    ConnectionConfig,
    ScenarioConfig,
    load_scenario,
)
from agent_sim.scenario.factory import build_scenario
from agent_sim.scenario.hooks import LifecycleHooks
from agent_sim.scenario.recorder import EventRecorder, EventType, SimulationEvent
from agent_sim.scenario.runner import RunResult, ScenarioRunner
from agent_sim.scenario.batch import BatchResult


# ─── Helper Agents ───

class EchoAgent(Agent):
    """Echo back any message received."""
    async def step(self) -> list[Message]:
        replies = []
        for msg in self.inbox:
            replies.append(Message(
                sender=self.name, receiver=msg.sender,
                content=f"echo:{msg.content}", msg_type=MessageType.RESPONSE,
            ))
        self.inbox.clear()
        self.increment_step()
        return replies


class PingAgent(Agent):
    """Send ping to targets on first step."""
    async def step(self) -> list[Message]:
        replies = []
        for msg in self.inbox:
            if msg.content == "ping":
                replies.append(Message(
                    sender=self.name, receiver=msg.sender,
                    content="pong", msg_type=MessageType.RESPONSE,
                ))
        self.inbox.clear()
        if self.step_count == 0:
            for target in self.context.get("targets", []):
                replies.append(Message(
                    sender=self.name, receiver=target,
                    content="ping", msg_type=MessageType.REQUEST,
                ))
        self.increment_step()
        return replies


def _make_simple_agents():
    """Create a simple 2-agent setup for testing."""
    a = EchoAgent(name="alice", role=Role(name="echo"))
    b = PingAgent(name="bob", role=Role(name="ping"), context={"targets": ["alice"]})
    sandbox = Sandbox(agents=[a, b])
    bus = MessageBus()
    bus.register(a)
    bus.register(b)
    return sandbox, bus


# ═══════════════════════════════════════════════
# 1. Event Replay Engine Tests
# ═══════════════════════════════════════════════

class TestReplayEngine:
    """Test the event replay system."""

    def test_replay_engine_creation(self):
        """ReplayEngine can be created from events."""
        from agent_sim.scenario.replay import ReplayEngine

        events = [
            SimulationEvent(event_type="simulation_start", step=0, data={"steps": 3, "agent_count": 2}),
            SimulationEvent(event_type="step_start", step=1, data={}),
            SimulationEvent(event_type="message", step=1, data={"sender": "alice", "receiver": "bob"}),
            SimulationEvent(event_type="step_end", step=1, data={"messages_sent": 1}),
            SimulationEvent(event_type="step_start", step=2, data={}),
            SimulationEvent(event_type="step_end", step=2, data={"messages_sent": 0}),
            SimulationEvent(event_type="simulation_end", step=3, data={"duration": 0.1}),
        ]
        engine = ReplayEngine(events)
        assert engine.total_steps == 3
        assert engine.event_count == 7

    def test_replay_from_recorder(self):
        """ReplayEngine can be built from an EventRecorder."""
        from agent_sim.scenario.replay import ReplayEngine

        recorder = EventRecorder()
        recorder.record(EventType.SIM_START, steps=2, agent_count=1)
        recorder.record(EventType.STEP_START, step=1)
        recorder.record(EventType.MESSAGE, step=1, sender="a", receiver="b")
        recorder.record(EventType.STEP_END, step=1, messages_sent=1)
        recorder.record(EventType.SIM_END, duration=0.05)

        engine = ReplayEngine.from_recorder(recorder)
        assert engine.event_count == 5

    def test_replay_step_by_step(self):
        """Can iterate through events step by step."""
        from agent_sim.scenario.replay import ReplayEngine

        events = [
            SimulationEvent(event_type="simulation_start", step=0, data={}),
            SimulationEvent(event_type="step_start", step=1, data={}),
            SimulationEvent(event_type="message", step=1, data={"sender": "a"}),
            SimulationEvent(event_type="step_end", step=1, data={"messages_sent": 1}),
            SimulationEvent(event_type="step_start", step=2, data={}),
            SimulationEvent(event_type="step_end", step=2, data={"messages_sent": 0}),
            SimulationEvent(event_type="simulation_end", step=0, data={}),
        ]
        engine = ReplayEngine(events)

        step1 = engine.get_step(1)
        assert len(step1) == 3  # step_start, message, step_end
        assert all(e.step == 1 for e in step1)

        step2 = engine.get_step(2)
        assert len(step2) == 2

    def test_replay_filter_by_type(self):
        """Can filter events by type during replay."""
        from agent_sim.scenario.replay import ReplayEngine

        events = [
            SimulationEvent(event_type="step_start", step=1, data={}),
            SimulationEvent(event_type="message", step=1, data={"sender": "a"}),
            SimulationEvent(event_type="message", step=1, data={"sender": "b"}),
            SimulationEvent(event_type="step_end", step=1, data={}),
        ]
        engine = ReplayEngine(events)

        messages = engine.filter_by_type("message")
        assert len(messages) == 2
        assert all(e.event_type == "message" for e in messages)

    def test_replay_to_json(self):
        """ReplayEngine can export replay data as JSON."""
        from agent_sim.scenario.replay import ReplayEngine

        events = [
            SimulationEvent(event_type="simulation_start", step=0, data={"steps": 1}),
            SimulationEvent(event_type="step_start", step=1, data={}),
            SimulationEvent(event_type="simulation_end", step=0, data={}),
        ]
        engine = ReplayEngine(events)
        data = engine.to_dict()

        assert "total_steps" in data
        assert "event_count" in data
        assert "steps" in data
        assert len(data["steps"]) >= 1

    def test_replay_timeline(self):
        """Can get a timeline view of all events."""
        from agent_sim.scenario.replay import ReplayEngine

        events = [
            SimulationEvent(event_type="simulation_start", step=0, data={}),
            SimulationEvent(event_type="step_start", step=1, data={}),
            SimulationEvent(event_type="message", step=1, data={"sender": "a", "receiver": "b"}),
            SimulationEvent(event_type="step_end", step=1, data={}),
            SimulationEvent(event_type="simulation_end", step=0, data={}),
        ]
        engine = ReplayEngine(events)
        timeline = engine.timeline()

        assert len(timeline) == 5
        assert timeline[0]["event_type"] == "simulation_start"
        assert timeline[2]["event_type"] == "message"

    def test_replay_from_json_file(self):
        """Can load replay data from a JSON file."""
        from agent_sim.scenario.replay import ReplayEngine

        data = {
            "events": [
                {"event_type": "simulation_start", "timestamp": 1.0, "step": 0, "data": {}},
                {"event_type": "step_start", "timestamp": 2.0, "step": 1, "data": {}},
                {"event_type": "simulation_end", "timestamp": 3.0, "step": 0, "data": {}},
            ]
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        engine = ReplayEngine.from_json(path)
        assert engine.event_count == 3
        Path(path).unlink()

    def test_replay_summary(self):
        """ReplayEngine provides a summary of the replay."""
        from agent_sim.scenario.replay import ReplayEngine

        events = [
            SimulationEvent(event_type="simulation_start", step=0, data={}),
            SimulationEvent(event_type="message", step=1, data={"sender": "a"}),
            SimulationEvent(event_type="message", step=2, data={"sender": "b"}),
            SimulationEvent(event_type="agent_error", step=2, data={"agent": "a"}),
            SimulationEvent(event_type="simulation_end", step=0, data={}),
        ]
        engine = ReplayEngine(events)
        summary = engine.summary()

        assert summary["total_events"] == 5
        assert summary["total_steps"] == 2
        assert summary["event_counts"]["message"] == 2
        assert summary["event_counts"]["agent_error"] == 1


# ═══════════════════════════════════════════════
# 2. HTML Report Tests
# ═══════════════════════════════════════════════

class TestHTMLReport:
    """Test HTML report generation."""

    def test_html_report_creation(self):
        """HTMLReport can be created from RunResult."""
        from agent_sim.export import HTMLReport

        result = RunResult(
            steps_completed=5,
            total_messages=10,
            agent_states={"alice": "completed", "bob": "completed"},
            duration=0.5,
            metrics={"step_details": [
                {"step": 1, "messages_sent": 3, "agents_active": 2},
                {"step": 2, "messages_sent": 2, "agents_active": 2},
            ]},
        )
        report = HTMLReport(result, scenario_name="test-scenario")
        assert report is not None

    def test_html_report_render(self):
        """HTMLReport renders valid HTML."""
        from agent_sim.export import HTMLReport

        result = RunResult(
            steps_completed=3,
            total_messages=5,
            agent_states={"a": "completed", "b": "completed"},
            duration=0.1,
        )
        report = HTMLReport(result, scenario_name="test")
        html = report.render()

        assert "<!DOCTYPE html>" in html
        assert "test" in html
        assert "3" in html  # steps_completed
        assert "5" in html  # total_messages

    def test_html_report_contains_charts(self):
        """HTML report includes SVG charts."""
        from agent_sim.export import HTMLReport

        result = RunResult(
            steps_completed=3,
            total_messages=5,
            agent_states={"a": "completed", "b": "failed"},
            duration=0.1,
            metrics={"step_details": [
                {"step": 1, "messages_sent": 2},
                {"step": 2, "messages_sent": 3},
            ]},
        )
        report = HTMLReport(result, scenario_name="chart-test")
        html = report.render()

        assert "<svg" in html

    def test_html_report_save_to_file(self):
        """HTMLReport can save to a file."""
        from agent_sim.export import HTMLReport

        result = RunResult(steps_completed=1, total_messages=1, agent_states={"a": "completed"}, duration=0.01)
        report = HTMLReport(result, scenario_name="save-test")

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            path = f.name

        report.save(path)
        content = Path(path).read_text(encoding="utf-8")
        assert "<!DOCTYPE html>" in content
        assert "save-test" in content
        Path(path).unlink()

    def test_html_report_with_eval(self):
        """HTML report can include evaluation results."""
        from agent_sim.export import HTMLReport
        from agent_sim.metrics.evaluator import EvalReport, EvalResult

        result = RunResult(steps_completed=3, total_messages=10, agent_states={"a": "completed"}, duration=0.1)
        eval_report = EvalReport(
            results=[
                EvalResult(name="volume", score=0.8, passed=True),
                EvalResult(name="completion", score=1.0, passed=True),
            ],
            overall_score=0.9,
            passed=True,
        )
        report = HTMLReport(result, scenario_name="eval-test", eval_report=eval_report)
        html = report.render()

        assert "volume" in html
        assert "0.9" in html


# ═══════════════════════════════════════════════
# 3. Batch Runner Tests
# ═══════════════════════════════════════════════

class TestBatchRunner:
    """Test batch simulation runner."""

    def test_batch_runner_creation(self):
        """BatchRunner can be created."""
        from agent_sim.scenario.batch import BatchRunner

        runner = BatchRunner(runs=5)
        assert runner.runs == 5

    @pytest.mark.asyncio
    async def test_batch_runner_execute(self):
        """BatchRunner runs multiple simulations."""
        from agent_sim.scenario.batch import BatchRunner

        sandbox, bus = _make_simple_agents()
        runner = BatchRunner(runs=3)

        results = await runner.run(
            sandbox_factory=lambda: Sandbox(agents=[
                EchoAgent(name="alice", role=Role(name="echo")),
                PingAgent(name="bob", role=Role(name="ping"), context={"targets": ["alice"]}),
            ]),
            bus_factory=lambda: MessageBus(),
            steps=2,
        )

        assert isinstance(results, BatchResult)
        assert len(results.results) == 3

    @pytest.mark.asyncio
    async def test_batch_runner_statistics(self):
        """BatchRunner computes aggregate statistics."""
        from agent_sim.scenario.batch import BatchRunner

        runner = BatchRunner(runs=5)

        batch_result = await runner.run(
            sandbox_factory=lambda: Sandbox(agents=[
                EchoAgent(name="alice", role=Role(name="echo")),
                PingAgent(name="bob", role=Role(name="ping"), context={"targets": ["alice"]}),
            ]),
            bus_factory=lambda: MessageBus(),
            steps=3,
        )

        stats = batch_result.statistics
        assert "avg_messages" in stats
        assert "avg_duration" in stats
        assert "total_runs" in stats
        assert stats["total_runs"] == 5

    def test_batch_result_to_dict(self):
        """BatchResult can be serialized."""
        from agent_sim.scenario.batch import BatchResult, BatchRunner

        results = [
            RunResult(steps_completed=3, total_messages=5, duration=0.1),
            RunResult(steps_completed=3, total_messages=7, duration=0.12),
        ]
        batch = BatchResult(results=results)
        d = batch.to_dict()

        assert d["total_runs"] == 2
        assert "statistics" in d
        assert "runs" in d

    @pytest.mark.asyncio
    async def test_batch_runner_from_config(self):
        """BatchRunner can run from a ScenarioConfig."""
        from agent_sim.scenario.batch import BatchRunner

        config = ScenarioConfig(
            name="batch-test",
            steps=2,
            agents=[
                AgentConfig(name="a", type="echo"),
                AgentConfig(name="b", type="echo"),
            ],
        )
        runner = BatchRunner(runs=2)
        batch_result = await runner.run_from_config(config)

        assert len(batch_result.results) == 2


# ═══════════════════════════════════════════════
# 4. Scenario Inheritance Tests
# ═══════════════════════════════════════════════

class TestScenarioInheritance:
    """Test scenario inheritance/composition via extends."""

    def test_scenario_extends_base(self):
        """A scenario can extend a base scenario."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            base.write_text("""
name: base-scenario
description: base config
steps: 5
agents:
  - name: alice
    type: echo
  - name: bob
    type: echo
""")
            child = Path(tmpdir) / "child.yaml"
            child.write_text("""
extends: base.yaml
name: child-scenario
steps: 10
agents:
  - name: alice
    type: echo
  - name: bob
    type: echo
  - name: charlie
    type: ping
    context:
      targets: [alice]
""")

            from agent_sim.scenario.config import load_scenario
            config = load_scenario(str(child))

            assert config.name == "child-scenario"
            assert config.steps == 10
            assert len(config.agents) == 3

    def test_scenario_extends_inherits_agents(self):
        """Child scenario inherits agents from parent when not overridden."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            base.write_text("""
name: base
steps: 5
agents:
  - name: alice
    type: echo
    role: leader
""")
            child = Path(tmpdir) / "child.yaml"
            child.write_text("""
extends: base.yaml
name: child
agents:
  - name: alice
    type: echo
    role: leader
  - name: bob
    type: echo
""")

            from agent_sim.scenario.config import load_scenario
            config = load_scenario(str(child))
            assert len(config.agents) == 2

    def test_scenario_extends_override_steps(self):
        """Child can override parent's steps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir) / "base.yaml"
            base.write_text("""
name: base
steps: 5
agents:
  - name: a
    type: echo
""")
            child = Path(tmpdir) / "child.yaml"
            child.write_text("""
extends: base.yaml
steps: 20
agents:
  - name: a
    type: echo
""")

            from agent_sim.scenario.config import load_scenario
            config = load_scenario(str(child))
            assert config.steps == 20

    def test_scenario_extends_missing_base_raises(self):
        """Missing base file raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            child = Path(tmpdir) / "child.yaml"
            child.write_text("""
extends: nonexistent.yaml
name: child
steps: 5
agents:
  - name: a
    type: echo
""")

            from agent_sim.scenario.config import load_scenario
            with pytest.raises((FileNotFoundError, ValueError)):
                load_scenario(str(child))

    def test_scenario_no_extends_works_normally(self):
        """Scenario without extends field works as before."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "normal.yaml"
            f.write_text("""
name: normal
steps: 3
agents:
  - name: a
    type: echo
""")

            from agent_sim.scenario.config import load_scenario
            config = load_scenario(str(f))
            assert config.name == "normal"
            assert config.steps == 3


# ═══════════════════════════════════════════════
# 5. CLI Integration Tests
# ═══════════════════════════════════════════════

class TestCLINewCommands:
    """Test new CLI commands for v0.7.0."""

    def test_cli_batch_command_exists(self):
        """CLI has a batch command."""
        from click.testing import CliRunner
        from agent_sim.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["batch", "--help"])
        assert result.exit_code == 0
        assert "batch" in result.output.lower() or "批量" in result.output

    def test_cli_replay_command_exists(self):
        """CLI has a replay command."""
        from click.testing import CliRunner
        from agent_sim.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["replay", "--help"])
        assert result.exit_code == 0

    def test_cli_html_report_command(self):
        """CLI report command supports --format html."""
        from click.testing import CliRunner
        from agent_sim.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["export", "--help"])
        assert result.exit_code == 0

    def test_cli_batch_run(self):
        """CLI batch command runs multiple simulations."""
        from click.testing import CliRunner
        from agent_sim.cli import main

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
name: cli-batch-test
steps: 2
agents:
  - name: a
    type: echo
  - name: b
    type: echo
""")
            config_path = f.name

        runner = CliRunner()
        result = runner.invoke(main, ["batch", "--config", config_path, "--runs", "2"])
        assert result.exit_code == 0
        Path(config_path).unlink()


# ═══════════════════════════════════════════════
# Integration: Full Pipeline Test
# ═══════════════════════════════════════════════

class TestV070Integration:
    """Integration test for the full v0.7.0 pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_run_record_replay_report(self):
        """Full pipeline: run → record → replay → HTML report."""
        from agent_sim.scenario.replay import ReplayEngine
        from agent_sim.export import HTMLReport

        # 1. Setup
        a = EchoAgent(name="alice", role=Role(name="echo"))
        b = PingAgent(name="bob", role=Role(name="ping"), context={"targets": ["alice"]})
        sandbox = Sandbox(agents=[a, b])
        bus = MessageBus()
        bus.register(a)
        bus.register(b)

        # 2. Run with recorder
        recorder = EventRecorder()
        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        recorder.attach_to(runner.hooks)
        result = await runner.run(steps=3)

        # 3. Replay
        engine = ReplayEngine.from_recorder(recorder)
        assert engine.event_count > 0
        timeline = engine.timeline()
        assert len(timeline) > 0

        # 4. HTML Report
        report = HTMLReport(result, scenario_name="integration-test")
        html = report.render()
        assert "<!DOCTYPE html>" in html

        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
            report.save(f.name)
            assert Path(f.name).stat().st_size > 100
            Path(f.name).unlink()
