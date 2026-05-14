"""Agent health monitoring with heartbeat detection and auto-recovery."""
from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """Agent 健康状态。"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    DEAD = "dead"


class AgentHealth(BaseModel):
    """单个 Agent 的健康信息。

    Attributes:
        agent_name: Agent 名称
        status: 健康状态
        last_heartbeat: 上次心跳时间
        last_step: 上次执行步数
        error_count: 累计错误数
        consecutive_errors: 连续错误数
        recovery_count: 恢复次数
    """

    agent_name: str
    status: HealthStatus = HealthStatus.HEALTHY
    last_heartbeat: float = 0.0
    last_step: int = 0
    error_count: int = 0
    consecutive_errors: int = 0
    recovery_count: int = 0


class HealthReport(BaseModel):
    """健康检查报告。

    Attributes:
        timestamp: 报告时间
        total_agents: Agent 总数
        healthy: 健康数
        degraded: 降级数
        unhealthy: 不健康数
        dead: 死亡数
        details: 各 Agent 详情
    """

    timestamp: float = 0.0
    total_agents: int = 0
    healthy: int = 0
    degraded: int = 0
    unhealthy: int = 0
    dead: int = 0
    details: list[AgentHealth] = Field(default_factory=list)


class AgentHealthMonitor:
    """Agent 健康监控器。

    监控所有 Agent 的运行状态，支持心跳检测、错误统计、自动恢复。

    Features:
        - 心跳超时检测
        - 连续错误自动标记为不健康
        - 自动恢复尝试
        - 健康报告生成

    Example:
        >>> monitor = AgentHealthMonitor(heartbeat_timeout=5.0)
        >>> monitor.register("agent_a")
        >>> monitor.heartbeat("agent_a", step=1)
        >>> report = monitor.check_all()
    """

    def __init__(
        self,
        heartbeat_timeout: float = 10.0,
        max_consecutive_errors: int = 3,
        recovery_fn: Callable[[str], bool] | None = None,
    ) -> None:
        """初始化健康监控器。

        Args:
            heartbeat_timeout: 心跳超时秒数
            max_consecutive_errors: 最大连续错误数（超过则标记为不健康）
            recovery_fn: 恢复函数，接收 agent_name 返回是否恢复成功
        """
        self._heartbeat_timeout = heartbeat_timeout
        self._max_consecutive_errors = max_consecutive_errors
        self._recovery_fn = recovery_fn
        self._agents: dict[str, AgentHealth] = {}

    def register(self, agent_name: str) -> None:
        """注册 Agent 进行监控。

        Args:
            agent_name: Agent 名称
        """
        self._agents[agent_name] = AgentHealth(
            agent_name=agent_name,
            last_heartbeat=time.time(),
        )
        logger.debug("注册监控: %s", agent_name)

    def unregister(self, agent_name: str) -> bool:
        """取消注册。

        Args:
            agent_name: Agent 名称

        Returns:
            是否成功取消
        """
        if agent_name in self._agents:
            del self._agents[agent_name]
            return True
        return False

    def heartbeat(self, agent_name: str, step: int = 0) -> None:
        """记录 Agent 心跳。

        Args:
            agent_name: Agent 名称
            step: 当前步数
        """
        if agent_name not in self._agents:
            self.register(agent_name)
            return

        health = self._agents[agent_name]
        health.last_heartbeat = time.time()
        health.last_step = step
        health.consecutive_errors = 0

        if health.status in (HealthStatus.DEGRADED, HealthStatus.UNHEALTHY):
            health.status = HealthStatus.HEALTHY
            health.recovery_count += 1
            logger.info("Agent %s 已恢复 (第%d次)", agent_name, health.recovery_count)

        health.status = HealthStatus.HEALTHY

    def record_error(self, agent_name: str, error: str = "") -> None:
        """记录 Agent 错误。

        Args:
            agent_name: Agent 名称
            error: 错误信息
        """
        if agent_name not in self._agents:
            self.register(agent_name)

        health = self._agents[agent_name]
        health.error_count += 1
        health.consecutive_errors += 1

        if health.consecutive_errors >= self._max_consecutive_errors:
            health.status = HealthStatus.UNHEALTHY
            logger.warning(
                "Agent %s 标记为不健康 (连续%d次错误)",
                agent_name, health.consecutive_errors,
            )
        elif health.consecutive_errors >= self._max_consecutive_errors // 2:
            health.status = HealthStatus.DEGRADED

    def check_agent(self, agent_name: str) -> HealthStatus:
        """检查单个 Agent 健康状态。

        Args:
            agent_name: Agent 名称

        Returns:
            健康状态
        """
        if agent_name not in self._agents:
            return HealthStatus.DEAD

        health = self._agents[agent_name]
        now = time.time()

        # 检查心跳超时
        if now - health.last_heartbeat > self._heartbeat_timeout:
            if health.status != HealthStatus.DEAD:
                health.status = HealthStatus.DEAD
                logger.warning("Agent %s 心跳超时，标记为死亡", agent_name)

        return health.status

    def check_all(self) -> HealthReport:
        """检查所有 Agent 健康状态。

        Returns:
            健康检查报告
        """
        report = HealthReport(timestamp=time.time(), total_agents=len(self._agents))

        for agent_name in self._agents:
            status = self.check_agent(agent_name)
            if status == HealthStatus.HEALTHY:
                report.healthy += 1
            elif status == HealthStatus.DEGRADED:
                report.degraded += 1
            elif status == HealthStatus.UNHEALTHY:
                report.unhealthy += 1
            else:
                report.dead += 1

        report.details = list(self._agents.values())
        return report

    def try_recover(self, agent_name: str) -> bool:
        """尝试恢复不健康的 Agent。

        Args:
            agent_name: Agent 名称

        Returns:
            是否恢复成功
        """
        if agent_name not in self._agents:
            return False

        health = self._agents[agent_name]
        if health.status in (HealthStatus.HEALTHY,):
            return True

        if self._recovery_fn:
            try:
                success = self._recovery_fn(agent_name)
                if success:
                    health.status = HealthStatus.HEALTHY
                    health.consecutive_errors = 0
                    health.recovery_count += 1
                    logger.info("Agent %s 恢复成功", agent_name)
                    return success
            except Exception as e:
                logger.error("恢复 Agent %s 失败: %s", agent_name, e)
                return False

        return False

    def try_recover_all(self) -> dict[str, bool]:
        """尝试恢复所有不健康的 Agent。

        Returns:
            各 Agent 恢复结果
        """
        results = {}
        for agent_name, health in self._agents.items():
            if health.status in (HealthStatus.UNHEALTHY, HealthStatus.DEAD):
                results[agent_name] = self.try_recover(agent_name)
        return results

    @property
    def unhealthy_agents(self) -> list[str]:
        """获取不健康的 Agent 名称列表。"""
        return [
            name for name, health in self._agents.items()
            if health.status in (HealthStatus.UNHEALTHY, HealthStatus.DEAD)
        ]

    @property
    def agent_count(self) -> int:
        """监控的 Agent 数量。"""
        return len(self._agents)
