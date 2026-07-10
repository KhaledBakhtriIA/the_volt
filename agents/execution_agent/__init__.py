"""Execution agent — routes risk-approved orders to the broker."""
from __future__ import annotations

from agents.base import BaseAgent
from orchestration.event_bus import EventBus, Event, Topic
from trading_engine.execution.execution_gateway import OrderStatus


class ExecutionAgent(BaseAgent):
    """Submits sized orders through the PaperExecutor and reports fills."""

    name = "execution_agent"

    def __init__(self, bus: EventBus, executor) -> None:
        super().__init__(bus)
        self.executor = executor
        bus.subscribe(Topic.SIZED_ORDER, self.on_sized_order)

    def on_sized_order(self, event: Event) -> None:
        self._handled()
        order = event.payload["order"]
        result = self.executor.submit_order(order)
        topic = Topic.ORDER_FILLED if result.status == OrderStatus.FILLED else Topic.ORDER_REJECTED
        self.emit(Event(topic, {"order": result}, self.name))


__all__ = ["ExecutionAgent"]
