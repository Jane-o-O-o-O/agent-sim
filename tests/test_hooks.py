"""Tests for lifecycle hooks."""
from __future__ import annotations

import asyncio
import pytest

from agent_sim.scenario.hooks import LifecycleHooks


class TestLifecycleHooks:
    """生命周期钩子测试。"""

    def test_create_hooks(self) -> None:
        hooks = LifecycleHooks()
        assert hooks.event_names == []

    def test_register_callback(self) -> None:
        hooks = LifecycleHooks()
        hooks.on_simulation_start(lambda steps, agent_count: None)
        assert "on_simulation_start" in hooks.event_names

    def test_register_multiple_callbacks(self) -> None:
        hooks = LifecycleHooks()
        hooks.on_step_end(lambda step, messages_sent: None)
        hooks.on_step_end(lambda step, messages_sent: None)
        assert len(hooks._hooks["on_step_end"]) == 2

    @pytest.mark.asyncio
    async def test_trigger_sync_callback(self) -> None:
        called = []
        hooks = LifecycleHooks()
        hooks.on_step_start(lambda step: called.append(step))
        await hooks.trigger("on_step_start", step=1)
        assert called == [1]

    @pytest.mark.asyncio
    async def test_trigger_async_callback(self) -> None:
        called = []
        hooks = LifecycleHooks()

        async def my_hook(step: int) -> None:
            called.append(step)

        hooks.on_step_start(my_hook)
        await hooks.trigger("on_step_start", step=1)
        assert called == [1]

    @pytest.mark.asyncio
    async def test_trigger_no_callbacks(self) -> None:
        hooks = LifecycleHooks()
        # Should not raise
        await hooks.trigger("on_step_start", step=1)

    @pytest.mark.asyncio
    async def test_trigger_with_kwargs(self) -> None:
        captured = {}
        hooks = LifecycleHooks()

        def capture(**kwargs: object) -> None:
            captured.update(kwargs)

        hooks.on_simulation_start(capture)
        await hooks.trigger("on_simulation_start", steps=10, agent_count=3)
        assert captured == {"steps": 10, "agent_count": 3}

    @pytest.mark.asyncio
    async def test_callback_error_does_not_propagate(self) -> None:
        """回调异常不应阻断后续回调执行。"""
        results = []
        hooks = LifecycleHooks()
        hooks.on_step_end(lambda step, messages_sent: 1 / 0)  # type: ignore
        hooks.on_step_end(lambda step, messages_sent: results.append("ok"))
        await hooks.trigger("on_step_end", step=1, messages_sent=5)
        assert results == ["ok"]

    def test_clear_specific_event(self) -> None:
        hooks = LifecycleHooks()
        hooks.on_step_start(lambda step: None)
        hooks.on_step_end(lambda step, messages_sent: None)
        hooks.clear("on_step_start")
        assert "on_step_start" not in hooks.event_names
        assert "on_step_end" in hooks.event_names

    def test_clear_all(self) -> None:
        hooks = LifecycleHooks()
        hooks.on_step_start(lambda step: None)
        hooks.on_step_end(lambda step, messages_sent: None)
        hooks.clear()
        assert hooks.event_names == []

    def test_str_repr(self) -> None:
        hooks = LifecycleHooks()
        hooks.on_step_start(lambda step: None)
        hooks.on_step_end(lambda step, messages_sent: None)
        s = str(hooks)
        assert "events=2" in s
        assert "callbacks=2" in s

    def test_convenience_methods(self) -> None:
        hooks = LifecycleHooks()
        hooks.on_simulation_start(lambda **kw: None)
        hooks.on_simulation_end(lambda **kw: None)
        hooks.on_step_start(lambda **kw: None)
        hooks.on_step_end(lambda **kw: None)
        hooks.on_message(lambda **kw: None)
        hooks.on_agent_error(lambda **kw: None)
        hooks.on_agent_state_change(lambda **kw: None)
        assert len(hooks.event_names) == 7
