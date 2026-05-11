"""CLI entry point for Agent Sim."""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import click

from agent_sim import __version__


@click.group()
@click.version_option(version=__version__, prog_name="agent-sim")
@click.option("-v", "--verbose", is_flag=True, help="启用详细日志输出")
def main(verbose: bool) -> None:
    """Agent Sim - 多智能体仿真框架。

    \b
    快速开始:
      agent-sim run --example          运行内置示例
      agent-sim run --config scene.yaml  从 YAML 配置运行
      agent-sim info                   显示框架信息
      agent-sim validate scene.yaml    验证场景配置
    """
    from agent_sim.log import setup_logging
    level = logging.DEBUG if verbose else logging.INFO
    setup_logging(level=level)


@main.command()
@click.option("--steps", default=None, type=int, help="仿真步数 (覆盖配置文件)")
@click.option("--example", is_flag=True, help="运行内置示例场景")
@click.option("--config", "config_path", default=None, type=click.Path(exists=True),
              help="YAML 场景配置文件路径")
@click.option("--output", "output_path", default=None, type=click.Path(),
              help="结果输出文件路径 (JSON)")
def run(steps: int | None, example: bool, config_path: str | None, output_path: str | None) -> None:
    """运行仿真场景。

    \b
    示例:
      agent-sim run --example --steps 5
      agent-sim run --config scenarios/ping_pong.yaml
      agent-sim run --config scene.yaml --steps 20 --output result.json
    """
    if config_path:
        result = asyncio.run(_run_from_config(config_path, steps))
    elif example:
        result = asyncio.run(_run_example(steps or 5))
    else:
        click.echo("请指定 --example 或 --config，例如:")
        click.echo("  agent-sim run --example")
        click.echo("  agent-sim run --config scenario.yaml")
        raise SystemExit(1)

    result_json = json.dumps(result, indent=2, ensure_ascii=False)
    click.echo(result_json)

    if output_path:
        Path(output_path).write_text(result_json, encoding="utf-8")
        click.echo(f"\n结果已保存到: {output_path}", err=True)


async def _run_from_config(config_path: str, steps: int | None) -> dict[str, Any]:
    """从 YAML 配置文件运行仿真。"""
    from agent_sim.log import get_logger
    from agent_sim.scenario.config import load_scenario
    from agent_sim.scenario.factory import build_scenario
    from agent_sim.scenario.runner import ScenarioRunner

    logger = get_logger("cli")

    config = load_scenario(config_path)
    logger.info("场景: %s (%d agents, %d steps)", config.name, len(config.agents), config.steps)

    sandbox, bus = build_scenario(config)
    runner = ScenarioRunner(sandbox=sandbox, bus=bus)

    n_steps = steps or config.steps
    result = await runner.run(steps=n_steps)

    return {
        "scenario": config.name,
        "description": config.description,
        "steps_completed": result.steps_completed,
        "total_messages": result.total_messages,
        "duration_seconds": round(result.duration, 4),
        "agent_states": result.agent_states,
        "metrics": result.metrics,
    }


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
@click.argument("config_path", type=click.Path(exists=True))
def validate(config_path: str) -> None:
    """验证 YAML 场景配置文件。

    \b
    示例:
      agent-sim validate scenarios/ping_pong.yaml
    """
    from agent_sim.scenario.config import load_scenario

    try:
        config = load_scenario(config_path)
        click.echo(f"✅ 配置有效: {config.name}")
        click.echo(f"   描述: {config.description or '(无)'}")
        click.echo(f"   Agent 数: {len(config.agents)}")
        click.echo(f"   仿真步数: {config.steps}")
        click.echo(f"   连接数: {len(config.connections)}")
        for agent_config in config.agents:
            click.echo(f"   - {agent_config.name} ({agent_config.type})")
    except Exception as e:
        click.echo(f"❌ 配置无效: {e}", err=True)
        raise SystemExit(1)


@main.command()
def info() -> None:
    """显示框架信息和版本。"""
    click.echo(f"Agent Sim v{__version__}")
    click.echo("多智能体仿真框架")
    click.echo()
    click.echo("核心模块:")
    click.echo("  agent         - Agent 基类和角色定义")
    click.echo("  agent.llm     - LLM Agent（可插拔后端）")
    click.echo("  agent.tool    - Tool Agent（工具调用）")
    click.echo("  communication - 消息模型和通信总线")
    click.echo("  environment   - 沙箱环境和状态管理")
    click.echo("  scenario      - 场景配置和运行器")
    click.echo("  metrics       - 指标收集")
    click.echo()
    click.echo("Python API:")
    click.echo("  from agent_sim import Agent, Sandbox, ScenarioRunner")
    click.echo("  from agent_sim import LLMAgent, ToolAgent")
    click.echo("  from agent_sim import load_scenario, build_scenario")
    click.echo()
    click.echo("CLI 命令:")
    click.echo("  agent-sim run --example          运行内置示例")
    click.echo("  agent-sim run --config scene.yaml  从 YAML 配置运行")
    click.echo("  agent-sim validate scene.yaml    验证场景配置")
    click.echo("  agent-sim info                   显示此信息")


if __name__ == "__main__":
    main()
