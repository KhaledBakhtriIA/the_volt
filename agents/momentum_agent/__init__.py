"""Momentum agent — turns market-data frames into directional signals."""
from __future__ import annotations

from agents.base import BaseAgent
from orchestration.event_bus import EventBus, Event, Topic


class MomentumAgent(BaseAgent):
    """Emits a BUY/SELL signal from the latest price change of a symbol.

    A deliberately small strategy so the agent chain is easy to reason about;
    swap the body for `models.inference.predictive_models.MomentumModel` to use
    the trained classifier instead."""

    name = "momentum_agent"

    def __init__(self, bus: EventBus, symbol: str = "BTC-USD", price_col: str = "price") -> None:
        super().__init__(bus)
        self.symbol = symbol
        self.price_col = price_col
        bus.subscribe(Topic.MARKET_DATA, self.on_market_data)

    def on_market_data(self, event: Event) -> None:
        frame = event.payload.get("frame")
        if frame is None or self.price_col not in frame.columns:
            return
        rows = frame[frame["symbol"] == self.symbol]
        if len(rows) < 2:
            return
        self._handled()
        prev, last = float(rows.iloc[-2][self.price_col]), float(rows.iloc[-1][self.price_col])
        change = (last - prev) / prev if prev else 0.0
        side = "BUY" if change >= 0 else "SELL"
        # Map |change| into a bounded win-probability edge around 0.5.
        win_prob = min(0.5 + abs(change) * 5.0, 0.65)
        self.emit(Event(Topic.SIGNAL, {
            "symbol": self.symbol,
            "side": side,
            "strength": abs(change),
            "win_prob": win_prob,
        }, self.name))


__all__ = ["MomentumAgent"]
