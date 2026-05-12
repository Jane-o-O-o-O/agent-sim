"""Tests for LLM backend implementations."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from agent_sim.agent.llm_agent import EchoLLMBackend, LLMBackend, LLMAgent


# ======================================================================
# Helpers
# ======================================================================

def await_call(coro):
    """Synchronous helper for async calls."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _make_mock_response(status_code=200, json_data=None, text=""):
    """Create a mock httpx.Response that works correctly."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code}", request=MagicMock(), response=resp
        )
    return resp


# ======================================================================
# LLMBackend ABC contract
# ======================================================================

class TestLLMBackendContract:
    def test_backend_is_abstract(self):
        """LLMBackend cannot be instantiated directly."""
        with pytest.raises(TypeError):
            LLMBackend()  # type: ignore[abstract]

    def test_echo_backend_returns_user_content(self):
        backend = EchoLLMBackend()
        result = await_call(backend.generate([
            {"role": "system", "content": "you are helpful"},
            {"role": "user", "content": "hello"},
        ]))
        assert result == "echo:hello"

    def test_echo_backend_empty_returns_empty(self):
        backend = EchoLLMBackend()
        result = await_call(backend.generate([]))
        assert result == "echo:empty"


# ======================================================================
# OpenAI-compatible backend
# ======================================================================

class TestOpenAIBackend:
    def _make_backend(self, **kwargs):
        from agent_sim.agent.llm_backend import OpenAIBackend
        return OpenAIBackend(api_key="test-key", **kwargs)

    def test_create_default(self):
        backend = self._make_backend()
        assert backend.base_url == "https://api.openai.com/v1"
        assert backend.model == "gpt-4o-mini"
        assert backend.api_key == "test-key"

    def test_create_custom(self):
        backend = self._make_backend(
            base_url="http://localhost:8000/v1",
            model="gpt-4",
            temperature=0.7,
            max_tokens=500,
        )
        assert backend.base_url == "http://localhost:8000/v1"
        assert backend.model == "gpt-4"
        assert backend.temperature == 0.7
        assert backend.max_tokens == 500

    def test_generate_calls_api(self):
        """Mock HTTP response and verify correct request."""
        backend = self._make_backend(model="gpt-4o-mini")

        mock_resp = _make_mock_response(json_data={
            "choices": [{"message": {"content": "Hello! How can I help?"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8},
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            result = await_call(backend.generate([
                {"role": "user", "content": "hi"},
            ]))

            assert result == "Hello! How can I help?"
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            body = call_args.kwargs.get("json") or call_args[1].get("json")
            assert body["model"] == "gpt-4o-mini"
            assert body["messages"] == [{"role": "user", "content": "hi"}]

    def test_generate_passes_parameters(self):
        backend = self._make_backend(
            model="gpt-4",
            temperature=0.9,
            max_tokens=200,
        )

        mock_resp = _make_mock_response(json_data={
            "choices": [{"message": {"content": "response"}}],
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            await_call(backend.generate([{"role": "user", "content": "test"}]))

            body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
            assert body["model"] == "gpt-4"
            assert body["temperature"] == 0.9
            assert body["max_tokens"] == 200

    def test_generate_http_error_raises(self):
        backend = self._make_backend()

        mock_resp = _make_mock_response(status_code=500, text="Internal Server Error")

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            with pytest.raises(httpx.HTTPStatusError):
                await_call(backend.generate([{"role": "user", "content": "test"}]))

    def test_generate_connection_error_raises(self):
        backend = self._make_backend()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("connection refused")

            with pytest.raises(httpx.ConnectError):
                await_call(backend.generate([{"role": "user", "content": "test"}]))

    def test_generate_timeout_error_raises(self):
        backend = self._make_backend(timeout=1.0)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("timeout")

            with pytest.raises(httpx.TimeoutException):
                await_call(backend.generate([{"role": "user", "content": "test"}]))

    def test_generate_empty_choices_returns_empty(self):
        backend = self._make_backend()

        mock_resp = _make_mock_response(json_data={"choices": []})

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            result = await_call(backend.generate([{"role": "user", "content": "test"}]))
            assert result == ""

    def test_generate_with_env_api_key(self):
        """Backend should fall back to OPENAI_API_KEY env var."""
        from agent_sim.agent.llm_backend import OpenAIBackend
        with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key"}):
            backend = OpenAIBackend()
            assert backend.api_key == "env-key"

    def test_generate_includes_extra_headers(self):
        backend = self._make_backend(extra_headers={"X-Custom": "value"})

        mock_resp = _make_mock_response(json_data={
            "choices": [{"message": {"content": "ok"}}],
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            await_call(backend.generate([{"role": "user", "content": "hi"}]))

            headers = mock_post.call_args.kwargs.get("headers") or mock_post.call_args[1].get("headers")
            assert headers["X-Custom"] == "value"
            assert "Bearer test-key" in headers["Authorization"]


# ======================================================================
# Ollama backend
# ======================================================================

class TestOllamaBackend:
    def _make_backend(self, **kwargs):
        from agent_sim.agent.llm_backend import OllamaBackend
        return OllamaBackend(**kwargs)

    def test_create_default(self):
        backend = self._make_backend()
        assert backend.base_url == "http://localhost:11434"
        assert backend.model == "llama3"

    def test_create_custom(self):
        backend = self._make_backend(
            base_url="http://gpu-server:11434",
            model="mistral",
        )
        assert backend.base_url == "http://gpu-server:11434"
        assert backend.model == "mistral"

    def test_generate_calls_chat_api(self):
        backend = self._make_backend(model="llama3")

        mock_resp = _make_mock_response(json_data={
            "message": {"content": "I am LLaMA."},
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            result = await_call(backend.generate([
                {"role": "user", "content": "who are you?"},
            ]))

            assert result == "I am LLaMA."
            # Verify the request body
            body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
            assert body["model"] == "llama3"
            assert body["stream"] is False
            # Verify URL includes /api/chat
            url = mock_post.call_args.args[0] if mock_post.call_args.args else mock_post.call_args.kwargs.get("url", "")
            assert "/api/chat" in str(url)

    def test_generate_passes_options(self):
        backend = self._make_backend(
            model="mistral",
            temperature=0.5,
            num_predict=100,
        )

        mock_resp = _make_mock_response(json_data={
            "message": {"content": "response"},
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            await_call(backend.generate([{"role": "user", "content": "hi"}]))

            body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
            assert body["options"]["temperature"] == 0.5
            assert body["options"]["num_predict"] == 100

    def test_generate_connection_error_raises(self):
        backend = self._make_backend()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("connection refused")

            with pytest.raises(httpx.ConnectError):
                await_call(backend.generate([{"role": "user", "content": "hi"}]))

    def test_generate_extra_options(self):
        backend = self._make_backend(extra_options={"top_k": 40, "repeat_penalty": 1.2})

        mock_resp = _make_mock_response(json_data={
            "message": {"content": "ok"},
        })

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            await_call(backend.generate([{"role": "user", "content": "hi"}]))

            body = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
            assert body["options"]["top_k"] == 40
            assert body["options"]["repeat_penalty"] == 1.2


# ======================================================================
# Factory integration: create_backend()
# ======================================================================

class TestCreateBackend:
    def test_create_echo(self):
        from agent_sim.agent.llm_backend import create_backend
        backend = create_backend("echo")
        assert isinstance(backend, EchoLLMBackend)

    def test_create_openai(self):
        from agent_sim.agent.llm_backend import create_backend, OpenAIBackend
        backend = create_backend("openai", api_key="sk-test", model="gpt-4")
        assert isinstance(backend, OpenAIBackend)
        assert backend.model == "gpt-4"

    def test_create_openai_missing_key_raises(self):
        from agent_sim.agent.llm_backend import create_backend
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            with pytest.raises(ValueError, match="api_key"):
                create_backend("openai")

    def test_create_ollama(self):
        from agent_sim.agent.llm_backend import create_backend, OllamaBackend
        backend = create_backend("ollama", model="llama3")
        assert isinstance(backend, OllamaBackend)
        assert backend.model == "llama3"

    def test_create_unknown_raises(self):
        from agent_sim.agent.llm_backend import create_backend
        with pytest.raises(ValueError, match="Unknown"):
            create_backend("unknown-provider")


# ======================================================================
# Scenario factory integration
# ======================================================================

class TestFactoryLLMIntegration:
    def test_factory_creates_llm_agent_with_echo_backend(self):
        from agent_sim.scenario.config import ScenarioConfig, AgentConfig as ScenAgentConfig
        from agent_sim.scenario.factory import build_scenario

        config = ScenarioConfig(
            name="test-llm",
            steps=1,
            agents=[
                ScenAgentConfig(
                    name="llm-agent",
                    type="llm",
                    llm_backend="echo",
                ),
            ],
        )
        sandbox, bus = build_scenario(config)
        agent = sandbox.get_agent("llm-agent")
        assert agent is not None
        assert isinstance(agent.backend, EchoLLMBackend)

    def test_factory_creates_openai_backend(self):
        from agent_sim.scenario.config import ScenarioConfig, AgentConfig as ScenAgentConfig
        from agent_sim.scenario.factory import build_scenario
        from agent_sim.agent.llm_backend import OpenAIBackend

        config = ScenarioConfig(
            name="test-openai",
            steps=1,
            agents=[
                ScenAgentConfig(
                    name="oa-agent",
                    type="llm",
                    llm_backend="openai",
                    llm_model="gpt-4o",
                    context={"api_key": "sk-test"},
                ),
            ],
        )
        sandbox, bus = build_scenario(config)
        agent = sandbox.get_agent("oa-agent")
        assert isinstance(agent.backend, OpenAIBackend)
        assert agent.backend.model == "gpt-4o"

    def test_factory_creates_ollama_backend(self):
        from agent_sim.scenario.config import ScenarioConfig, AgentConfig as ScenAgentConfig
        from agent_sim.scenario.factory import build_scenario
        from agent_sim.agent.llm_backend import OllamaBackend

        config = ScenarioConfig(
            name="test-ollama",
            steps=1,
            agents=[
                ScenAgentConfig(
                    name="ollm-agent",
                    type="llm",
                    llm_backend="ollama",
                    llm_model="mistral",
                ),
            ],
        )
        sandbox, bus = build_scenario(config)
        agent = sandbox.get_agent("ollm-agent")
        assert isinstance(agent.backend, OllamaBackend)
        assert agent.backend.model == "mistral"

    def test_factory_default_llm_uses_echo(self):
        """LLM agent without llm_backend specified should use EchoLLMBackend."""
        from agent_sim.scenario.config import ScenarioConfig, AgentConfig as ScenAgentConfig
        from agent_sim.scenario.factory import build_scenario

        config = ScenarioConfig(
            name="test-default",
            steps=1,
            agents=[
                ScenAgentConfig(name="agent1", type="llm"),
            ],
        )
        sandbox, bus = build_scenario(config)
        agent = sandbox.get_agent("agent1")
        assert isinstance(agent.backend, EchoLLMBackend)


# ======================================================================
# LLMAgent with backend end-to-end
# ======================================================================

class TestLLMAgentWithBackend:
    def test_llm_agent_uses_backend(self):
        """LLMAgent step() should call backend.generate() and return response."""
        class MockBackend(LLMBackend):
            async def generate(self, messages, **kwargs):
                return "mocked-response"

        agent = LLMAgent(
            name="test-agent",
            system_prompt="You are a test.",
            backend=MockBackend(),
        )
        from agent_sim.communication.message import Message
        agent.inbox.append(Message(sender="user", content="hello"))

        messages = await_call(agent.step())

        assert len(messages) == 1
        assert messages[0].content == "mocked-response"
        assert messages[0].receiver == "user"

    def test_llm_agent_build_prompt_includes_system(self):
        class CaptureBackend(LLMBackend):
            captured: list = []
            async def generate(self, messages, **kwargs):
                self.captured = messages
                return "ok"

        backend = CaptureBackend()
        agent = LLMAgent(
            name="a",
            system_prompt="Be helpful.",
            backend=backend,
        )
        from agent_sim.communication.message import Message
        agent.inbox.append(Message(sender="b", content="hi"))

        await_call(agent.step())

        assert backend.captured[0]["role"] == "system"
        assert backend.captured[0]["content"] == "Be helpful."
        assert any("[From b]" in m["content"] for m in backend.captured if m["role"] == "user")

    def test_llm_agent_handles_backend_error(self):
        """If backend raises, agent should return empty replies gracefully."""
        class FailingBackend(LLMBackend):
            async def generate(self, messages, **kwargs):
                raise RuntimeError("LLM service down")

        agent = LLMAgent(
            name="err-agent",
            backend=FailingBackend(),
        )
        from agent_sim.communication.message import Message
        agent.inbox.append(Message(sender="user", content="test"))

        messages = await_call(agent.step())

        assert messages == []
        assert agent.step_count == 1
        assert agent.inbox == []
