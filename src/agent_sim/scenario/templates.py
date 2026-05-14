"""Built-in scenario templates for common multi-agent patterns."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# Template registry
_TEMPLATES: dict[str, dict[str, Any]] = {}


def _register_template(name: str, template: dict[str, Any]) -> None:
    """Register a scenario template."""
    _TEMPLATES[name] = template


def get_template(name: str) -> dict[str, Any]:
    """Get a scenario template by name.

    Args:
        name: Template name

    Returns:
        Template dict (deep copy)

    Raises:
        KeyError: Template not found
    """
    import copy
    if name not in _TEMPLATES:
        raise KeyError(f"Template '{name}' not found. Available: {list_templates()}")
    return copy.deepcopy(_TEMPLATES[name])


def list_templates() -> list[str]:
    """List all available template names."""
    return sorted(_TEMPLATES.keys())


def template_info(name: str) -> dict[str, str]:
    """Get template metadata.

    Args:
        name: Template name

    Returns:
        Dict with name, description, agents info
    """
    t = get_template(name)
    return {
        "name": t.get("name", name),
        "description": t.get("description", ""),
        "agents": str(len(t.get("agents", []))),
        "steps": str(t.get("steps", 10)),
    }


def save_template_to_yaml(name: str, path: str | Path) -> Path:
    """Save a template to a YAML file.

    Args:
        name: Template name
        path: Output file path

    Returns:
        Path to the written file
    """
    template = get_template(name)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(template, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    logger.info("模板 '%s' 已保存到 %s", name, path)
    return path


# ── Built-in templates ──────────────────────────────────────────

_register_template("ping_pong", {
    "name": "ping-pong",
    "description": "Ping-Pong 通信测试 — 两个 Agent 互相发送消息",
    "steps": 5,
    "agents": [
        {
            "name": "pinger",
            "type": "ping",
            "role": "sender",
            "goals": ["发送 ping 并接收 pong"],
            "context": {"targets": ["ponger"]},
        },
        {
            "name": "ponger",
            "type": "echo",
            "role": "receiver",
            "goals": ["接收消息并回复"],
        },
    ],
    "connections": [
        {"from_agent": "pinger", "to_agent": "ponger", "topic": "ping"},
    ],
})

_register_template("debate", {
    "name": "debate",
    "description": "结构化辩论场景 — 正反方围绕主题辩论",
    "steps": 6,
    "agents": [
        {
            "name": "moderator",
            "type": "collaborate",
            "role": "moderator",
            "goals": ["主持辩论", "总结观点"],
            "context": {"mode": "moderator"},
        },
        {
            "name": "proponent",
            "type": "debate",
            "role": "proponent",
            "goals": ["支持论点", "反驳对方"],
            "context": {"stance": "support", "topic": "AI regulation"},
        },
        {
            "name": "opponent",
            "type": "debate",
            "role": "opponent",
            "goals": ["反对论点", "反驳对方"],
            "context": {"stance": "oppose", "topic": "AI regulation"},
        },
    ],
    "connections": [
        {"from_agent": "moderator", "to_agent": "proponent", "topic": "开始辩论"},
        {"from_agent": "moderator", "to_agent": "opponent", "topic": "开始辩论"},
    ],
})

_register_template("brainstorm", {
    "name": "brainstorm",
    "description": "头脑风暴场景 — 多个 Agent 提出想法，协调者汇总",
    "steps": 5,
    "agents": [
        {
            "name": "facilitator",
            "type": "collaborate",
            "role": "facilitator",
            "goals": ["引导讨论", "汇总想法"],
            "context": {"mode": "moderator"},
        },
        {
            "name": "thinker_1",
            "type": "echo",
            "role": "thinker",
            "goals": ["提出创新想法"],
            "context": {"style": "creative"},
        },
        {
            "name": "thinker_2",
            "type": "echo",
            "role": "thinker",
            "goals": ["提出实用想法"],
            "context": {"style": "practical"},
        },
        {
            "name": "thinker_3",
            "type": "echo",
            "role": "thinker",
            "goals": ["提出批判性想法"],
            "context": {"style": "critical"},
        },
    ],
    "connections": [
        {"from_agent": "facilitator", "topic": "请提出关于提升团队效率的想法"},
    ],
})

_register_template("code_review", {
    "name": "code_review",
    "description": "代码审查场景 — 提交者提交代码，审查者提出反馈",
    "steps": 4,
    "agents": [
        {
            "name": "author",
            "type": "echo",
            "role": "developer",
            "goals": ["提交代码", "回应审查反馈"],
            "context": {"code_snippet": "def hello(): print('world')"},
        },
        {
            "name": "reviewer",
            "type": "echo",
            "role": "reviewer",
            "goals": ["审查代码", "提出改进建议"],
        },
        {
            "name": "approver",
            "type": "collaborate",
            "role": "tech_lead",
            "goals": ["最终审批"],
            "context": {"mode": "moderator"},
        },
    ],
    "connections": [
        {"from_agent": "author", "to_agent": "reviewer", "topic": "请审查此PR"},
    ],
})

_register_template("task_delegation", {
    "name": "task_delegation",
    "description": "任务分配场景 — 协调者分配任务给工作者并收集结果",
    "steps": 6,
    "agents": [
        {
            "name": "coordinator",
            "type": "ping",
            "role": "coordinator",
            "goals": ["分配任务", "收集结果", "汇总报告"],
            "context": {"targets": ["worker_1", "worker_2", "worker_3"]},
        },
        {
            "name": "worker_1",
            "type": "echo",
            "role": "worker",
            "goals": ["执行任务A"],
        },
        {
            "name": "worker_2",
            "type": "echo",
            "role": "worker",
            "goals": ["执行任务B"],
        },
        {
            "name": "worker_3",
            "type": "echo",
            "role": "worker",
            "goals": ["执行任务C"],
        },
    ],
    "connections": [
        {"from_agent": "coordinator", "to_agent": "worker_1", "topic": "任务A"},
        {"from_agent": "coordinator", "to_agent": "worker_2", "topic": "任务B"},
        {"from_agent": "coordinator", "to_agent": "worker_3", "topic": "任务C"},
    ],
})

_register_template("multi_round_discussion", {
    "name": "multi_round_discussion",
    "description": "多轮讨论场景 — 多个 Agent 轮流发言并回应",
    "steps": 8,
    "agents": [
        {
            "name": "facilitator",
            "type": "collaborate",
            "role": "facilitator",
            "goals": ["引导讨论", "确保每人发言"],
            "context": {"mode": "moderator"},
        },
        {
            "name": "expert_a",
            "type": "echo",
            "role": "domain_expert",
            "goals": ["提供专业见解"],
        },
        {
            "name": "expert_b",
            "type": "echo",
            "role": "domain_expert",
            "goals": ["提供不同视角"],
        },
    ],
    "connections": [
        {"from_agent": "facilitator", "topic": "请讨论未来技术趋势"},
    ],
})
