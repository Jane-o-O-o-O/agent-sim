"""Tests for MessageBus communication bus."""
import pytest

from agent_sim.agent.base import Agent
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType


class TestMessageBus:
    """Test MessageBus routing and delivery."""

    def test_create_bus(self) -> None:
        """创建通信总线。"""
        bus = MessageBus()
        assert bus.agent_count == 0
        assert bus.message_count == 0

    def test_register_agent(self) -> None:
        """注册 Agent 到总线。"""
        bus = MessageBus()
        agent = Agent(name="a")
        bus.register(agent)
        assert bus.agent_count == 1
        assert bus.has_agent("a")

    def test_unregister_agent(self) -> None:
        """注销 Agent。"""
        bus = MessageBus()
        agent = Agent(name="a")
        bus.register(agent)
        bus.unregister("a")
        assert bus.agent_count == 0
        assert not bus.has_agent("a")

    def test_unregister_nonexistent_raises(self) -> None:
        """注销不存在的 Agent 抛出 KeyError。"""
        bus = MessageBus()
        with pytest.raises(KeyError):
            bus.unregister("ghost")

    def test_register_duplicate_raises(self) -> None:
        """重复注册同名 Agent 抛出 ValueError。"""
        bus = MessageBus()
        bus.register(Agent(name="a"))
        with pytest.raises(ValueError):
            bus.register(Agent(name="a"))

    def test_send_direct_message(self) -> None:
        """发送定向消息。"""
        bus = MessageBus()
        a = Agent(name="a")
        b = Agent(name="b")
        bus.register(a)
        bus.register(b)

        msg = Message(
            sender="a", receiver="b", content="hello", msg_type=MessageType.DIRECT
        )
        bus.send(msg)

        assert len(b.inbox) == 1
        assert b.inbox[0].content == "hello"
        assert len(a.inbox) == 0

    def test_send_broadcast_message(self) -> None:
        """发送广播消息（发送者除外）。"""
        bus = MessageBus()
        a = Agent(name="a")
        b = Agent(name="b")
        c = Agent(name="c")
        bus.register(a)
        bus.register(b)
        bus.register(c)

        msg = Message(
            sender="a", content="broadcast!", msg_type=MessageType.BROADCAST
        )
        bus.send(msg)

        assert len(a.inbox) == 0  # 发送者不收
        assert len(b.inbox) == 1
        assert len(c.inbox) == 1
        assert b.inbox[0].content == "broadcast!"

    def test_send_to_nonexistent_agent(self) -> None:
        """发送消息给不存在的 Agent 记录为 dead letter。"""
        bus = MessageBus()
        bus.register(Agent(name="a"))

        msg = Message(sender="a", receiver="ghost", content="hi", msg_type=MessageType.DIRECT)
        bus.send(msg)

        assert bus.dead_letter_count == 1

    def test_message_history(self) -> None:
        """总线记录消息历史。"""
        bus = MessageBus()
        bus.register(Agent(name="a"))
        bus.register(Agent(name="b"))

        bus.send(Message(sender="a", receiver="b", content="m1"))
        bus.send(Message(sender="b", receiver="a", content="m2"))

        assert bus.message_count == 2
        assert len(bus.history) == 2

    def test_get_history_for_agent(self) -> None:
        """获取特定 Agent 的消息历史。"""
        bus = MessageBus()
        bus.register(Agent(name="a"))
        bus.register(Agent(name="b"))
        bus.register(Agent(name="c"))

        bus.send(Message(sender="a", receiver="b", content="m1"))
        bus.send(Message(sender="b", receiver="c", content="m2"))
        bus.send(Message(sender="c", receiver="a", content="m3"))

        a_history = bus.get_history("a")
        assert len(a_history) == 2  # m1 (sent) + m3 (received)

    def test_clear_history(self) -> None:
        """清空历史。"""
        bus = MessageBus()
        bus.register(Agent(name="a"))
        bus.register(Agent(name="b"))
        bus.send(Message(sender="a", receiver="b", content="m1"))

        bus.clear_history()
        assert bus.message_count == 0
        assert bus.dead_letter_count == 0

    def test_bus_str(self) -> None:
        """总线字符串表示。"""
        bus = MessageBus()
        s = str(bus)
        assert "MessageBus" in s
