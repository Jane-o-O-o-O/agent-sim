"""Tests for conversation export."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agent_sim.communication.message import Message, MessageType
from agent_sim.export import (
    export_messages_to_json,
    export_messages_to_markdown,
    format_conversation_table,
)


@pytest.fixture
def sample_messages() -> list[Message]:
    """示例消息列表。"""
    return [
        Message(sender="alice", receiver="bob", content="Hello!", msg_type=MessageType.REQUEST),
        Message(sender="bob", receiver="alice", content="Hi there!", msg_type=MessageType.RESPONSE),
        Message(sender="alice", content="Broadcast!", msg_type=MessageType.BROADCAST),
    ]


class TestExportToJSON:
    """JSON 导出测试。"""

    def test_export_creates_file(self, sample_messages: list[Message]) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_messages_to_json(sample_messages, Path(tmpdir) / "out.json")
            assert path.exists()
            assert path.suffix == ".json"

    def test_export_content_valid_json(self, sample_messages: list[Message]) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_messages_to_json(sample_messages, Path(tmpdir) / "out.json")
            data = json.loads(path.read_text())
            assert data["message_count"] == 3
            assert len(data["messages"]) == 3
            assert "exported_at" in data

    def test_export_message_fields(self, sample_messages: list[Message]) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_messages_to_json(sample_messages, Path(tmpdir) / "out.json")
            data = json.loads(path.read_text())
            msg = data["messages"][0]
            assert msg["sender"] == "alice"
            assert msg["receiver"] == "bob"
            assert msg["content"] == "Hello!"
            assert "timestamp" in msg


class TestExportToMarkdown:
    """Markdown 导出测试。"""

    def test_export_creates_file(self, sample_messages: list[Message]) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_messages_to_markdown(sample_messages, Path(tmpdir) / "out.md")
            assert path.exists()
            assert path.suffix == ".md"

    def test_export_contains_title(self, sample_messages: list[Message]) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_messages_to_markdown(
                sample_messages, Path(tmpdir) / "out.md", title="My Chat"
            )
            content = path.read_text()
            assert "# My Chat" in content

    def test_export_contains_messages(self, sample_messages: list[Message]) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = export_messages_to_markdown(sample_messages, Path(tmpdir) / "out.md")
            content = path.read_text()
            assert "alice" in content
            assert "Hello!" in content
            assert "bob" in content


class TestFormatConversationTable:
    """表格格式化测试。"""

    def test_empty_messages(self) -> None:
        result = format_conversation_table([])
        assert result == "(无消息)"

    def test_contains_headers(self, sample_messages: list[Message]) -> None:
        result = format_conversation_table(sample_messages)
        assert "Time" in result
        assert "From" in result
        assert "To" in result

    def test_contains_message_data(self, sample_messages: list[Message]) -> None:
        result = format_conversation_table(sample_messages)
        assert "alice" in result
        assert "bob" in result
        assert "Hello!" in result

    def test_long_content_truncated(self) -> None:
        messages = [
            Message(
                sender="a",
                content="x" * 100,
                msg_type=MessageType.REQUEST,
            )
        ]
        result = format_conversation_table(messages)
        assert "..." in result
