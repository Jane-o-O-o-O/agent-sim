"""Tests for v0.6.0 features: registry, EventRecorder, timeout, compare, scenarios."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.role import Role
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.scenario.config import AgentConfig, ScenarioConfig, load_scenario
from agent_sim.scenario.factory import (
    _AGENT_REGISTRY,
    build_scenario,
    get_registered_types,
    register_agent_type,
    unregister_agent_type,
)
from agent_sim.scenario.hooks import LifecycleHooks
from agent_sim.scenario.recorder import EventRecorder, EventType, SimulationEvent
from agent_sim.scenario.runner import RunResult, ScenarioRunner, SimulationTimeout


# ─── Agent Registry Tests ───────────────────────────────────────

class TestAgentRegistry:
    """测试 Agent 类型注册表。"""

    def test_builtin_types_registered(self):
        """内置类型应全部注册。"""
        types = get_registered_types()
        assert "echo" in types
        assert "ping" in types
        assert "llm" in types
        assert "memory" in types
        assert "tool" in types
        assert "debate" in types
        assert "collaborate" in types
        assert "custom" in types

    def test_register_custom_type(self):
        """应能注册自定义类型。"""
        class MyAgent(Agent):
            async def step(self):
                self.increment_step()
                return []

        register_agent_type("my_test_agent", lambda cfg: MyAgent(name=cfg.name))
        assert "my_test_agent" in get_registered_types()

        # 清理
        unregister_agent_type("my_test_agent")
        assert "my_test_agent" not in get_registered_types()

    def test_register_duplicate_raises(self):
        """注册已存在的类型应抛出 ValueError。"""
        with pytest.raises(ValueError, match="已注册"):
            register_agent_type("echo", lambda cfg: Agent(name=cfg.name))

    def test_unregister_nonexistent_raises(self):
        """注销不存在的类型应抛出 KeyError。"""
        with pytest.raises(KeyError, match="未注册"):
            unregister_agent_type("nonexistent_type_xyz")

    def test_build_memory_agent_from_config(self):
        """应能从配置创建 MemoryAgent。"""
        config = ScenarioConfig(
            name="memory-test",
            steps=1,
            agents=[
                AgentConfig(
                    name="memo",
                    type="memory",
                    llm_backend="echo",
                    context={"system_prompt": "You are helpful."},
                ),
            ],
        )
        sandbox, bus = build_scenario(config)
        assert len(sandbox.agents) == 1
        agent = sandbox.agents["memo"]
        assert hasattr(agent, "buffer")
        assert hasattr(agent, "facts")
        assert hasattr(agent, "memory_window")

    def test_build_all_builtin_types(self):
        """应能从配置构建所有内置类型。"""
        from agent_sim.agent.llm_agent import EchoLLMBackend
        types_to_test = ["echo", "ping", "debate", "collaborate"]
        for agent_type in types_to_test:
            config = ScenarioConfig(
                name=f"test-{agent_type}",
                steps=1,
                agents=[
                    AgentConfig(name="a", type=agent_type, context={}),
                ],
            )
            sandbox, bus = build_scenario(config)
            assert "a" in sandbox.agents

    def test_unsupported_type_raises(self):
        """不支持的类型应抛出 ValidationError。"""
        with pytest.raises(Exception, match="不支持的 Agent 类型"):
            ScenarioConfig(
                name="bad",
                steps=1,
                agents=[AgentConfig(name="a", type="nonexistent_xyz")],
            )


# ─── Config Validator Tests ─────────────────────────────────────

class TestConfigValidator:
    """测试配置验证器。"""

    def test_memory_type_valid(self):
        """memory 类型应被接受。"""
        config = AgentConfig(name="m", type="memory")
        assert config.type == "memory"

    def test_invalid_type_raises(self):
        """无效类型应抛出 ValueError。"""
        with pytest.raises(ValueError, match="不支持"):
            AgentConfig(name="x", type="invalid_type")


# ─── EventRecorder Tests ────────────────────────────────────────

class TestEventRecorder:
    """测试事件记录器。"""

    def test_record_event(self):
        """应能记录事件。"""
        recorder = EventRecorder()
        event = recorder.record(EventType.STEP_START, step=1)
        assert recorder.event_count == 1
        assert event.event_type == "step_start"
        assert event.step == 1

    def test_record_with_data(self):
        """事件应包含数据。"""
        recorder = EventRecorder()
        recorder.record(EventType.MESSAGE, step=2, sender="a", receiver="b")
        events = recorder.get_events()
        assert len(events) == 1
        assert events[0].data["sender"] == "a"
        assert events[0].data["receiver"] == "b"

    def test_filter_by_type(self):
        """应能按类型过滤事件。"""
        recorder = EventRecorder()
        recorder.record(EventType.STEP_START, step=1)
        recorder.record(EventType.MESSAGE, step=1, sender="a")
        recorder.record(EventType.STEP_END, step=1)
        recorder.record(EventType.MESSAGE, step=2, sender="b")

        messages = recorder.get_events(event_type=EventType.MESSAGE)
        assert len(messages) == 2

    def test_filter_by_step(self):
        """应能按步数过滤事件。"""
        recorder = EventRecorder()
        recorder.record(EventType.STEP_START, step=1)
        recorder.record(EventType.STEP_START, step=2)
        recorder.record(EventType.STEP_START, step=1)

        step1 = recorder.get_events(step=1)
        assert len(step1) == 2

    def test_summary(self):
        """应能生成事件摘要。"""
        recorder = EventRecorder()
        recorder.record(EventType.STEP_START, step=1)
        recorder.record(EventType.MESSAGE, step=1)
        recorder.record(EventType.STEP_END, step=1)

        summary = recorder.summary()
        assert summary["total_events"] == 3
        assert summary["event_counts"]["step_start"] == 1
        assert summary["event_counts"]["message"] == 1

    def test_clear(self):
        """应能清除所有事件。"""
        recorder = EventRecorder()
        recorder.record(EventType.STEP_START, step=1)
        recorder.record(EventType.MESSAGE, step=1)
        assert recorder.event_count == 2
        recorder.clear()
        assert recorder.event_count == 0

    def test_export_json(self):
        """应能导出为 JSON。"""
        recorder = EventRecorder()
        recorder.record(EventType.SIM_START, steps=5, agent_count=3)
        recorder.record(EventType.STEP_START, step=1)
        recorder.record(EventType.SIM_END, duration=1.5)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        result = recorder.export_json(path)
        assert result.exists()

        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["summary"]["total_events"] == 3
        assert len(data["events"]) == 3
        path.unlink()

    def test_export_csv(self):
        """应能导出为 CSV。"""
        recorder = EventRecorder()
        recorder.record(EventType.STEP_START, step=1)
        recorder.record(EventType.MESSAGE, step=1, sender="a")

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = Path(f.name)

        result = recorder.export_csv(path)
        assert result.exists()

        content = path.read_text(encoding="utf-8")
        assert "timestamp" in content
        assert "step_start" in content
        path.unlink()

    def test_attach_to_hooks(self):
        """应能绑定到 LifecycleHooks。"""
        recorder = EventRecorder()
        hooks = LifecycleHooks()
        recorder.attach_to(hooks)

        # 触发事件
        asyncio.run(hooks.trigger("on_simulation_start", steps=5, agent_count=3))
        asyncio.run(hooks.trigger("on_step_start", step=1))
        asyncio.run(hooks.trigger("on_step_end", step=1, messages_sent=3))
        asyncio.run(hooks.trigger("on_message", message=None, step=1))

        assert recorder.event_count == 4
        sim_start = recorder.get_events(event_type=EventType.SIM_START)
        assert len(sim_start) == 1
        assert sim_start[0].data["steps"] == 5

    def test_simulation_event_time_iso(self):
        """SimulationEvent.time_iso 应返回 ISO 格式。"""
        event = SimulationEvent(event_type="test", timestamp=1000000.0)
        iso = event.time_iso
        assert "T" in iso  # ISO format contains T

    def test_str_repr(self):
        """__str__ 应返回可读字符串。"""
        recorder = EventRecorder()
        recorder.record(EventType.STEP_START, step=1)
        assert "EventRecorder" in str(recorder)
        assert "1" in str(recorder)


# ─── ScenarioRunner Timeout Tests ──────────────────────────────

class TestScenarioTimeout:
    """测试仿真超时保护。"""

    @pytest.mark.asyncio
    async def test_no_timeout(self):
        """无超时设置应正常运行。"""
        class FastAgent(Agent):
            async def step(self):
                self.increment_step()
                return []

        sandbox = Sandbox(agents=[FastAgent(name="a")])
        bus = MessageBus()
        bus.register(sandbox.agents["a"])

        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=3)
        assert result.steps_completed == 3
        assert result.timed_out is False

    @pytest.mark.asyncio
    async def test_timeout_triggers(self):
        """超时应提前终止仿真。"""
        class SlowAgent(Agent):
            async def step(self):
                await asyncio.sleep(0.2)
                self.increment_step()
                return []

        sandbox = Sandbox(agents=[SlowAgent(name="a")])
        bus = MessageBus()
        bus.register(sandbox.agents["a"])

        runner = ScenarioRunner(sandbox=sandbox, bus=bus, timeout_seconds=0.3)
        result = await runner.run(steps=100)
        assert result.timed_out is True
        assert result.steps_completed < 100
        assert result.duration < 1.0  # Should be well under 1s

    @pytest.mark.asyncio
    async def test_timeout_preserves_partial_results(self):
        """超时应保留已完成的部分结果。"""
        call_count = 0

        class CountingAgent(Agent):
            async def step(self):
                nonlocal call_count
                call_count += 1
                await asyncio.sleep(0.05)
                self.increment_step()
                return []

        sandbox = Sandbox(agents=[CountingAgent(name="a")])
        bus = MessageBus()
        bus.register(sandbox.agents["a"])

        runner = ScenarioRunner(sandbox=sandbox, bus=bus, timeout_seconds=0.3)
        result = await runner.run(steps=1000)
        assert result.timed_out is True
        assert result.steps_completed > 0  # At least some steps completed

    @pytest.mark.asyncio
    async def test_timeout_zero_means_no_timeout(self):
        """timeout=0 表示无超时。"""
        class FastAgent(Agent):
            async def step(self):
                self.increment_step()
                return []

        sandbox = Sandbox(agents=[FastAgent(name="a")])
        bus = MessageBus()
        bus.register(sandbox.agents["a"])

        runner = ScenarioRunner(sandbox=sandbox, bus=bus, timeout_seconds=0)
        result = await runner.run(steps=5)
        assert result.steps_completed == 5
        assert result.timed_out is False


# ─── YAML Scenario Tests ────────────────────────────────────────

class TestBuiltInScenarios:
    """测试内置 YAML 场景。"""

    def test_ping_pong_scenario(self):
        """ping_pong.yaml 应能加载和运行。"""
        config = load_scenario("scenarios/ping_pong.yaml")
        assert config.name == "ping-pong"
        assert len(config.agents) == 2
        assert config.steps == 5

        sandbox, bus = build_scenario(config)
        assert len(sandbox.agents) == 2
        result = asyncio.run(ScenarioRunner(sandbox=sandbox, bus=bus).run(steps=config.steps))
        assert result.steps_completed == 5
        assert result.total_messages > 0

    def test_debate_scenario(self):
        """debate.yaml 应能加载和运行。"""
        config = load_scenario("scenarios/debate.yaml")
        assert config.name == "debate"
        assert len(config.agents) == 2

        sandbox, bus = build_scenario(config)
        result = asyncio.run(ScenarioRunner(sandbox=sandbox, bus=bus).run(steps=config.steps))
        assert result.steps_completed == 3
        assert result.total_messages > 0

    def test_team_collaborate_scenario(self):
        """team_collaborate.yaml 应能加载和运行。"""
        config = load_scenario("scenarios/team_collaborate.yaml")
        assert config.name == "team-collaborate"
        assert len(config.agents) == 4

        sandbox, bus = build_scenario(config)
        result = asyncio.run(ScenarioRunner(sandbox=sandbox, bus=bus).run(steps=config.steps))
        assert result.steps_completed == 4

    def test_all_scenarios_load(self):
        """所有场景文件应能加载。"""
        for path in [
            "scenarios/ping_pong.yaml",
            "scenarios/debate.yaml",
            "scenarios/team_collaborate.yaml",
        ]:
            config = load_scenario(path)
            assert config.name


# ─── Integration: EventRecorder + Runner ────────────────────────

class TestEventRecorderIntegration:
    """测试 EventRecorder 与 ScenarioRunner 的集成。"""

    @pytest.mark.asyncio
    async def test_recorder_captures_full_lifecycle(self):
        """记录器应捕获完整仿真生命周期。"""
        class EchoAgent(Agent):
            async def step(self):
                replies = []
                for msg in self.inbox:
                    replies.append(Message(
                        sender=self.name, receiver=msg.sender,
                        content=f"echo:{msg.content}",
                    ))
                self.inbox.clear()
                self.increment_step()
                return replies

        sandbox = Sandbox(agents=[
            EchoAgent(name="a", context={}),
            EchoAgent(name="b", context={}),
        ])
        bus = MessageBus()
        bus.register(sandbox.agents["a"])
        bus.register(sandbox.agents["b"])

        # Send initial message
        bus.send(Message(sender="a", receiver="b", content="hello"))

        hooks = LifecycleHooks()
        recorder = EventRecorder()
        recorder.attach_to(hooks)

        runner = ScenarioRunner(sandbox=sandbox, bus=bus, hooks=hooks)
        result = await runner.run(steps=3)

        assert result.steps_completed == 3

        # Verify recorder captured events
        assert recorder.event_count > 0

        sim_starts = recorder.get_events(event_type=EventType.SIM_START)
        assert len(sim_starts) == 1
        assert sim_starts[0].data["steps"] == 3

        sim_ends = recorder.get_events(event_type=EventType.SIM_END)
        assert len(sim_ends) == 1

        step_starts = recorder.get_events(event_type=EventType.STEP_START)
        assert len(step_starts) == 3

        step_ends = recorder.get_events(event_type=EventType.STEP_END)
        assert len(step_ends) == 3

    @pytest.mark.asyncio
    async def test_recorder_captures_agent_errors(self):
        """记录器应捕获 Agent 错误。"""
        class BadAgent(Agent):
            async def step(self):
                raise RuntimeError("boom")

        sandbox = Sandbox(agents=[BadAgent(name="bad")])
        bus = MessageBus()
        bus.register(sandbox.agents["bad"])

        hooks = LifecycleHooks()
        recorder = EventRecorder()
        recorder.attach_to(hooks)

        runner = ScenarioRunner(sandbox=sandbox, bus=bus, hooks=hooks)
        result = await runner.run(steps=1)

        errors = recorder.get_events(event_type=EventType.AGENT_ERROR)
        assert len(errors) == 1
        assert errors[0].data["agent"] == "bad"
        assert "boom" in errors[0].data["error"]


# ─── RunResult Tests ─────────────────────────────────────────────

class TestRunResultTimedOut:
    """测试 RunResult.timed_out 字段。"""

    @pytest.mark.asyncio
    async def test_normal_run_not_timed_out(self):
        """正常运行 timed_out 应为 False。"""
        class SimpleAgent(Agent):
            async def step(self):
                self.increment_step()
                return []

        sandbox = Sandbox(agents=[SimpleAgent(name="a")])
        bus = MessageBus()
        bus.register(sandbox.agents["a"])
        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=1)
        assert result.timed_out is False
