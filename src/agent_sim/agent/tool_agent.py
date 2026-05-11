"""Tool-calling agent with registered tool functions."""
from __future__ import annotations

import json
import logging
from typing import Any, Callable

from agent_sim.agent.base import Agent
from agent_sim.communication.message import Message, MessageType

logger = logging.getLogger(__name__)


class Tool:
    """工具定义。

    封装一个可调用的函数，包含名称、描述和参数 schema。

    Attributes:
        name: 工具名称
        description: 工具描述
        fn: 工具函数
    """

    def __init__(
        self,
        name: str,
        description: str,
        fn: Callable[..., Any],
    ) -> None:
        self.name = name
        self.description = description
        self.fn = fn

    def execute(self, **kwargs: Any) -> Any:
        """执行工具函数。

        Args:
            **kwargs: 工具参数

        Returns:
            工具返回值
        """
        logger.debug("执行工具 %s(%s)", self.name, kwargs)
        return self.fn(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        """转为字典描述。"""
        return {"name": self.name, "description": self.description}


class ToolAgent(Agent):
    """支持工具调用的 Agent。

    可注册工具，通过消息触发工具调用并返回结果。

    消息格式 (content 字段):
        - `{"tool": "name", "args": {...}}` — 调用工具
        - 其他字符串 — 作为普通消息回复

    Attributes:
        tools: 已注册工具字典

    Example:
        >>> def add(a: int, b: int) -> int:
        ...     return a + b
        >>> agent = ToolAgent(name="calculator")
        >>> agent.register_tool("add", "两数相加", add)
    """

    tools: dict[str, Tool] = {}

    model_config = {"arbitrary_types_allowed": True}

    def model_post_init(self, __context: Any) -> None:
        """初始化工具字典。"""
        if not self.tools:
            self.tools = {}

    def register_tool(
        self,
        name: str,
        description: str,
        fn: Callable[..., Any],
    ) -> None:
        """注册工具。

        Args:
            name: 工具名称
            description: 工具描述
            fn: 工具函数
        """
        self.tools[name] = Tool(name=name, description=description, fn=fn)
        logger.info("Agent %s: 注册工具 '%s'", self.name, name)

    def has_tool(self, name: str) -> bool:
        """检查是否已注册某工具。"""
        return name in self.tools

    def list_tools(self) -> list[dict[str, Any]]:
        """列出所有已注册工具。"""
        return [t.to_dict() for t in self.tools.values()]

    def _call_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        """调用工具并返回结果字符串。

        Args:
            tool_name: 工具名称
            args: 工具参数

        Returns:
            工具结果的 JSON 字符串
        """
        tool = self.tools.get(tool_name)
        if tool is None:
            return json.dumps({"error": f"工具 '{tool_name}' 未注册"})

        try:
            result = tool.execute(**args)
            return json.dumps({"result": result}, ensure_ascii=False, default=str)
        except Exception as e:
            logger.error("Agent %s: 工具 '%s' 执行失败: %s", self.name, tool_name, e)
            return json.dumps({"error": str(e)})

    async def step(self) -> list[Message]:
        """执行一步：解析消息中的工具调用指令并执行。

        Returns:
            工具调用结果消息
        """
        replies: list[Message] = []

        for msg in self.inbox:
            response_content = self._process_message(msg)
            replies.append(Message(
                sender=self.name,
                receiver=msg.sender,
                content=response_content,
                msg_type=MessageType.RESPONSE,
            ))

        self.inbox.clear()
        self.increment_step()
        return replies

    def _process_message(self, msg: Message) -> str:
        """处理单条消息。

        如果消息 content 是包含 tool 和 args 的字典，执行工具调用；
        否则返回工具列表信息。

        Args:
            msg: 输入消息

        Returns:
            处理结果字符串
        """
        content = msg.content

        if isinstance(content, dict) and "tool" in content:
            tool_name = content["tool"]
            args = content.get("args", {})
            return self._call_tool(tool_name, args)

        if isinstance(content, str):
            # 尝试 JSON 解析
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "tool" in data:
                    return self._call_tool(data["tool"], data.get("args", {}))
            except (json.JSONDecodeError, TypeError):
                pass

        # 默认返回工具列表
        tools_info = self.list_tools()
        return json.dumps({
            "message": f"收到: {content}",
            "available_tools": tools_info,
        }, ensure_ascii=False)
