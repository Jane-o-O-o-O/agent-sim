"""Network topology definitions for agent communication patterns."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TopologyType(str, Enum):
    """网络拓扑类型枚举。"""

    MESH = "mesh"          # 全连接：每对 Agent 互相通信
    STAR = "star"          # 星型：中心节点与所有其他节点通信
    CHAIN = "chain"        # 链式：A→B→C→...
    TREE = "tree"          # 树型：层级结构
    RING = "ring"          # 环形：A→B→C→A
    CUSTOM = "custom"      # 自定义连接


class Link(BaseModel):
    """两个 Agent 之间的通信连接。

    Attributes:
        source: 源 Agent 名称
        target: 目标 Agent 名称
        bidirectional: 是否双向通信
    """

    source: str
    target: str
    bidirectional: bool = True


class NetworkTopology(BaseModel):
    """Agent 通信网络拓扑。

    定义 Agent 之间的通信连接关系，支持多种预定义拓扑和自定义连接。

    Attributes:
        topology_type: 拓扑类型
        agents: Agent 名称列表
        links: 连接列表
        center: 中心节点名称（星型拓扑使用）
        metadata: 附加元数据

    Example:
        >>> topo = build_topology(TopologyType.STAR, ["a", "b", "c", "d"], center="a")
        >>> topo.get_neighbors("a")
        ["b", "c", "d"]
        >>> topo.get_neighbors("b")
        ["a"]
    """

    topology_type: TopologyType = TopologyType.MESH
    agents: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    center: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def get_neighbors(self, agent_name: str) -> list[str]:
        """获取指定 Agent 的邻居列表。

        Args:
            agent_name: Agent 名称

        Returns:
            邻居 Agent 名称列表
        """
        neighbors = []
        for link in self.links:
            if link.source == agent_name:
                neighbors.append(link.target)
            elif link.bidirectional and link.target == agent_name:
                neighbors.append(link.source)
        return neighbors

    def is_connected(self, agent_a: str, agent_b: str) -> bool:
        """检查两个 Agent 是否直接连接。

        Args:
            agent_a: Agent A 名称
            agent_b: Agent B 名称

        Returns:
            是否直接连接
        """
        return agent_b in self.get_neighbors(agent_a)

    def get_degree(self, agent_name: str) -> int:
        """获取 Agent 的连接度（邻居数）。

        Args:
            agent_name: Agent 名称

        Returns:
            邻居数
        """
        return len(self.get_neighbors(agent_name))

    def add_link(self, source: str, target: str, bidirectional: bool = True) -> None:
        """添加一条连接。

        Args:
            source: 源 Agent
            target: 目标 Agent
            bidirectional: 是否双向
        """
        # 避免重复
        for link in self.links:
            if link.source == source and link.target == target:
                return
            if bidirectional and link.source == target and link.target == source:
                return
        self.links.append(Link(source=source, target=target, bidirectional=bidirectional))

    def adjacency_matrix(self) -> dict[str, dict[str, bool]]:
        """生成邻接矩阵。

        Returns:
            {agent_a: {agent_b: True/False, ...}, ...}
        """
        matrix: dict[str, dict[str, bool]] = {}
        for a in self.agents:
            matrix[a] = {b: False for b in self.agents}
        for link in self.links:
            matrix[link.source][link.target] = True
            if link.bidirectional:
                matrix[link.target][link.source] = True
        return matrix

    def summary(self) -> dict[str, Any]:
        """返回拓扑摘要。"""
        return {
            "type": self.topology_type.value,
            "agents": len(self.agents),
            "links": len(self.links),
            "center": self.center,
            "avg_degree": (
                sum(self.get_degree(a) for a in self.agents) / len(self.agents)
                if self.agents
                else 0
            ),
        }

    def to_ascii(self) -> str:
        """生成拓扑的 ASCII 图。

        Returns:
            ASCII 字符串表示
        """
        if not self.agents:
            return "(empty topology)"

        lines = [f"Topology: {self.topology_type.value} ({len(self.agents)} agents)"]
        lines.append("")

        for agent in self.agents:
            neighbors = self.get_neighbors(agent)
            if neighbors:
                lines.append(f"  [{agent}] ──→ {', '.join(neighbors)}")
            else:
                lines.append(f"  [{agent}] (isolated)")

        return "\n".join(lines)

    def __str__(self) -> str:
        return (
            f"NetworkTopology(type={self.topology_type.value}, "
            f"agents={len(self.agents)}, links={len(self.links)})"
        )


def build_topology(
    topology_type: TopologyType,
    agents: list[str],
    center: str | None = None,
    custom_links: list[tuple[str, str]] | None = None,
) -> NetworkTopology:
    """构建指定类型的网络拓扑。

    Args:
        topology_type: 拓扑类型
        agents: Agent 名称列表
        center: 中心节点（星型/树型拓扑使用，默认第一个）
        custom_links: 自定义连接列表（custom 类型使用）

    Returns:
        NetworkTopology 实例

    Raises:
        ValueError: 参数无效

    Example:
        >>> topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        >>> len(topo.links)  # 3 links for 3 nodes mesh
        3
    """
    if not agents:
        raise ValueError("agents 列表不能为空")

    topo = NetworkTopology(topology_type=topology_type, agents=list(agents), center=center)

    if topology_type == TopologyType.MESH:
        _build_mesh(topo, agents)
    elif topology_type == TopologyType.STAR:
        _build_star(topo, agents, center or agents[0])
        if not topo.center:
            topo.center = center or agents[0]
    elif topology_type == TopologyType.CHAIN:
        _build_chain(topo, agents)
    elif topology_type == TopologyType.TREE:
        _build_tree(topo, agents, center or agents[0])
        if not topo.center:
            topo.center = center or agents[0]
    elif topology_type == TopologyType.RING:
        _build_ring(topo, agents)
    elif topology_type == TopologyType.CUSTOM:
        if custom_links:
            for src, tgt in custom_links:
                topo.add_link(src, tgt)

    logger.info("构建拓扑: %s (%d agents, %d links)", topology_type.value, len(agents), len(topo.links))
    return topo


def _build_mesh(topo: NetworkTopology, agents: list[str]) -> None:
    """构建全连接拓扑。"""
    for i, a in enumerate(agents):
        for b in agents[i + 1:]:
            topo.add_link(a, b, bidirectional=True)


def _build_star(topo: NetworkTopology, agents: list[str], center: str | None) -> None:
    """构建星型拓扑。"""
    hub = center or agents[0]
    if hub not in agents:
        raise ValueError(f"中心节点 '{hub}' 不在 agents 列表中")
    for agent in agents:
        if agent != hub:
            topo.add_link(hub, agent, bidirectional=True)


def _build_chain(topo: NetworkTopology, agents: list[str]) -> None:
    """构建链式拓扑。"""
    for i in range(len(agents) - 1):
        topo.add_link(agents[i], agents[i + 1], bidirectional=True)


def _build_tree(topo: NetworkTopology, agents: list[str], center: str | None) -> None:
    """构建二叉树拓扑（BFS 方式填充）。"""
    root = center or agents[0]
    if root not in agents:
        raise ValueError(f"根节点 '{root}' 不在 agents 列表中")
    others = [a for a in agents if a != root]
    queue = [root]
    idx = 0
    while queue and idx < len(others):
        parent = queue.pop(0)
        # 每个节点最多 2 个子节点
        for _ in range(2):
            if idx < len(others):
                child = others[idx]
                topo.add_link(parent, child, bidirectional=True)
                queue.append(child)
                idx += 1


def _build_ring(topo: NetworkTopology, agents: list[str]) -> None:
    """构建环形拓扑。"""
    for i in range(len(agents)):
        next_i = (i + 1) % len(agents)
        topo.add_link(agents[i], agents[next_i], bidirectional=True)
