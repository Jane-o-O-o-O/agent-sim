"""Plugin registry for extensible agent and evaluator types."""
from __future__ import annotations

import importlib
import logging
import sys
from typing import Any, Type

logger = logging.getLogger(__name__)


class PluginInfo:
    """插件信息。

    Attributes:
        name: 插件名称
        plugin_type: 插件类型 (agent/evaluator/middleware)
        cls: 插件类
        module: 来源模块
        description: 描述
    """

    def __init__(
        self,
        name: str,
        plugin_type: str,
        cls: type,
        module: str = "",
        description: str = "",
    ) -> None:
        self.name = name
        self.plugin_type = plugin_type
        self.cls = cls
        self.module = module
        self.description = description

    def __repr__(self) -> str:
        return f"PluginInfo({self.name}, type={self.plugin_type})"


class PluginRegistry:
    """插件注册表。

    管理可扩展的 Agent、Evaluator、Middleware 类型注册。
    支持通过 entry_points 自动发现插件，也支持手动注册。

    Features:
        - 手动注册自定义类型
        - entry_points 自动发现
        - 按类型查询
        - 延迟加载

    Example:
        >>> registry = PluginRegistry()
        >>> registry.register_agent("my_agent", MyAgentClass)
        >>> registry.register_evaluator("my_eval", MyEvaluatorClass)
        >>> agents = registry.get_agents()
        >>> registry.discover()  # 从 entry_points 加载
    """

    def __init__(self) -> None:
        self._plugins: dict[str, PluginInfo] = {}
        self._discovered = False

    def register_agent(self, name: str, cls: type, description: str = "") -> None:
        """注册 Agent 类型。

        Args:
            name: 类型名称
            cls: Agent 子类
            description: 描述
        """
        self._plugins[name] = PluginInfo(
            name=name, plugin_type="agent", cls=cls,
            module=cls.__module__, description=description,
        )
        logger.debug("注册 Agent 插件: %s -> %s", name, cls.__name__)

    def register_evaluator(self, name: str, cls: type, description: str = "") -> None:
        """注册 Evaluator 类型。

        Args:
            name: 类型名称
            cls: Evaluator 子类
            description: 描述
        """
        self._plugins[name] = PluginInfo(
            name=name, plugin_type="evaluator", cls=cls,
            module=cls.__module__, description=description,
        )
        logger.debug("注册 Evaluator 插件: %s -> %s", name, cls.__name__)

    def register_middleware(self, name: str, cls: type, description: str = "") -> None:
        """注册 Middleware 类型。

        Args:
            name: 类型名称
            cls: Middleware 子类
            description: 描述
        """
        self._plugins[name] = PluginInfo(
            name=name, plugin_type="middleware", cls=cls,
            module=cls.__module__, description=description,
        )
        logger.debug("注册 Middleware 插件: %s -> %s", name, cls.__name__)

    def unregister(self, name: str) -> bool:
        """取消注册。

        Args:
            name: 插件名称

        Returns:
            是否成功取消
        """
        if name in self._plugins:
            del self._plugins[name]
            return True
        return False

    def get(self, name: str) -> PluginInfo | None:
        """获取插件信息。

        Args:
            name: 插件名称

        Returns:
            插件信息，不存在返回 None
        """
        return self._plugins.get(name)

    def get_class(self, name: str) -> type | None:
        """获取插件类。

        Args:
            name: 插件名称

        Returns:
            插件类，不存在返回 None
        """
        info = self._plugins.get(name)
        return info.cls if info else None

    def get_agents(self) -> list[PluginInfo]:
        """获取所有 Agent 插件。"""
        return [p for p in self._plugins.values() if p.plugin_type == "agent"]

    def get_evaluators(self) -> list[PluginInfo]:
        """获取所有 Evaluator 插件。"""
        return [p for p in self._plugins.values() if p.plugin_type == "evaluator"]

    def get_middlewares(self) -> list[PluginInfo]:
        """获取所有 Middleware 插件。"""
        return [p for p in self._plugins.values() if p.plugin_type == "middleware"]

    def get_all(self, plugin_type: str | None = None) -> list[PluginInfo]:
        """获取所有插件。

        Args:
            plugin_type: 可选的类型过滤

        Returns:
            插件列表
        """
        if plugin_type:
            return [p for p in self._plugins.values() if p.plugin_type == plugin_type]
        return list(self._plugins.values())

    def discover(self) -> int:
        """从 entry_points 自动发现插件。

        使用 importlib.metadata 查找注册为 "agent_sim.plugins" 的 entry_points。

        Returns:
            发现的插件数量
        """
        if self._discovered:
            return 0

        discovered = 0

        # Python 3.10+ 使用 importlib.metadata
        try:
            if sys.version_info >= (3, 10):
                from importlib.metadata import entry_points
                eps = entry_points(group="agent_sim.plugins")
            else:
                from importlib.metadata import entry_points
                eps = entry_points().get("agent_sim.plugins", [])

            for ep in eps:
                try:
                    cls = ep.load()
                    name = ep.name
                    # 根据类的基类判断类型
                    plugin_type = self._detect_type(cls)
                    self._plugins[name] = PluginInfo(
                        name=name, plugin_type=plugin_type, cls=cls,
                        module=cls.__module__,
                    )
                    discovered += 1
                    logger.info("发现插件: %s (%s)", name, plugin_type)
                except Exception as e:
                    logger.warning("加载插件 %s 失败: %s", ep.name, e)

        except ImportError:
            logger.debug("importlib.metadata 不可用")

        self._discovered = True
        return discovered

    @staticmethod
    def _detect_type(cls: type) -> str:
        """检测插件类型。

        Args:
            cls: 插件类

        Returns:
            类型字符串
        """
        # 尝试从基类名推断
        bases = [b.__name__ for b in cls.__mro__]
        if "Agent" in bases:
            return "agent"
        if "Evaluator" in bases:
            return "evaluator"
        if "MessageMiddleware" in bases:
            return "middleware"
        return "unknown"

    @property
    def count(self) -> int:
        """插件总数。"""
        return len(self._plugins)

    def summary(self) -> dict[str, Any]:
        """获取注册表摘要。

        Returns:
            摘要字典
        """
        agents = self.get_agents()
        evaluators = self.get_evaluators()
        middlewares = self.get_middlewares()
        return {
            "total": self.count,
            "agents": len(agents),
            "evaluators": len(evaluators),
            "middlewares": len(middlewares),
            "plugins": [
                {
                    "name": p.name,
                    "type": p.plugin_type,
                    "module": p.module,
                }
                for p in self._plugins.values()
            ],
        }

    def __str__(self) -> str:
        return f"PluginRegistry(agents={len(self.get_agents())}, evaluators={len(self.get_evaluators())}, middlewares={len(self.get_middlewares())})"
