"""Integration tests — end-to-end scenario execution."""
import json
import textwrap
from pathlib import Path

import pytest
import yaml

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.llm_agent import EchoLLMBackend, LLMAgent
from agent_sim.agent.role import Role
from agent_sim.agent.tool_agent import ToolAgent
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.scenario.config import ScenarioConfig, AgentConfig, load_scenario
from agent_sim.scenario.factory import build_scenario, EchoAgent, PingAgent
from agent_sim.scenario.runner import ScenarioRunner


class TestScenarioFactory:
    """Test scenario factory — building from config."""

    def test_build_echo_agent(self) -> None:
        """从配置创建 EchoAgent。"""
        config = ScenarioConfig(
            agents=[AgentConfig(name="a", type="echo")],
        )
        sandbox, bus = build_scenario(config)
        assert sandbox.agent_count == 1
        assert bus.has_agent("a")

    def test_build_ping_agent(self) -> None:
        """从配置创建 PingAgent。"""
        config = ScenarioConfig(
            agents=[
                AgentConfig(
                    name="pinger",
                    type="ping",
                    context={"targets": ["echoer"]},
                ),
                AgentConfig(name="echoer", type="echo"),
            ],
        )
        sandbox, bus = build_scenario(config)
        assert sandbox.agent_count == 2

    def test_build_llm_agent(self) -> None:
        """从配置创建 LLMAgent。"""
        config = ScenarioConfig(
            agents=[AgentConfig(name="llm", type="llm", context={"system_prompt": "Hi"})],
        )
        sandbox, bus = build_scenario(config)
        agent = sandbox.get_agent("llm")
        assert isinstance(agent, LLMAgent)

    def test_build_tool_agent(self) -> None:
        """从配置创建 ToolAgent。"""
        config = ScenarioConfig(
            agents=[AgentConfig(name="tool", type="tool")],
        )
        sandbox, bus = build_scenario(config)
        agent = sandbox.get_agent("tool")
        assert isinstance(agent, ToolAgent)

    def test_build_with_connections(self) -> None:
        """带连接配置构建场景。"""
        from agent_sim.scenario.config import ConnectionConfig
        config = ScenarioConfig(
            agents=[
                AgentConfig(name="a", type="echo"),
                AgentConfig(name="b", type="echo"),
            ],
            connections=[
                ConnectionConfig(from_agent="a", to_agent="b", topic="hello"),
            ],
        )
        sandbox, bus = build_scenario(config)
        assert bus.message_count == 1
        agent_b = sandbox.get_agent("b")
        assert len(agent_b.inbox) == 1


class TestEndToEnd:
    """End-to-end integration tests."""

    @pytest.mark.asyncio
    async def test_ping_pong_scenario(self) -> None:
        """完整 Ping-Pong 场景。"""
        config = ScenarioConfig(
            name="ping-pong",
            steps=3,
            agents=[
                AgentConfig(
                    name="pinger",
                    type="ping",
                    context={"targets": ["echoer"]},
                ),
                AgentConfig(name="echoer", type="echo"),
            ],
        )
        sandbox, bus = build_scenario(config)
        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=3)

        assert result.steps_completed == 3
        assert result.total_messages >= 2
        assert result.duration >= 0

    @pytest.mark.asyncio
    async def test_llm_agent_communication(self) -> None:
        """LLM Agent 通信。"""
        config = ScenarioConfig(
            name="llm-test",
            steps=2,
            agents=[
                AgentConfig(name="asker", type="echo"),
                AgentConfig(name="assistant", type="llm"),
            ],
        )
        sandbox, bus = build_scenario(config)

        # 手动发消息给 LLM agent
        bus.send(Message(sender="asker", receiver="assistant", content="What is AI?"))

        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=2)

        assert result.steps_completed == 2

    @pytest.mark.asyncio
    async def test_tool_agent_scenario(self) -> None:
        """ToolAgent 完整场景。"""
        sandbox = Sandbox()
        bus = MessageBus()

        tool_agent = ToolAgent(name="calculator")
        tool_agent.register_tool("add", "两数相加", lambda a, b: a + b)
        sandbox.add_agent(tool_agent)
        bus.register(tool_agent)

        echo = EchoAgent(name="requester")
        sandbox.add_agent(echo)
        bus.register(echo)

        # 发送工具调用请求
        bus.send(Message(
            sender="requester",
            receiver="calculator",
            content={"tool": "add", "args": {"a": 10, "b": 20}},
        ))

        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=2)

        assert result.steps_completed == 2
        assert result.total_messages >= 1

    @pytest.mark.asyncio
    async def test_multi_agent_broadcast(self) -> None:
        """多 Agent 广播场景。"""
        config = ScenarioConfig(
            name="broadcast-test",
            steps=2,
            agents=[
                AgentConfig(name="sender", type="echo"),
                AgentConfig(name="r1", type="echo"),
                AgentConfig(name="r2", type="echo"),
                AgentConfig(name="r3", type="echo"),
            ],
        )
        sandbox, bus = build_scenario(config)

        # 广播消息
        bus.send(Message(
            sender="sender",
            content="announcement",
            msg_type=MessageType.BROADCAST,
        ))

        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=1)

        # 3 个接收者应收到消息
        for name in ["r1", "r2", "r3"]:
            agent = sandbox.get_agent(name)
            # After step, inbox should be cleared, but the echo reply should exist
            assert result.total_messages >= 3

    @pytest.mark.asyncio
    async def test_load_and_run_yaml(self, tmp_path: Path) -> None:
        """从 YAML 加载并运行完整流程。"""
        yaml_content = textwrap.dedent("""\
            name: integration-test
            description: 集成测试场景
            steps: 3
            agents:
              - name: leader
                type: ping
                context:
                  targets: ["worker_1", "worker_2"]
              - name: worker_1
                type: echo
              - name: worker_2
                type: echo
        """)
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_scenario(config_file)
        sandbox, bus = build_scenario(config)
        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=config.steps)

        assert result.steps_completed == 3
        assert result.total_messages >= 2

    @pytest.mark.asyncio
    async def test_agent_failure_isolation(self) -> None:
        """Agent 失败不影响其他 Agent。"""

        class FailingAgent(Agent):
            async def step(self):
                raise RuntimeError("I fail")

        sandbox = Sandbox()
        bus = MessageBus()

        fail = FailingAgent(name="fail")
        ok = EchoAgent(name="ok")
        sandbox.add_agent(fail)
        sandbox.add_agent(ok)
        bus.register(fail)
        bus.register(ok)

        # 发消息给两个 agent
        bus.send(Message(sender="fail", receiver="ok", content="hi"))
        bus.send(Message(sender="ok", receiver="fail", content="hi"))

        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=2)

        assert result.steps_completed == 2
        assert result.agent_states["fail"] == AgentState.FAILED.value
        assert result.agent_states["ok"] == AgentState.COMPLETED.value

    @pytest.mark.asyncio
    async def test_full_metrics_collection(self) -> None:
        """完整指标收集。"""
        config = ScenarioConfig(
            name="metrics-test",
            steps=5,
            agents=[
                AgentConfig(name="pinger", type="ping", context={"targets": ["echo"]}),
                AgentConfig(name="echo", type="echo"),
            ],
        )
        sandbox, bus = build_scenario(config)
        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=5)

        assert result.metrics["total_steps"] == 5
        assert result.metrics["total_messages"] > 0
        assert "agent_states" in result.metrics
        assert result.metrics["avg_messages_per_step"] > 0

