import pandas as pd

from orchestration.event_bus import EventBus, Event, Topic
from agents.momentum_agent import MomentumAgent


def test_event_bus_publish_invokes_subscribers_in_order():
    bus = EventBus()
    seen = []
    bus.subscribe("t", lambda e: seen.append(("a", e.payload["n"])))
    bus.subscribe("t", lambda e: seen.append(("b", e.payload["n"])))

    bus.publish(Event("t", {"n": 1}))

    assert seen == [("a", 1), ("b", 1)]
    assert len(bus.log) == 1
    assert bus.events("t")[0].payload["n"] == 1


def _frame(prices):
    return pd.DataFrame({"symbol": ["BTC-USD"] * len(prices), "price": prices})


def test_momentum_agent_emits_buy_on_rising_prices():
    bus = EventBus()
    MomentumAgent(bus, symbol="BTC-USD")
    bus.publish(Event(Topic.MARKET_DATA, {"frame": _frame([100.0, 101.0])}, "data_agent"))

    signals = bus.events(Topic.SIGNAL)
    assert len(signals) == 1
    assert signals[0].payload["side"] == "BUY"
    assert signals[0].payload["win_prob"] >= 0.5


def test_momentum_agent_emits_sell_on_falling_prices():
    bus = EventBus()
    MomentumAgent(bus, symbol="BTC-USD")
    bus.publish(Event(Topic.MARKET_DATA, {"frame": _frame([100.0, 98.0])}, "data_agent"))

    assert bus.events(Topic.SIGNAL)[0].payload["side"] == "SELL"


def test_momentum_agent_ignores_single_row():
    bus = EventBus()
    MomentumAgent(bus, symbol="BTC-USD")
    bus.publish(Event(Topic.MARKET_DATA, {"frame": _frame([100.0])}, "data_agent"))
    assert bus.events(Topic.SIGNAL) == []
