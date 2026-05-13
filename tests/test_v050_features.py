"""Tests for v0.5.0 features — MemoryAgent, middleware, checkpoint, retry, correlation, concurrent."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile

import pytest

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.llm_agent import EchoLLMBackend, LLMBackend, LLMAgent
from agent_sim.agent.memory_agent import MemoryAgent
from agent_sim.agent.retry import RetryConfig, RetryManager, RetryStats
from agent_sim.agent.role import Role
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.correlation import CorrelationEntry, ResponseTracker
from agent_sim.communication.message import Message, MessageType
from agent_sim.communication.middleware import (
    DeduplicationMiddleware,
    FilterMiddleware,
    LoggingMiddleware,
    MessageMiddleware,
    RateLimitMiddleware,
    TransformMiddleware,
)
from agent_sim.environment.sandbox import Sandbox
from agent_sim.export import export_messages_to_csv, export_messages_to_json, export_messages_to_markdown
from agent_sim.memory.buffer import SlidingWindowBuffer
from agent_sim.memory.facts import KeyFactMemory
from agent_sim.scenario.checkpoint import Checkpoint, CheckpointManager
from agent_sim.scenario.runner import ScenarioRunner


def await_call(coro):
    """Synchronous helper for async calls."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ======================================================================
# MemoryAgent
# ======================================================================

class TestMemoryAgent:
    def test_create_default(self):
        """MemoryAgent creates with default memory components."""
        agent = MemoryAgent(name="test", backend=EchoLLMBackend())
        assert agent.buffer is not None
        assert agent.facts is not None
        assert agent.memory_window == 10
        assert agent.include_facts is True

    def test_create_custom_buffer(self):
        """MemoryAgent accepts custom buffer."""
        buf = SlidingWindowBuffer(window_size=5)
        agent = MemoryAgent(name="test", backend=EchoLLMBackend(), buffer=buf)
        assert agent.buffer is buf

    def test_remember_and_recall(self):
        """MemoryAgent can store and recall facts."""
        agent = MemoryAgent(name="test", backend=EchoLLMBackend())
        agent.remember("user_name", "Alice", confidence=0.9)
        assert agent.recall("user_name") == "Alice"

    def test_search_memory(self):
        """MemoryAgent can search facts."""
        agent = MemoryAgent(name="test", backend=EchoLLMBackend())
        agent.remember("user_name", "Alice")
        agent.remember("user_age", "30")
        results = agent.search_memory("user")
        assert len(results) == 2

    def test_step_with_memory(self):
        """MemoryAgent step() returns LLM response and manages buffer."""
        agent = MemoryAgent(name="assistant", backend=EchoLLMBackend(), system_prompt="Be helpful.")
        agent.inbox.append(Message(sender="user", content="hello"))

        messages = await_call(agent.step())

        assert len(messages) == 1
        assert "echo:[From user] hello" in messages[0].content
        assert agent.step_count == 1

    def test_step_empty_inbox(self):
        """MemoryAgent step() with empty inbox returns empty list."""
        agent = MemoryAgent(name="test", backend=EchoLLMBackend())
        messages = await_call(agent.step())
        assert messages == []
        assert agent.step_count == 1

    def test_build_prompt_includes_facts(self):
        """build_prompt() includes facts context when include_facts=True."""
        agent = MemoryAgent(name="test", backend=EchoLLMBackend(), include_facts=True)
        agent.remember("key1", "value1")
        agent.remember("key2", "value2")
        agent.inbox.append(Message(sender="user", content="hi"))

        prompt = agent.build_prompt()
        contents = " ".join(m["content"] for m in prompt)
        assert "Known facts" in contents
        assert "key1" in contents
        assert "value1" in contents

    def test_build_prompt_excludes_facts(self):
        """build_prompt() excludes facts when include_facts=False."""
        agent = MemoryAgent(name="test", backend=EchoLLMBackend(), include_facts=False)
        agent.remember("key1", "value1")
        agent.inbox.append(Message(sender="user", content="hi"))

        prompt = agent.build_prompt()
        contents = " ".join(m["content"] for m in prompt)
        assert "Known facts" not in contents

    def test_step_records_to_buffer(self):
        """MemoryAgent step() records messages to buffer."""
        agent = MemoryAgent(name="test", backend=EchoLLMBackend())
        agent.inbox.append(Message(sender="user", content="hello"))
        await_call(agent.step())

        history = agent.buffer.get_messages()
        assert len(history) >= 2  # user msg + assistant response

    def test_step_handles_backend_error(self):
        """MemoryAgent step() handles backend errors gracefully."""
        class FailingBackend(LLMBackend):
            async def generate(self, messages, **kwargs):
                raise RuntimeError("backend down")

        agent = MemoryAgent(name="test", backend=FailingBackend())
        agent.inbox.append(Message(sender="user", content="hi"))
        messages = await_call(agent.step())
        assert messages == []
        assert agent.step_count == 1

    def test_step_multiple_messages(self):
        """MemoryAgent step() handles multiple inbox messages."""
        agent = MemoryAgent(name="test", backend=EchoLLMBackend())
        agent.inbox.append(Message(sender="a", content="msg1"))
        agent.inbox.append(Message(sender="b", content="msg2"))

        messages = await_call(agent.step())
        assert len(messages) == 2


# ======================================================================
# Message Middleware
# ======================================================================

class TestLoggingMiddleware:
    def test_passes_message_through(self):
        """LoggingMiddleware passes message through unchanged."""
        mw = LoggingMiddleware()
        msg = Message(sender="a", receiver="b", content="hello")
        result = mw.process(msg)
        assert result is msg
        assert len(mw.logged) == 1

    def test_logs_multiple_messages(self):
        """LoggingMiddleware accumulates logged messages."""
        mw = LoggingMiddleware()
        for i in range(5):
            mw.process(Message(sender="a", content=f"msg{i}"))
        assert len(mw.logged) == 5


class TestFilterMiddleware:
    def test_block_sender(self):
        """FilterMiddleware blocks messages from blocked senders."""
        mw = FilterMiddleware(blocked_senders={"spam"})
        msg_blocked = Message(sender="spam", content="x")
        msg_ok = Message(sender="good", content="x")
        assert mw.process(msg_blocked) is None
        assert mw.process(msg_ok) is not None

    def test_block_receiver(self):
        """FilterMiddleware blocks messages to blocked receivers."""
        mw = FilterMiddleware(blocked_receivers={"blocked_agent"})
        msg = Message(sender="a", receiver="blocked_agent", content="x")
        assert mw.process(msg) is None

    def test_allowed_types(self):
        """FilterMiddleware filters by message type."""
        mw = FilterMiddleware(allowed_types={MessageType.REQUEST})
        req = Message(sender="a", content="x", msg_type=MessageType.REQUEST)
        broadcast = Message(sender="a", content="x", msg_type=MessageType.BROADCAST)
        assert mw.process(req) is not None
        assert mw.process(broadcast) is None

    def test_max_content_length(self):
        """FilterMiddleware filters messages exceeding max content length."""
        mw = FilterMiddleware(max_content_length=10)
        short = Message(sender="a", content="hi")
        long_msg = Message(sender="a", content="x" * 20)
        assert mw.process(short) is not None
        assert mw.process(long_msg) is None

    def test_no_filters_passes_all(self):
        """FilterMiddleware with no filters passes all messages."""
        mw = FilterMiddleware()
        msg = Message(sender="a", content="x")
        assert mw.process(msg) is not None


class TestTransformMiddleware:
    def test_transform_message(self):
        """TransformMiddleware applies transform function."""
        mw = TransformMiddleware(
            transform=lambda m: m.model_copy(update={"content": f"[LOGGED] {m.content}"})
        )
        msg = Message(sender="a", content="hello")
        result = mw.process(msg)
        assert "[LOGGED] hello" in result.content

    def test_no_transform_passes_through(self):
        """TransformMiddleware without transform passes through."""
        mw = TransformMiddleware()
        msg = Message(sender="a", content="hello")
        result = mw.process(msg)
        assert result.content == "hello"


class TestDeduplicationMiddleware:
    def test_deduplicates_messages(self):
        """DeduplicationMiddleware filters duplicate messages."""
        mw = DeduplicationMiddleware(window_seconds=10.0)
        msg1 = Message(sender="a", receiver="b", content="same")
        msg2 = Message(sender="a", receiver="b", content="same")
        msg3 = Message(sender="a", receiver="b", content="different")

        assert mw.process(msg1) is not None
        assert mw.process(msg2) is None  # duplicate
        assert mw.process(msg3) is not None  # different content


class TestRateLimitMiddleware:
    def test_allows_within_limit(self):
        """RateLimitMiddleware allows messages within rate limit."""
        mw = RateLimitMiddleware(max_per_second=5)
        for _ in range(5):
            msg = Message(sender="a", content="x")
            assert mw.process(msg) is not None

    def test_blocks_over_limit(self):
        """RateLimitMiddleware blocks messages exceeding rate limit."""
        mw = RateLimitMiddleware(max_per_second=2)
        assert mw.process(Message(sender="a", content="1")) is not None
        assert mw.process(Message(sender="a", content="2")) is not None
        assert mw.process(Message(sender="a", content="3")) is None  # over limit


class TestMessageBusMiddleware:
    def test_bus_with_filter_middleware(self):
        """MessageBus with filter middleware blocks messages."""
        bus = MessageBus()
        bus.add_middleware(FilterMiddleware(blocked_senders={"spam"}))

        a = Agent(name="a")
        b = Agent(name="b")
        bus.register(a)
        bus.register(b)

        # This should be filtered
        bus.send(Message(sender="spam", receiver="a", content="blocked"))
        assert len(a.inbox) == 0

        # This should go through
        bus.send(Message(sender="b", receiver="a", content="ok"))
        assert len(a.inbox) == 1

    def test_bus_remove_middleware(self):
        """MessageBus can remove middleware by type."""
        bus = MessageBus()
        bus.add_middleware(LoggingMiddleware())
        bus.add_middleware(FilterMiddleware())
        assert len(bus._middleware) == 2

        removed = bus.remove_middleware(LoggingMiddleware)
        assert removed == 1
        assert len(bus._middleware) == 1

    def test_bus_middleware_chain(self):
        """MessageBus middleware executes in order."""
        bus = MessageBus()
        order = []

        class TrackingMiddleware(MessageMiddleware):
            def __init__(self, name):
                self.name = name
            def process(self, message):
                order.append(self.name)
                return message

        bus.add_middleware(TrackingMiddleware("first"))
        bus.add_middleware(TrackingMiddleware("second"))

        a = Agent(name="a")
        bus.register(a)
        bus.send(Message(sender="b", receiver="a", content="hi"))

        assert order == ["first", "second"]


# ======================================================================
# Checkpoint
# ======================================================================

class TestCheckpoint:
    def test_create_checkpoint(self):
        """CheckpointManager creates checkpoint from simulation state."""
        a = Agent(name="a")
        b = Agent(name="b")
        a.step_count = 5
        a.context = {"key": "value"}

        sandbox = Sandbox(agents=[a, b])
        bus = MessageBus()
        bus.register(a)
        bus.register(b)
        bus.send(Message(sender="a", receiver="b", content="test"))

        manager = CheckpointManager()
        cp = manager.create_checkpoint(sandbox, bus, step=5, metadata={"test": True})

        assert cp.step == 5
        assert len(cp.agents) == 2
        assert cp.metadata == {"test": True}
        assert len(cp.message_history) == 1

    def test_save_and_load_checkpoint(self):
        """CheckpointManager can save and load checkpoints."""
        a = Agent(name="a")
        a.step_count = 3
        sandbox = Sandbox(agents=[a])
        bus = MessageBus()
        bus.register(a)

        manager = CheckpointManager()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            cp = manager.create_checkpoint(sandbox, bus, step=3)
            manager.save(cp, path)

            loaded = manager.load(path)
            assert loaded.step == 3
            assert len(loaded.agents) == 1
            assert loaded.agents[0].name == "a"
            assert loaded.agents[0].step_count == 3
        finally:
            os.unlink(path)

    def test_restore_checkpoint(self):
        """CheckpointManager restores simulation state from checkpoint."""
        a = Agent(name="a")
        b = Agent(name="b")
        sandbox = Sandbox(agents=[a, b])
        bus = MessageBus()
        bus.register(a)
        bus.register(b)

        manager = CheckpointManager()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            # Save initial state with modified agent
            a.step_count = 10
            a.context = {"restored": True}
            cp = manager.create_checkpoint(sandbox, bus, step=10)
            manager.save(cp, path)

            # Reset agents
            a.step_count = 0
            a.context = {}

            # Restore
            loaded = manager.load(path)
            restored = manager.restore(loaded, sandbox, bus)
            assert restored == 2
            assert a.step_count == 10
            assert a.context == {"restored": True}
        finally:
            os.unlink(path)

    def test_load_nonexistent_raises(self):
        """CheckpointManager.load raises FileNotFoundError for missing files."""
        manager = CheckpointManager()
        with pytest.raises(FileNotFoundError):
            manager.load("/nonexistent/path.json")

    def test_restore_skips_missing_agents(self):
        """CheckpointManager.restore skips agents not in sandbox."""
        a = Agent(name="a")
        sandbox = Sandbox(agents=[a])
        bus = MessageBus()
        bus.register(a)

        manager = CheckpointManager()
        cp = Checkpoint(
            agents=[
                {"name": "a", "state": "idle", "step_count": 5, "context": {}, "inbox": [], "agent_type": "Agent"},
                {"name": "ghost", "state": "idle", "step_count": 0, "context": {}, "inbox": [], "agent_type": "Agent"},
            ],
            step=5,
        )
        restored = manager.restore(cp, sandbox, bus)
        assert restored == 1  # only "a" was restored


# ======================================================================
# Retry
# ======================================================================

class TestRetryManager:
    def test_success_on_first_try(self):
        """RetryManager returns result on first successful call."""
        manager = RetryManager(RetryConfig(max_retries=3, base_delay=0.01))

        async def success():
            return "ok"

        result = await_call(manager.retry_async(success))
        assert result == "ok"
        assert manager.stats.total_successes == 1
        assert manager.stats.total_retries == 0

    def test_retry_on_failure(self):
        """RetryManager retries on failure and succeeds eventually."""
        attempts = 0

        async def flaky():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise RuntimeError("fail")
            return "success"

        manager = RetryManager(RetryConfig(max_retries=3, base_delay=0.01))
        result = await_call(manager.retry_async(flaky))
        assert result == "success"
        assert manager.stats.total_retries == 2
        assert manager.stats.total_successes == 1

    def test_exhausts_retries(self):
        """RetryManager raises after exhausting retries."""
        async def always_fail():
            raise RuntimeError("always fail")

        manager = RetryManager(RetryConfig(max_retries=2, base_delay=0.01))
        with pytest.raises(RuntimeError, match="always fail"):
            await_call(manager.retry_async(always_fail))

        assert manager.stats.total_retries == 2
        assert manager.stats.total_failures == 1

    def test_retryable_errors_filter(self):
        """RetryManager only retries specified error types."""
        async def value_error():
            raise ValueError("bad value")

        manager = RetryManager(RetryConfig(
            max_retries=3,
            base_delay=0.01,
            retryable_errors=["RuntimeError"],
        ))

        with pytest.raises(ValueError):
            await_call(manager.retry_async(value_error))

        assert manager.stats.total_retries == 0  # ValueError not retryable

    def test_reset_stats(self):
        """RetryManager can reset statistics."""
        manager = RetryManager()

        async def ok():
            return True

        await_call(manager.retry_async(ok))
        assert manager.stats.total_calls == 1

        manager.reset_stats()
        assert manager.stats.total_calls == 0


# ======================================================================
# Response Correlation
# ======================================================================

class TestResponseTracker:
    def test_track_request(self):
        """ResponseTracker tracks request and returns correlation ID."""
        tracker = ResponseTracker()
        msg = Message(sender="a", receiver="b", content="query")
        cid = tracker.track_request(msg)
        assert cid is not None
        assert len(cid) == 8

    def test_track_response(self):
        """ResponseTracker correlates response to request."""
        tracker = ResponseTracker()
        req = Message(sender="a", receiver="b", content="query")
        cid = tracker.track_request(req)

        resp = Message(sender="b", receiver="a", content="answer", correlation_id=cid)
        assert tracker.track_response(resp) is True

        entry = tracker.get_entry(cid)
        assert entry.completed is True
        assert entry.response is not None

    def test_track_response_unknown_id(self):
        """ResponseTracker returns False for unknown correlation ID."""
        tracker = ResponseTracker()
        resp = Message(sender="b", receiver="a", content="answer", correlation_id="unknown")
        assert tracker.track_response(resp) is False

    def test_get_pending(self):
        """ResponseTracker returns pending entries."""
        tracker = ResponseTracker()
        cid1 = tracker.track_request(Message(sender="a", content="q1"))
        cid2 = tracker.track_request(Message(sender="a", content="q2"))
        tracker.track_response(Message(sender="b", content="a1", correlation_id=cid1))

        pending = tracker.get_pending()
        assert len(pending) == 1
        assert pending[0].correlation_id == cid2

    def test_get_completed(self):
        """ResponseTracker returns completed entries."""
        tracker = ResponseTracker()
        cid = tracker.track_request(Message(sender="a", content="q"))
        tracker.track_response(Message(sender="b", content="a", correlation_id=cid))

        completed = tracker.get_completed()
        assert len(completed) == 1

    def test_get_stats(self):
        """ResponseTracker returns statistics."""
        tracker = ResponseTracker()
        cid = tracker.track_request(Message(sender="a", content="q"))
        tracker.track_response(Message(sender="b", content="a", correlation_id=cid))

        stats = tracker.get_stats()
        assert stats["total"] == 1
        assert stats["completed"] == 1
        assert stats["pending"] == 0
        assert stats["avg_latency"] >= 0

    def test_auto_generate_id(self):
        """ResponseTracker auto-generates ID for messages without one."""
        tracker = ResponseTracker()
        msg = Message(sender="a", content="q", correlation_id=None)
        cid = tracker.track_request(msg)
        assert cid is not None

    def test_clear(self):
        """ResponseTracker.clear() removes all entries."""
        tracker = ResponseTracker()
        tracker.track_request(Message(sender="a", content="q"))
        assert len(tracker._entries) == 1
        tracker.clear()
        assert len(tracker._entries) == 0


# ======================================================================
# Concurrent Execution
# ======================================================================

class TestConcurrentRunner:
    def test_concurrent_runner_same_result(self):
        """Concurrent runner produces valid results (steps completed, messages)."""
        class CountingAgent(Agent):
            async def step(self):
                msgs = []
                for msg in self.inbox:
                    msgs.append(Message(
                        sender=self.name,
                        receiver=msg.sender,
                        content=f"reply:{msg.content}",
                    ))
                self.inbox.clear()
                self.increment_step()
                return msgs

        # Concurrent
        a2 = CountingAgent(name="a")
        b2 = CountingAgent(name="b")
        sandbox2 = Sandbox(agents=[a2, b2])
        bus2 = MessageBus()
        bus2.register(a2)
        bus2.register(b2)
        bus2.send(Message(sender="a", receiver="b", content="start"))

        result_con = await_call(ScenarioRunner(
            sandbox=sandbox2, bus=bus2, concurrent=True
        ).run(steps=3))

        assert result_con.steps_completed == 3
        assert result_con.total_messages >= 1  # at least the initial message
        assert a2.step_count == 3
        assert b2.step_count == 3

    def test_concurrent_runner_handles_errors(self):
        """Concurrent runner handles agent errors without crashing."""
        class FailingAgent(Agent):
            async def step(self):
                raise RuntimeError("agent error")

        class GoodAgent(Agent):
            async def step(self):
                self.increment_step()
                return []

        a = FailingAgent(name="fail")
        b = GoodAgent(name="good")
        sandbox = Sandbox(agents=[a, b])
        bus = MessageBus()
        bus.register(a)
        bus.register(b)

        runner = ScenarioRunner(sandbox=sandbox, bus=bus, concurrent=True)
        result = await_call(runner.run(steps=2))
        assert result.steps_completed == 2
        assert b.step_count == 2


# ======================================================================
# CSV Export
# ======================================================================

class TestCSVExport:
    def test_export_to_csv(self):
        """export_messages_to_csv creates valid CSV file."""
        messages = [
            Message(sender="a", receiver="b", content="hello", msg_type=MessageType.DIRECT),
            Message(sender="b", receiver="a", content="world", msg_type=MessageType.RESPONSE),
        ]

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name

        try:
            result = export_messages_to_csv(messages, path)
            assert result.exists()
            content = result.read_text()
            assert "sender" in content
            assert "a" in content
            assert "hello" in content
            assert "world" in content
        finally:
            os.unlink(path)

    def test_export_empty_csv(self):
        """export_messages_to_csv handles empty message list."""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name

        try:
            result = export_messages_to_csv([], path)
            content = result.read_text()
            assert "timestamp" in content  # header only
        finally:
            os.unlink(path)


# ======================================================================
# Message correlation_id
# ======================================================================

class TestMessageCorrelationId:
    def test_message_has_correlation_id_field(self):
        """Message model supports correlation_id field."""
        msg = Message(sender="a", content="test", correlation_id="abc123")
        assert msg.correlation_id == "abc123"

    def test_message_default_correlation_id_is_none(self):
        """Message correlation_id defaults to None."""
        msg = Message(sender="a", content="test")
        assert msg.correlation_id is None

    def test_message_round_trip_with_correlation(self):
        """Message can be serialized and deserialized with correlation_id."""
        msg = Message(sender="a", content="test", correlation_id="cid1")
        data = msg.model_dump()
        restored = Message(**data)
        assert restored.correlation_id == "cid1"
