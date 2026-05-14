"""Dynamic topology management for runtime topology switching."""
from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from agent_sim.topology.topology import (
    Link,
    NetworkTopology,
    TopologyType,
    build_topology,
)

logger = logging.getLogger(__name__)


class TopologySnapshot(BaseModel):
    """拓扑快照，用于回滚。

    Attributes:
        topology_type: 拓扑类型
        links: 连接列表
        center: 中心节点
        step: 快照时的仿真步数
    """

    topology_type: TopologyType = TopologyType.MESH
    links: list[Link] = Field(default_factory=list)
    center: str | None = None
    step: int = 0


class DynamicTopology:
    """动态拓扑管理器。

    支持在仿真运行时动态修改 Agent 间的通信拓扑结构，
    包括添加/移除连接、切换拓扑类型、回滚等操作。

    Features:
        - 运行时添加/移除通信连接
        - 动态切换拓扑类型
        - 拓扑快照与回滚
        - 变更事件回调

    Example:
        >>> topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        >>> dyn = DynamicTopology(topo)
        >>> dyn.add_link("a", "d")  # 添加新连接
        >>> dyn.switch_topology(TopologyType.STAR, center="a")  # 切换拓扑
        >>> dyn.rollback()  # 回滚到上一个快照
    """

    def __init__(self, topology: NetworkTopology) -> None:
        self._topology = topology
        self._snapshots: list[TopologySnapshot] = []
        self._change_count = 0

    @property
    def topology(self) -> NetworkTopology:
        """当前拓扑。"""
        return self._topology

    @property
    def change_count(self) -> int:
        """变更次数。"""
        return self._change_count

    def snapshot(self, step: int = 0) -> TopologySnapshot:
        """创建拓扑快照。

        Args:
            step: 当前仿真步数

        Returns:
            拓扑快照
        """
        snap = TopologySnapshot(
            topology_type=self._topology.topology_type,
            links=list(self._topology.links),
            center=self._topology.center,
            step=step,
        )
        self._snapshots.append(snap)
        logger.debug("创建拓扑快照 (step=%d)", step)
        return snap

    def rollback(self) -> bool:
        """回滚到上一个快照。

        Returns:
            是否成功回滚
        """
        if not self._snapshots:
            logger.warning("无快照可回滚")
            return False

        snap = self._snapshots.pop()
        self._topology.topology_type = snap.topology_type
        self._topology.links = list(snap.links)
        self._topology.center = snap.center
        self._change_count += 1
        logger.info("回滚拓扑到 step=%d", snap.step)
        return True

    @property
    def snapshot_count(self) -> int:
        """快照数量。"""
        return len(self._snapshots)

    def add_link(
        self, source: str, target: str, bidirectional: bool = True,
    ) -> None:
        """添加通信连接。

        Args:
            source: 源 Agent 名称
            target: 目标 Agent 名称
            bidirectional: 是否双向通信
        """
        # 检查是否已存在
        for link in self._topology.links:
            if link.source == source and link.target == target:
                logger.debug("连接已存在: %s -> %s", source, target)
                return
            if (
                bidirectional
                and link.bidirectional
                and link.source == target
                and link.target == source
            ):
                logger.debug("连接已存在（反向）: %s -> %s", target, source)
                return

        new_link = Link(source=source, target=target, bidirectional=bidirectional)
        self._topology.links.append(new_link)
        self._topology.topology_type = TopologyType.CUSTOM
        self._change_count += 1
        logger.info("添加连接: %s -> %s (双向=%s)", source, target, bidirectional)

    def remove_link(self, source: str, target: str) -> bool:
        """移除通信连接。

        Args:
            source: 源 Agent 名称
            target: 目标 Agent 名称

        Returns:
            是否成功移除
        """
        original_count = len(self._topology.links)
        self._topology.links = [
            link for link in self._topology.links
            if not (link.source == source and link.target == target)
        ]
        if len(self._topology.links) < original_count:
            self._topology.topology_type = TopologyType.CUSTOM
            self._change_count += 1
            logger.info("移除连接: %s -> %s", source, target)
            return True
        logger.debug("连接不存在: %s -> %s", source, target)
        return False

    def remove_agent(self, agent_name: str) -> int:
        """移除 Agent 的所有连接。

        Args:
            agent_name: Agent 名称

        Returns:
            移除的连接数
        """
        original_count = len(self._topology.links)
        self._topology.links = [
            link for link in self._topology.links
            if link.source != agent_name and link.target != agent_name
        ]
        removed = original_count - len(self._topology.links)
        if removed > 0:
            if agent_name in self._topology.agents:
                self._topology.agents.remove(agent_name)
            self._topology.topology_type = TopologyType.CUSTOM
            self._change_count += 1
            logger.info("移除 Agent %s 的 %d 个连接", agent_name, removed)
        return removed

    def add_agent(self, agent_name: str, connect_to: list[str] | None = None) -> None:
        """添加 Agent 到拓扑并可选连接。

        Args:
            agent_name: Agent 名称
            connect_to: 要连接的 Agent 列表
        """
        if agent_name not in self._topology.agents:
            self._topology.agents.append(agent_name)

        if connect_to:
            for target in connect_to:
                self.add_link(agent_name, target)

        self._change_count += 1
        logger.info("添加 Agent: %s (连接到 %s)", agent_name, connect_to)

    def switch_topology(
        self,
        topology_type: TopologyType,
        center: str | None = None,
        step: int = 0,
    ) -> None:
        """切换拓扑类型。

        自动创建快照后切换。

        Args:
            topology_type: 目标拓扑类型
            center: 中心节点（星型拓扑使用）
            step: 当前步数
        """
        self.snapshot(step)
        agents = list(self._topology.agents)
        new_topo = build_topology(topology_type, agents, center=center)
        self._topology.topology_type = new_topo.topology_type
        self._topology.links = new_topo.links
        self._topology.center = new_topo.center
        self._change_count += 1
        logger.info("切换拓扑: %s -> %s", self._topology.topology_type, topology_type)

    def get_neighbors(self, agent_name: str) -> list[str]:
        """获取 Agent 的邻居列表。

        Args:
            agent_name: Agent 名称

        Returns:
            邻居 Agent 名称列表
        """
        return self._topology.get_neighbors(agent_name)

    def is_connected(self, agent_a: str, agent_b: str) -> bool:
        """检查两个 Agent 是否连接。

        Args:
            agent_a: Agent A 名称
            agent_b: Agent B 名称

        Returns:
            是否连接
        """
        return agent_b in self.get_neighbors(agent_a)

    def summary(self) -> dict[str, Any]:
        """获取拓扑摘要。

        Returns:
            拓扑摘要字典
        """
        return {
            "topology_type": self._topology.topology_type,
            "agents": len(self._topology.agents),
            "links": len(self._topology.links),
            "change_count": self._change_count,
            "snapshots": len(self._snapshots),
        }
