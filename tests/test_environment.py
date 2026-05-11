"""Tests for Sandbox environment."""
import pytest

from agent_sim.agent.base import Agent
from agent_sim.environment.sandbox import Sandbox
from agent_sim.environment.state import EnvironmentState


class TestEnvironmentState:
    """Test environment state management."""

    def test_create_state(self) -> None:
        """创建空环境状态。"""
        state = EnvironmentState()
        assert state.step == 0
        assert state.data == {}

    def test_state_get_set(self) -> None:
        """状态读写。"""
        state = EnvironmentState()
        state.set("temperature", 25.0)
        assert state.get("temperature") == 25.0

    def test_state_get_default(self) -> None:
        """获取不存在的键返回默认值。"""
        state = EnvironmentState()
        assert state.get("missing") is None
        assert state.get("missing", 42) == 42

    def test_state_snapshot(self) -> None:
        """状态快照。"""
        state = EnvironmentState()
        state.set("x", 10)
        snap = state.snapshot()
        assert snap == {"x": 10}
        # 修改原状态不影响快照
        state.set("x", 20)
        assert snap["x"] == 10

    def test_state_events(self) -> None:
        """记录环境事件。"""
        state = EnvironmentState()
        state.add_event("agent_spawned", {"name": "a"})
        state.add_event("task_completed", {"task": "analysis"})
        assert len(state.events) == 2
        assert state.events[0]["type"] == "agent_spawned"

    def test_state_str(self) -> None:
        """状态字符串表示。"""
        state = EnvironmentState()
        s = str(state)
        assert "EnvironmentState" in s


class TestSandbox:
    """Test Sandbox simulation environment."""

    def test_create_sandbox(self) -> None:
        """创建空沙箱。"""
        sandbox = Sandbox()
        assert sandbox.agent_count == 0
        assert sandbox.current_step == 0

    def test_create_sandbox_with_agents(self) -> None:
        """带 Agent 列表创建沙箱。"""
        agents = [Agent(name="a"), Agent(name="b")]
        sandbox = Sandbox(agents=agents)
        assert sandbox.agent_count == 2

    def test_add_agent(self) -> None:
        """动态添加 Agent。"""
        sandbox = Sandbox()
        sandbox.add_agent(Agent(name="a"))
        assert sandbox.agent_count == 1

    def test_add_duplicate_agent_raises(self) -> None:
        """添加重名 Agent 抛出异常。"""
        sandbox = Sandbox()
        sandbox.add_agent(Agent(name="a"))
        with pytest.raises(ValueError):
            sandbox.add_agent(Agent(name="a"))

    def test_get_agent(self) -> None:
        """获取 Agent。"""
        sandbox = Sandbox(agents=[Agent(name="a")])
        agent = sandbox.get_agent("a")
        assert agent.name == "a"

    def test_get_nonexistent_agent(self) -> None:
        """获取不存在的 Agent 返回 None。"""
        sandbox = Sandbox()
        assert sandbox.get_agent("ghost") is None

    def test_remove_agent(self) -> None:
        """移除 Agent。"""
        sandbox = Sandbox(agents=[Agent(name="a")])
        sandbox.remove_agent("a")
        assert sandbox.agent_count == 0

    def test_remove_nonexistent_raises(self) -> None:
        """移除不存在的 Agent 抛出异常。"""
        sandbox = Sandbox()
        with pytest.raises(KeyError):
            sandbox.remove_agent("ghost")

    def test_sandbox_state(self) -> None:
        """沙箱环境状态。"""
        sandbox = Sandbox()
        assert isinstance(sandbox.state, EnvironmentState)
        sandbox.state.set("weather", "sunny")
        assert sandbox.state.get("weather") == "sunny"

    def test_sandbox_advance_step(self) -> None:
        """推进仿真步数。"""
        sandbox = Sandbox()
        assert sandbox.current_step == 0
        sandbox.advance()
        assert sandbox.current_step == 1
        sandbox.advance()
        assert sandbox.current_step == 2

    def test_sandbox_agents_dict(self) -> None:
        """获取所有 Agent 字典。"""
        sandbox = Sandbox(agents=[Agent(name="a"), Agent(name="b")])
        agents = sandbox.agents
        assert len(agents) == 2
        assert "a" in agents
        assert "b" in agents

    def test_sandbox_str(self) -> None:
        """沙箱字符串表示。"""
        sandbox = Sandbox(agents=[Agent(name="a")])
        s = str(sandbox)
        assert "Sandbox" in s
        assert "1" in s
