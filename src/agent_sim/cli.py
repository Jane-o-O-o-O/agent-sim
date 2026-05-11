"""CLI entry point for Agent Sim."""
from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import click

from agent_sim import __version__


@click.group()
@click.version_option(version=__version__, prog_name="agent-sim")
def main() -> None:
    """Agent Sim - 多智能体仿真框架。"""
    pass


@main.command()
@click.option("--steps", default=5, type=int, help="仿真步数")
@click.option("--example", is_flag=True, help="运行内置示例场景")
def run(steps: int, example: bool) -> None:
    """运行仿真场景。"""
    if example:
        result = asyncio.run(_run_example(steps))
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        click.echo("请指定 --example 运行内置示例，或使用 Python API 自定义场景。")
        click.echo("示例: agent-sim run --example --steps 5")


async def _run_example(steps: int) -> dict[str, Any]:
    """运行内置示例：Ping-Pong 通信。"""
    from agent_sim.agent.base import Agent, AgentState
    from agent_sim.agent.role import Role
    from agent_sim.communication.bus import MessageBus
    from agent_sim.communication.message import Message, MessageType
    from agent_sim.environment.sandbox import Sandbox
    from agent_sim.scenario.runner import ScenarioRunner

    class PingAgent(Agent):
        """发送 ping 并等待 pong。"""

        async def step(self) -> list[Message]:
            replies: list[Message] = []
            for msg in self.inbox:
                if msg.content == "ping":
                    replies.append(Message(
                        sender=self.name,
                        receiver=msg.sender,
                        content="pong",
                        msg_type=MessageType.RESPONSE,
                    ))
            self.inbox.clear()
            if self.step_count == 0:
                for target in self.context.get("targets", []):
                    replies.append(Message(
                        sender=self.name,
                        receiver=target,
                        content="ping",
                        msg_type=MessageType.REQUEST,
                    ))
            self.increment_step()
            return replies

    class WorkerAgent(Agent):
        """处理任务请求。"""

        async def step(self) -> list[Message]:
            replies: list[Message] = []
            for msg in self.inbox:
                replies.append(Message(
                    sender=self.name,
                    receiver=msg.sender,
                    content=f"completed:{msg.content}",
                    msg_type=MessageType.RESPONSE,
                ))
            self.inbox.clear()
            self.increment_step()
            return replies

    # 创建 Agent
    coordinator = PingAgent(
        name="coordinator",
        role=Role(name="coordinator", goals=["协调任务"]),
        context={"targets": ["worker_1", "worker_2"]},
    )
    worker1 = WorkerAgent(
        name="worker_1",
        role=Role(name="worker", goals=["执行任务"]),
    )
    worker2 = WorkerAgent(
        name="worker_2",
        role=Role(name="worker", goals=["执行任务"]),
    )

    # 创建环境
    sandbox = Sandbox(agents=[coordinator, worker1, worker2])
    bus = MessageBus()
    bus.register(coordinator)
    bus.register(worker1)
    bus.register(worker2)

    # 运行仿真
    runner = ScenarioRunner(sandbox=sandbox, bus=bus)
    result = await runner.run(steps=steps)

    return {
        "steps_completed": result.steps_completed,
        "total_messages": result.total_messages,
        "duration_seconds": round(result.duration, 4),
        "agent_states": result.agent_states,
        "metrics": result.metrics,
    }


@main.command()
def info() -> None:
    """显示框架信息。"""
    click.echo(f"Agent Sim v{__version__}")
    click.echo("多智能体仿真框架")
    click.echo()
    click.echo("核心模块:")
    click.echo("  agent        - Agent 基类和角色定义")
    click.echo("  communication - 消息模型和通信总线")
    click.echo("  environment  - 沙箱环境和状态管理")
    click.echo("  scenario     - 场景运行器")
    click.echo("  metrics      - 指标收集")
    click.echo()
    click.echo("Python API:")
    click.echo("  from agent_sim.agent import Agent, Role")
    click.echo("  from agent_sim.communication import MessageBus, Message")
    click.echo("  from agent_sim.environment import Sandbox")
    click.echo("  from agent_sim.scenario import ScenarioRunner")


if __name__ == "__main__":
    main()
