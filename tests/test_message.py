"""Tests for message model."""
import time

from agent_sim.communication.message import Message, MessageType


class TestMessage:
    """Test Message data model."""

    def test_create_basic_message(self) -> None:
        """创建基本消息。"""
        msg = Message(sender="agent_a", content="hello")
        assert msg.sender == "agent_a"
        assert msg.content == "hello"
        assert msg.receiver is None  # broadcast by default
        assert msg.msg_type == MessageType.BROADCAST

    def test_create_directed_message(self) -> None:
        """创建定向消息。"""
        msg = Message(
            sender="agent_a",
            receiver="agent_b",
            content={"task": "analyze"},
            msg_type=MessageType.DIRECT,
        )
        assert msg.receiver == "agent_b"
        assert msg.msg_type == MessageType.DIRECT
        assert msg.content == {"task": "analyze"}

    def test_message_has_timestamp(self) -> None:
        """消息自动带有时间戳。"""
        before = time.time()
        msg = Message(sender="a", content="test")
        after = time.time()
        assert before <= msg.timestamp <= after

    def test_message_metadata(self) -> None:
        """消息支持元数据。"""
        msg = Message(
            sender="a",
            content="test",
            metadata={"priority": "high", "ttl": 30},
        )
        assert msg.metadata["priority"] == "high"
        assert msg.metadata["ttl"] == 30

    def test_message_default_metadata(self) -> None:
        """默认元数据为空字典。"""
        msg = Message(sender="a", content="test")
        assert msg.metadata == {}

    def test_message_str(self) -> None:
        """消息的字符串表示。"""
        msg = Message(sender="a", receiver="b", content="hello")
        s = str(msg)
        assert "a" in s
        assert "b" in s

    def test_message_repr(self) -> None:
        """消息的 repr。"""
        msg = Message(sender="a", content="hello")
        r = repr(msg)
        assert "Message" in r

    def test_message_with_request_type(self) -> None:
        """请求类型消息。"""
        msg = Message(
            sender="a",
            receiver="b",
            content="do something",
            msg_type=MessageType.REQUEST,
        )
        assert msg.msg_type == MessageType.REQUEST

    def test_message_with_response_type(self) -> None:
        """响应类型消息。"""
        msg = Message(
            sender="b",
            receiver="a",
            content="done",
            msg_type=MessageType.RESPONSE,
            metadata={"in_reply_to": "msg-123"},
        )
        assert msg.msg_type == MessageType.RESPONSE
        assert msg.metadata["in_reply_to"] == "msg-123"

    def test_message_with_system_type(self) -> None:
        """系统类型消息。"""
        msg = Message(
            sender="__system__",
            content="simulation started",
            msg_type=MessageType.SYSTEM,
        )
        assert msg.msg_type == MessageType.SYSTEM


class TestMessageType:
    """Test MessageType enum."""

    def test_message_types_exist(self) -> None:
        """所有消息类型存在。"""
        assert MessageType.DIRECT
        assert MessageType.BROADCAST
        assert MessageType.REQUEST
        assert MessageType.RESPONSE
        assert MessageType.SYSTEM

    def test_message_type_values(self) -> None:
        """消息类型值为字符串。"""
        assert isinstance(MessageType.DIRECT.value, str)
        assert isinstance(MessageType.BROADCAST.value, str)
