# Agent Sim

Multi-agent simulation framework for testing agent communication, coordination, and evaluation.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## About

Agent Sim 是一个多智能体仿真框架，用于定义、运行和评估多个 Agent 之间的通信和协调场景。支持声明式 YAML 配置、可插拔 LLM 后端、工具调用、自动评估和生命周期钩子，适用于多智能体交互模式的研究和测试。

## Features

### Agent 体系
- **Agent ABC** — 统一基类，子类只需实现 `step()` 方法
- **LLMAgent** — 可插拔 LLM 后端（OpenAI/本地模型等），自动管理对话历史
- **MemoryAgent** — 记忆增强 LLM Agent，自动注入对话缓冲区和事实记忆到 prompt (v0.5.0)
- **ToolAgent** — 支持注册和调用工具函数，消息触发工具执行
- **DebateAgent** — 结构化辩论 Agent（支持/反对立场，多轮论证） (v0.4.0)
- **CollaborateAgent** — 协作解题 Agent（协调者/工作者/审核者模式） (v0.4.0)
- **Role** — 角色定义，包含名称、描述和目标
- **AgentHealthMonitor** — Agent 健康监控，心跳检测、错误追踪、自动恢复 (v0.8.0)

### LLM 集成
- **OpenAIBackend** — 异步 OpenAI API 调用，支持所有 OpenAI 兼容端点
- **TokenBucketRateLimiter** — 令牌桶限流器，防止 API 超速调用

### 记忆系统 (v0.4.0)
- **ConversationBuffer** — 全量对话缓冲区，自动 LRU 淘汰
- **SlidingWindowBuffer** — 滑动窗口缓冲区，保留最近 N 条消息
- **KeyFactMemory** — 键值事实记忆，支持置信度过滤和搜索

### 通信
- **MessageBus** — Agent 间通信总线，支持定向/广播消息路由
- **Message** — Pydantic 消息模型（sender, receiver, content, type, correlation_id）
- **Dead Letter** — 无法投递的消息自动记录
- **Middleware Pipeline** — 消息中间件管道，支持拦截/过滤/变换 (v0.5.0)
  - LoggingMiddleware, FilterMiddleware, TransformMiddleware
  - RateLimitMiddleware, DeduplicationMiddleware
- **ResponseTracker** — 请求-响应消息关联追踪 (v0.5.0)

### 网络拓扑 (v0.4.0)
- **NetworkTopology** — Agent 通信网络拓扑定义
- **TopologyType** — 支持 mesh/star/chain/tree/ring/custom 六种拓扑
- **build_topology()** — 一键构建指定拓扑

### 场景 & 生命周期
- **ScenarioConfig** — 声明式场景配置，支持 YAML 文件定义
- **ScenarioConfig.extends** — 场景继承，子配置覆盖父配置 (v0.7.0)
- **ScenarioRunner** — 多步仿真循环，支持顺序和并发执行模式 (v0.5.0 并发)
- **LifecycleHooks** — 7 种事件钩子（on_start, on_step, on_message, on_error 等）
- **Factory** — 从配置自动构建 Agent（含 LLM 后端）、Sandbox 和 MessageBus
- **CheckpointManager** — 仿真状态检查点，支持保存/恢复到 JSON (v0.5.0)
- **RetryManager** — Agent 错误恢复，指数退避重试 (v0.5.0)
- **SimulationMonitor** — 实时仿真监控，step回调、消息流追踪、进度条、通信矩阵 (v0.9.0)
- **TopologyScheduler** — 拓扑规则引擎，基于步数/条件自动切换网络拓扑 (v0.9.0)
- **CommunicationProtocol** — 结构化通信协议：RoundRobin轮流发言、BroadcastCollect任务分发、Consensus共识投票 (v0.9.0)
- **Scenario Templates** — 6个内置场景模板：ping_pong/debate/brainstorm/code_review/task_delegation/multi_round_discussion (v0.9.0)

### 评估系统
- **EvalSuite** — 可插拔评估套件，组合多个评估器
- **MessageVolumeEvaluator** — 评估消息通信活跃度
- **AgentParticipationEvaluator** — 评估 Agent 参与度
- **CompletionEvaluator** — 评估仿真完成度
- **LatencyEvaluator** — 评估运行延迟
- **NetworkHealthEvaluator** — 评估网络拓扑健康度 (v0.4.0)
- **ConversationFlowEvaluator** — 评估对话均衡度 (v0.4.0)
- **MetricAggregator** — 高级指标聚合：百分位数 P50/P90/P95/P99、直方图、趋势分析、移动平均、异常值检测 (v0.8.0)

### 可视化 (v0.4.0)
- **bar_chart()** — ASCII 水平柱状图（支持颜色）
- **line_chart()** — ASCII 折线图
- **sparkline()** — Unicode 迷你折线图
- **metrics_table()** — 指标数据表格
- **ConversationGraph** — Agent间消息流可视化：Mermaid序列图、ASCII通信矩阵、流量统计 (v0.9.0)

### 导出
- **export_messages_to_json** — 消息历史导出为 JSON
- **export_messages_to_markdown** — 消息历史导出为 Markdown
- **export_messages_to_csv** — 消息历史导出为 CSV (v0.5.0)
- **HTMLReport** — 美观的 HTML 仿真报告，含 SVG 图表和评估结果 (v0.7.0)
- **format_conversation_table** — 终端表格格式化

### 环境 & 指标
- **Sandbox** — 仿真沙箱，管理 Agent 集合和环境状态
- **EnvironmentState** — 共享键值存储 + 事件日志
- **MetricsCollector** — 步骤级指标收集（消息数、Agent 状态等）
- **AsyncEventBus** — 异步 pub/sub 事件总线，支持主题层级、通配符匹配（* 和 **）、一次性订阅 (v0.8.0)
- **DynamicTopology** — 运行时动态拓扑管理，添加/移除连接、切换拓扑类型、快照回滚 (v0.8.0)
- **PluginRegistry** — 插件注册表，支持 Agent/Evaluator/Middleware 类型注册和 entry_points 自动发现 (v0.8.0)
- **BenchmarkRunner** — 性能基准测试，多规模梯度测试（10-1000+ Agent），吞吐量/延迟统计 (v0.8.0)

### CLI
- `agent-sim run --example` — 运行内置示例
- `agent-sim run --config scene.yaml` — 从 YAML 配置运行
- `agent-sim validate scene.yaml` — 验证场景配置
- `agent-sim info` — 框架信息
- `agent-sim report --config scene.yaml` — 运行并生成终端可视化报告 (v0.4.0)
- `agent-sim export --config scene.yaml -o output.json` — 运行并导出消息 (JSON/Markdown/CSV/HTML) (v0.5.0, HTML v0.7.0)
- `agent-sim compare a.yaml b.yaml` — 对比两个场景结果 (v0.6.0)
- `agent-sim replay events.json` — 回放仿真事件日志 (v0.7.0)
- `agent-sim batch --config scene.yaml --runs 10` — 批量运行仿真并统计 (v0.7.0)
- `agent-sim init <template>` — 从模板创建场景 YAML 配置文件 (v0.9.0)
- `agent-sim graph --config scene.yaml --format mermaid` — 运行仿真并生成通信流图 (v0.9.0)

### 事件回放 (v0.7.0)
- **ReplayEngine** — 加载 EventRecorder 数据，按步回放仿真
- 支持按步数/事件类型过滤，导出时间线和摘要
- 从 JSON 文件或 EventRecorder 实例创建

### 批量运行 (v0.7.0)
- **BatchRunner** — 运行 N 次仿真，统计聚合结果
- **BatchResult** — 含平均值、标准差、最小/最大值等统计
- 支持从 ScenarioConfig 运行，每次使用独立实例

## Tech Stack

| Category | Technology |
|----------|-----------|
| Language | Python 3.10+ |
| Data validation | Pydantic v2 |
| CLI | Click |
| Config | PyYAML |
| LLM (optional) | OpenAI SDK |
| Testing | pytest, pytest-asyncio, pytest-cov |
| Linting | Ruff |

## Project Structure

```
agent-sim/
├── src/agent_sim/
│   ├── __init__.py              # 顶层导出
│   ├── cli.py                   # CLI 入口
│   ├── log.py                   # 日志配置
│   ├── export.py                # 消息导出 (JSON/Markdown/CSV/HTML) (v0.7.0)
│   ├── agent/
│   │   ├── base.py              # Agent ABC + AgentState
│   │   ├── role.py              # Role 角色定义
│   │   ├── llm_agent.py         # LLMAgent + LLMBackend
│   │   ├── memory_agent.py      # MemoryAgent (v0.5.0)
│   │   ├── openai_backend.py    # OpenAI API 后端
│   │   ├── rate_limiter.py      # 令牌桶限流器
│   │   ├── retry.py             # RetryManager 指数退避重试 (v0.5.0)
│   │   ├── tool_agent.py        # ToolAgent + Tool
│   │   └── debate_agent.py      # DebateAgent + CollaborateAgent (v0.4.0)
│   ├── communication/
│   │   ├── message.py           # Message + MessageType
│   │   ├── bus.py               # MessageBus
│   │   ├── middleware.py        # 消息中间件管道 (v0.5.0)
│   │   └── correlation.py       # ResponseTracker (v0.5.0)
│   ├── environment/
│   │   ├── state.py             # EnvironmentState
│   │   └── sandbox.py           # Sandbox
│   ├── memory/                  # Agent 记忆系统 (v0.4.0)
│   │   ├── buffer.py            # ConversationBuffer + SlidingWindowBuffer
│   │   └── facts.py             # KeyFactMemory
│   ├── topology/                # 网络拓扑 (v0.4.0)
│   │   └── topology.py          # NetworkTopology + build_topology
│   ├── viz/                     # 终端可视化 (v0.4.0)
│   │   ├── charts.py            # bar_chart, line_chart, sparkline, metrics_table
│   │   └── conversation_graph.py # ConversationGraph 消息流图 (v0.9.0)
│   ├── scenario/
│   │   ├── config.py            # ScenarioConfig + YAML loader
│   │   ├── factory.py           # Config → Sandbox/Bus builder (registry pattern v0.6.0)
│   │   ├── hooks.py             # LifecycleHooks
│   │   ├── runner.py            # ScenarioRunner + RunResult (concurrent + timeout)
│   │   ├── checkpoint.py        # CheckpointManager (v0.5.0)
│   │   ├── recorder.py          # EventRecorder (v0.6.0)
│   │   ├── replay.py            # ReplayEngine 事件回放 (v0.7.0)
│   │   ├── batch.py             # BatchRunner 批量运行 (v0.7.0)
│   │   ├── monitor.py           # SimulationMonitor 实时监控 (v0.9.0)
│   │   ├── protocol.py          # CommunicationProtocol 通信协议 (v0.9.0)
│   │   ├── topology_scheduler.py # TopologyScheduler 拓扑规则 (v0.9.0)
│   │   └── templates.py         # 场景模板库 (v0.9.0)
│   └── metrics/
│       ├── collector.py         # MetricsCollector
│       └── evaluator.py         # EvalSuite + Evaluators
├── tests/                       # 593 tests
├── scenarios/                   # 示例 YAML 场景
└── examples/                    # Python 示例脚本
```

## Installation

```bash
git clone https://github.com/Jane-o-O-o-O/agent-sim.git
cd agent-sim
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 可选：OpenAI 后端
pip install openai
```

## Quick Start

### Python API

```python
from agent_sim import Agent, Sandbox, MessageBus, Message, ScenarioRunner
from agent_sim import LLMAgent, ToolAgent, load_scenario, build_scenario
from agent_sim import LifecycleHooks, EvalSuite

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

# 添加生命周期钩子
hooks = LifecycleHooks()
hooks.on_step_end(lambda step, messages_sent: print(f"Step {step}: {messages_sent} msgs"))

runner = ScenarioRunner(sandbox=sandbox, bus=bus, hooks=hooks)
result = await runner.run(steps=10)

# 方式 2: YAML 配置
config = load_scenario("scenarios/ping_pong.yaml")
sandbox, bus = build_scenario(config)
runner = ScenarioRunner(sandbox=sandbox, bus=bus)
result = await runner.run(steps=config.steps)
```

### 记忆系统 (v0.4.0)

```python
from agent_sim import ConversationBuffer, SlidingWindowBuffer, KeyFactMemory

# 对话缓冲区
buf = SlidingWindowBuffer(window_size=10)
buf.add("system", "You are helpful")
buf.add("user", "What's the weather?")
messages = buf.get_messages()

# 事实记忆
mem = KeyFactMemory(max_facts=100)
mem.remember("user_name", "Alice", source="dialogue", confidence=0.9)
name = mem.recall("user_name")  # "Alice"
results = mem.search("user")    # [("user_name", "Alice")]
```

### 网络拓扑 (v0.4.0)

```python
from agent_sim import NetworkTopology, TopologyType, build_topology

# 星型拓扑
topo = build_topology(TopologyType.STAR, ["coordinator", "worker_1", "worker_2"], center="coordinator")
print(topo.to_ascii())

# 全连接拓扑
mesh = build_topology(TopologyType.MESH, ["a", "b", "c", "d"])
print(mesh.get_neighbors("a"))  # ["b", "c", "d"]
```

### 终端可视化 (v0.4.0)

```python
from agent_sim import bar_chart, line_chart, sparkline

# 柱状图
print(bar_chart({"A": 10, "B": 25, "C": 15}, title="Messages per Agent"))

# 折线图
print(line_chart([1, 5, 3, 8, 4, 7], title="Step Messages"))

# Sparkline
print(sparkline([1, 5, 3, 8, 4, 7]))  # ▁▅▂█▃▆
```

### 辩论场景 (v0.4.0)

```python
from agent_sim import DebateAgent, Role

pro = DebateAgent(
    name="pro_side",
    role=Role(name="advocate"),
    context={"stance": "for", "style": "balanced"},
)
con = DebateAgent(
    name="con_side",
    role=Role(name="critic"),
    context={"stance": "against", "style": "aggressive"},
)
```

### CLI 报告 (v0.4.0)

```bash
# 运行并生成终端可视化报告
agent-sim report --config scenarios/ping_pong.yaml
agent-sim report --config scenarios/debate.yaml --steps 4
```

### MemoryAgent (v0.5.0)

```python
from agent_sim import MemoryAgent, EchoLLMBackend

agent = MemoryAgent(
    name="assistant",
    backend=EchoLLMBackend(),
    system_prompt="You are a helpful assistant.",
    memory_window=10,
    include_facts=True,
)

# 自动管理记忆
agent.remember("user_name", "Alice", confidence=0.9)
agent.recall("user_name")  # "Alice"
# step() 时自动注入记忆上下文到 prompt
```

### 消息中间件 (v0.5.0)

```python
from agent_sim import MessageBus, FilterMiddleware, LoggingMiddleware, TransformMiddleware

bus = MessageBus()
bus.add_middleware(LoggingMiddleware())
bus.add_middleware(FilterMiddleware(blocked_senders={"spam"}))
bus.add_middleware(TransformMiddleware(
    transform=lambda m: m.model_copy(update={"content": f"[LOGGED] {m.content}"})
))
# 所有消息自动经过中间件管道处理
```

### 仿真检查点 (v0.5.0)

```python
from agent_sim import CheckpointManager

manager = CheckpointManager()
# 保存
checkpoint = manager.create_checkpoint(sandbox, bus, step=5)
manager.save(checkpoint, "checkpoint.json")
# 恢复
checkpoint = manager.load("checkpoint.json")
manager.restore(checkpoint, sandbox, bus)
```

### 并发执行 (v0.5.0)

```python
from agent_sim import ScenarioRunner

# 并发模式 — 所有 Agent 同时 step()
runner = ScenarioRunner(sandbox=sandbox, bus=bus, concurrent=True)
result = await runner.run(steps=10)
```

### CLI 导出 (v0.5.0)

```bash
# 导出为 JSON
agent-sim export --config scene.yaml -o messages.json
# 导出为 CSV
agent-sim export --config scene.yaml --format csv -o messages.csv
# 导出为 Markdown
agent-sim export --config scene.yaml --format markdown -o messages.md
```

### Agent 注册表 (v0.6.0)

```python
from agent_sim import register_agent_type, get_registered_types

# 查看已注册类型
print(get_registered_types())
# ['echo', 'ping', 'llm', 'memory', 'tool', 'debate', 'collaborate', 'custom']

# 注册自定义类型
register_agent_type("my_agent", lambda cfg: MyAgent(name=cfg.name))
# 之后可在 YAML 中使用 type: my_agent
```

### 事件记录器 (v0.6.0)

```python
from agent_sim import EventRecorder, LifecycleHooks, ScenarioRunner

recorder = EventRecorder()
hooks = LifecycleHooks()
recorder.attach_to(hooks)  # 自动绑定所有事件

runner = ScenarioRunner(sandbox=sandbox, bus=bus, hooks=hooks)
result = await runner.run(steps=10)

# 查看事件摘要
print(recorder.summary())
# {'total_events': 42, 'event_counts': {...}, 'duration': 1.5}

# 按类型过滤
errors = recorder.get_events(event_type="agent_error")
messages = recorder.get_events(event_type="message", step=3)

# 导出
recorder.export_json("events.json")
recorder.export_csv("events.csv")
```

### 仿真超时 (v0.6.0)

```python
from agent_sim import ScenarioRunner

# 设置 30 秒超时
runner = ScenarioRunner(sandbox=sandbox, bus=bus, timeout_seconds=30)
result = await runner.run(steps=1000)

if result.timed_out:
    print(f"超时! 已完成 {result.steps_completed} 步")
```

### CLI 对比 (v0.6.0)

```bash
# 对比两个场景的仿真结果
agent-sim compare scenarios/ping_pong.yaml scenarios/debate.yaml
agent-sim compare a.yaml b.yaml --steps 10

# 超时运行
agent-sim run --config scene.yaml --timeout 30
```

### 内置示例场景 (v0.6.0)

```bash
# 可直接使用内置场景
agent-sim run --config scenarios/ping_pong.yaml
agent-sim run --config scenarios/debate.yaml
agent-sim run --config scenarios/team_collaborate.yaml
```

### 事件回放 (v0.7.0)

```python
from agent_sim import ReplayEngine, EventRecorder

# 从 EventRecorder 创建回放引擎
engine = ReplayEngine.from_recorder(recorder)

# 按步回放
for step_events in engine.iter_steps():
    for event in step_events:
        print(f"Step {event.step}: {event.event_type} {event.data}")

# 按类型过滤
messages = engine.filter_by_type("message")
errors = engine.filter_by_type("agent_error")

# 摘要
print(engine.summary())
# {'total_events': 42, 'total_steps': 10, 'event_counts': {...}}

# 从 JSON 文件加载
engine = ReplayEngine.from_json("events.json")
```

### 批量运行 (v0.7.0)

```python
from agent_sim import BatchRunner, ScenarioConfig, load_scenario

# 从配置批量运行
config = load_scenario("scenarios/ping_pong.yaml")
runner = BatchRunner(runs=10)
batch_result = await runner.run_from_config(config)

# 统计结果
stats = batch_result.statistics
print(f"平均消息数: {stats['avg_messages']}")
print(f"平均耗时: {stats['avg_duration']}s")
print(f"成功率: {stats['success_rate']}")
```

### HTML 报告 (v0.7.0)

```python
from agent_sim import HTMLReport

# 生成 HTML 报告
report = HTMLReport(result, scenario_name="my-scenario")
report.save("report.html")
# 包含 SVG 图表、Agent 状态表格、评估结果
```

### 场景继承 (v0.7.0)

```yaml
# base.yaml
name: base-scenario
steps: 5
agents:
  - name: alice
    type: echo
  - name: bob
    type: echo

# child.yaml
extends: base.yaml
name: child-scenario
steps: 20  # 覆盖父配置的步数
agents:
  - name: alice
    type: echo
  - name: bob
    type: echo
  - name: charlie
    type: ping
    context:
      targets: [alice]
```

### CLI 批量和回放 (v0.7.0)

```bash
# 批量运行 10 次仿真
agent-sim batch --config scene.yaml --runs 10 --output stats.json

# 回放事件日志
agent-sim replay events.json
agent-sim replay events.json --step 1
agent-sim replay events.json --summary

# 导出 HTML 报告
agent-sim export --config scene.yaml --format html -o report.html

# 性能基准测试 (v0.8.0)
agent-sim benchmark --agents 10,50,100 --steps 10
agent-sim benchmark --agents 10,25,50,100,200 --steps 5 --timeout 120

# 查看插件 (v0.8.0)
agent-sim plugins
```

### AsyncEventBus (v0.8.0)

异步 pub/sub 事件总线，支持主题层级和通配符匹配。

```python
from agent_sim import AsyncEventBus

bus = AsyncEventBus()

# 订阅（支持 * 和 ** 通配符）
async def on_agent_event(topic, data):
    print(f"{topic}: {data}")

bus.subscribe("agent.*", on_agent_event)
bus.subscribe("message.**", lambda t, d: print(t))

# 发布
await bus.publish("agent.step", {"count": 1})
await bus.publish("message.sent", {"from": "a", "to": "b"})

# 一次性订阅
bus.subscribe("shutdown", lambda t, d: ..., once=True)
```

### DynamicTopology (v0.8.0)

运行时动态拓扑管理，支持快照回滚。

```python
from agent_sim import DynamicTopology, build_topology, TopologyType

topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
dyn = DynamicTopology(topo)

dyn.add_link("a", "d")  # 添加连接
dyn.remove_link("a", "b")  # 移除连接
dyn.add_agent("e", connect_to=["a", "c"])  # 添加 Agent
dyn.switch_topology(TopologyType.STAR, center="a", step=5)  # 切换拓扑

dyn.rollback()  # 回滚到上一个快照
```

### BenchmarkRunner (v0.8.0)

性能基准测试，支持多规模梯度测试。

```python
from agent_sim import BenchmarkRunner

runner = BenchmarkRunner(timeout_seconds=60)
suite = await runner.run_scale_test(
    agent_counts=[10, 50, 100, 200],
    steps=10,
)
print(suite.summary())
```

### AgentHealthMonitor (v0.8.0)

Agent 健康监控，心跳检测和自动恢复。

```python
from agent_sim import AgentHealthMonitor

monitor = AgentHealthMonitor(heartbeat_timeout=5.0, max_consecutive_errors=3)
monitor.register("agent_a")
monitor.heartbeat("agent_a", step=1)
monitor.record_error("agent_a")

report = monitor.check_all()
print(report.healthy, report.dead)
```

### MetricAggregator (v0.8.0)

高级指标聚合：百分位数、直方图、趋势分析。

```python
from agent_sim import MetricAggregator

agg = MetricAggregator()
pct = agg.percentiles([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
print(f"P50={pct.p50}, P95={pct.p95}")

hist = agg.histogram([1, 2, 2, 3, 3, 3, 4, 5], bins=5)
trend = agg.trend([10, 20, 30, 40, 50])
outliers = agg.outliers([1, 2, 3, 4, 100])
```

### PluginRegistry (v0.8.0)

插件系统，支持自定义 Agent/Evaluator/Middleware 注册。

```python
from agent_sim import PluginRegistry

registry = PluginRegistry()
registry.register_agent("my_agent", MyAgentClass, description="自定义 Agent")
registry.register_evaluator("my_eval", MyEvaluatorClass)

# 自动发现 entry_points 插件
registry.discover()
```

### SimulationMonitor (v0.9.0)

实时仿真监控，跟踪 step 回调、消息流和通信矩阵。

```python
from agent_sim import SimulationMonitor, MonitorConfig

config = MonitorConfig(show_messages=True, show_step_summary=True, compact=True)
monitor = SimulationMonitor(total_steps=10, config=config)

# 通过 ScenarioRunner hooks 集成
runner.hooks.on_simulation_start(lambda steps, agent_count: monitor.on_simulation_start(steps, agent_count))
runner.hooks.on_step_start(lambda step: monitor.on_step_start(step))
runner.hooks.on_message(lambda message, step: monitor.on_message(message.sender, message.receiver, message.content))
runner.hooks.on_step_end(lambda step, messages_sent: monitor.on_step_end(step, messages_sent))

# 分析
print(monitor.progress_bar())  # [████████░░░░░░░░░░░░] 40% (4/10)
print(monitor.get_communication_matrix())  # {a: {b: 5}, b: {a: 3}}
print(monitor.summary())
```

### TopologyScheduler (v0.9.0)

拓扑规则引擎，基于步数或条件自动切换网络拓扑。

```python
from agent_sim import TopologyScheduler, TopologyRule, DynamicTopology, TopologyType

topo = build_topology(TopologyType.MESH, ["leader", "w1", "w2", "w3"])
dyn = DynamicTopology(topo)
scheduler = TopologyScheduler(dyn)

# 声明式规则
scheduler.add_rule(TopologyRule(step=3, topology_type=TopologyType.STAR, center="leader"))
scheduler.add_rule(TopologyRule(step=7, topology_type=TopologyType.MESH))

# 条件规则
scheduler.add_conditional_rule(
    condition=lambda step: step % 5 == 0,
    topology_type=TopologyType.RING,
)

# 集成到 hooks
for step in range(10):
    scheduler.on_step(step)  # 自动在 step 3, 5, 7, 10 应用拓扑变更
```

### CommunicationProtocol (v0.9.0)

结构化通信协议，控制 Agent 间的消息流模式。

```python
from agent_sim import create_protocol, ProtocolType

# Round-Robin：轮流发言
protocol = create_protocol("round_robin", ["alice", "bob", "charlie"])
result = await protocol.execute_step(bus, agents)
print(result.phase)  # "alice speaking (round 1)"

# Broadcast-Collect：任务分发
protocol = create_protocol("broadcast_collect", ["manager", "dev_1", "dev_2"],
                           coordinator="manager")

# Consensus：共识投票
protocol = create_protocol("consensus", ["voter_1", "voter_2", "voter_3"], rounds=3)
```

### Scenario Templates (v0.9.0)

内置 6 个场景模板，快速创建常用仿真配置。

```bash
# 查看所有模板
agent-sim init list

# 从模板创建 YAML
agent-sim init debate
agent-sim init brainstorm -o my_brainstorm.yaml
```

```python
from agent_sim import get_template, list_templates, template_info

# 列出模板
print(list_templates())
# ['brainstorm', 'code_review', 'debate', 'multi_round_discussion', 'ping_pong', 'task_delegation']

# 获取模板
template = get_template("debate")
info = template_info("brainstorm")
```

### ConversationGraph (v0.9.0)

Agent 间消息流可视化：Mermaid 序列图、ASCII 通信矩阵。

```python
from agent_sim import ConversationGraph

graph = ConversationGraph.from_history(result.message_history)

# Mermaid 序列图
print(graph.to_mermaid(title="Agent 通信流"))
# sequenceDiagram
#     participant alice
#     participant bob
#     alice->>bob: hello
#     bob->>alice: hi there

# ASCII 通信矩阵
print(graph.to_ascii_matrix())

# 流量统计
print(graph.to_flow_summary())
```

```bash
# CLI 生成通信图
agent-sim graph --config scene.yaml --format mermaid
agent-sim graph --config scene.yaml --format ascii
agent-sim graph --config scene.yaml --format summary
```

## Agent Types

| Type | Description |
|------|------------|
| `echo` | 回显收到的消息 |
| `ping` | 第一步发 ping，收到 ping 回复 pong |
| `llm` | LLM 驱动的 Agent，可插拔后端 |
| `memory` | 记忆增强 LLM Agent，自动注入记忆到 prompt (v0.5.0) |
| `tool` | 工具调用 Agent，消息触发工具执行 |
| `debate` | 辩论 Agent，支持/反对立场论证 (v0.4.0) |
| `collaborate` | 协作 Agent，协调者/工作者/审核者 (v0.4.0) |
| `custom` | 自定义 Agent 类（指定 module 和 class_name） |

## Lifecycle Hooks

```python
hooks = LifecycleHooks()
hooks.on_simulation_start(lambda steps, agent_count: ...)
hooks.on_simulation_end(lambda result, duration: ...)
hooks.on_step_start(lambda step: ...)
hooks.on_step_end(lambda step, messages_sent: ...)
hooks.on_message(lambda message, step: ...)
hooks.on_agent_error(lambda agent_name, error, step: ...)
hooks.on_agent_state_change(lambda agent_name, old_state, new_state: ...)
```

## Roadmap

- [x] **v0.1.0** - Agent base class + MessageBus
- [x] **v0.2.0** - YAML config, LLMAgent, ToolAgent, logging
- [x] **v0.3.0** - OpenAI backend, evaluation system, lifecycle hooks, export
- [x] **v0.4.0** - Memory system, topology, visualization, debate/collaborate agents
- [x] **v0.5.0** - MemoryAgent, middleware pipeline, checkpointing, retry, concurrent, CSV export
- [x] **v0.6.0** - Agent registry, EventRecorder, simulation timeout, CLI compare, built-in scenarios
- [x] **v0.7.0** - ReplayEngine, BatchRunner, HTML report, scenario inheritance, CLI replay/batch
- [x] **v0.8.0** - AsyncEventBus, DynamicTopology, BenchmarkRunner, HealthMonitor, MetricAggregator, PluginRegistry, CLI benchmark/plugins
- [x] **v0.9.0** - SimulationMonitor, TopologyScheduler, CommunicationProtocol, ScenarioTemplates, ConversationGraph, CLI init/graph
- [ ] **v1.0.0** - Stable API, complete documentation

## License

MIT License (c) 2026 Jane-o-O-o-O
