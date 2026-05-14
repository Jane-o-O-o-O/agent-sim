"""Configuration validation and schema utilities.

Provides:
- validate_scenario(): detailed validation with clear error messages
- config_schema(): JSON Schema export for YAML config files
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from agent_sim.exceptions import ConfigValidationError
from agent_sim.scenario.config import AgentConfig, ScenarioConfig


def validate_scenario(path: str | Path) -> list[str]:
    """Validate a scenario YAML file with detailed error reporting.

    Unlike load_scenario(), this returns ALL errors at once instead of
    failing on the first one.

    Args:
        path: YAML file path

    Returns:
        List of error descriptions (empty = valid)
    """
    path = Path(path)
    errors: list[str] = []

    if not path.exists():
        return [f"文件不存在: {path}"]

    if not path.suffix in (".yaml", ".yml"):
        errors.append(f"警告: 文件扩展名 {path.suffix} 不是 YAML (.yaml/.yml)")

    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return [f"YAML 语法错误: {e}"]

    if not isinstance(data, dict):
        return [f"顶层结构应为字典，实际为 {type(data).__name__}"]

    # Required fields
    if "name" not in data:
        errors.append("缺少必填字段: name")
    elif not isinstance(data["name"], str) or not data["name"].strip():
        errors.append("name 必须是非空字符串")

    if "agents" not in data:
        errors.append("缺少必填字段: agents (至少需要一个 Agent)")
    elif not isinstance(data["agents"], list):
        errors.append(f"agents 应为列表，实际为 {type(data['agents']).__name__}")
    elif len(data["agents"]) == 0:
        errors.append("agents 列表为空 — 至少需要一个 Agent")
    else:
        # Validate each agent
        names = []
        for i, agent_data in enumerate(data["agents"]):
            prefix = f"agents[{i}]"
            if not isinstance(agent_data, dict):
                errors.append(f"{prefix}: 应为字典")
                continue

            name = agent_data.get("name", "")
            if not name or not isinstance(name, str) or not name.strip():
                errors.append(f"{prefix}: 缺少 name 字段或 name 为空")
            else:
                if name in names:
                    errors.append(f"{prefix}: Agent 名称 '{name}' 重复")
                names.append(name)

            agent_type = agent_data.get("type", "echo")
            valid_types = {"echo", "ping", "llm", "tool", "debate", "collaborate", "memory", "custom"}
            if agent_type not in valid_types:
                errors.append(f"{prefix} ({name}): 不支持的类型 '{agent_type}'，可选: {valid_types}")

            if agent_type == "custom":
                if not agent_data.get("module"):
                    errors.append(f"{prefix} ({name}): type=custom 但缺少 module")
                if not agent_data.get("class_name"):
                    errors.append(f"{prefix} ({name}): type=custom 但缺少 class_name")

    # Optional fields validation
    steps = data.get("steps", 10)
    if not isinstance(steps, int) or steps < 1:
        errors.append(f"steps 应为正整数，实际为: {steps}")
    elif steps > 10000:
        errors.append(f"steps={steps} 过大 (最大 10000)")

    connections = data.get("connections", [])
    if not isinstance(connections, list):
        errors.append(f"connections 应为列表，实际为 {type(connections).__name__}")
    else:
        agent_names = set()
        if isinstance(data.get("agents"), list):
            for a in data["agents"]:
                if isinstance(a, dict) and a.get("name"):
                    agent_names.add(a["name"])

        for i, conn in enumerate(connections):
            if not isinstance(conn, dict):
                errors.append(f"connections[{i}]: 应为字典")
                continue
            from_agent = conn.get("from_agent", "")
            if not from_agent:
                errors.append(f"connections[{i}]: 缺少 from_agent")
            elif agent_names and from_agent not in agent_names:
                errors.append(f"connections[{i}]: from_agent '{from_agent}' 不在 agents 列表中")

            to_agent = conn.get("to_agent")
            if to_agent and agent_names and to_agent not in agent_names:
                errors.append(f"connections[{i}]: to_agent '{to_agent}' 不在 agents 列表中")

    return errors


def config_schema() -> dict[str, Any]:
    """Export ScenarioConfig as JSON Schema.

    Returns:
        JSON Schema dict describing the YAML configuration format
    """
    schema = ScenarioConfig.model_json_schema()

    # Add human-readable descriptions
    schema["$schema"] = "http://json-schema.org/draft-07/schema#"
    schema["title"] = "Agent Sim Scenario Configuration"
    schema["description"] = (
        "声明式场景配置文件格式。定义多智能体仿真的 Agent、连接和参数。"
    )

    return schema


def config_schema_yaml() -> str:
    """Export config schema as YAML string.

    Returns:
        YAML-formatted JSON Schema string
    """
    schema = config_schema()
    return yaml.dump(schema, default_flow_style=False, allow_unicode=True, sort_keys=False)


def config_schema_json(indent: int = 2) -> str:
    """Export config schema as JSON string.

    Args:
        indent: JSON indentation (default 2)

    Returns:
        JSON-formatted schema string
    """
    import json
    return json.dumps(config_schema(), indent=indent, ensure_ascii=False)
