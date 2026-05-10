# 🤖 Agent Sim

> 多智能体仿真框架 — 测试 Agent 通信、协作与评估

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 项目简介

Agent Sim 是一个多智能体仿真框架，用于定义、运行和评估多个 Agent 之间的通信与协作场景。适用于研究和测试多 Agent 系统的交互模式、冲突解决策略以及整体效能。

## ✨ 核心特性

### 🧑‍💻 Agent 定义
- 基于角色（Role）、工具（Tools）、目标（Goals）的 Agent 配置
- 支持自定义 Agent 行为与决策逻辑
- 声明式 Agent 定义，支持 YAML/Python 配置

### 🌍 环境/沙箱仿真
- 隔离的仿真环境，Agent 在沙箱中运行
- 可配置的环境状态与资源限制
- 事件驱动的状态更新

### 📡 通信总线
- Agent 间消息传递机制
- 支持广播、单播、组播模式
- 消息队列与异步处理

### 🎬 场景运行器
- 声明式场景定义
- 多步骤流程编排
- 条件终止与超时控制

### 📊 指标采集
- 任务完成率
- 通信效率指标
- Agent 资源消耗统计
- 协作质量评分

## 🛠️ 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| 异步 | asyncio |
| 数据验证 | pydantic |
| CLI | click |
| 测试 | pytest, pytest-asyncio |

## 📁 项目结构

```
agent-sim/
├── src/
│   └── agent_sim/
│       ├── __init__.py
│       ├── cli.py              # CLI 入口
│       ├── agent/              # Agent 核心
│       │   ├── __init__.py
│       │   ├── base.py         # Agent 基类
│       │   ├── role.py         # 角色定义
│       │   └── tool.py         # 工具抽象
│       ├── environment/        # 仿真环境
│       │   ├── __init__.py
│       │   ├── sandbox.py      # 沙箱环境
│       │   └── state.py        # 环境状态
│       ├── communication/      # 通信模块
│       │   ├── __init__.py
│       │   ├── bus.py          # 通信总线
│       │   ├── message.py      # 消息定义
│       │   └── protocol.py     # 通信协议
│       ├── scenario/           # 场景运行
│       │   ├── __init__.py
│       │   ├── runner.py       # 场景运行器
│       │   └── config.py       # 场景配置
│       └── metrics/            # 指标采集
│           ├── __init__.py
│           ├── collector.py    # 指标收集器
│           └── reporter.py     # 报告生成
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_agent.py
│   ├── test_environment.py
│   ├── test_communication.py
│   ├── test_scenario.py
│   └── test_metrics.py
├── examples/
├── pyproject.toml
└── README.md
```

## 🚀 安装

```bash
git clone https://github.com/Jane-o-O-o-O/agent-sim.git
cd agent-sim

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## 📖 使用方法

### CLI 命令

```bash
# 运行场景
agent-sim run --config scenario.yaml

# 列出已注册 Agent
agent-sim list-agents

# 查看仿真报告
agent-sim report --run-id <id>
```

### Python API

```python
import asyncio
from agent_sim.agent import Agent, Role
from agent_sim.environment import Sandbox
from agent_sim.communication import MessageBus
from agent_sim.scenario import ScenarioRunner

async def main():
    # 定义 Agent
    researcher = Agent(name="researcher", role=Role(name="researcher", goals=["find_info"]))
    planner = Agent(name="planner", role=Role(name="planner", goals=["create_plan"]))

    # 创建环境
    sandbox = Sandbox(agents=[researcher, planner])
    bus = MessageBus()

    # 运行场景
    runner = ScenarioRunner(sandbox=sandbox, bus=bus)
    results = await runner.run(steps=10)
    print(results)

asyncio.run(main())
```

## 🗺️ 路线图

- [ ] **v0.1.0** — 基础框架：Agent 定义、沙箱环境
- [ ] **v0.2.0** — 通信总线与消息协议
- [ ] **v0.3.0** — 场景编排与运行器
- [ ] **v0.4.0** — 指标采集与可视化
- [ ] **v1.0.0** — 稳定 API，完整文档

## 📄 许可证

MIT License © 2026 Jane-o-O-o-O
