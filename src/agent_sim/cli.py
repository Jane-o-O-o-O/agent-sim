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


def _get_version() -> str:
    """获取版本号。"""
    return __version__


@click.group()
@click.version_option(version=_get_version(), prog_name="agent-sim")
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
@click.option("--timeout", default=0, type=float, help="超时秒数 (0=无超时)")
def run(steps: int | None, example: bool, config_path: str | None,
        output_path: str | None, timeout: float) -> None:
    """运行仿真场景。

    \b
    示例:
      agent-sim run --example --steps 5
      agent-sim run --config scenarios/ping_pong.yaml
      agent-sim run --config scene.yaml --steps 20 --output result.json
      agent-sim run --config scene.yaml --timeout 30
    """
    if config_path:
        result = asyncio.run(_run_from_config(config_path, steps, timeout))
    elif example:
        result = asyncio.run(_run_example(steps or 5, timeout))
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


async def _run_from_config(
    config_path: str, steps: int | None, timeout: float = 0,
) -> dict[str, Any]:
    """从 YAML 配置文件运行仿真。"""
    from agent_sim.log import get_logger
    from agent_sim.scenario.config import load_scenario
    from agent_sim.scenario.factory import build_scenario
    from agent_sim.scenario.runner import ScenarioRunner

    logger = get_logger("cli")

    config = load_scenario(config_path)
    logger.info("场景: %s (%d agents, %d steps)", config.name, len(config.agents), config.steps)

    sandbox, bus = build_scenario(config)
    runner = ScenarioRunner(
        sandbox=sandbox, bus=bus, timeout_seconds=timeout,
    )

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
        "timed_out": result.timed_out,
    }


async def _run_example(steps: int, timeout: float = 0) -> dict[str, Any]:
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
                        sender=self.name, receiver=msg.sender,
                        content="pong", msg_type=MessageType.RESPONSE,
                    ))
            self.inbox.clear()
            if self.step_count == 0:
                for target in self.context.get("targets", []):
                    replies.append(Message(
                        sender=self.name, receiver=target,
                        content="ping", msg_type=MessageType.REQUEST,
                    ))
            self.increment_step()
            return replies

    class WorkerAgent(Agent):
        """处理任务请求。"""
        async def step(self) -> list[Message]:
            replies: list[Message] = []
            for msg in self.inbox:
                replies.append(Message(
                    sender=self.name, receiver=msg.sender,
                    content=f"completed:{msg.content}",
                    msg_type=MessageType.RESPONSE,
                ))
            self.inbox.clear()
            self.increment_step()
            return replies

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

    sandbox = Sandbox(agents=[coordinator, worker1, worker2])
    bus = MessageBus()
    bus.register(coordinator)
    bus.register(worker1)
    bus.register(worker2)

    runner = ScenarioRunner(sandbox=sandbox, bus=bus, timeout_seconds=timeout)
    result = await runner.run(steps=steps)

    return {
        "steps_completed": result.steps_completed,
        "total_messages": result.total_messages,
        "duration_seconds": round(result.duration, 4),
        "agent_states": result.agent_states,
        "metrics": result.metrics,
        "timed_out": result.timed_out,
    }


@main.command()
@click.argument("config_path", type=click.Path(exists=True))
def validate(config_path: str) -> None:
    """验证 YAML 场景配置文件。

    提供详细的错误信息，一次性报告所有问题。

    \\b
    示例:
      agent-sim validate scenarios/ping_pong.yaml
    """
    from agent_sim.scenario.validation import validate_scenario

    errors = validate_scenario(config_path)
    if errors:
        click.echo(f"❌ 配置验证失败 ({len(errors)} 个问题):")
        for err in errors:
            click.echo(f"  • {err}")
        raise SystemExit(1)

    from agent_sim.scenario.config import load_scenario
    config = load_scenario(config_path)
    click.echo(f"✅ 配置有效: {config.name}")
    click.echo(f"   描述: {config.description or '(无)'}")
    click.echo(f"   Agent 数: {len(config.agents)}")
    click.echo(f"   仿真步数: {config.steps}")
    click.echo(f"   连接数: {len(config.connections)}")
    for agent_config in config.agents:
        click.echo(f"   - {agent_config.name} ({agent_config.type})")


@main.command()
def info() -> None:
    """显示框架信息和版本。"""
    from agent_sim.scenario.factory import get_registered_types
    click.echo(f"Agent Sim v{__version__}")
    click.echo("多智能体仿真框架")
    click.echo()
    click.echo("已注册 Agent 类型:")
    for t in get_registered_types():
        click.echo(f"  - {t}")
    click.echo()
    click.echo("核心模块:")
    click.echo("  agent         - Agent 基类和角色定义")
    click.echo("  agent.llm     - LLM Agent（可插拔后端）")
    click.echo("  agent.memory  - Memory Agent（记忆增强）")
    click.echo("  agent.tool    - Tool Agent（工具调用）")
    click.echo("  communication - 消息模型和通信总线")
    click.echo("  environment   - 沙箱环境和状态管理")
    click.echo("  scenario      - 场景配置和运行器")
    click.echo("  metrics       - 指标收集和评估")
    click.echo()
    click.echo("Python API:")
    click.echo("  from agent_sim import Agent, Sandbox, ScenarioRunner")
    click.echo("  from agent_sim import LLMAgent, MemoryAgent, ToolAgent")
    click.echo("  from agent_sim import load_scenario, build_scenario")
    click.echo()
    click.echo("CLI 命令:")
    click.echo("  agent-sim run --example          运行内置示例")
    click.echo("  agent-sim run --config scene.yaml  从 YAML 配置运行")
    click.echo("  agent-sim validate scene.yaml    验证场景配置")
    click.echo("  agent-sim compare a.yaml b.yaml  对比两个场景")
    click.echo("  agent-sim info                   显示此信息")
    click.echo("  agent-sim benchmark              性能基准测试")
    click.echo("  agent-sim plugins                查看插件信息")


if __name__ == "__main__":
    main()


@main.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True),
              help="YAML 场景配置文件路径")
@click.option("--steps", default=None, type=int, help="仿真步数")
@click.option("--eval/--no-eval", default=True, help="是否运行评估")
def report(config_path: str, steps: int | None, eval: bool) -> None:
    """运行仿真并生成终端可视化报告。

    \\b
    示例:
      agent-sim report --config scenarios/ping_pong.yaml
      agent-sim report --config scenarios/debate.yaml --steps 4
    """
    result = asyncio.run(_run_and_report(config_path, steps, eval))
    click.echo(result)


async def _run_and_report(
    config_path: str, steps: int | None, run_eval: bool,
) -> str:
    """运行仿真并生成可视化报告。"""
    from agent_sim.metrics.evaluator import (
        AgentParticipationEvaluator,
        CompletionEvaluator,
        ConversationFlowEvaluator,
        EvalSuite,
        LatencyEvaluator,
        MessageVolumeEvaluator,
    )
    from agent_sim.scenario.config import load_scenario
    from agent_sim.scenario.factory import build_scenario
    from agent_sim.scenario.runner import ScenarioRunner
    from agent_sim.viz.charts import bar_chart, line_chart, metrics_table, sparkline

    config = load_scenario(config_path)
    sandbox, bus = build_scenario(config)
    runner = ScenarioRunner(sandbox=sandbox, bus=bus)
    n_steps = steps or config.steps
    result = await runner.run(steps=n_steps)

    lines = []
    lines.append(f"╔══════════════════════════════════════════════╗")
    lines.append(f"║  Agent Sim Report: {config.name:<25} ║")
    lines.append(f"╚══════════════════════════════════════════════╝")
    lines.append("")

    lines.append(f"场景: {config.description or config.name}")
    lines.append(f"步数: {result.steps_completed}/{n_steps}")
    lines.append(f"消息: {result.total_messages}")
    lines.append(f"耗时: {result.duration:.3f}s")
    lines.append(f"Agent 数: {len(result.agent_states)}")
    if result.timed_out:
        lines.append(f"⚠️ 仿真因超时终止")
    lines.append("")

    lines.append("Agent 状态:")
    lines.append(bar_chart(result.agent_states, width=30, char="█"))
    lines.append("")

    step_msgs = [d.get("messages_sent", 0) for d in result.metrics.get("step_details", [])]
    if step_msgs:
        lines.append("每步消息量:")
        lines.append(sparkline(step_msgs))
        lines.append("")

    step_details = result.metrics.get("step_details", [])
    if step_details:
        lines.append("步骤详情:")
        lines.append(metrics_table(step_details))
        lines.append("")

    from agent_sim.topology.topology import TopologyType, build_topology as bt
    try:
        topo = bt(TopologyType.MESH, list(result.agent_states.keys()))
        lines.append("通信拓扑:")
        lines.append(topo.to_ascii())
        lines.append("")
    except Exception:
        pass

    if run_eval:
        suite = EvalSuite.default()
        suite.add(ConversationFlowEvaluator())
        eval_data = {
            "total_messages": result.total_messages,
            "steps_completed": result.steps_completed,
            "agent_states": result.agent_states,
            "duration_seconds": result.duration,
            "expected_steps": n_steps,
            "agent_message_counts": _count_agent_messages(bus.history),
            "topology": topo.summary() if "topo" in dir() else {},
        }
        report = suite.run(eval_data)
        lines.append("评估报告:")
        lines.append(f"  综合分数: {report.overall_score:.3f}")
        lines.append(f"  通过: {'✅' if report.passed else '❌'}")
        for r in report.results:
            status = "✅" if r.passed else "❌"
            lines.append(f"  {status} {r.name}: {r.score:.3f}")
        lines.append("")

    return "\n".join(lines)


def _count_agent_messages(history: list) -> dict[str, int]:
    """统计每个 Agent 发送的消息数。"""
    counts: dict[str, int] = {}
    for msg in history:
        sender = msg.sender if hasattr(msg, "sender") else msg.get("sender", "unknown")
        counts[sender] = counts.get(sender, 0) + 1
    return counts


@main.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True),
              help="YAML 场景配置文件路径")
@click.option("--steps", default=None, type=int, help="仿真步数")
@click.option("--format", "fmt", type=click.Choice(["json", "markdown", "csv", "html"]), default="json",
              help="导出格式")
@click.option("--output", "-o", "output_path", required=True, type=click.Path(),
              help="输出文件路径")
def export(config_path: str, steps: int | None, fmt: str, output_path: str) -> None:
    """运行仿真并导出消息历史。

    \b
    示例:
      agent-sim export --config scene.yaml -o messages.json
      agent-sim export --config scene.yaml --format csv -o messages.csv
      agent-sim export --config scene.yaml --format markdown -o messages.md
    """
    asyncio.run(_export_messages(config_path, steps, fmt, output_path))
    click.echo(f"✅ 导出完成: {output_path} ({fmt})")


async def _export_messages(
    config_path: str, steps: int | None, fmt: str, output_path: str,
) -> None:
    """运行仿真并导出消息。"""
    from agent_sim.export import (
        HTMLReport,
        export_messages_to_csv,
        export_messages_to_json,
        export_messages_to_markdown,
    )
    from agent_sim.scenario.config import load_scenario
    from agent_sim.scenario.factory import build_scenario
    from agent_sim.scenario.runner import ScenarioRunner

    config = load_scenario(config_path)
    sandbox, bus = build_scenario(config)
    runner = ScenarioRunner(sandbox=sandbox, bus=bus)
    result = await runner.run(steps=steps or config.steps)

    if fmt == "html":
        report = HTMLReport(result, scenario_name=config.name)
        report.save(output_path)
        return

    messages = bus.history

    if fmt == "json":
        export_messages_to_json(messages, output_path)
    elif fmt == "markdown":
        export_messages_to_markdown(messages, output_path)
    elif fmt == "csv":
        export_messages_to_csv(messages, output_path)


@main.command()
@click.argument("config_a", type=click.Path(exists=True))
@click.argument("config_b", type=click.Path(exists=True))
@click.option("--steps", default=None, type=int, help="仿真步数")
def compare(config_a: str, config_b: str, steps: int | None) -> None:
    """对比两个场景配置的仿真结果。

    \b
    示例:
      agent-sim compare scenarios/ping_pong.yaml scenarios/debate.yaml
      agent-sim compare a.yaml b.yaml --steps 10
    """
    result = asyncio.run(_run_compare(config_a, config_b, steps))
    click.echo(result)


async def _run_compare(
    config_a: str, config_b: str, steps: int | None,
) -> str:
    """运行两个场景并对比结果。"""
    from agent_sim.scenario.config import load_scenario
    from agent_sim.scenario.factory import build_scenario
    from agent_sim.scenario.runner import ScenarioRunner
    from agent_sim.viz.charts import bar_chart, sparkline

    lines = []
    lines.append("╔══════════════════════════════════════════════════╗")
    lines.append("║  Agent Sim Compare                               ║")
    lines.append("╚══════════════════════════════════════════════════╝")
    lines.append("")

    results = []
    for path in [config_a, config_b]:
        config = load_scenario(path)
        sandbox, bus = build_scenario(config)
        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        n_steps = steps or config.steps
        result = await runner.run(steps=n_steps)
        results.append((config, result, bus))

    # Side-by-side comparison table
    cfg_a, res_a, bus_a = results[0]
    cfg_b, res_b, bus_b = results[1]

    lines.append(f"{'指标':<20} {'场景 A':<20} {'场景 B':<20}")
    lines.append("-" * 60)
    lines.append(f"{'名称':<20} {cfg_a.name:<20} {cfg_b.name:<20}")
    lines.append(f"{'描述':<20} {(cfg_a.description or '-')[:18]:<20} {(cfg_b.description or '-')[:18]:<20}")
    lines.append(f"{'Agent 数':<20} {len(cfg_a.agents):<20} {len(cfg_b.agents):<20}")
    lines.append(f"{'步数':<20} {res_a.steps_completed:<20} {res_b.steps_completed:<20}")
    lines.append(f"{'消息总数':<20} {res_a.total_messages:<20} {res_b.total_messages:<20}")
    lines.append(f"{'耗时(s)':<20} {res_a.duration:<20.4f} {res_b.duration:<20.4f}")
    lines.append(f"{'超时':<20} {'是' if res_a.timed_out else '否':<20} {'是' if res_b.timed_out else '否':<20}")
    lines.append("")

    # Per-step message comparison
    msgs_a = [d.get("messages_sent", 0) for d in res_a.metrics.get("step_details", [])]
    msgs_b = [d.get("messages_sent", 0) for d in res_b.metrics.get("step_details", [])]

    if msgs_a or msgs_b:
        lines.append("每步消息量:")
        max_steps = max(len(msgs_a), len(msgs_b))
        lines.append(f"  场景 A: {sparkline(msgs_a) if msgs_a else '(无)'}")
        lines.append(f"  场景 B: {sparkline(msgs_b) if msgs_b else '(无)'}")
        lines.append("")

    # Agent states comparison
    lines.append("Agent 状态:")
    lines.append(f"  场景 A:")
    lines.append(bar_chart(res_a.agent_states, width=25, char="█"))
    lines.append(f"  场景 B:")
    lines.append(bar_chart(res_b.agent_states, width=25, char="█"))
    lines.append("")

    # Per-agent message counts
    lines.append("每 Agent 消息数:")
    for name, res, bus in [("场景 A", res_a, bus_a), ("场景 B", res_b, bus_b)]:
        counts = _count_agent_messages(bus.history)
        if counts:
            lines.append(f"  {name}:")
            lines.append(bar_chart(counts, width=20, char="█"))
    lines.append("")

    return "\n".join(lines)


@main.command()
@click.argument("events_path", type=click.Path(exists=True))
@click.option("--step", default=None, type=int, help="只显示指定步数的事件")
@click.option("--type", "event_type", default=None, help="只显示指定类型的事件")
@click.option("--summary", is_flag=True, help="只显示摘要")
def replay(events_path: str, step: int | None, event_type: str | None, summary: bool) -> None:
    """回放仿真事件日志。

    加载 EventRecorder 导出的 JSON 文件，按步回放事件。

    \\b
    示例:
      agent-sim replay events.json
      agent-sim replay events.json --step 1
      agent-sim replay events.json --type message
      agent-sim replay events.json --summary
    """
    from agent_sim.scenario.replay import ReplayEngine

    engine = ReplayEngine.from_json(events_path)

    if summary:
        s = engine.summary()
        click.echo(f"事件总数: {s['total_events']}")
        click.echo(f"总步数: {s['total_steps']}")
        click.echo(f"事件类型分布:")
        for etype, count in s["event_counts"].items():
            click.echo(f"  {etype}: {count}")
        return

    events = engine._events
    if step is not None:
        events = engine.get_step(step)
        click.echo(f"--- 步 {step} 的事件 ({len(events)} 个) ---")
    if event_type is not None:
        events = [e for e in events if e.event_type == event_type]

    for event in events:
        click.echo(f"  [{event.time_iso}] step={event.step} {event.event_type}")
        if event.data:
            click.echo(f"    data: {json.dumps(event.data, ensure_ascii=False)[:200]}")


@main.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True),
              help="YAML 场景配置文件路径")
@click.option("--runs", default=5, type=int, help="运行次数")
@click.option("--steps", default=None, type=int, help="仿真步数")
@click.option("--timeout", default=0, type=float, help="超时秒数")
@click.option("--output", "output_path", default=None, type=click.Path(),
              help="结果输出文件路径 (JSON)")
def batch(config_path: str, runs: int, steps: int | None, timeout: float,
          output_path: str | None) -> None:
    """批量运行仿真并统计结果。

    \\b
    示例:
      agent-sim batch --config scene.yaml --runs 10
      agent-sim batch --config scene.yaml --runs 5 --steps 20 --output stats.json
    """
    from agent_sim.scenario.batch import BatchRunner
    from agent_sim.scenario.config import load_scenario

    config = load_scenario(config_path)
    n_steps = steps or config.steps

    async def _run() -> dict[str, Any]:
        runner = BatchRunner(runs=runs)
        batch_result = await runner.run_from_config(config, timeout_seconds=timeout)
        return batch_result.to_dict()

    result = asyncio.run(_run())
    result_json = json.dumps(result, indent=2, ensure_ascii=False)
    click.echo(result_json)

    if output_path:
        Path(output_path).write_text(result_json, encoding="utf-8")
        click.echo(f"\n结果已保存到: {output_path}", err=True)


@main.command()
@click.option("--agents", default="10,50,100", help="Agent 数量梯度，逗号分隔")
@click.option("--steps", default=10, type=int, help="仿真步数")
@click.option("--timeout", default=60.0, type=float, help="超时秒数")
@click.option("--output", "output_path", default=None, type=click.Path(),
              help="结果输出文件路径 (JSON)")
def benchmark(agents: str, steps: int, timeout: float, output_path: str | None) -> None:
    """运行性能基准测试。

    \\b
    示例:
      agent-sim benchmark --agents 10,50,100 --steps 10
      agent-sim benchmark --agents 10,25,50,100,200 --steps 5 --timeout 120
    """
    from agent_sim.scenario.benchmark import BenchmarkRunner

    agent_counts = [int(x.strip()) for x in agents.split(",")]

    async def _run() -> dict[str, Any]:
        runner = BenchmarkRunner(timeout_seconds=timeout)
        suite = await runner.run_scale_test(agent_counts=agent_counts, steps=steps)
        return suite.summary()

    result = asyncio.run(_run())
    result_json = json.dumps(result, indent=2, ensure_ascii=False)
    click.echo(result_json)

    if output_path:
        Path(output_path).write_text(result_json, encoding="utf-8")
        click.echo(f"\n结果已保存到: {output_path}", err=True)


@main.command()
def plugins() -> None:
    """显示已注册的插件信息。

    \\b
    示例:
      agent-sim plugins
    """
    from agent_sim.scenario.plugins import PluginRegistry

    registry = PluginRegistry()
    discovered = registry.discover()
    summary = registry.summary()

    click.echo("Agent Sim 插件注册表")
    click.echo(f"已发现: {discovered} 个插件")
    click.echo(f"已注册: {summary['total']} 个插件")
    click.echo()

    if summary["agents"] > 0:
        click.echo("Agent 类型:")
        for p in summary["plugins"]:
            if p["type"] == "agent":
                click.echo(f"  - {p['name']} ({p['module']})")

    if summary["evaluators"] > 0:
        click.echo("Evaluator 类型:")
        for p in summary["plugins"]:
            if p["type"] == "evaluator":
                click.echo(f"  - {p['name']} ({p['module']})")

    if summary["middlewares"] > 0:
        click.echo("Middleware 类型:")
        for p in summary["plugins"]:
            if p["type"] == "middleware":
                click.echo(f"  - {p['name']} ({p['module']})")

    if summary["total"] == 0:
        click.echo("(暂无注册插件)")


@main.command()
@click.argument("template_name")
@click.option("--output", "-o", "output_path", default=None, type=click.Path(),
              help="输出文件路径 (默认: <template_name>.yaml)")
def init(template_name: str, output_path: str | None) -> None:
    """从模板创建场景 YAML 配置文件。

    \b
    可用模板:
      ping_pong        Ping-Pong 通信测试
      debate           结构化辩论
      brainstorm       头脑风暴
      code_review      代码审查
      task_delegation  任务分配
      multi_round_discussion  多轮讨论

    \b
    示例:
      agent-sim init ping_pong
      agent-sim init debate -o my_debate.yaml
      agent-sim init brainstorm --output scenarios/brainstorm.yaml
    """
    from agent_sim.scenario.templates import get_template, list_templates, save_template_to_yaml

    if template_name == "list":
        click.echo("可用模板:")
        for name in list_templates():
            t = get_template(name)
            click.echo(f"  {name:<25} {t.get('description', '')}")
        return

    try:
        path = output_path or f"{template_name}.yaml"
        result = save_template_to_yaml(template_name, path)
        click.echo(f"✅ 场景文件已创建: {result}")
        click.echo(f"   运行: agent-sim run --config {result}")
    except KeyError:
        click.echo(f"❌ 未知模板: {template_name}", err=True)
        click.echo(f"   可用模板: {', '.join(list_templates())}", err=True)
        raise SystemExit(1)


@main.command()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True),
              help="YAML 场景配置文件路径")
@click.option("--steps", default=None, type=int, help="仿真步数")
@click.option("--format", "fmt", type=click.Choice(["mermaid", "ascii", "summary"]), default="mermaid",
              help="输出格式")
def graph(config_path: str, steps: int | None, fmt: str) -> None:
    """运行仿真并生成通信流图。

    \b
    示例:
      agent-sim graph --config scene.yaml --format mermaid
      agent-sim graph --config scene.yaml --format ascii
      agent-sim graph --config scene.yaml --format summary
    """
    result = asyncio.run(_run_and_graph(config_path, steps, fmt))
    click.echo(result)


async def _run_and_graph(config_path: str, steps: int | None, fmt: str) -> str:
    """运行仿真并生成通信图。"""
    from agent_sim.scenario.config import load_scenario
    from agent_sim.scenario.factory import build_scenario
    from agent_sim.scenario.runner import ScenarioRunner
    from agent_sim.viz.conversation_graph import ConversationGraph

    config = load_scenario(config_path)
    sandbox, bus = build_scenario(config)
    runner = ScenarioRunner(sandbox=sandbox, bus=bus)
    n_steps = steps or config.steps
    result = await runner.run(steps=n_steps)

    graph = ConversationGraph.from_history(result.message_history)

    if fmt == "mermaid":
        return graph.to_mermaid(title=config.name)
    elif fmt == "ascii":
        return graph.to_ascii_matrix()
    else:
        return graph.to_flow_summary()


@main.command()
def doctor() -> None:
    """检查环境依赖和 Agent Sim 安装状态。

    检查 Python 版本、依赖包、已注册的 Agent 类型和 LLM 后端。

    \\b
    示例:
      agent-sim doctor
    """
    from agent_sim.scenario.factory import get_registered_types

    lines = []
    lines.append("🔍 Agent Sim 环境检查")
    lines.append("=" * 40)

    # Python version
    v = sys.version_info
    py_ok = v >= (3, 10)
    status = "✅" if py_ok else "❌"
    lines.append(f"{status} Python {v.major}.{v.minor}.{v.micro} (需要 3.10+)")

    # Core dependencies
    deps = [
        ("pydantic", "pydantic"),
        ("yaml", "PyYAML"),
        ("click", "click"),
        ("httpx", "httpx"),
    ]
    lines.append("")
    lines.append("依赖包:")
    for module_name, pkg_name in deps:
        try:
            mod = __import__(module_name)
            ver = getattr(mod, "__version__", getattr(mod, "VERSION", "installed"))
            lines.append(f"  ✅ {pkg_name}: {ver}")
        except ImportError:
            lines.append(f"  ❌ {pkg_name}: 未安装")

    # Optional dependencies
    lines.append("")
    lines.append("可选依赖:")
    optional = [("openai", "openai")]
    for module_name, pkg_name in optional:
        try:
            mod = __import__(module_name)
            ver = getattr(mod, "__version__", "installed")
            lines.append(f"  ✅ {pkg_name}: {ver}")
        except ImportError:
            lines.append(f"  ⚠️ {pkg_name}: 未安装 (可选)")

    # Registered agent types
    lines.append("")
    lines.append("已注册 Agent 类型:")
    for t in get_registered_types():
        lines.append(f"  ✅ {t}")

    # Version
    lines.append("")
    lines.append(f"版本: agent-sim v{__version__}")

    click.echo("\n".join(lines))


@main.command()
@click.option("--format", "fmt", type=click.Choice(["json", "yaml"]), default="yaml",
              help="输出格式")
@click.option("--output", "-o", "output_path", default=None, type=click.Path(),
              help="输出文件路径")
def schema(fmt: str, output_path: str | None) -> None:
    """导出场景配置的 JSON Schema。

    可用于 IDE 自动补全和 YAML 配置文件校验。

    \\b
    示例:
      agent-sim schema
      agent-sim schema --format json
      agent-sim schema --format json -o scenario-schema.json
    """
    from agent_sim.scenario.validation import config_schema_json, config_schema_yaml

    if fmt == "json":
        content = config_schema_json()
    else:
        content = config_schema_yaml()

    if output_path:
        Path(output_path).write_text(content, encoding="utf-8")
        click.echo(f"✅ Schema 已保存到: {output_path}")
    else:
        click.echo(content)


@main.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell: str) -> None:
    """生成 Shell 自动补全脚本。

    将输出添加到你的 shell 配置文件中以启用 Tab 补全。

    \\b
    安装方法:
      # Bash
      eval "$(_AGENT_SIM_COMPLETE=bash_source agent-sim)"

      # Zsh
      eval "$(_AGENT_SIM_COMPLETE=zsh_source agent-sim)"

      # Fish
      eval (env _AGENT_SIM_COMPLETE=fish_source agent-sim)

    \\b
    示例:
      agent-sim completion bash
      agent-sim completion zsh
      agent-sim completion fish
    """
    if shell == "bash":
        click.echo('# Bash 自动补全 — 添加到 ~/.bashrc:')
        click.echo('eval "$(_AGENT_SIM_COMPLETE=bash_source agent-sim)"')
    elif shell == "zsh":
        click.echo('# Zsh 自动补全 — 添加到 ~/.zshrc:')
        click.echo('eval "$(_AGENT_SIM_COMPLETE=zsh_source agent-sim)"')
    elif shell == "fish":
        click.echo('# Fish 自动补全 — 添加到 ~/.config/fish/config.fish:')
        click.echo('eval (env _AGENT_SIM_COMPLETE=fish_source agent-sim)')
