"""Memory-enabled LLM agent with automatic context injection.

Integrates the memory system (ConversationBuffer, KeyFactMemory) with LLMAgent,
automatically injecting relevant memory context into LLM prompts.
"""
from __future__ import annotations

import logging
from typing import Any

from agent_sim.agent.llm_agent import LLMAgent, LLMBackend
from agent_sim.communication.message import Message
from agent_sim.memory.buffer import ConversationBuffer, SlidingWindowBuffer
from agent_sim.memory.facts import KeyFactMemory

logger = logging.getLogger(__name__)


class MemoryAgent(LLMAgent):
    """支持记忆系统的 LLM Agent。

    自动管理对话缓冲区和事实记忆，在每次 LLM 调用时将记忆上下文注入 prompt。

    Attributes:
        buffer: 对话历史缓冲区
        facts: 事实记忆存储
        memory_window: 注入 prompt 的历史消息数量
        include_facts: 是否在 prompt 中包含相关事实

    Example:
        >>> agent = MemoryAgent(
        ...     name="assistant",
        ...     backend=EchoLLMBackend(),
        ...     system_prompt="You are helpful.",
        ...     memory_window=10,
        ... )
        >>> # 记忆自动管理，step() 时自动注入
    """

    buffer: Any = None  # ConversationBuffer or SlidingWindowBuffer
    facts: Any = None  # KeyFactMemory
    memory_window: int = 10
    include_facts: bool = True

    def model_post_init(self, __context: Any) -> None:
        """初始化记忆组件。"""
        super().model_post_init(__context)
        if self.buffer is None:
            self.buffer = SlidingWindowBuffer(window_size=self.memory_window)
        if self.facts is None:
            self.facts = KeyFactMemory(max_facts=200)

    def build_prompt(self) -> list[dict[str, str]]:
        """构建包含记忆上下文的 prompt。

        自动注入:
        1. 系统提示词
        2. 相关事实记忆 (如果 include_facts=True)
        3. 对话历史缓冲区中的消息
        4. 当前 inbox 消息

        Returns:
            包含记忆上下文的消息列表
        """
        messages: list[dict[str, str]] = []

        # 系统提示词
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})

        # 注入相关事实
        if self.include_facts and self.facts:
            facts_text = self._build_facts_context()
            if facts_text:
                messages.append({"role": "system", "content": facts_text})

        # 注入对话历史
        if self.buffer:
            history = self.buffer.get_messages()
            for msg in history[-self.memory_window:]:
                messages.append(msg)

        # 当前 inbox 消息
        for msg in self.inbox:
            sender_tag = f"[From {msg.sender}] " if msg.sender else ""
            messages.append({
                "role": "user",
                "content": f"{sender_tag}{msg.content}",
            })
            # 自动记录到缓冲区
            self.buffer.add("user", f"{sender_tag}{msg.content}")

        return messages

    def _build_facts_context(self) -> str:
        """从事实记忆构建上下文文本。

        Returns:
            格式化的事实文本，如 "Known facts:\n- user_name: Alice\n- ..."
        """
        if not self.facts or not self.facts._facts:
            return ""

        facts = list(self.facts._facts.items())[:20]  # 最多注入20条
        lines = ["Known facts:"]
        for key, fact in facts:
            confidence_str = f" (confidence: {fact.confidence:.1%})" if fact.confidence < 1.0 else ""
            lines.append(f"- {key}: {fact.value}{confidence_str}")
        return "\n".join(lines)

    async def step(self) -> list[Message]:
        """执行一步，带记忆管理。

        1. 构建包含记忆的 prompt
        2. 调用 LLM 生成响应
        3. 记录助手响应到缓冲区
        4. 自动提取事实（如果 LLM 输出包含可记忆信息）

        Returns:
            出站消息列表
        """
        if not self.inbox:
            self.increment_step()
            return []

        prompt = self.build_prompt()

        try:
            response = await self.backend.generate(prompt)
        except Exception as e:
            logger.error("Agent %s LLM 调用失败: %s", self.name, e)
            self.inbox.clear()
            self.increment_step()
            return []

        # 记录助手响应到缓冲区
        self.buffer.add("assistant", response)

        replies: list[Message] = []
        for msg in self.inbox:
            replies.append(Message(
                sender=self.name,
                receiver=msg.sender,
                content=response,
            ))

        self.inbox.clear()
        self.increment_step()
        return replies

    def remember(self, key: str, value: str, confidence: float = 1.0, source: str = "agent") -> None:
        """存储事实到记忆。

        Args:
            key: 事实键
            value: 事实值
            confidence: 置信度 (0.0-1.0)
            source: 来源标识
        """
        self.facts.remember(key, value, source=source, confidence=confidence)

    def recall(self, key: str) -> str | None:
        """从记忆中回忆事实。

        Args:
            key: 事实键

        Returns:
            事实值，不存在返回 None
        """
        return self.facts.recall(key)

    def search_memory(self, query: str) -> list[tuple[str, str]]:
        """搜索记忆。

        Args:
            query: 搜索关键词

        Returns:
            匹配的 (key, value) 列表
        """
        return self.facts.search(query)
