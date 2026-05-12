"""Lifecycle hooks for simulation events."""
from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

logger = logging.getLogger(__name__)

# 回调类型
HookCallback = Callable[..., Awaitable[None] | None]


class LifecycleHooks:
    """仿真生命周期钩子管理器。

    支持在仿真关键节点注册回调函数，用于日志、监控、自定义逻辑等。

    支持的钩子事件:
        - on_simulation_start: 仿真开始前
        - on_simulation_end: 仿真结束后
        - on_step_start: 每步开始前
        - on_step_end: 每步结束后
        - on_message: 消息发送时
        - on_agent_error: Agent 执行出错时
        - on_agent_state_change: Agent 状态变化时

    Example:
        >>> hooks = LifecycleHooks()
        >>> hooks.on_step_end(lambda step, msgs: print(f"Step {step}: {msgs} msgs"))
        >>> await hooks.trigger("on_step_end", step=1, messages=5)
    """

    def __init__(self) -> None:
        self._hooks: dict[str, list[HookCallback]] = {}

    def register(self, event: str, callback: HookCallback) -> None:
        """注册钩子回调。

        Args:
            event: 事件名称
            callback: 回调函数（可以是同步或异步）
        """
        if event not in self._hooks:
            self._hooks[event] = []
        self._hooks[event].append(callback)
        logger.debug("注册钩子: %s -> %s", event, callback.__name__)

    def on_simulation_start(self, callback: HookCallback) -> None:
        """注册仿真开始钩子。"""
        self.register("on_simulation_start", callback)

    def on_simulation_end(self, callback: HookCallback) -> None:
        """注册仿真结束钩子。"""
        self.register("on_simulation_end", callback)

    def on_step_start(self, callback: HookCallback) -> None:
        """注册步骤开始钩子。"""
        self.register("on_step_start", callback)

    def on_step_end(self, callback: HookCallback) -> None:
        """注册步骤结束钩子。"""
        self.register("on_step_end", callback)

    def on_message(self, callback: HookCallback) -> None:
        """注册消息钩子。"""
        self.register("on_message", callback)

    def on_agent_error(self, callback: HookCallback) -> None:
        """注册 Agent 错误钩子。"""
        self.register("on_agent_error", callback)

    def on_agent_state_change(self, callback: HookCallback) -> None:
        """注册 Agent 状态变化钩子。"""
        self.register("on_agent_state_change", callback)

    async def trigger(self, event: str, **kwargs: Any) -> None:
        """触发事件钩子。

        Args:
            event: 事件名称
            **kwargs: 传递给回调的参数
        """
        callbacks = self._hooks.get(event, [])
        for callback in callbacks:
            try:
                result = callback(**kwargs)
                # 支持异步回调
                if hasattr(result, "__await__"):
                    await result
            except Exception as e:
                logger.error("钩子 %s (%s) 执行失败: %s", event, callback.__name__, e)

    def clear(self, event: str | None = None) -> None:
        """清除钩子。

        Args:
            event: 指定事件名清除，None 清除所有
        """
        if event:
            self._hooks.pop(event, None)
        else:
            self._hooks.clear()

    @property
    def event_names(self) -> list[str]:
        """已注册的事件名列表。"""
        return list(self._hooks.keys())

    def __str__(self) -> str:
        total = sum(len(cbs) for cbs in self._hooks.values())
        return f"LifecycleHooks(events={len(self._hooks)}, callbacks={total})"
