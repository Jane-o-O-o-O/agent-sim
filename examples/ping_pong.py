#!/usr/bin/env python3
"""Agent Sim 示例：Ping-Pong 多 Agent 通信演示。

演示内容：
- 定义自定义 Agent（PingAgent、WorkerAgent）
- 通过 MessageBus 进行 Agent 间通信
- 使用 ScenarioRunner 运行仿真
- 查看仿真结果和指标

运行方式：
    PYTHONPATH=src python3 examples/ping_pong.py
"""
from __future__ import annotations

import asyncio
import json

from agent_sim.agent.base import Agent, AgentState
from agent_sim.agent.role import Role
from agent_sim.communication.bus import MessageBus
from agent_sim.communication.message import Message, MessageType
from agent_sim.environment.sandbox import Sandbox
from agent_sim.scenario.runner import ScenarioRunner


class PingAgent(Agent):
    """Ping Agent：第一步发送 ping，收到 ping 后回复 pong。"""

    async def step(self) -> list[Message]:
        replies: list[Message] = []

        # 回复收到的 ping
        for msg in self.inbox:
            if msg.content == "ping":
                replies.append(Message(
                    sender=self.name,
                    receiver=msg.sender,
                    content="pong",
                    msg_type=MessageType.RESPONSE,
                ))
        self.inbox.clear()

        # 第一步主动发 ping
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
    """Worker Agent：处理任务请求并返回结果。"""

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


async def main() -> None:
    print("🤖 Agent Sim - Ping-Pong 演示\n")

    # 1. 定义 Agent
    coordinator = PingAgent(
        name="coordinator",
        role=Role(name="coordinator", goals=["协调任务分配"]),
        context={"targets": ["worker_1", "worker_2"]},
    )
    worker1 = WorkerAgent(
        name="worker_1",
        role=Role(name="worker", goals=["执行分析任务"]),
    )
    worker2 = WorkerAgent(
        name="worker_2",
        role=Role(name="worker", goals=["执行计算任务"]),
    )

    # 2. 创建沙箱和通信总线
    sandbox = Sandbox(agents=[coordinator, worker1, worker2])
    bus = MessageBus()
    bus.register(coordinator)
    bus.register(worker1)
    bus.register(worker2)

    # 3. 运行仿真
    print("▶ 开始仿真 (5 步)...")
    runner = ScenarioRunner(sandbox=sandbox, bus=bus)
    result = await runner.run(steps=5)

    # 4. 输出结果
    print(f"\n✅ 仿真完成!")
    print(f"   步数: {result.steps_completed}")
    print(f"   消息总数: {result.total_messages}")
    print(f"   耗时: {result.duration:.4f}s")
    print(f"\n📊 Agent 状态:")
    for name, state in result.agent_states.items():
        print(f"   {name}: {state}")

    print(f"\n📨 消息历史:")
    for msg in bus.history:
        print(f"   {msg}")

    print(f"\n📈 指标摘要:")
    print(json.dumps(result.metrics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
