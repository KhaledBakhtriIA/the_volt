"""Supervisor agent — coordinates and health-checks the agent fleet."""
from __future__ import annotations

from typing import List

from agents.base import BaseAgent
from orchestration.event_bus import EventBus


class SupervisorAgent(BaseAgent):
    """Owns the fleet roster and aggregates health. It does not sit in the
    trading hot-path; it observes the other agents and the bus."""

    name = "supervisor_agent"

    def __init__(self, bus: EventBus, fleet: List[BaseAgent] | None = None) -> None:
        super().__init__(bus)
        self.fleet = fleet or []

    def register(self, agent: BaseAgent) -> None:
        self.fleet.append(agent)

    def fleet_health(self) -> dict:
        members = [a.health() for a in self.fleet]
        degraded = [m["agent"] for m in members if m["status"] != "ok"]
        return {
            "agents": len(members),
            "degraded": degraded,
            "status": "degraded" if degraded else "ok",
            "members": members,
            "events_on_bus": len(self.bus.log),
        }


__all__ = ["SupervisorAgent"]
