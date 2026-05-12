"""Tests for network topology module."""
from __future__ import annotations

import pytest

from agent_sim.topology.topology import (
    Link,
    NetworkTopology,
    TopologyType,
    build_topology,
)


class TestTopologyType:
    """TopologyType 枚举测试。"""

    def test_values(self) -> None:
        assert TopologyType.MESH == "mesh"
        assert TopologyType.STAR == "star"
        assert TopologyType.CHAIN == "chain"
        assert TopologyType.TREE == "tree"
        assert TopologyType.RING == "ring"
        assert TopologyType.CUSTOM == "custom"


class TestLink:
    """Link 模型测试。"""

    def test_create(self) -> None:
        link = Link(source="a", target="b")
        assert link.source == "a"
        assert link.target == "b"
        assert link.bidirectional is True

    def test_unidirectional(self) -> None:
        link = Link(source="a", target="b", bidirectional=False)
        assert link.bidirectional is False


class TestNetworkTopology:
    """NetworkTopology 测试。"""

    def test_create_empty(self) -> None:
        topo = NetworkTopology()
        assert topo.topology_type == TopologyType.MESH
        assert len(topo.agents) == 0

    def test_get_neighbors(self) -> None:
        topo = NetworkTopology(
            agents=["a", "b", "c"],
            links=[
                Link(source="a", target="b"),
                Link(source="a", target="c"),
            ],
        )
        neighbors = topo.get_neighbors("a")
        assert set(neighbors) == {"b", "c"}

    def test_get_neighbors_bidirectional(self) -> None:
        topo = NetworkTopology(
            agents=["a", "b"],
            links=[Link(source="a", target="b", bidirectional=True)],
        )
        assert "a" in topo.get_neighbors("b")
        assert "b" in topo.get_neighbors("a")

    def test_get_neighbors_unidirectional(self) -> None:
        topo = NetworkTopology(
            agents=["a", "b"],
            links=[Link(source="a", target="b", bidirectional=False)],
        )
        assert "b" in topo.get_neighbors("a")
        assert "a" not in topo.get_neighbors("b")

    def test_is_connected(self) -> None:
        topo = NetworkTopology(
            agents=["a", "b", "c"],
            links=[Link(source="a", target="b")],
        )
        assert topo.is_connected("a", "b") is True
        assert topo.is_connected("a", "c") is False

    def test_get_degree(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        assert topo.get_degree("a") == 2

    def test_add_link(self) -> None:
        topo = NetworkTopology(agents=["a", "b"])
        topo.add_link("a", "b")
        assert len(topo.links) == 1

    def test_add_link_no_duplicate(self) -> None:
        topo = NetworkTopology(agents=["a", "b"])
        topo.add_link("a", "b")
        topo.add_link("a", "b")
        assert len(topo.links) == 1

    def test_adjacency_matrix(self) -> None:
        topo = build_topology(TopologyType.CHAIN, ["a", "b", "c"])
        matrix = topo.adjacency_matrix()
        assert matrix["a"]["b"] is True
        assert matrix["b"]["a"] is True
        assert matrix["a"]["c"] is False

    def test_summary(self) -> None:
        topo = build_topology(TopologyType.STAR, ["a", "b", "c", "d"], center="a")
        s = topo.summary()
        assert s["type"] == "star"
        assert s["agents"] == 4
        assert s["center"] == "a"

    def test_to_ascii(self) -> None:
        topo = build_topology(TopologyType.CHAIN, ["a", "b"])
        ascii_str = topo.to_ascii()
        assert "[a]" in ascii_str
        assert "[b]" in ascii_str

    def test_to_ascii_empty(self) -> None:
        topo = NetworkTopology()
        assert "(empty topology)" in topo.to_ascii()

    def test_str(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b"])
        assert "mesh" in str(topo)
        assert "agents=2" in str(topo)


class TestBuildTopology:
    """build_topology 函数测试。"""

    def test_empty_agents(self) -> None:
        with pytest.raises(ValueError, match="不能为空"):
            build_topology(TopologyType.MESH, [])

    def test_mesh(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b", "c"])
        assert len(topo.links) == 3  # C(3,2) = 3

    def test_mesh_two(self) -> None:
        topo = build_topology(TopologyType.MESH, ["a", "b"])
        assert len(topo.links) == 1

    def test_star(self) -> None:
        topo = build_topology(TopologyType.STAR, ["a", "b", "c", "d"], center="a")
        assert len(topo.links) == 3
        assert topo.get_degree("a") == 3
        assert topo.get_degree("b") == 1

    def test_star_default_center(self) -> None:
        topo = build_topology(TopologyType.STAR, ["a", "b", "c"])
        assert topo.center == "a"
        assert topo.get_degree("a") == 2
        assert topo.get_degree("b") == 1

    def test_star_invalid_center(self) -> None:
        with pytest.raises(ValueError, match="不在 agents"):
            build_topology(TopologyType.STAR, ["a", "b"], center="z")

    def test_chain(self) -> None:
        topo = build_topology(TopologyType.CHAIN, ["a", "b", "c", "d"])
        assert len(topo.links) == 3
        assert topo.is_connected("a", "b")
        assert topo.is_connected("b", "c")
        assert topo.is_connected("c", "d")
        assert not topo.is_connected("a", "d")

    def test_tree(self) -> None:
        topo = build_topology(TopologyType.TREE, ["root", "a", "b", "c", "d"])
        assert topo.is_connected("root", "a")
        assert topo.is_connected("root", "b")
        assert topo.is_connected("a", "c")
        assert topo.is_connected("a", "d")

    def test_tree_default_root(self) -> None:
        topo = build_topology(TopologyType.TREE, ["a", "b", "c"])
        assert topo.center == "a"
        assert topo.get_degree("a") == 2

    def test_tree_invalid_root(self) -> None:
        with pytest.raises(ValueError, match="不在 agents"):
            build_topology(TopologyType.TREE, ["a", "b"], center="z")

    def test_ring(self) -> None:
        topo = build_topology(TopologyType.RING, ["a", "b", "c", "d"])
        assert len(topo.links) == 4
        assert topo.is_connected("a", "b")
        assert topo.is_connected("d", "a")  # wrap-around
        assert not topo.is_connected("a", "c")

    def test_ring_two(self) -> None:
        topo = build_topology(TopologyType.RING, ["a", "b"])
        assert len(topo.links) == 1  # a↔b bidirectional single link

    def test_custom(self) -> None:
        topo = build_topology(
            TopologyType.CUSTOM,
            ["a", "b", "c"],
            custom_links=[("a", "b"), ("b", "c")],
        )
        assert len(topo.links) == 2

    def test_custom_empty(self) -> None:
        topo = build_topology(TopologyType.CUSTOM, ["a", "b"])
        assert len(topo.links) == 0
