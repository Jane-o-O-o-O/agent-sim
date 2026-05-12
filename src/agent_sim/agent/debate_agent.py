"""Debate agent — structured argumentation agent for adversarial discussions."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import Field

from agent_sim.agent.base import Agent
from agent_sim.agent.role import Role
from agent_sim.communication.message import Message, MessageType

logger = logging.getLogger(__name__)


class DebateAgent(Agent):
    """辩论 Agent。

    支持结构化辩论：提出论点、反驳、总结。
    根据 context 中的立场参数化行为。

    Attributes:
        stance: 辩论立场 (for/against)
        argument_style: 论证风格 (aggressive/balanced/defensive)
        round_count: 当前辩论轮次

    Example:
        >>> agent = DebateAgent(
        ...     name="pro",
        ...     role=Role(name="pro_side", goals=["支持AI发展"]),
        ...     context={"stance": "for", "topic": "AI safety"},
        ... )
    """

    stance: str = "for"
    argument_style: str = "balanced"
    round_count: int = 0
    _arguments: list[str] = []
    _rebuttals: list[str] = []

    model_config = {"arbitrary_types_allowed": True}

    def model_post_init(self, __context: Any) -> None:
        """从 context 中读取配置。"""
        self.stance = self.context.get("stance", self.stance)
        self.argument_style = self.context.get("style", self.argument_style)

    async def step(self) -> list[Message]:
        """执行一步辩论逻辑。

        第一步：提出初始论点
        后续步骤：反驳对方论点或补充自己论点

        Returns:
            出站消息列表
        """
        replies: list[Message] = []

        for msg in self.inbox:
            content = msg.content if isinstance(msg.content, str) else str(msg.content)

            if self.round_count == 0:
                argument = self._make_argument(content)
                self._arguments.append(argument)
            else:
                rebuttal = self._make_rebuttal(content)
                self._rebuttals.append(rebuttal)
                argument = rebuttal

            replies.append(Message(
                sender=self.name,
                receiver=msg.sender,
                content=argument,
                msg_type=MessageType.DIRECT,
                metadata={
                    "stance": self.stance,
                    "round": self.round_count,
                    "style": self.argument_style,
                },
            ))

        self.inbox.clear()
        self.round_count += 1
        self.increment_step()
        return replies

    def _make_argument(self, topic: str) -> str:
        """构建初始论点。"""
        stance_word = "支持" if self.stance == "for" else "反对"
        return f"[{self.name}] {stance_word}立场论点: 关于'{topic}'，我的观点是..."

    def _make_rebuttal(self, opponent_msg: str) -> str:
        """构建反驳论点。"""
        if self.argument_style == "aggressive":
            prefix = "强烈反驳"
        elif self.argument_style == "defensive":
            prefix = "谨慎回应"
        else:
            prefix = "理性分析"

        return f"[{self.name}] {prefix}: 针对'{opponent_msg[:50]}...'，我认为..."

    @property
    def total_arguments(self) -> int:
        """总论证数。"""
        return len(self._arguments) + len(self._rebuttals)


class CollaborateAgent(Agent):
    """协作解题 Agent。

    支持任务分解、子任务分发、结果汇总的协作模式。

    Attributes:
        role_type: 角色类型 (coordinator/worker/reviewer)

    Example:
        >>> coordinator = CollaborateAgent(
        ...     name="coordinator",
        ...     context={"role_type": "coordinator", "subtasks": ["task1", "task2"]},
        ... )
    """

    role_type: str = "worker"
    completed_tasks: list[str] = Field(default_factory=list)
    _pending_tasks: list[str] = []
    _results: dict[str, str] = {}

    model_config = {"arbitrary_types_allowed": True}

    def model_post_init(self, __context: Any) -> None:
        """从 context 中读取配置。"""
        self.role_type = self.context.get("role_type", self.role_type)
        self._pending_tasks = list(self.context.get("subtasks", []))

    async def step(self) -> list[Message]:
        """执行一步协作逻辑。

        coordinator: 分发子任务或汇总结果
        worker: 处理收到的任务并返回结果
        reviewer: 审核结果并提供反馈

        Returns:
            出站消息列表
        """
        replies: list[Message] = []

        if self.role_type == "coordinator":
            replies.extend(self._coordinator_step())
        elif self.role_type == "worker":
            replies.extend(self._worker_step())
        elif self.role_type == "reviewer":
            replies.extend(self._reviewer_step())

        self.inbox.clear()
        self.increment_step()
        return replies

    def _coordinator_step(self) -> list[Message]:
        """协调者逻辑：分发任务或汇总结果。"""
        replies = []

        # 收集结果
        for msg in self.inbox:
            if isinstance(msg.content, dict) and "result" in msg.content:
                task_id = msg.content.get("task_id", "unknown")
                self._results[task_id] = msg.content["result"]
                self.completed_tasks.append(task_id)

        # 分发待处理任务
        if self._pending_tasks:
            task = self._pending_tasks.pop(0)
            targets = self.context.get("workers", [])
            for target in targets:
                replies.append(Message(
                    sender=self.name,
                    receiver=target,
                    content={"task": task, "task_id": task},
                    msg_type=MessageType.DIRECT,
                ))
        elif self._results and self.inbox:
            summary = f"任务汇总: {len(self._results)} 个子任务完成"
            for msg in self.inbox:
                replies.append(Message(
                    sender=self.name,
                    receiver=msg.sender,
                    content={"summary": summary, "results": dict(self._results)},
                    msg_type=MessageType.RESPONSE,
                ))

        return replies

    def _worker_step(self) -> list[Message]:
        """工作者逻辑：处理任务。"""
        replies = []
        for msg in self.inbox:
            if isinstance(msg.content, dict) and "task" in msg.content:
                task_id = msg.content.get("task_id", "unknown")
                result = self._process_task(msg.content["task"])
                self.completed_tasks.append(task_id)
                replies.append(Message(
                    sender=self.name,
                    receiver=msg.sender,
                    content={"task_id": task_id, "result": result},
                    msg_type=MessageType.RESPONSE,
                ))
            else:
                replies.append(Message(
                    sender=self.name,
                    receiver=msg.sender,
                    content=f"收到: {msg.content}",
                    msg_type=MessageType.RESPONSE,
                ))
        return replies

    def _reviewer_step(self) -> list[Message]:
        """审核者逻辑：审核结果。"""
        replies = []
        for msg in self.inbox:
            content = msg.content if isinstance(msg.content, dict) else {"raw": msg.content}
            review = f"审核通过: {content}"
            replies.append(Message(
                sender=self.name,
                receiver=msg.sender,
                content={"review": review, "approved": True},
                msg_type=MessageType.RESPONSE,
            ))
        return replies

    def _process_task(self, task: str) -> str:
        """处理子任务。"""
        return f"已完成任务: {task}"
