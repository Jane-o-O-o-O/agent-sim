"""Tests for communication bus."""

from agent_sim.agent import AgentConfig
from agent_sim.communication import Message, MessageBus
from tests.conftest import EchoAgent


class TestMessage:
    def test_create(self):
        msg = Message(sender="a", receiver="b", content="hello")
        assert msg.sender == "a"
        assert msg.receiver == "b"
        assert msg.content == "hello"
        assert msg.topic == "default"
        assert len(msg.id) == 12

    def test_custom_topic(self):
        msg = Message(sender="a", receiver="b", content=42, topic="data")
        assert msg.topic == "data"

    def test_is_serializable(self):
        msg = Message(sender="a", receiver="b", content={"key": 1})
        d = msg.model_dump()
        assert d["sender"] == "a"
        assert d["content"]["key"] == 1


class TestMessageBus:
    def _make_agent(self, name, aid=None):
        return EchoAgent(AgentConfig(name=name), agent_id=aid)

    def test_register_and_send_direct(self, bus):
        a1 = self._make_agent("a", "agent-a")
        a2 = self._make_agent("b", "agent-b")
        bus.register(a1)
        bus.register(a2)

        msg = Message(sender="agent-a", receiver="agent-b", content="ping")
        count = bus.send(msg)
        assert count == 1
        assert len(a2._inbox) == 1
        assert a2._inbox[0].content == "ping"

    def test_send_to_unknown_returns_zero(self, bus):
        a1 = self._make_agent("a", "agent-a")
        bus.register(a1)
        msg = Message(sender="agent-a", receiver="ghost", content="hello")
        assert bus.send(msg) == 0

    def test_broadcast(self, bus):
        agents = [self._make_agent(f"ag{i}", f"id-{i}") for i in range(4)]
        for ag in agents:
            bus.register(ag)

        msg = Message(sender="id-0", receiver="*", content="broadcast!")
        count = bus.send(msg)
        assert count == 3  # all except sender
        for ag in agents[1:]:
            assert len(ag._inbox) == 1
        assert len(agents[0]._inbox) == 0  # sender does not receive

    def test_unregister(self, bus):
        a1 = self._make_agent("a", "agent-a")
        a2 = self._make_agent("b", "agent-b")
        bus.register(a1)
        bus.register(a2)
        bus.unregister("agent-b")

        msg = Message(sender="agent-a", receiver="agent-b", content="test")
        assert bus.send(msg) == 0

    def test_history(self, bus):
        a1 = self._make_agent("a", "a1")
        a2 = self._make_agent("b", "a2")
        bus.register(a1)
        bus.register(a2)

        bus.send(Message(sender="a1", receiver="a2", content="msg1"))
        bus.send(Message(sender="a2", receiver="a1", content="msg2"))

        history = bus.history
        assert len(history) == 2
        assert history[0].content == "msg1"
        assert history[1].content == "msg2"

    def test_clear(self, bus):
        a1 = self._make_agent("a", "a1")
        a2 = self._make_agent("b", "a2")
        bus.register(a1)
        bus.register(a2)
        bus.send(Message(sender="a1", receiver="a2", content="x"))
        assert len(bus.history) == 1
        bus.clear()
        assert len(bus.history) == 0
