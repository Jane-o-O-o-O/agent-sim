"""Declarative scenario configuration models for YAML-based scenario definitions."""
from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from agent_sim.exceptions import ConfigValidationError, ScenarioFileNotFoundError

logger = logging.getLogger(__name__)


class AgentConfig(BaseModel):
    """Agent 配置模型。

    在 YAML 场景文件中定义单个 Agent 的配置。

    Attributes:
        name: Agent 唯一名称
        type: Agent 类型 (echo, ping, llm, tool, custom)
        role: 角色名称
        goals: 目标列表
        context: 运行时上下文
        module: 自定义 Agent 类的模块路径 (type=custom 时使用)
        class_name: 自定义 Agent 类名 (type=custom 时使用)
    """

    name: str
    type: str = "echo"
    role: str = "default"
    goals: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)
    module: str | None = None
    class_name: str | None = None
    llm_backend: str | None = None
    llm_model: str | None = None
    tools: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Agent 名称不能为空。"""
        if not v.strip():
            raise ValueError("Agent 名称不能为空")
        return v.strip()

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        """验证 Agent 类型。"""
        valid_types = {"echo", "ping", "llm", "tool", "debate", "collaborate", "memory", "custom"}
        if v not in valid_types:
            raise ValueError(f"不支持的 Agent 类型: {v}，可选: {valid_types}")
        return v


class ConnectionConfig(BaseModel):
    """连接配置模型。

    定义 Agent 之间的通信连接。

    Attributes:
        from_agent: 发送方 Agent 名称
        to_agent: 接收方 Agent 名称 (None 表示广播)
        topic: 消息主题 (可选)
    """

    from_agent: str
    to_agent: str | None = None
    topic: str | None = None


class ScenarioConfig(BaseModel):
    """场景声明式配置模型。

    可从 YAML 文件加载，定义完整的仿真场景。
    支持 extends 字段实现场景继承。

    Attributes:
        name: 场景名称
        description: 场景描述
        steps: 仿真步数
        agents: Agent 配置列表
        connections: Agent 间连接配置
        metadata: 附加元数据

    Example:
        >>> config = ScenarioConfig(
        ...     name="ping-pong",
        ...     description="Ping-Pong 通信测试",
        ...     steps=5,
        ...     agents=[
        ...         AgentConfig(name="pinger", type="ping", context={"targets": ["ponger"]}),
        ...         AgentConfig(name="ponger", type="echo"),
        ...     ],
        ... )
    """

    name: str = "unnamed"
    description: str = ""
    steps: int = Field(default=10, ge=1, le=10000)
    agents: list[AgentConfig] = Field(default_factory=list)
    connections: list[ConnectionConfig] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("agents")
    @classmethod
    def unique_agent_names(cls, v: list[AgentConfig]) -> list[AgentConfig]:
        """Agent 名称必须唯一。"""
        names = [a.name for a in v]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"Agent 名称重复: {dupes}")
        return v

    @property
    def agent_names(self) -> list[str]:
        """所有 Agent 名称列表。"""
        return [a.name for a in self.agents]


def _merge_configs(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """合并基础配置和覆盖配置。

    覆盖规则：
    - 顶层标量字段：子配置覆盖父配置
    - agents 列表：子配置完全替换父配置
    - connections 列表：子配置完全替换父配置
    - metadata 字典：合并，子配置的值覆盖父配置

    Args:
        base: 基础配置字典
        override: 覆盖配置字典

    Returns:
        合并后的配置字典
    """
    result = copy.deepcopy(base)

    for key, value in override.items():
        if key == "agents":
            # agents 列表完全替换
            result["agents"] = value
        elif key == "connections":
            # connections 列表完全替换
            result["connections"] = value
        elif key == "metadata" and isinstance(value, dict) and isinstance(result.get("metadata"), dict):
            # metadata 合并
            result["metadata"] = {**result["metadata"], **value}
        elif value is not None:
            result[key] = value

    return result


def _resolve_extends(data: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """解析 extends 字段，递归合并父配置。

    Args:
        data: 场景配置字典
        base_dir: 基准目录（用于解析相对路径）

    Returns:
        合并后的配置字典（不含 extends 字段）

    Raises:
        FileNotFoundError: 父配置文件不存在
        ValueError: 循环引用检测
    """
    extends = data.get("extends")
    if not extends:
        return data

    parent_path = base_dir / extends
    if not parent_path.exists():
        raise ScenarioFileNotFoundError(f"父场景文件不存在: {parent_path}")

    logger.info("加载父场景: %s", parent_path)
    with open(parent_path) as f:
        parent_data = yaml.safe_load(f)

    if not isinstance(parent_data, dict):
        raise ValueError(f"父场景文件格式错误: {parent_path}")

    # 递归解析父配置的 extends
    parent_data = _resolve_extends(parent_data, parent_path.parent)

    # 合并：子配置覆盖父配置
    merged = _merge_configs(parent_data, data)
    # 移除 extends 字段，不再需要
    merged.pop("extends", None)

    return merged


def load_scenario(path: str | Path) -> ScenarioConfig:
    """从 YAML 文件加载场景配置。

    支持 extends 字段实现场景继承。子配置可以覆盖父配置的
    steps、name 等字段，agents 列表完全替换。

    Args:
        path: YAML 文件路径

    Returns:
        ScenarioConfig 实例

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: YAML 格式错误或配置验证失败

    Example:
        >>> config = load_scenario("scenarios/ping_pong.yaml")
        >>> print(config.name, config.steps)
    """
    path = Path(path)
    if not path.exists():
        raise ScenarioFileNotFoundError(f"场景文件不存在: {path}")

    logger.info("加载场景配置: %s", path)

    with open(path) as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigValidationError(f"YAML 解析错误: {e}") from e

    if not isinstance(data, dict):
        raise ConfigValidationError(f"场景文件格式错误: 顶层应为字典，实际为 {type(data).__name__}")

    # 解析 extends 继承
    data = _resolve_extends(data, path.parent)

    try:
        config = ScenarioConfig(**data)
    except Exception as e:
        raise ConfigValidationError(f"场景配置验证失败: {e}") from e

    logger.info(
        "场景加载成功: name=%s, agents=%d, steps=%d",
        config.name, len(config.agents), config.steps,
    )
    return config
