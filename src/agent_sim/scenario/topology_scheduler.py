"""Dynamic topology integration for ScenarioRunner.

Provides topology rule definitions that automatically switch
network topology during simulation based on step number or conditions.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from pydantic import BaseModel, Field

from agent_sim.topology.dynamic import DynamicTopology
from agent_sim.topology.topology import TopologyType

logger = logging.getLogger(__name__)


class TopologyRule(BaseModel):
    """A rule that triggers topology change at a specific step.

    Attributes:
        step: Step number to trigger the change (1-indexed)
        topology_type: Target topology type
        center: Center node for star topology
        description: Human-readable description of the rule
    """

    step: int = Field(ge=1)
    topology_type: TopologyType
    center: str | None = None
    description: str = ""


class TopologyScheduler:
    """Schedules topology changes during simulation.

    Manages a list of TopologyRule instances and applies them
    at the appropriate simulation steps via a DynamicTopology.

    Features:
        - Declarative topology change rules
        - Step-triggered automatic switching
        - Conditional rules with custom predicates
        - Integration with ScenarioRunner hooks

    Example:
        >>> scheduler = TopologyScheduler(dynamic_topo)
        >>> scheduler.add_rule(TopologyRule(step=3, topology_type=TopologyType.STAR, center="leader"))
        >>> scheduler.add_rule(TopologyRule(step=7, topology_type=TopologyType.MESH))
        >>> scheduler.on_step(1)  # no-op
        >>> scheduler.on_step(3)  # triggers STAR switch
    """

    def __init__(self, dynamic_topology: DynamicTopology) -> None:
        self._dynamic = dynamic_topology
        self._rules: list[TopologyRule] = []
        self._conditional_rules: list[tuple[Callable[[int], bool], TopologyType, str | None]] = []
        self._applied_steps: list[int] = []

    @property
    def rules(self) -> list[TopologyRule]:
        """All registered rules."""
        return list(self._rules)

    @property
    def applied_steps(self) -> list[int]:
        """Steps at which rules were applied."""
        return list(self._applied_steps)

    def add_rule(self, rule: TopologyRule) -> None:
        """Add a topology change rule.

        Args:
            rule: The topology rule to add
        """
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.step)
        logger.info("添加拓扑规则: step=%d -> %s", rule.step, rule.topology_type)

    def add_conditional_rule(
        self,
        condition: Callable[[int], bool],
        topology_type: TopologyType,
        center: str | None = None,
    ) -> None:
        """Add a conditional topology rule.

        Args:
            condition: Function receiving step number, returns True to trigger
            topology_type: Target topology type
            center: Center node for star topology
        """
        self._conditional_rules.append((condition, topology_type, center))

    def on_step(self, step: int) -> bool:
        """Process step — apply any matching rules.

        Args:
            step: Current simulation step (1-indexed)

        Returns:
            True if any topology change was applied
        """
        changed = False

        for rule in self._rules:
            if rule.step == step:
                logger.info(
                    "应用拓扑规则: step=%d -> %s", step, rule.topology_type
                )
                self._dynamic.switch_topology(
                    rule.topology_type, center=rule.center, step=step
                )
                self._applied_steps.append(step)
                changed = True

        for condition, topo_type, center in self._conditional_rules:
            if condition(step):
                logger.info("应用条件拓扑规则: step=%d -> %s", step, topo_type)
                self._dynamic.switch_topology(topo_type, center=center, step=step)
                self._applied_steps.append(step)
                changed = True

        return changed

    def summary(self) -> dict[str, Any]:
        """Get scheduler summary.

        Returns:
            Summary dict
        """
        return {
            "total_rules": len(self._rules),
            "conditional_rules": len(self._conditional_rules),
            "applied_count": len(self._applied_steps),
            "applied_steps": list(self._applied_steps),
            "rules": [
                {
                    "step": r.step,
                    "topology": r.topology_type.value,
                    "center": r.center,
                    "description": r.description,
                }
                for r in self._rules
            ],
        }
