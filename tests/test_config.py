"""Tests for ScenarioConfig and YAML loading."""
import json
import textwrap
from pathlib import Path

import pytest
import yaml

from agent_sim.scenario.config import (
    AgentConfig,
    ConnectionConfig,
    ScenarioConfig,
    load_scenario,
)


class TestAgentConfig:
    """Test AgentConfig model."""

    def test_create_agent_config(self) -> None:
        """创建基本 Agent 配置。"""
        config = AgentConfig(name="test_agent")
        assert config.name == "test_agent"
        assert config.type == "echo"
        assert config.role == "default"
        assert config.goals == []

    def test_agent_config_with_type(self) -> None:
        """指定 Agent 类型。"""
        config = AgentConfig(name="llm_agent", type="llm")
        assert config.type == "llm"

    def test_agent_config_with_context(self) -> None:
        """Agent 配置带上下文。"""
        config = AgentConfig(name="a", context={"key": "value"})
        assert config.context == {"key": "value"}

    def test_agent_config_empty_name_raises(self) -> None:
        """空名称抛出异常。"""
        with pytest.raises(ValueError, match="名称不能为空"):
            AgentConfig(name="")

    def test_agent_config_whitespace_name_raises(self) -> None:
        """空白名称抛出异常。"""
        with pytest.raises(ValueError, match="名称不能为空"):
            AgentConfig(name="   ")

    def test_agent_config_invalid_type_raises(self) -> None:
        """无效类型抛出异常。"""
        with pytest.raises(ValueError, match="不支持的 Agent 类型"):
            AgentConfig(name="a", type="invalid_type")

    def test_valid_types(self) -> None:
        """所有有效类型。"""
        for t in ["echo", "ping", "llm", "tool", "custom"]:
            config = AgentConfig(name=f"agent_{t}", type=t)
            assert config.type == t

    def test_agent_config_custom_fields(self) -> None:
        """自定义 Agent 字段。"""
        config = AgentConfig(
            name="custom",
            type="custom",
            module="my_module",
            class_name="MyAgent",
        )
        assert config.module == "my_module"
        assert config.class_name == "MyAgent"

    def test_agent_config_llm_fields(self) -> None:
        """LLM Agent 字段。"""
        config = AgentConfig(
            name="llm",
            type="llm",
            llm_backend="openai",
            llm_model="gpt-4",
        )
        assert config.llm_backend == "openai"
        assert config.llm_model == "gpt-4"


class TestConnectionConfig:
    """Test ConnectionConfig model."""

    def test_create_connection(self) -> None:
        """创建连接配置。"""
        conn = ConnectionConfig(from_agent="a", to_agent="b")
        assert conn.from_agent == "a"
        assert conn.to_agent == "b"
        assert conn.topic is None

    def test_connection_with_topic(self) -> None:
        """带主题的连接。"""
        conn = ConnectionConfig(from_agent="a", to_agent="b", topic="task")
        assert conn.topic == "task"

    def test_broadcast_connection(self) -> None:
        """广播连接（无 to_agent）。"""
        conn = ConnectionConfig(from_agent="a")
        assert conn.to_agent is None


class TestScenarioConfig:
    """Test ScenarioConfig model."""

    def test_create_empty_config(self) -> None:
        """创建空场景配置。"""
        config = ScenarioConfig()
        assert config.name == "unnamed"
        assert config.steps == 10
        assert config.agents == []

    def test_create_config_with_agents(self) -> None:
        """带 Agent 的场景配置。"""
        config = ScenarioConfig(
            name="test",
            agents=[
                AgentConfig(name="a", type="echo"),
                AgentConfig(name="b", type="ping"),
            ],
        )
        assert len(config.agents) == 2
        assert config.agent_names == ["a", "b"]

    def test_duplicate_agent_names_raises(self) -> None:
        """重复 Agent 名称抛出异常。"""
        with pytest.raises(ValueError, match="名称重复"):
            ScenarioConfig(
                agents=[
                    AgentConfig(name="a"),
                    AgentConfig(name="a"),
                ],
            )

    def test_config_steps_validation(self) -> None:
        """步数验证。"""
        with pytest.raises(ValueError):
            ScenarioConfig(steps=0)

        with pytest.raises(ValueError):
            ScenarioConfig(steps=10001)

        config = ScenarioConfig(steps=100)
        assert config.steps == 100

    def test_config_with_connections(self) -> None:
        """带连接的配置。"""
        config = ScenarioConfig(
            connections=[
                ConnectionConfig(from_agent="a", to_agent="b"),
            ],
        )
        assert len(config.connections) == 1

    def test_config_with_metadata(self) -> None:
        """带元数据的配置。"""
        config = ScenarioConfig(metadata={"version": "1.0"})
        assert config.metadata == {"version": "1.0"}

    def test_agent_names_property(self) -> None:
        """agent_names 属性。"""
        config = ScenarioConfig(
            agents=[
                AgentConfig(name="x"),
                AgentConfig(name="y"),
                AgentConfig(name="z"),
            ],
        )
        assert config.agent_names == ["x", "y", "z"]


class TestLoadScenario:
    """Test YAML scenario loading."""

    def test_load_valid_yaml(self, tmp_path: Path) -> None:
        """加载有效的 YAML 文件。"""
        yaml_content = textwrap.dedent("""\
            name: test-scenario
            description: 测试场景
            steps: 5
            agents:
              - name: agent_a
                type: echo
                role: worker
                goals: ["执行任务"]
              - name: agent_b
                type: ping
                context:
                  targets: ["agent_a"]
        """)
        config_file = tmp_path / "test.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_scenario(config_file)
        assert config.name == "test-scenario"
        assert config.description == "测试场景"
        assert config.steps == 5
        assert len(config.agents) == 2
        assert config.agents[0].name == "agent_a"
        assert config.agents[0].type == "echo"
        assert config.agents[1].context == {"targets": ["agent_a"]}

    def test_load_nonexistent_file_raises(self) -> None:
        """文件不存在抛出异常。"""
        with pytest.raises(FileNotFoundError, match="不存在"):
            load_scenario("/nonexistent/path.yaml")

    def test_load_invalid_yaml_raises(self, tmp_path: Path) -> None:
        """无效 YAML 抛出异常。"""
        config_file = tmp_path / "bad.yaml"
        config_file.write_text("not: [valid: yaml: {{", encoding="utf-8")

        with pytest.raises(ValueError):
            load_scenario(config_file)

    def test_load_non_dict_yaml_raises(self, tmp_path: Path) -> None:
        """非字典 YAML 抛出异常。"""
        config_file = tmp_path / "list.yaml"
        config_file.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(ValueError, match="顶层应为字典"):
            load_scenario(config_file)

    def test_load_minimal_yaml(self, tmp_path: Path) -> None:
        """最小配置 YAML。"""
        config_file = tmp_path / "minimal.yaml"
        config_file.write_text("name: minimal\n", encoding="utf-8")

        config = load_scenario(config_file)
        assert config.name == "minimal"
        assert config.steps == 10  # default

    def test_load_yaml_with_connections(self, tmp_path: Path) -> None:
        """带连接的 YAML。"""
        yaml_content = textwrap.dedent("""\
            name: connected
            agents:
              - name: a
              - name: b
            connections:
              - from_agent: a
                to_agent: b
                topic: hello
        """)
        config_file = tmp_path / "conn.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_scenario(config_file)
        assert len(config.connections) == 1
        assert config.connections[0].from_agent == "a"
        assert config.connections[0].topic == "hello"
