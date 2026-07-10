"""Shared base class for all Volt agents.

An agent is a thin, single-responsibility wrapper over an existing engine
component. It talks to the rest of the system only through the EventBus, so the
fleet stays decoupled and independently testable.
"""
from __future__ import annotations

from orchestration.event_bus import EventBus, Event


class BaseAgent:
    """Common wiring: a name, a bus handle, and a health snapshot."""

    name: str = "agent"

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self.events_handled = 0
        self.errors = 0

    def emit(self, event: Event) -> None:
        self.bus.publish(event)

    def _handled(self) -> None:
        self.events_handled += 1

    def health(self) -> dict:
        return {
            "agent": self.name,
            "events_handled": self.events_handled,
            "errors": self.errors,
            "status": "degraded" if self.errors else "ok",
        }
