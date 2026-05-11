"""Tests for ScenarioRunner and metrics."""
import asyncio

import pytest

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.role import Role
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.metrics.collector import MetricsCollector
from agent_sim.scenario.runner import ScenarioRunner, RunResult


class PingAgent(Agent):
    """Ping Agent：发送 ping，收到 ping 回复 pong。"""

    async def step(self) -> list[Message]:
        replies = []
        for msg in self.inbox:
            if msg.content == "ping":
                replies.append(Message(
                    sender=self.name,
                    receiver=msg.sender,
                    content="pong",
                    msg_type=MessageType.RESPONSE,
                ))
        self.inbox.clear()

        # 第一步主动发 ping
        if self.step_count == 0:
            for target in self.context.get("targets", []):
                replies.append(Message(
                    sender=self.name,
                    receiver=target,
                    content="ping",
                    msg_type=MessageType.REQUEST,
                ))
        self.increment_step()
        return replies


class EchoAgent(Agent):
    """Echo Agent：回显收到的消息。"""

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


class TestScenarioRunner:
    """Test ScenarioRunner execution."""

    def test_create_runner(self) -> None:
        """创建场景运行器。"""
        sandbox = Sandbox()
        bus = MessageBus()
        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        assert runner.max_steps == 10

    def test_create_runner_custom_steps(self) -> None:
        """自定义最大步数。"""
        runner = ScenarioRunner(sandbox=Sandbox(), bus=MessageBus(), max_steps=5)
        assert runner.max_steps == 5

    @pytest.mark.asyncio
    async def test_run_empty_sandbox(self) -> None:
        """空沙箱运行。"""
        runner = ScenarioRunner(sandbox=Sandbox(), bus=MessageBus())
        result = await runner.run(steps=3)
        assert isinstance(result, RunResult)
        assert result.steps_completed == 3

    @pytest.mark.asyncio
    async def test_run_with_agents(self) -> None:
        """带 Agent 运行仿真。"""
        a = PingAgent(name="ping", context={"targets": ["echo"]})
        b = EchoAgent(name="echo")
        sandbox = Sandbox(agents=[a, b])
        bus = MessageBus()
        bus.register(a)
        bus.register(b)

        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=3)

        assert result.steps_completed == 3
        assert result.total_messages > 0

    @pytest.mark.asyncio
    async def test_run_agents_communicate(self) -> None:
        """Agent 间通信测试。"""
        a = PingAgent(name="ping", context={"targets": ["echo"]})
        b = EchoAgent(name="echo")
        sandbox = Sandbox(agents=[a, b])
        bus = MessageBus()
        bus.register(a)
        bus.register(b)

        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=2)

        # ping 发了 ping，echo 回了 echo:pong
        assert result.total_messages >= 2
        # 两个 Agent 都执行了 step
        assert a.step_count == 2
        assert b.step_count == 2

    @pytest.mark.asyncio
    async def test_run_result_fields(self) -> None:
        """运行结果字段。"""
        runner = ScenarioRunner(sandbox=Sandbox(), bus=MessageBus())
        result = await runner.run(steps=1)
        assert hasattr(result, "steps_completed")
        assert hasattr(result, "total_messages")
        assert hasattr(result, "agent_states")
        assert hasattr(result, "duration")

    @pytest.mark.asyncio
    async def test_run_agents_set_to_running(self) -> None:
        """运行期间 Agent 状态变为 RUNNING。"""
        agent = Agent(name="a")
        sandbox = Sandbox(agents=[agent])
        bus = MessageBus()
        bus.register(agent)

        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=1)
        # 运行完成后应恢复
        assert result.agent_states["a"] == AgentState.COMPLETED.value

    @pytest.mark.asyncio
    async def test_run_agent_failure_handling(self) -> None:
        """Agent 异常处理。"""

        class FailAgent(Agent):
            async def step(self):
                raise RuntimeError("boom")

        agent = FailAgent(name="fail_agent")
        sandbox = Sandbox(agents=[agent])
        bus = MessageBus()
        bus.register(agent)

        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=2)

        # Agent 失败但不崩溃
        assert result.steps_completed == 2
        assert result.agent_states["fail_agent"] == AgentState.FAILED.value


class TestMetricsCollector:
    """Test MetricsCollector."""

    def test_create_collector(self) -> None:
        """创建指标收集器。"""
        collector = MetricsCollector()
        assert collector.step_count == 0

    def test_record_step(self) -> None:
        """记录步骤指标。"""
        collector = MetricsCollector()
        collector.record_step(messages_sent=3, agents_active=2)
        collector.record_step(messages_sent=5, agents_active=2)
        assert collector.step_count == 2
        assert collector.total_messages == 8

    def test_record_agent_state(self) -> None:
        """记录 Agent 状态。"""
        collector = MetricsCollector()
        collector.record_agent_state("a", "completed")
        collector.record_agent_state("b", "failed")
        assert collector.agent_states["a"] == "completed"
        assert collector.agent_states["b"] == "failed"

    def test_summary(self) -> None:
        """生成摘要。"""
        collector = MetricsCollector()
        collector.record_step(messages_sent=10, agents_active=3)
        collector.record_agent_state("a", "completed")
        summary = collector.summary()
        assert summary["total_steps"] == 1
        assert summary["total_messages"] == 10
        assert summary["agent_states"]["a"] == "completed"

    def test_collector_str(self) -> None:
        """收集器字符串表示。"""
        collector = MetricsCollector()
        s = str(collector)
        assert "MetricsCollector" in s
