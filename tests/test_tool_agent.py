"""Tests for ToolAgent."""
import json

import pytest

from agent_sim.agent.tool_agent import Tool, ToolAgent
from agent_sim.communication.message import Message, MessageType


class TestTool:
    """Test Tool wrapper."""

    def test_create_tool(self) -> None:
        """创建工具。"""
        tool = Tool(name="add", description="两数相加", fn=lambda a, b: a + b)
        assert tool.name == "add"
        assert tool.description == "两数相加"

    def test_execute_tool(self) -> None:
        """执行工具。"""
        tool = Tool(name="add", description="add", fn=lambda a, b: a + b)
        result = tool.execute(a=3, b=4)
        assert result == 7

    def test_tool_to_dict(self) -> None:
        """工具转字典。"""
        tool = Tool(name="add", description="add", fn=lambda: None)
        d = tool.to_dict()
        assert d == {"name": "add", "description": "add"}


class TestToolAgent:
    """Test ToolAgent."""

    def test_create_tool_agent(self) -> None:
        """创建 ToolAgent。"""
        agent = ToolAgent(name="tool_user")
        assert agent.name == "tool_user"
        assert agent.tools == {}

    def test_register_tool(self) -> None:
        """注册工具。"""
        agent = ToolAgent(name="a")
        agent.register_tool("add", "两数相加", lambda a, b: a + b)
        assert agent.has_tool("add")
        assert len(agent.tools) == 1

    def test_has_tool(self) -> None:
        """检查工具存在。"""
        agent = ToolAgent(name="a")
        agent.register_tool("x", "test", lambda: None)
        assert agent.has_tool("x")
        assert not agent.has_tool("y")

    def test_list_tools(self) -> None:
        """列出工具。"""
        agent = ToolAgent(name="a")
        agent.register_tool("add", "两数相加", lambda a, b: a + b)
        agent.register_tool("mul", "两数相乘", lambda a, b: a * b)
        tools = agent.list_tools()
        assert len(tools) == 2
        assert tools[0]["name"] == "add"

    @pytest.mark.asyncio
    async def test_step_no_messages(self) -> None:
        """无消息时返回空。"""
        agent = ToolAgent(name="a")
        result = await agent.step()
        assert result == []

    @pytest.mark.asyncio
    async def test_step_tool_call_via_dict(self) -> None:
        """通过字典消息调用工具。"""
        agent = ToolAgent(name="calc")
        agent.register_tool("add", "add", lambda a, b: a + b)

        msg = Message(
            sender="user",
            receiver="calc",
            content={"tool": "add", "args": {"a": 3, "b": 4}},
        )
        agent.receive(msg)
        replies = await agent.step()

        assert len(replies) == 1
        result = json.loads(replies[0].content)
        assert result["result"] == 7

    @pytest.mark.asyncio
    async def test_step_tool_call_via_json_string(self) -> None:
        """通过 JSON 字符串调用工具。"""
        agent = ToolAgent(name="calc")
        agent.register_tool("add", "add", lambda a, b: a + b)

        msg = Message(
            sender="user",
            content=json.dumps({"tool": "add", "args": {"a": 10, "b": 20}}),
        )
        agent.receive(msg)
        replies = await agent.step()

        result = json.loads(replies[0].content)
        assert result["result"] == 30

    @pytest.mark.asyncio
    async def test_step_unknown_tool(self) -> None:
        """调用未注册工具。"""
        agent = ToolAgent(name="a")
        msg = Message(
            sender="user",
            content={"tool": "nonexistent", "args": {}},
        )
        agent.receive(msg)
        replies = await agent.step()

        result = json.loads(replies[0].content)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_step_tool_error(self) -> None:
        """工具执行出错。"""
        def broken():
            raise RuntimeError("boom")

        agent = ToolAgent(name="a")
        agent.register_tool("broken", "breaks", broken)

        msg = Message(sender="user", content={"tool": "broken", "args": {}})
        agent.receive(msg)
        replies = await agent.step()

        result = json.loads(replies[0].content)
        assert "error" in result
        assert "boom" in result["error"]

    @pytest.mark.asyncio
    async def test_step_non_tool_message(self) -> None:
        """非工具调用消息返回工具列表。"""
        agent = ToolAgent(name="a")
        agent.register_tool("add", "add", lambda a, b: a + b)

        msg = Message(sender="user", content="hello")
        agent.receive(msg)
        replies = await agent.step()

        result = json.loads(replies[0].content)
        assert "available_tools" in result
        assert len(result["available_tools"]) == 1

    @pytest.mark.asyncio
    async def test_step_multiple_messages(self) -> None:
        """处理多条消息。"""
        agent = ToolAgent(name="a")
        agent.register_tool("add", "add", lambda a, b: a + b)

        agent.receive(Message(sender="u1", content={"tool": "add", "args": {"a": 1, "b": 2}}))
        agent.receive(Message(sender="u2", content={"tool": "add", "args": {"a": 3, "b": 4}}))
        replies = await agent.step()

        assert len(replies) == 2

    @pytest.mark.asyncio
    async def test_step_clears_inbox(self) -> None:
        """执行后清空 inbox。"""
        agent = ToolAgent(name="a")
        agent.receive(Message(sender="user", content="hi"))
        await agent.step()
        assert agent.inbox == []

    @pytest.mark.asyncio
    async def test_step_increments_count(self) -> None:
        """步数递增。"""
        agent = ToolAgent(name="a")
        await agent.step()
        assert agent.step_count == 1
