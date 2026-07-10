"""Risk agent — sizes or vetoes signals via the PortfolioRiskModel."""
from __future__ import annotations

from agents.base import BaseAgent
from orchestration.event_bus import EventBus, Event, Topic
from trading_engine.execution.execution_gateway import OrderContract, OrderSide


class RiskAgent(BaseAgent):
    """Consumes signals, turns them into risk-checked, sized orders. Wraps the
    existing RiskManager (which enforces the PortfolioRiskModel kill-switch and
    Kelly sizing)."""

    name = "risk_agent"

    def __init__(self, bus: EventBus, risk_manager) -> None:
        super().__init__(bus)
        self.risk_manager = risk_manager
        bus.subscribe(Topic.SIGNAL, self.on_signal)

    def on_signal(self, event: Event) -> None:
        self._handled()
        p = event.payload
        side = OrderSide.BUY if p.get("side", "BUY") == "BUY" else OrderSide.SELL
        order = OrderContract(
            symbol=p["symbol"], side=side, size=0.0,
            strategy_id=event.source, execution_strategy="TWAP",
        )
        passed, reason, size = self.risk_manager.evaluate(
            order, win_prob=p.get("win_prob", 0.55),
        )
        if passed:
            order.size = size
            self.emit(Event(Topic.SIZED_ORDER, {"order": order, "reason": reason}, self.name))
        else:
            self.errors += 0  # a veto is a healthy outcome, not an error
            self.emit(Event(Topic.ORDER_REJECTED, {"order": order, "reason": reason}, self.name))


__all__ = ["RiskAgent"]
