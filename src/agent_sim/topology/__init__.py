"""Network topology for agent communication."""
from agent_sim.topology.topology import (
    NetworkTopology,
    TopologyType,
    build_topology,
)

__all__ = [
    "NetworkTopology",
    "TopologyType",
    "build_topology",
]

from agent_sim.topology.dynamic import DynamicTopology, TopologySnapshot  # noqa: E402

__all__ += ["DynamicTopology", "TopologySnapshot"]
