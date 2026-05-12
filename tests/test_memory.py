"""Tests for memory subsystem."""
from __future__ import annotations

import pytest

from agent_sim.memory.buffer import ConversationBuffer, SlidingWindowBuffer
from agent_sim.memory.facts import Fact, KeyFactMemory


# ────────────────────── ConversationBuffer ──────────────────────


class TestConversationBuffer:
    """ConversationBuffer 测试。"""

    def test_create_default(self) -> None:
        buf = ConversationBuffer()
        assert buf.size == 0
        assert buf.max_size == 0

    def test_create_with_max(self) -> None:
        buf = ConversationBuffer(max_size=50)
        assert buf.max_size == 50

    def test_add_and_get(self) -> None:
        buf = ConversationBuffer()
        buf.add("user", "hello")
        buf.add("assistant", "hi")
        msgs = buf.get_messages()
        assert len(msgs) == 2
        assert msgs[0] == {"role": "user", "content": "hello"}
        assert msgs[1] == {"role": "assistant", "content": "hi"}

    def test_add_with_metadata(self) -> None:
        buf = ConversationBuffer()
        buf.add("user", "hello", source="web")
        msgs = buf.get_messages()
        assert msgs[0]["metadata"] == {"source": "web"}

    def test_max_size_eviction(self) -> None:
        buf = ConversationBuffer(max_size=3)
        buf.add("user", "msg1")
        buf.add("assistant", "reply1")
        buf.add("user", "msg2")
        buf.add("assistant", "reply2")  # should evict msg1
        assert buf.size == 3
        contents = [m["content"] for m in buf.get_messages()]
        assert "msg1" not in contents

    def test_max_size_preserves_system(self) -> None:
        buf = ConversationBuffer(max_size=2)
        buf.add("system", "You are helpful")
        buf.add("user", "msg1")
        buf.add("assistant", "reply1")  # should evict msg1, not system
        msgs = buf.get_messages()
        assert msgs[0]["role"] == "system"

    def test_clear(self) -> None:
        buf = ConversationBuffer()
        buf.add("system", "sys")
        buf.add("user", "hello")
        buf.add("assistant", "hi")
        buf.clear()
        assert buf.size == 1
        assert buf.get_messages()[0]["role"] == "system"

    def test_str(self) -> None:
        buf = ConversationBuffer(max_size=10)
        buf.add("user", "test")
        assert "size=1" in str(buf)
        assert "max=10" in str(buf)


# ────────────────────── SlidingWindowBuffer ──────────────────────


class TestSlidingWindowBuffer:
    """SlidingWindowBuffer 测试。"""

    def test_create(self) -> None:
        buf = SlidingWindowBuffer(window_size=5)
        assert buf.window_size == 5
        assert buf.size == 0

    def test_invalid_window_size(self) -> None:
        with pytest.raises(ValueError, match="window_size"):
            SlidingWindowBuffer(window_size=0)

    def test_system_messages_preserved(self) -> None:
        buf = SlidingWindowBuffer(window_size=2)
        buf.add("system", "You are helpful")
        buf.add("user", "msg1")
        buf.add("assistant", "reply1")
        buf.add("user", "msg2")
        buf.add("assistant", "reply2")  # exceeds window, msg1 evicted
        msgs = buf.get_messages()
        assert len(msgs) == 3  # system + 2 window
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "You are helpful"

    def test_window_slides(self) -> None:
        buf = SlidingWindowBuffer(window_size=2)
        buf.add("user", "msg1")
        buf.add("assistant", "reply1")
        buf.add("user", "msg2")
        buf.add("assistant", "reply2")
        msgs = buf.get_messages()
        contents = [m["content"] for m in msgs]
        assert "msg1" not in contents
        assert "msg2" in contents

    def test_clear_preserves_system(self) -> None:
        buf = SlidingWindowBuffer(window_size=5)
        buf.add("system", "sys")
        buf.add("user", "hello")
        buf.clear()
        assert buf.size == 1
        assert buf.get_messages()[0]["role"] == "system"

    def test_str(self) -> None:
        buf = SlidingWindowBuffer(window_size=3)
        assert "window=3" in str(buf)


# ────────────────────── KeyFactMemory ──────────────────────


class TestKeyFactMemory:
    """KeyFactMemory 测试。"""

    def test_create(self) -> None:
        mem = KeyFactMemory()
        assert mem.size == 0
        assert len(mem) == 0

    def test_remember_and_recall(self) -> None:
        mem = KeyFactMemory()
        mem.remember("user_name", "Alice", source="dialogue")
        assert mem.recall("user_name") == "Alice"

    def test_recall_nonexistent(self) -> None:
        mem = KeyFactMemory()
        assert mem.recall("missing") is None

    def test_remember_update(self) -> None:
        mem = KeyFactMemory()
        mem.remember("key", "value1", confidence=0.5)
        mem.remember("key", "value2", confidence=0.8)
        assert mem.recall("key") == "value2"

    def test_remember_low_confidence_no_update(self) -> None:
        mem = KeyFactMemory()
        mem.remember("key", "value1", confidence=0.8)
        mem.remember("key", "value2", confidence=0.3)  # lower, should not update
        assert mem.recall("key") == "value1"

    def test_forget(self) -> None:
        mem = KeyFactMemory()
        mem.remember("key", "value")
        assert mem.forget("key") is True
        assert mem.recall("key") is None
        assert mem.forget("missing") is False

    def test_search(self) -> None:
        mem = KeyFactMemory()
        mem.remember("user_name", "Alice")
        mem.remember("user_age", "30")
        mem.remember("color", "blue")
        results = mem.search("user")
        assert len(results) == 2

    def test_search_confidence_filter(self) -> None:
        mem = KeyFactMemory()
        mem.remember("key1", "hello", confidence=0.9)
        mem.remember("key2", "hello world", confidence=0.3)
        results = mem.search("hello", min_confidence=0.5)
        assert len(results) == 1

    def test_get_all(self) -> None:
        mem = KeyFactMemory()
        mem.remember("a", "1")
        mem.remember("b", "2")
        all_facts = mem.get_all()
        assert all_facts == {"a": "1", "b": "2"}

    def test_max_facts_lru_eviction(self) -> None:
        mem = KeyFactMemory(max_facts=2)
        import time
        mem.remember("a", "1")
        time.sleep(0.01)
        mem.remember("b", "2")
        time.sleep(0.01)
        mem.remember("c", "3")  # should evict "a" (least recently accessed)
        assert mem.recall("a") is None
        assert mem.size == 2

    def test_clear(self) -> None:
        mem = KeyFactMemory()
        mem.remember("a", "1")
        mem.remember("b", "2")
        mem.clear()
        assert mem.size == 0

    def test_keys(self) -> None:
        mem = KeyFactMemory()
        mem.remember("x", "1")
        mem.remember("y", "2")
        assert set(mem.keys) == {"x", "y"}

    def test_stats_empty(self) -> None:
        mem = KeyFactMemory()
        stats = mem.stats()
        assert stats["count"] == 0

    def test_stats_with_facts(self) -> None:
        mem = KeyFactMemory()
        mem.remember("a", "1", confidence=0.8)
        mem.remember("b", "2", confidence=0.6)
        mem.recall("a")
        mem.recall("a")
        stats = mem.stats()
        assert stats["count"] == 2
        assert stats["total_accesses"] == 2
        assert stats["most_accessed"] == "a"

    def test_access_count(self) -> None:
        mem = KeyFactMemory()
        mem.remember("key", "value")
        mem.recall("key")
        mem.recall("key")
        # Access count should be 2 (verified via stats)
        assert mem.stats()["total_accesses"] == 2

    def test_str(self) -> None:
        mem = KeyFactMemory(max_facts=10)
        mem.remember("a", "1")
        assert "facts=1" in str(mem)

    def test_fact_model(self) -> None:
        fact = Fact(key="test", value="val", confidence=0.9)
        assert fact.key == "test"
        assert fact.confidence == 0.9
        assert fact.access_count == 0
