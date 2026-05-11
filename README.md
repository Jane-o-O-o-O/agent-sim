# Agent Sim

Multi-agent simulation framework for testing agent communication, coordination, and evaluation.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## About

Agent Sim 是一个多智能体仿真框架，用于定义、运行和评估多个 Agent 之间的通信和协调场景。支持声明式 YAML 配置、可插拔 LLM 后端、工具调用，适用于多智能体交互模式的研究和测试。

## Features

### Agent 体系
- **Agent ABC** — 统一基类，子类只需实现 `step()` 方法
- **LLMAgent** — 可插拔 LLM 后端（OpenAI/本地模型等），自动管理对话历史
- **ToolAgent** — 支持注册和调用工具函数，消息触发工具执行
- **Role** — 角色定义，包含名称、描述和目标

### 通信
- **MessageBus** — Agent 间通信总线，支持定向/广播消息路由
- **Message** — Pydantic 消息模型（sender, receiver, content, type）
- **Dead Letter** — 无法投递的消息自动记录

### 场景
- **ScenarioConfig** — 声明式场景配置，支持 YAML 文件定义
- **ScenarioRunner** — 多步仿真循环，自动收集指标
- **Factory** — 从配置自动构建 Agent、Sandbox 和 MessageBus

### 环境 & 评估
- **Sandbox** — 仿真沙箱，管理 Agent 集合和环境状态
- **EnvironmentState** — 共享键值存储 + 事件日志
- **MetricsCollector** — 步骤级指标收集（消息数、Agent 状态等）

### CLI
- `agent-sim run --example` — 运行内置示例
- `agent-sim run --config scene.yaml` — 从 YAML 配置运行
- `agent-sim validate scene.yaml` — 验证场景配置
- `agent-sim info` — 框架信息

## Tech Stack

| Category | Technology |
|----------|-----------|
| Language | Python 3.10+ |
| Data validation | Pydantic v2 |
| CLI | Click |
| Config | PyYAML |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Linting | Ruff |

## Project Structure

```
agent-sim/
├── src/agent_sim/
│   ├── __init__.py              # 顶层导出
│   ├── cli.py                   # CLI 入口
│   ├── log.py                   # 日志配置
│   ├── agent/
│   │   ├── base.py              # Agent ABC + AgentState
│   │   ├── role.py              # Role 角色定义
│   │   ├── llm_agent.py         # LLMAgent + LLMBackend
│   │   └── tool_agent.py        # ToolAgent + Tool
│   ├── communication/
│   │   ├── message.py           # Message + MessageType
│   │   └── bus.py               # MessageBus
│   ├── environment/
│   │   ├── state.py             # EnvironmentState
│   │   └── sandbox.py           # Sandbox
│   ├── scenario/
│   │   ├── config.py            # ScenarioConfig + YAML loader
│   │   ├── factory.py           # Config → Sandbox/Bus builder
│   │   └── runner.py            # ScenarioRunner + RunResult
│   └── metrics/
│       └── collector.py         # MetricsCollector
├── tests/                       # 144 tests
├── scenarios/                   # 示例 YAML 场景
└── examples/                    # Python 示例脚本
```

## Installation

```bash
git clone https://github.com/Jane-o-O-o-O/agent-sim.git
cd agent-sim
python -m venv .venv && source .venv/activate
pip install -e ".[dev]"
```

## Quick Start

### Python API

```python
from agent_sim import Agent, Sandbox, MessageBus, Message, ScenarioRunner
from agent_sim import LLMAgent, ToolAgent, load_scenario, build_scenario

# 方式 1: 编程式
class MyAgent(Agent):
    async def step(self):
        replies = []
        for msg in self.inbox:
            replies.append(Message(
                sender=self.name,
                receiver=msg.sender,
                content=f"echo:{msg.content}",
            ))
        self.inbox.clear()
        self.increment_step()
        return replies

sandbox = Sandbox(agents=[MyAgent(name="a"), MyAgent(name="b")])
bus = MessageBus()
# ... register and run

# 方式 2: YAML 配置
config = load_scenario("scenarios/ping_pong.yaml")
sandbox, bus = build_scenario(config)
runner = ScenarioRunner(sandbox=sandbox, bus=bus)
result = await runner.run(steps=config.steps)
```

### YAML 场景配置

```yaml
name: ping-pong
description: Ping-Pong 通信演示
steps: 5

agents:
  - name: coordinator
    type: ping
    role: coordinator
    context:
      targets: ["worker_1", "worker_2"]

  - name: worker_1
    type: echo
    role: worker
```

### CLI

```bash
# 运行内置示例
agent-sim run --example --steps 5

# 从 YAML 配置运行
agent-sim run --config scenarios/ping_pong.yaml

# 验证配置
agent-sim validate scenarios/ping_pong.yaml

# 详细日志
agent-sim -v run --config scenarios/ping_pong.yaml
```

## Agent Types

| Type | Description |
|------|------------|
| `echo` | 回显收到的消息 |
| `ping` | 第一步发 ping，收到 ping 回复 pong |
| `llm` | LLM 驱动的 Agent，可插拔后端 |
| `tool` | 工具调用 Agent，消息触发工具执行 |
| `custom` | 自定义 Agent 类（指定 module 和 class_name） |

## Roadmap

- [x] **v0.1.0** - Agent base class + MessageBus
- [x] **v0.2.0** - YAML config, LLMAgent, ToolAgent, logging
- [ ] **v0.3.0** - LLM backend integrations (OpenAI, local models)
- [ ] **v0.4.0** - Advanced metrics & visualization
- [ ] **v1.0.0** - Stable API, complete documentation

## License

MIT License (c) 2026 Jane-o-O-o-O
