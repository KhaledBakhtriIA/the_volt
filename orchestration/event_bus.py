"""In-process publish/subscribe event bus for the agent fleet.

Synchronous and deterministic: `publish` invokes every subscribed handler in
registration order and records the event. This is intentionally simple so the
agent chain is easy to test end-to-end; swap the transport for Redpanda/Kafka
later without changing agent code (they only touch `subscribe`/`publish`).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


class Topic:
    """Well-known event topics exchanged between agents."""
    MARKET_DATA = "market.data"
    NEWS_DATA = "news.data"
    SIGNAL = "signal"
    SIZED_ORDER = "order.sized"
    ORDER_FILLED = "order.filled"
    ORDER_REJECTED = "order.rejected"


@dataclass
class Event:
    """A single message on the bus."""
    topic: str
    payload: Dict[str, Any] = field(default_factory=dict)
    source: str = ""


Handler = Callable[[Event], None]


class EventBus:
    """Minimal synchronous pub/sub with an audit log of everything published."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Handler]] = defaultdict(list)
        self.log: List[Event] = []

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._subscribers[topic].append(handler)

    def publish(self, event: Event) -> None:
        self.log.append(event)
        logger.debug("event %s from %s", event.topic, event.source)
        for handler in list(self._subscribers.get(event.topic, [])):
            handler(event)

    def events(self, topic: str) -> List[Event]:
        """All logged events for a topic (handy for assertions/telemetry)."""
        return [e for e in self.log if e.topic == topic]
