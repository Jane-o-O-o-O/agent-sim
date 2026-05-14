"""Tests for v1.0.0 features: validation, CLI doctor/schema, exceptions."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from agent_sim.exceptions import (
    AgentAlreadyExistsError,
    AgentError,
    AgentNotFoundError,
    AgentNotRegisteredError,
    AgentSimError,
    AgentTypeError,
    CommunicationError,
    ConfigError,
    ConfigValidationError,
    LLMError,
    ProtocolError,
    SandboxError,
    ScenarioFileNotFoundError,
    SimulationError,
    SimulationTimeout,
    TemplateError,
    TopologyError,
)


# ── Exception Hierarchy Tests ────────────────────────────────


class TestExceptionHierarchy:
    """Verify all exceptions inherit correctly."""

    def test_base_hierarchy(self):
        assert issubclass(AgentSimError, Exception)

    def test_config_exceptions(self):
        assert issubclass(ConfigError, AgentSimError)
        assert issubclass(ScenarioFileNotFoundError, ConfigError)
        assert issubclass(ScenarioFileNotFoundError, FileNotFoundError)
        assert issubclass(ConfigValidationError, ConfigError)
        assert issubclass(ConfigValidationError, ValueError)

    def test_agent_exceptions(self):
        assert issubclass(AgentError, AgentSimError)
        assert issubclass(AgentNotFoundError, AgentError)
        assert issubclass(AgentNotFoundError, KeyError)
        assert issubclass(AgentTypeError, AgentError)
        assert issubclass(AgentTypeError, ValueError)
        assert issubclass(AgentAlreadyExistsError, AgentError)
        assert issubclass(AgentAlreadyExistsError, ValueError)

    def test_communication_exceptions(self):
        assert issubclass(CommunicationError, AgentSimError)
        assert issubclass(AgentNotRegisteredError, CommunicationError)
        assert issubclass(AgentNotRegisteredError, KeyError)

    def test_topology_error_inherits_value_error(self):
        assert issubclass(TopologyError, AgentSimError)
        assert issubclass(TopologyError, ValueError)

    def test_llm_error_inherits_both(self):
        assert issubclass(LLMError, AgentSimError)
        assert issubclass(LLMError, ValueError)
        assert issubclass(LLMError, RuntimeError)

    def test_simulation_exceptions(self):
        assert issubclass(SimulationError, AgentSimError)
        assert issubclass(SimulationTimeout, SimulationError)

    def test_protocol_error(self):
        assert issubclass(ProtocolError, AgentSimError)
        assert issubclass(ProtocolError, ValueError)

    def test_template_error(self):
        assert issubclass(TemplateError, AgentSimError)
        assert issubclass(TemplateError, KeyError)

    def test_catch_with_standard_exception(self):
        """Custom exceptions must be catchable with standard exception types."""
        with pytest.raises(ValueError):
            raise TopologyError("test")
        with pytest.raises(ValueError):
            raise ConfigValidationError("test")
        with pytest.raises(KeyError):
            raise AgentNotFoundError("test")
        with pytest.raises(FileNotFoundError):
            raise ScenarioFileNotFoundError("test")
        with pytest.raises(RuntimeError):
            raise LLMError("test")

    def test_catch_with_base(self):
        """All exceptions catchable via AgentSimError."""
        for exc_cls in [
            ConfigValidationError, AgentTypeError, AgentAlreadyExistsError,
            TopologyError, LLMError, ProtocolError, TemplateError,
            SimulationTimeout, AgentNotRegisteredError, ScenarioFileNotFoundError,
        ]:
            with pytest.raises(AgentSimError):
                raise exc_cls("test")


# ── Validation Module Tests ─────────────────────────────────


class TestValidateScenario:
    """Tests for scenario validation with detailed errors."""

    def _write_yaml(self, data: dict) -> Path:
        p = Path(tempfile.mktemp(suffix=".yaml"))
        p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
        return p

    def test_valid_config(self):
        from agent_sim.scenario.validation import validate_scenario
        p = self._write_yaml({
            "name": "test",
            "steps": 5,
            "agents": [{"name": "a", "type": "echo"}, {"name": "b", "type": "echo"}],
        })
        errors = validate_scenario(p)
        assert errors == []
        p.unlink()

    def test_nonexistent_file(self):
        from agent_sim.scenario.validation import validate_scenario
        errors = validate_scenario("/nonexistent/path.yaml")
        assert len(errors) == 1
        assert "不存在" in errors[0]

    def test_invalid_yaml_syntax(self):
        from agent_sim.scenario.validation import validate_scenario
        p = Path(tempfile.mktemp(suffix=".yaml"))
        p.write_text("{{invalid yaml", encoding="utf-8")
        errors = validate_scenario(p)
        assert any("YAML" in e for e in errors)
        p.unlink()

    def test_missing_name(self):
        from agent_sim.scenario.validation import validate_scenario
        p = self._write_yaml({"agents": [{"name": "a"}]})
        errors = validate_scenario(p)
        assert any("name" in e for e in errors)
        p.unlink()

    def test_missing_agents(self):
        from agent_sim.scenario.validation import validate_scenario
        p = self._write_yaml({"name": "test"})
        errors = validate_scenario(p)
        assert any("agents" in e for e in errors)
        p.unlink()

    def test_empty_agents_list(self):
        from agent_sim.scenario.validation import validate_scenario
        p = self._write_yaml({"name": "test", "agents": []})
        errors = validate_scenario(p)
        assert any("为空" in e for e in errors)
        p.unlink()

    def test_duplicate_agent_names(self):
        from agent_sim.scenario.validation import validate_scenario
        p = self._write_yaml({
            "name": "test",
            "agents": [
                {"name": "a", "type": "echo"},
                {"name": "a", "type": "ping"},
            ],
        })
        errors = validate_scenario(p)
        assert any("重复" in e for e in errors)
        p.unlink()

    def test_invalid_agent_type(self):
        from agent_sim.scenario.validation import validate_scenario
        p = self._write_yaml({
            "name": "test",
            "agents": [{"name": "a", "type": "nonexistent"}],
        })
        errors = validate_scenario(p)
        assert any("不支持" in e for e in errors)
        p.unlink()

    def test_custom_agent_missing_module(self):
        from agent_sim.scenario.validation import validate_scenario
        p = self._write_yaml({
            "name": "test",
            "agents": [{"name": "a", "type": "custom", "class_name": "Foo"}],
        })
        errors = validate_scenario(p)
        assert any("module" in e for e in errors)
        p.unlink()

    def test_connection_refers_to_nonexistent_agent(self):
        from agent_sim.scenario.validation import validate_scenario
        p = self._write_yaml({
            "name": "test",
            "agents": [{"name": "a"}],
            "connections": [{"from_agent": "a", "to_agent": "nonexistent"}],
        })
        errors = validate_scenario(p)
        assert any("nonexistent" in e for e in errors)
        p.unlink()

    def test_multiple_errors_reported(self):
        """All errors reported at once, not just the first."""
        from agent_sim.scenario.validation import validate_scenario
        p = self._write_yaml({
            "agents": [
                {"name": "", "type": "bad"},
                {"name": "", "type": "bad2"},
            ],
        })
        errors = validate_scenario(p)
        assert len(errors) >= 3  # missing name, bad types, empty names
        p.unlink()

    def test_large_steps_warning(self):
        from agent_sim.scenario.validation import validate_scenario
        p = self._write_yaml({
            "name": "test",
            "steps": 99999,
            "agents": [{"name": "a"}],
        })
        errors = validate_scenario(p)
        assert any("过大" in e for e in errors)
        p.unlink()


class TestConfigSchema:
    """Tests for JSON Schema export."""

    def test_schema_is_dict(self):
        from agent_sim.scenario.validation import config_schema
        schema = config_schema()
        assert isinstance(schema, dict)
        assert "$schema" in schema
        assert "properties" in schema

    def test_schema_has_required_fields(self):
        from agent_sim.scenario.validation import config_schema
        schema = config_schema()
        props = schema.get("properties", {})
        assert "name" in props
        assert "steps" in props
        assert "agents" in props

    def test_schema_json_string(self):
        from agent_sim.scenario.validation import config_schema_json
        content = config_schema_json()
        parsed = json.loads(content)
        assert isinstance(parsed, dict)

    def test_schema_yaml_string(self):
        from agent_sim.scenario.validation import config_schema_yaml
        content = config_schema_yaml()
        parsed = yaml.safe_load(content)
        assert isinstance(parsed, dict)


# ── Integration: Exception Usage Tests ───────────────────────


class TestExceptionsInAction:
    """Verify that exceptions are raised correctly in real scenarios."""

    def test_sandbox_add_duplicate_agent(self):
        from agent_sim.agent.base import Agent
        from agent_sim.environment.sandbox import Sandbox
        a = Agent(name="x")
        sb = Sandbox(agents=[a])
        with pytest.raises(AgentAlreadyExistsError):
            sb.add_agent(Agent(name="x"))

    def test_sandbox_remove_nonexistent(self):
        from agent_sim.environment.sandbox import Sandbox
        sb = Sandbox()
        with pytest.raises(AgentNotFoundError):
            sb.remove_agent("nope")

    def test_bus_register_duplicate(self):
        from agent_sim.agent.base import Agent
        from agent_sim.communication.bus import MessageBus
        bus = MessageBus()
        bus.register(Agent(name="a"))
        with pytest.raises(AgentAlreadyExistsError):
            bus.register(Agent(name="a"))

    def test_bus_unregister_nonexistent(self):
        from agent_sim.communication.bus import MessageBus
        bus = MessageBus()
        with pytest.raises(AgentNotRegisteredError):
            bus.unregister("nope")

    def test_topology_empty_agents(self):
        from agent_sim.topology.topology import TopologyType, build_topology
        with pytest.raises(TopologyError):
            build_topology(TopologyType.MESH, [])

    def test_template_not_found(self):
        from agent_sim.scenario.templates import get_template
        with pytest.raises(TemplateError):
            get_template("nonexistent_template")

    def test_factory_unknown_type(self):
        from agent_sim.scenario.factory import _create_agent
        from agent_sim.scenario.config import AgentConfig
        # Bypass pydantic validator to test factory-level error
        cfg = AgentConfig.model_construct(name="a", type="nonexistent")
        with pytest.raises(AgentTypeError):
            _create_agent(cfg)

    def test_config_file_not_found(self):
        from agent_sim.scenario.config import load_scenario
        with pytest.raises(ScenarioFileNotFoundError):
            load_scenario("/nonexistent/path.yaml")
