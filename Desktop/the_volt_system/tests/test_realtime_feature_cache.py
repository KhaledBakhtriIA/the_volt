from __future__ import annotations

from src.canonical.realtime_runtime import RedisFeatureCache, TickEvent


def test_feature_cache_in_memory_latest_and_vector() -> None:
    cache = RedisFeatureCache(redis_client=None)

    cache.update_tick(TickEvent(symbol="BTC-USD", timestamp="2026-03-31T00:00:00Z", price=100.0, volume=1.0))
    cache.update_tick(TickEvent(symbol="BTC-USD", timestamp="2026-03-31T00:00:01Z", price=101.0, volume=2.0))

    latest = cache.latest("BTC-USD")
    vector = cache.feature_vector("BTC-USD")

    assert latest is not None
    assert latest.price == 101.0
    assert vector is not None
    assert vector[0] == 101.0
    assert vector[1] > 0.0


def test_tick_event_validation() -> None:
    payload = {
        "symbol": "eth-usd",
        "price": "2500.5",
        "volume": "3.25",
        "timestamp": "2026-03-31T00:00:00Z",
    }

    tick = TickEvent.from_payload(payload)

    assert tick.symbol == "ETH-USD"
    assert tick.price == 2500.5
    assert tick.volume == 3.25
