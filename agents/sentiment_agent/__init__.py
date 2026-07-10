"""Sentiment agent — scores news/social streams into a sentiment signal."""
from __future__ import annotations

from agents.base import BaseAgent
from orchestration.event_bus import EventBus, Event, Topic


class SentimentAgent(BaseAgent):
    """Scores incoming articles with the SentimentProcessor and emits an
    aggregate sentiment signal. The processor is injected so tests can pass a
    lightweight stub."""

    name = "sentiment_agent"

    def __init__(self, bus: EventBus, processor=None, symbol: str = "BTC-USD") -> None:
        super().__init__(bus)
        self.symbol = symbol
        if processor is None:
            from data_layer.processors.sentiment import SentimentProcessor
            processor = SentimentProcessor()
        self.processor = processor
        bus.subscribe(Topic.NEWS_DATA, self.on_news)

    def on_news(self, event: Event) -> None:
        articles = event.payload.get("articles") or []
        if not articles:
            return
        self._handled()
        scores = []
        for art in articles:
            text = art.get("title", "") if isinstance(art, dict) else str(art)
            try:
                result = self.processor.analyze(text)
                scores.append(result.get("compound", 0.0) if isinstance(result, dict) else float(result))
            except Exception:
                self.errors += 1
        avg = sum(scores) / len(scores) if scores else 0.0
        self.emit(Event(Topic.SIGNAL, {
            "symbol": self.symbol,
            "side": "BUY" if avg >= 0 else "SELL",
            "strength": abs(avg),
            "win_prob": min(0.5 + abs(avg) * 0.1, 0.6),
            "kind": "sentiment",
        }, self.name))


__all__ = ["SentimentAgent"]
