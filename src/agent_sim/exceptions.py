"""Agent Sim 自定义异常层次结构。

所有框架异常继承自 AgentSimError，方便用户统一捕获。

Exception Hierarchy:
    AgentSimError
    ├── ConfigError
    │   ├── ScenarioFileNotFoundError
    │   └── ConfigValidationError
    ├── AgentError
    │   ├── AgentNotFoundError
    │   ├── AgentTypeError
    │   └── AgentAlreadyExistsError
    ├── CommunicationError
    │   └── AgentNotRegisteredError
    ├── TopologyError
    ├── SandboxError
    ├── TemplateError
    ├── ProtocolError
    ├── SimulationError
    │   └── SimulationTimeout
    └── LLMError
"""
from __future__ import annotations


class AgentSimError(Exception):
    """Agent Sim 框架基础异常。"""


# --- 配置相关 ---
class ConfigError(AgentSimError):
    """场景配置相关错误。"""


class ScenarioFileNotFoundError(ConfigError, FileNotFoundError):
    """场景文件不存在。"""


class ConfigValidationError(ConfigError, ValueError):
    """配置验证失败。"""


# --- Agent 相关 ---
class AgentError(AgentSimError):
    """Agent 相关错误。"""


class AgentNotFoundError(AgentError, KeyError):
    """Agent 不存在。"""


class AgentTypeError(AgentError, ValueError):
    """Agent 类型错误或不支持。"""


class AgentAlreadyExistsError(AgentError, ValueError):
    """Agent 已存在（重复注册/添加）。"""


# --- 通信相关 ---
class CommunicationError(AgentSimError):
    """通信总线相关错误。"""


class AgentNotRegisteredError(CommunicationError, KeyError):
    """Agent 未在通信总线注册。"""


# --- 拓扑相关 ---
class TopologyError(AgentSimError, ValueError):
    """网络拓扑相关错误。"""


# --- 沙箱相关 ---
class SandboxError(AgentSimError):
    """环境沙箱相关错误。"""


# --- 模板相关 ---
class TemplateError(AgentSimError, KeyError):
    """场景模板相关错误。"""


# --- 协议相关 ---
class ProtocolError(AgentSimError, ValueError):
    """通信协议相关错误。"""


# --- 仿真运行时 ---
class SimulationError(AgentSimError):
    """仿真运行时错误。"""


class SimulationTimeout(SimulationError):
    """仿真超时。"""


# --- LLM 后端 ---
class LLMError(AgentSimError, ValueError, RuntimeError):
    """LLM 后端调用错误。"""


__all__ = [
    "AgentSimError",
    "ConfigError",
    "ScenarioFileNotFoundError",
    "ConfigValidationError",
    "AgentError",
    "AgentNotFoundError",
    "AgentTypeError",
    "AgentAlreadyExistsError",
    "CommunicationError",
    "AgentNotRegisteredError",
    "TopologyError",
    "SandboxError",
    "TemplateError",
    "ProtocolError",
    "SimulationError",
    "SimulationTimeout",
    "LLMError",
]
