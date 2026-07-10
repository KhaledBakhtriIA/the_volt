"""Data agent — drives collectors and publishes market/news events."""
from __future__ import annotations

import pandas as pd

from agents.base import BaseAgent
from orchestration.event_bus import EventBus, Event, Topic


class DataAgent(BaseAgent):
    """Ingestion entry point. Wraps an optional collector and publishes frames
    onto the bus for downstream strategy agents to consume."""

    name = "data_agent"

    def __init__(self, bus: EventBus, collector=None) -> None:
        super().__init__(bus)
        self.collector = collector

    def emit_market_data(self, frame: "pd.DataFrame") -> None:
        """Publish a market-data frame (columns: symbol, price[, timestamp])."""
        self._handled()
        self.emit(Event(Topic.MARKET_DATA, {"frame": frame}, self.name))

    def emit_news(self, articles: list) -> None:
        self._handled()
        self.emit(Event(Topic.NEWS_DATA, {"articles": articles}, self.name))

    def run(self):
        """Fetch from the wrapped collector (if any) and broadcast the result."""
        frame = self.collector.fetch() if self.collector is not None else None
        if frame is not None:
            self.emit_market_data(frame)
        return frame


__all__ = ["DataAgent"]
