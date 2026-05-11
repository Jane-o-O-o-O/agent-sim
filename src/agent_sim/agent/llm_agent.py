"""LLM-powered agent base class with pluggable backends."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from agent_sim.agent.base import Agent
from agent_sim.communication.message import Message, MessageType

logger = logging.getLogger(__name__)


class LLMBackend(ABC):
    """LLM 后端抽象接口。

    子类实现具体 LLM 调用逻辑（如 OpenAI、本地模型等）。
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """生成 LLM 响应。

        Args:
            messages: 对话消息列表 [{"role": "user", "content": "..."}]
            **kwargs: 模型参数

        Returns:
            模型生成的文本
        """
        ...


class EchoLLMBackend(LLMBackend):
    """测试用 LLM 后端：回显输入。"""

    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """回显最后一条用户消息。"""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return f"echo:{msg['content']}"
        return "echo:empty"


class LLMAgent(Agent):
    """基于 LLM 的 Agent。

    使用可插拔的 LLM 后端生成响应。子类可重写 build_prompt() 定制提示词构建。

    Attributes:
        backend: LLM 后端实例
        system_prompt: 系统提示词
        conversation_history: 对话历史

    Example:
        >>> agent = LLMAgent(
        ...     name="assistant",
        ...     backend=EchoLLMBackend(),
        ...     system_prompt="You are a helpful assistant.",
        ... )
    """

    backend: Any = None  # LLMBackend instance, typed as Any for Pydantic
    system_prompt: str = ""
    conversation_history: list[dict[str, str]] = []

    model_config = {"arbitrary_types_allowed": True}

    def model_post_init(self, __context: Any) -> None:
        """初始化后处理。"""
        if self.backend is None:
            logger.debug("Agent %s: 未指定 backend，使用 EchoLLMBackend", self.name)
            self.backend = EchoLLMBackend()
        if not self.conversation_history and self.system_prompt:
            self.conversation_history = [
                {"role": "system", "content": self.system_prompt}
            ]

    def build_prompt(self) -> list[dict[str, str]]:
        """构建发送给 LLM 的消息列表。

        子类可重写此方法自定义 prompt 构建逻辑。

        Returns:
            消息列表
        """
        messages = list(self.conversation_history)

        # 添加 inbox 消息作为用户输入
        for msg in self.inbox:
            messages.append({
                "role": "user",
                "content": f"[From {msg.sender}]: {msg.content}",
            })

        return messages

    async def step(self) -> list[Message]:
        """执行一步：调用 LLM 生成回复。

        Returns:
            出站消息列表
        """
        replies: list[Message] = []

        if not self.inbox:
            self.increment_step()
            return replies

        prompt = self.build_prompt()
        logger.debug("Agent %s: 发送 prompt (%d messages)", self.name, len(prompt))

        try:
            response = await self.backend.generate(prompt)
            logger.debug("Agent %s: 收到响应 (%d chars)", self.name, len(response))
        except Exception as e:
            logger.error("Agent %s: LLM 调用失败: %s", self.name, e)
            self.inbox.clear()
            self.increment_step()
            return replies

        # 记录对话历史
        for msg in self.inbox:
            self.conversation_history.append({
                "role": "user",
                "content": f"[From {msg.sender}]: {msg.content}",
            })
        self.conversation_history.append({
            "role": "assistant",
            "content": response,
        })

        # 回复每个发送者
        for msg in self.inbox:
            replies.append(Message(
                sender=self.name,
                receiver=msg.sender,
                content=response,
                msg_type=MessageType.RESPONSE,
            ))

        self.inbox.clear()
        self.increment_step()
        return replies
