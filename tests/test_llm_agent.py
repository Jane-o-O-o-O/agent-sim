"""Tests for LLMAgent and LLMBackend."""
import pytest

from agent_sim.agent.llm_agent import EchoLLMBackend, LLMAgent, LLMBackend
from agent_sim.communication.message import Message, MessageType


class TestEchoLLMBackend:
    """Test EchoLLMBackend."""

    @pytest.mark.asyncio
    async def test_echo_returns_user_message(self) -> None:
        """回显最后一条用户消息。"""
        backend = EchoLLMBackend()
        result = await backend.generate([
            {"role": "user", "content": "hello"},
        ])
        assert result == "echo:hello"

    @pytest.mark.asyncio
    async def test_echo_with_system_prompt(self) -> None:
        """带系统提示时回显用户消息。"""
        backend = EchoLLMBackend()
        result = await backend.generate([
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "test"},
        ])
        assert result == "echo:test"

    @pytest.mark.asyncio
    async def test_echo_no_user_message(self) -> None:
        """无用户消息时返回默认值。"""
        backend = EchoLLMBackend()
        result = await backend.generate([
            {"role": "system", "content": "You are helpful."},
        ])
        assert result == "echo:empty"


class TestLLMAgent:
    """Test LLMAgent."""

    def test_create_llm_agent(self) -> None:
        """创建 LLM Agent。"""
        agent = LLMAgent(name="assistant")
        assert agent.name == "assistant"
        assert agent.backend is not None

    def test_create_with_system_prompt(self) -> None:
        """带系统提示创建。"""
        agent = LLMAgent(name="a", system_prompt="You are helpful.")
        assert agent.system_prompt == "You are helpful."

    def test_create_with_custom_backend(self) -> None:
        """自定义后端。"""
        backend = EchoLLMBackend()
        agent = LLMAgent(name="a", backend=backend)
        assert agent.backend is backend

    @pytest.mark.asyncio
    async def test_step_with_no_messages(self) -> None:
        """无消息时不调用 LLM。"""
        agent = LLMAgent(name="a")
        result = await agent.step()
        assert result == []
        assert agent.step_count == 1

    @pytest.mark.asyncio
    async def test_step_responds_to_messages(self) -> None:
        """收到消息后回复。"""
        agent = LLMAgent(name="assistant")
        agent.receive(Message(sender="user", content="hello"))
        replies = await agent.step()

        assert len(replies) == 1
        assert "hello" in replies[0].content
        assert replies[0].receiver == "user"
        assert replies[0].msg_type == MessageType.RESPONSE

    @pytest.mark.asyncio
    async def test_step_multiple_messages(self) -> None:
        """多条消息时回复每条。"""
        agent = LLMAgent(name="a")
        agent.receive(Message(sender="u1", content="msg1"))
        agent.receive(Message(sender="u2", content="msg2"))
        replies = await agent.step()

        assert len(replies) == 2
        assert replies[0].receiver == "u1"
        assert replies[1].receiver == "u2"

    @pytest.mark.asyncio
    async def test_conversation_history(self) -> None:
        """对话历史记录。"""
        agent = LLMAgent(name="a")
        agent.receive(Message(sender="user", content="hello"))
        await agent.step()

        # 应该有 user + assistant 两条历史
        assert len(agent.conversation_history) == 2
        assert agent.conversation_history[0]["role"] == "user"
        assert agent.conversation_history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_system_prompt_in_history(self) -> None:
        """系统提示在对话历史中。"""
        agent = LLMAgent(name="a", system_prompt="Be helpful.")
        agent.receive(Message(sender="user", content="hi"))
        await agent.step()

        assert agent.conversation_history[0]["role"] == "system"
        assert agent.conversation_history[0]["content"] == "Be helpful."

    @pytest.mark.asyncio
    async def test_build_prompt(self) -> None:
        """构建 prompt。"""
        agent = LLMAgent(name="a", system_prompt="Sys.")
        agent.receive(Message(sender="user", content="hi"))
        prompt = agent.build_prompt()

        assert prompt[0]["role"] == "system"
        assert prompt[-1]["role"] == "user"
        assert "hi" in prompt[-1]["content"]

    def test_increment_step(self) -> None:
        """步数递增。"""
        agent = LLMAgent(name="a")
        assert agent.step_count == 0
