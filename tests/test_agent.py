"""Tests for agent definition and behavior."""

from agent_sim.agent import Agent, AgentConfig, AgentState


class TestAgentConfig:
    def test_defaults(self):
        cfg = AgentConfig(name="test")
        assert cfg.name == "test"
        assert cfg.max_steps == 100
        assert cfg.description == ""

    def test_custom(self):
        cfg = AgentConfig(name="custom", max_steps=3, description="a test agent")
        assert cfg.max_steps == 3
        assert cfg.description == "a test agent"


class TestAgentState:
    def test_defaults(self):
        s = AgentState()
        assert s.step_count == 0
        assert s.status == "idle"
        assert s.data == {}

    def test_data_mutation(self):
        s = AgentState()
        s.data["x"] = 42
        assert s.data["x"] == 42


class TestAgentLifecycle:
    def test_agent_has_id(self, echo_agent):
        assert isinstance(echo_agent.id, str)
        assert len(echo_agent.id) == 8

    def test_custom_id(self):
        cfg = AgentConfig(name="test")
        a = type("A", (Agent,), {"act": lambda self: None})(cfg, agent_id="my-id")
        assert a.id == "my-id"

    def test_observe_stores_state(self, echo_agent):
        echo_agent.observe({"value": 99})
        assert echo_agent.state.data["last_observation"] == {"value": 99}

    def test_step_calls_observe_and_act(self, echo_agent):
        result = echo_agent.step({"value": 1})
        assert result == {"echo": {"value": 1}}
        assert echo_agent.state.step_count == 1
        assert echo_agent.state.status == "running"

    def test_step_without_env(self, echo_agent):
        result = echo_agent.step()
        assert result == {"echo": {}}
        assert echo_agent.state.step_count == 1

    def test_max_steps_marks_done(self, echo_agent):
        """max_steps=5, after 5 steps status should be done."""
        for _ in range(4):
            echo_agent.step()
            assert echo_agent.state.status == "running"
        echo_agent.step()
        assert echo_agent.state.status == "done"

    def test_reset(self, echo_agent):
        echo_agent.step({"value": 1})
        echo_agent._inbox.append("msg")
        echo_agent.reset()
        assert echo_agent.state.step_count == 0
        assert echo_agent.state.status == "idle"
        assert echo_agent._inbox == []

    def test_receive_message(self, echo_agent):
        echo_agent.receive_message({"from": "other", "text": "hello"})
        assert len(echo_agent._inbox) == 1


class TestAgentAbstract:
    def test_cannot_instantiate_directly(self):
        """Agent is abstract; instantiation must fail."""
        cfg = AgentConfig(name="abstract")
        try:
            Agent(cfg)
            assert False, "Should have raised TypeError"
        except TypeError:
            pass
