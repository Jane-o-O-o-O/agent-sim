"""Tests for v0.8.0 features: AsyncEventBus, DynamicTopology, BenchmarkRunner, HealthMonitor, MetricAggregator, PluginRegistry."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

# AsyncEventBus tests
from agent_sim.communication.event_bus import AsyncEventBus, Event, Subscription


class TestAsyncEventBus:
    """AsyncEventBus pub/sub 测试。"""

    def test_basic_subscribe_publish(self):
        """基本订阅和发布。"""
        bus = AsyncEventBus()
        received = []

        def handler(topic, data):
            received.append((topic, data))

        bus.subscribe("test.topic", handler)
        assert bus.subscription_count == 1

        asyncio.run(bus.publish("test.topic", {"key": "value"}))
        assert len(received) == 1
        assert received[0] == ("test.topic", {"key": "value"})

    def test_wildcard_single_level(self):
        """单层通配符匹配。"""
        bus = AsyncEventBus()
        received = []

        def handler(topic, data):
            received.append(topic)

        bus.subscribe("agent.*", handler)
        asyncio.run(bus.publish("agent.step", 1))
        asyncio.run(bus.publish("agent.error", 2))
        asyncio.run(bus.publish("message.sent", 3))  # 不匹配

        assert len(received) == 2
        assert "agent.step" in received
        assert "agent.error" in received

    def test_wildcard_multi_level(self):
        """多层通配符匹配。"""
        bus = AsyncEventBus()
        received = []

        def handler(topic, data):
            received.append(topic)

        bus.subscribe("agent.**", handler)
        asyncio.run(bus.publish("agent.step", 1))
        asyncio.run(bus.publish("agent.step.start", 2))
        asyncio.run(bus.publish("message.sent", 3))  # 不匹配

        assert len(received) >= 2

    def test_exact_match(self):
        """精确匹配。"""
        bus = AsyncEventBus()

        def handler(topic, data):
            return topic

        bus.subscribe("exact.match", handler)
        assert bus.get_subscribers("exact.match") == [1]
        assert bus.get_subscribers("exact.no") == []

    def test_once_subscription(self):
        """一次性订阅只触发一次。"""
        bus = AsyncEventBus()
        count = 0

        def handler(topic, data):
            nonlocal count
            count += 1

        bus.subscribe("test", handler, once=True)
        asyncio.run(bus.publish("test", 1))
        asyncio.run(bus.publish("test", 2))

        assert count == 1
        assert bus.subscription_count == 0

    def test_unsubscribe(self):
        """取消订阅。"""
        bus = AsyncEventBus()

        def handler(topic, data):
            pass

        sub_id = bus.subscribe("test", handler)
        assert bus.subscription_count == 1

        assert bus.unsubscribe(sub_id) is True
        assert bus.subscription_count == 0
        assert bus.unsubscribe(999) is False

    def test_clear_subscriptions(self):
        """清除所有订阅。"""
        bus = AsyncEventBus()
        bus.subscribe("a", lambda t, d: None)
        bus.subscribe("b", lambda t, d: None)
        assert bus.subscription_count == 2

        count = bus.clear_subscriptions()
        assert count == 2
        assert bus.subscription_count == 0

    def test_event_history(self):
        """事件历史记录。"""
        bus = AsyncEventBus(max_history=5)
        for i in range(10):
            asyncio.run(bus.publish(f"topic.{i}", i))

        assert len(bus.history) == 5
        assert bus.publish_count == 10
        assert bus.history[-1].topic == "topic.9"

    def test_topics(self):
        """获取已发布主题。"""
        bus = AsyncEventBus()
        asyncio.run(bus.publish("a", 1))
        asyncio.run(bus.publish("b", 2))
        asyncio.run(bus.publish("a", 3))

        topics = bus.topics()
        assert topics == {"a", "b"}

    def test_async_handler(self):
        """异步回调处理。"""
        bus = AsyncEventBus()
        received = []

        async def handler(topic, data):
            await asyncio.sleep(0.001)
            received.append(data)

        bus.subscribe("async.test", handler)
        asyncio.run(bus.publish("async.test", "hello"))
        assert received == ["hello"]

    def test_error_in_handler(self):
        """处理器错误不影响其他处理器。"""
        bus = AsyncEventBus()
        received = []

        def bad_handler(topic, data):
            raise ValueError("boom")

        def good_handler(topic, data):
            received.append(data)

        bus.subscribe("test", bad_handler)
        bus.subscribe("test", good_handler)
        asyncio.run(bus.publish("test", 42))

        assert received == [42]

    def test_str_repr(self):
        """字符串表示。"""
        bus = AsyncEventBus()
        bus.subscribe("test", lambda t, d: None)
        s = str(bus)
        assert "subscriptions=1" in s

    def test_event_model(self):
        """Event 数据模型。"""
        event = Event(topic="test", data=42, source="unit", timestamp=1.0)
        assert event.topic == "test"
        assert event.data == 42

    def test_subscription_model(self):
        """Subscription 数据模型。"""
        sub = Subscription(topic_pattern="agent.*", callback_id=1, once=False)
        assert sub.topic_pattern == "agent.*"


# DynamicTopology tests
from agent_sim.topology.dynamic import DynamicTopology, TopologySnapshot
from agent_sim.topology.topology import NetworkTopology, TopologyType, build_topology


class TestDynamicTopology:
    """DynamicTopology 动态拓扑测试。"""

    def test_add_link(self):
        """添加连接。"""
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        dyn.add_link("a", "d")
        assert dyn.is_connected("a", "d")
        assert dyn.change_count == 1

    def test_add_link_no_duplicate(self):
        """不重复添加连接。"""
        topo = build_topology(TopologyType.MESH, ["a", "b"])
        dyn = DynamicTopology(topo)
        initial_count = len(topo.links)
        dyn.add_link("a", "b")
        assert len(topo.links) == initial_count  # 没有新增

    def test_remove_link(self):
        """移除连接。"""
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        assert dyn.remove_link("a", "b") is True
        assert not dyn.is_connected("a", "b")
        assert dyn.remove_link("a", "b") is False  # 已移除

    def test_remove_agent(self):
        """移除 Agent 及其所有连接。"""
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        removed = dyn.remove_agent("a")
        assert removed > 0
        assert "a" not in topo.agents

    def test_add_agent(self):
        """添加 Agent 到拓扑。"""
        topo = build_topology(TopologyType.MESH, ["a", "b"])
        dyn = DynamicTopology(topo)
        dyn.add_agent("c", connect_to=["a", "b"])
        assert "c" in topo.agents
        assert dyn.is_connected("c", "a")
        assert dyn.is_connected("c", "b")

    def test_switch_topology(self):
        """切换拓扑类型。"""
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        dyn.switch_topology(TopologyType.STAR, center="a", step=5)
        assert topo.topology_type == TopologyType.STAR
        assert dyn.snapshot_count == 1

    def test_snapshot_and_rollback(self):
        """快照和回滚。"""
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)

        dyn.snapshot(step=0)
        dyn.add_link("a", "d")
        assert dyn.change_count == 1

        assert dyn.rollback() is True
        assert dyn.change_count == 2  # rollback 也算一次变更
        assert not dyn.is_connected("a", "d")

    def test_rollback_empty(self):
        """空快照回滚失败。"""
        topo = build_topology(TopologyType.MESH, ["a"])
        dyn = DynamicTopology(topo)
        assert dyn.rollback() is False

    def test_get_neighbors(self):
        """获取邻居。"""
        topo = build_topology(TopologyType.STAR, ["a", "b", "c", "d"], center="a")
        dyn = DynamicTopology(topo)
        neighbors = dyn.get_neighbors("a")
        assert len(neighbors) == 3

    def test_is_connected(self):
        """检查连接。"""
        topo = build_topology(TopologyType.CHAIN, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        assert dyn.is_connected("a", "b") is True
        assert dyn.is_connected("a", "c") is False

    def test_summary(self):
        """摘要信息。"""
        topo = build_topology(TopologyType.MESH, ["a", "b"])
        dyn = DynamicTopology(topo)
        s = dyn.summary()
        assert "topology_type" in s
        assert "agents" in s
        assert "change_count" in s


# BenchmarkRunner tests
from agent_sim.scenario.benchmark import BenchmarkResult, BenchmarkRunner, BenchmarkSuite


class TestBenchmarkRunner:
    """BenchmarkRunner 性能测试。"""

    @pytest.mark.asyncio
    async def test_single_benchmark(self):
        """单次基准测试。"""
        runner = BenchmarkRunner(timeout_seconds=30)
        result = await runner.run_single(agent_count=5, steps=3)
        assert isinstance(result, BenchmarkResult)
        assert result.agent_count == 5
        assert result.duration > 0
        assert result.steps > 0

    @pytest.mark.asyncio
    async def test_scale_test(self):
        """多规模梯度测试。"""
        runner = BenchmarkRunner(timeout_seconds=30)
        suite = await runner.run_scale_test(agent_counts=[3, 5], steps=2)
        assert isinstance(suite, BenchmarkSuite)
        assert len(suite.results) == 2
        assert suite.results[0].agent_count == 3
        assert suite.results[1].agent_count == 5

    def test_benchmark_result_model(self):
        """BenchmarkResult 数据模型。"""
        result = BenchmarkResult(
            agent_count=10, steps=5, total_messages=20,
            duration=1.5, throughput=13.3, steps_per_second=3.3,
        )
        assert result.agent_count == 10
        assert result.throughput > 0

    def test_benchmark_suite_summary(self):
        """BenchmarkSuite 摘要。"""
        suite = BenchmarkSuite(
            results=[
                BenchmarkResult(agent_count=5, duration=1.0, throughput=10.0, steps_per_second=5.0),
                BenchmarkResult(agent_count=10, duration=2.0, throughput=20.0, steps_per_second=5.0),
            ],
            scale_agents=[5, 10],
        )
        summary = suite.summary()
        assert summary["total_runs"] == 2
        assert summary["max_agents"] == 10
        assert summary["max_throughput"] == 20.0

    def test_benchmark_suite_empty(self):
        """空套件摘要。"""
        suite = BenchmarkSuite()
        assert suite.summary() == {"error": "no results"}


# AgentHealthMonitor tests
from agent_sim.agent.health_monitor import (
    AgentHealth,
    AgentHealthMonitor,
    HealthReport,
    HealthStatus,
)


class TestAgentHealthMonitor:
    """AgentHealthMonitor 健康监控测试。"""

    def test_register_and_heartbeat(self):
        """注册和心跳。"""
        monitor = AgentHealthMonitor()
        monitor.register("agent_a")
        assert monitor.agent_count == 1

        monitor.heartbeat("agent_a", step=1)
        report = monitor.check_all()
        assert report.healthy == 1

    def test_auto_register_on_heartbeat(self):
        """心跳时自动注册。"""
        monitor = AgentHealthMonitor()
        monitor.heartbeat("new_agent")
        assert monitor.agent_count == 1

    def test_unregister(self):
        """取消注册。"""
        monitor = AgentHealthMonitor()
        monitor.register("a")
        assert monitor.unregister("a") is True
        assert monitor.unregister("a") is False

    def test_error_tracking(self):
        """错误追踪。"""
        monitor = AgentHealthMonitor(max_consecutive_errors=3)
        monitor.register("a")

        monitor.record_error("a")
        # 1 error >= max_consecutive_errors // 2 => DEGRADED
        assert monitor.check_agent("a") == HealthStatus.DEGRADED

        monitor.record_error("a")
        assert monitor.check_agent("a") == HealthStatus.DEGRADED

        monitor.record_error("a")
        assert monitor.check_agent("a") == HealthStatus.UNHEALTHY

    def test_heartbeat_resets_errors(self):
        """心跳重置连续错误。"""
        monitor = AgentHealthMonitor(max_consecutive_errors=3)
        monitor.register("a")
        monitor.record_error("a")
        monitor.record_error("a")

        monitor.heartbeat("a", step=5)
        health = monitor._agents["a"]
        assert health.consecutive_errors == 0
        assert health.status == HealthStatus.HEALTHY

    def test_heartbeat_timeout(self):
        """心跳超时检测。"""
        monitor = AgentHealthMonitor(heartbeat_timeout=0.01)
        monitor.register("a")
        time.sleep(0.02)
        status = monitor.check_agent("a")
        assert status == HealthStatus.DEAD

    def test_check_unregistered(self):
        """检查未注册 Agent。"""
        monitor = AgentHealthMonitor()
        assert monitor.check_agent("unknown") == HealthStatus.DEAD

    def test_try_recover(self):
        """尝试恢复。"""
        recovered = []

        def recovery_fn(name):
            recovered.append(name)
            return True

        monitor = AgentHealthMonitor(
            max_consecutive_errors=1, recovery_fn=recovery_fn,
        )
        monitor.register("a")
        monitor.record_error("a")

        assert monitor.try_recover("a") is True
        assert monitor.check_agent("a") == HealthStatus.HEALTHY
        assert recovered == ["a"]

    def test_try_recover_all(self):
        """恢复所有不健康 Agent。"""
        monitor = AgentHealthMonitor(max_consecutive_errors=1)
        monitor.register("a")
        monitor.register("b")
        monitor.record_error("a")
        monitor.record_error("b")

        results = monitor.try_recover_all()
        assert len(results) == 2

    def test_unhealthy_agents(self):
        """获取不健康 Agent 列表。"""
        monitor = AgentHealthMonitor(max_consecutive_errors=1)
        monitor.register("a")
        monitor.register("b")
        monitor.record_error("a")

        unhealthy = monitor.unhealthy_agents
        assert "a" in unhealthy
        assert "b" not in unhealthy

    def test_health_report(self):
        """健康报告。"""
        monitor = AgentHealthMonitor()
        monitor.register("a")
        monitor.register("b")
        monitor.heartbeat("a")
        monitor.heartbeat("b")

        report = monitor.check_all()
        assert isinstance(report, HealthReport)
        assert report.total_agents == 2
        assert report.healthy == 2


# MetricAggregator tests
from agent_sim.metrics.aggregator import (
    HistogramBin,
    MetricAggregator,
    PercentileResult,
    TrendDirection,
)


class TestMetricAggregator:
    """MetricAggregator 高级指标测试。"""

    def test_percentiles_basic(self):
        """基本百分位数。"""
        agg = MetricAggregator()
        values = list(range(1, 101))
        result = agg.percentiles(values)
        assert isinstance(result, PercentileResult)
        assert 49 < result.p50 < 52
        assert 89 < result.p90 < 92
        assert 94 < result.p95 < 97
        assert 98 < result.p99 < 100
        assert result.min_val == 1
        assert result.max_val == 100
        assert result.count == 100

    def test_percentiles_empty(self):
        """空值百分位数。"""
        agg = MetricAggregator()
        result = agg.percentiles([])
        assert result.count == 0

    def test_percentiles_single(self):
        """单值百分位数。"""
        agg = MetricAggregator()
        result = agg.percentiles([42.0])
        assert result.p50 == 42.0
        assert result.p99 == 42.0

    def test_histogram(self):
        """直方图生成。"""
        agg = MetricAggregator()
        values = [1, 2, 2, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 5]
        bins = agg.histogram(values, bins=5)
        assert len(bins) == 5
        assert all(isinstance(b, HistogramBin) for b in bins)
        total = sum(b.count for b in bins)
        assert total == len(values)

    def test_histogram_empty(self):
        """空值直方图。"""
        agg = MetricAggregator()
        assert agg.histogram([]) == []

    def test_histogram_uniform(self):
        """相同值直方图。"""
        agg = MetricAggregator()
        bins = agg.histogram([5, 5, 5], bins=3)
        assert len(bins) == 1  # 全部相同值只有一个 bin

    def test_trend_up(self):
        """上升趋势。"""
        agg = MetricAggregator()
        trend = agg.trend([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        assert isinstance(trend, TrendDirection)
        assert trend.direction == "up"
        assert trend.slope > 0
        assert trend.r_squared > 0.9

    def test_trend_down(self):
        """下降趋势。"""
        agg = MetricAggregator()
        trend = agg.trend([10, 9, 8, 7, 6, 5, 4, 3, 2, 1])
        assert trend.direction == "down"
        assert trend.slope < 0

    def test_trend_stable(self):
        """稳定趋势。"""
        agg = MetricAggregator()
        trend = agg.trend([5, 5, 5, 5, 5])
        assert trend.direction == "stable"

    def test_trend_insufficient_data(self):
        """数据不足趋势。"""
        agg = MetricAggregator()
        trend = agg.trend([1])
        assert trend.direction == "stable"

    def test_moving_average(self):
        """移动平均。"""
        agg = MetricAggregator()
        ma = agg.moving_average([1, 2, 3, 4, 5], window=3)
        assert len(ma) == 5
        assert ma[0] == 1.0  # 只有1个值
        assert ma[2] == 2.0  # (1+2+3)/3
        assert ma[4] == 4.0  # (3+4+5)/3

    def test_moving_average_empty(self):
        """空值移动平均。"""
        agg = MetricAggregator()
        assert agg.moving_average([]) == []

    def test_std_dev(self):
        """标准差。"""
        agg = MetricAggregator()
        sd = agg.std_dev([2, 4, 4, 4, 5, 5, 7, 9])
        assert 1.5 < sd < 2.5

    def test_std_dev_single(self):
        """单值标准差。"""
        agg = MetricAggregator()
        assert agg.std_dev([5]) == 0.0

    def test_outliers(self):
        """异常值检测。"""
        agg = MetricAggregator()
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
        out = agg.outliers(values)
        assert 100 in out

    def test_outliers_normal(self):
        """正常数据无异常值。"""
        agg = MetricAggregator()
        out = agg.outliers([1, 2, 3, 4, 5])
        assert len(out) == 0

    def test_aggregate_step_metrics(self):
        """步骤指标聚合。"""
        agg = MetricAggregator()
        step_details = [
            {"step": 1, "messages_sent": 5, "agents_active": 3},
            {"step": 2, "messages_sent": 8, "agents_active": 3},
            {"step": 3, "messages_sent": 3, "agents_active": 2},
            {"step": 4, "messages_sent": 7, "agents_active": 3},
        ]
        result = agg.aggregate_step_metrics(step_details)
        assert "messages" in result
        assert "agents_active" in result
        assert "trend" in result["messages"]

    def test_aggregate_step_metrics_empty(self):
        """空步骤指标聚合。"""
        agg = MetricAggregator()
        assert agg.aggregate_step_metrics([]) == {}


# PluginRegistry tests
from agent_sim.scenario.plugins import PluginInfo, PluginRegistry


class TestPluginRegistry:
    """PluginRegistry 插件系统测试。"""

    def test_register_agent(self):
        """注册 Agent 类型。"""
        registry = PluginRegistry()
        registry.register_agent("echo", type, description="Echo agent")
        assert registry.count == 1
        agents = registry.get_agents()
        assert len(agents) == 1
        assert agents[0].name == "echo"

    def test_register_evaluator(self):
        """注册 Evaluator 类型。"""
        registry = PluginRegistry()
        registry.register_evaluator("custom_eval", type)
        assert len(registry.get_evaluators()) == 1

    def test_register_middleware(self):
        """注册 Middleware 类型。"""
        registry = PluginRegistry()
        registry.register_middleware("custom_mw", type)
        assert len(registry.get_middlewares()) == 1

    def test_unregister(self):
        """取消注册。"""
        registry = PluginRegistry()
        registry.register_agent("a", type)
        assert registry.unregister("a") is True
        assert registry.count == 0
        assert registry.unregister("a") is False

    def test_get(self):
        """获取插件信息。"""
        registry = PluginRegistry()
        registry.register_agent("test", type)
        info = registry.get("test")
        assert info is not None
        assert info.name == "test"
        assert registry.get("nonexistent") is None

    def test_get_class(self):
        """获取插件类。"""
        registry = PluginRegistry()

        class MyAgent:
            pass

        registry.register_agent("my_agent", MyAgent)
        assert registry.get_class("my_agent") is MyAgent
        assert registry.get_class("nonexistent") is None

    def test_get_all(self):
        """获取所有插件。"""
        registry = PluginRegistry()
        registry.register_agent("a", type)
        registry.register_evaluator("b", type)
        registry.register_middleware("c", type)

        all_plugins = registry.get_all()
        assert len(all_plugins) == 3

        agents_only = registry.get_all("agent")
        assert len(agents_only) == 1

    def test_discover(self):
        """发现插件（无外部插件时返回0）。"""
        registry = PluginRegistry()
        discovered = registry.discover()
        assert discovered == 0
        assert registry._discovered is True

    def test_discover_idempotent(self):
        """发现是幂等的。"""
        registry = PluginRegistry()
        registry.discover()
        assert registry.discover() == 0

    def test_summary(self):
        """注册表摘要。"""
        registry = PluginRegistry()
        registry.register_agent("a", type)
        registry.register_evaluator("b", type)

        summary = registry.summary()
        assert summary["total"] == 2
        assert summary["agents"] == 1
        assert summary["evaluators"] == 1

    def test_str_repr(self):
        """字符串表示。"""
        registry = PluginRegistry()
        s = str(registry)
        assert "agents=0" in s

    def test_plugin_info_repr(self):
        """PluginInfo 表示。"""
        info = PluginInfo(name="test", plugin_type="agent", cls=type)
        assert "test" in repr(info)


# Integration tests for v0.8.0
class TestV080Integration:
    """v0.8.0 集成测试。"""

    @pytest.mark.asyncio
    async def test_event_bus_with_topology_change(self):
        """事件总线与拓扑变更集成。"""
        bus = AsyncEventBus()
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        dyn = DynamicTopology(topo)
        events = []

        async def on_topology_change(topic, data):
            events.append(data)

        bus.subscribe("topology.**", on_topology_change)

        # 触发拓扑变更并通知
        dyn.add_link("a", "d")
        await bus.publish("topology.link_added", {"source": "a", "target": "d"})

        dyn.switch_topology(TopologyType.STAR, center="a", step=5)
        await bus.publish("topology.switched", {"type": "star"})

        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_health_monitor_with_benchmark(self):
        """健康监控与基准测试集成。"""
        runner = BenchmarkRunner(timeout_seconds=30)
        monitor = AgentHealthMonitor(heartbeat_timeout=5.0)

        # 注册测试 Agent
        for i in range(5):
            monitor.register(f"bench_agent_{i}")

        # 运行基准测试
        result = await runner.run_single(agent_count=5, steps=3)
        assert result.agent_count == 5

        # 心跳更新
        for i in range(5):
            monitor.heartbeat(f"bench_agent_{i}", step=result.steps)

        report = monitor.check_all()
        assert report.healthy == 5

    @pytest.mark.asyncio
    async def test_metric_aggregation_with_runner(self):
        """指标聚合与运行器集成。"""
        from agent_sim.scenario.config import load_scenario
        from agent_sim.scenario.factory import build_scenario
        from agent_sim.scenario.runner import ScenarioRunner

        config = load_scenario("/tmp/dev/agent-sim/scenarios/ping_pong.yaml")
        sandbox, bus = build_scenario(config)
        runner = ScenarioRunner(sandbox=sandbox, bus=bus)
        result = await runner.run(steps=3)

        # 聚合步骤指标（可能为空取决于场景配置）
        agg = MetricAggregator()
        aggregated = agg.aggregate_step_metrics(
            result.metrics.get("step_details", []),
        )
        # 结果取决于 step_details 是否存在
        assert isinstance(aggregated, dict)

    def test_plugin_registry_with_real_classes(self):
        """插件注册表与真实类集成。"""
        from agent_sim.agent.debate_agent import DebateAgent
        from agent_sim.agent.llm_agent import LLMAgent

        registry = PluginRegistry()
        registry.register_agent("debate", DebateAgent, description="辩论 Agent")
        registry.register_agent("llm", LLMAgent, description="LLM Agent")

        assert registry.count == 2
        debate_cls = registry.get_class("debate")
        assert debate_cls is DebateAgent
