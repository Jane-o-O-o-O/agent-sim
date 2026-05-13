"""Simulation checkpointing — save and restore simulation state.

Supports serializing agent states, message history, and environment state
to JSON for pause/resume functionality.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent_sim.agent.base import Agent, AgentState
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message
from agent_sim.environment.sandbox import Sandbox

logger = logging.getLogger(__name__)


class AgentSnapshot(BaseModel):
    """Agent 状态快照。"""

    name: str
    state: str
    step_count: int
    context: dict[str, Any] = Field(default_factory=dict)
    inbox: list[dict[str, Any]] = Field(default_factory=list)
    agent_type: str = ""


class Checkpoint(BaseModel):
    """仿真检查点。

    包含完整的仿真状态，可用于恢复运行。

    Attributes:
        version: 检查点格式版本
        timestamp: 创建时间戳
        step: 当前步数
        agents: Agent 快照列表
        message_history: 消息历史
        metadata: 附加元数据
    """

    version: int = 1
    timestamp: float = Field(default_factory=time.time)
    step: int = 0
    agents: list[AgentSnapshot] = Field(default_factory=list)
    message_history: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CheckpointManager:
    """检查点管理器。

    负责保存和恢复仿真状态。

    Example:
        >>> manager = CheckpointManager()
        >>> # 保存检查点
        >>> checkpoint = manager.create_checkpoint(sandbox, bus, step=5)
        >>> manager.save(checkpoint, "checkpoint.json")
        >>> # 恢复检查点
        >>> checkpoint = manager.load("checkpoint.json")
        >>> manager.restore(checkpoint, sandbox, bus)
    """

    def create_checkpoint(
        self,
        sandbox: Sandbox,
        bus: MessageBus,
        step: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> Checkpoint:
        """创建检查点。

        Args:
            sandbox: 仿真沙箱
            bus: 通信总线
            step: 当前步数
            metadata: 附加元数据

        Returns:
            Checkpoint 实例
        """
        agents = []
        for agent in sandbox.agents.values():
            snapshot = AgentSnapshot(
                name=agent.name,
                state=agent.state,
                step_count=agent.step_count,
                context=dict(agent.context),
                inbox=[msg.model_dump() for msg in agent.inbox],
                agent_type=type(agent).__name__,
            )
            agents.append(snapshot)

        message_history = [msg.model_dump() for msg in bus.history]

        return Checkpoint(
            step=step,
            agents=agents,
            message_history=message_history,
            metadata=metadata or {},
        )

    def save(self, checkpoint: Checkpoint, path: str | Path) -> None:
        """保存检查点到文件。

        Args:
            checkpoint: 检查点实例
            path: 文件路径
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            checkpoint.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("检查点已保存: %s (step=%d)", path, checkpoint.step)

    def load(self, path: str | Path) -> Checkpoint:
        """从文件加载检查点。

        Args:
            path: 文件路径

        Returns:
            Checkpoint 实例

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 文件格式错误
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"检查点文件不存在: {path}")

        data = json.loads(path.read_text(encoding="utf-8"))
        checkpoint = Checkpoint(**data)
        logger.info("检查点已加载: %s (step=%d)", path, checkpoint.step)
        return checkpoint

    def restore(
        self,
        checkpoint: Checkpoint,
        sandbox: Sandbox,
        bus: MessageBus,
    ) -> int:
        """从检查点恢复仿真状态。

        Args:
            checkpoint: 检查点实例
            sandbox: 仿真沙箱
            bus: 通信总线

        Returns:
            恢复的 Agent 数量
        """
        restored = 0
        for snapshot in checkpoint.agents:
            agent = sandbox.get_agent(snapshot.name)
            if agent is None:
                logger.warning("恢复跳过: Agent '%s' 不存在", snapshot.name)
                continue

            agent.state = snapshot.state
            agent.step_count = snapshot.step_count
            agent.context = dict(snapshot.context)
            agent.inbox = [Message(**msg_data) for msg_data in snapshot.inbox]
            restored += 1

        logger.info("恢复完成: %d agents, step=%d", restored, checkpoint.step)
        return restored
