from __future__ import annotations

import asyncio

from src.canonical.realtime_runtime import InMemoryTickQueue, RealTimeDecisionLoop, RedisFeatureCache, TickEvent


class _StubOrchestrator:
    def __init__(self) -> None:
        self.predictions = {}
        self.outcomes = {}

    def predict(self, model_name, X):
        return [0.75]

    def record_prediction(self, model_name, prediction_id, predicted_value):
        self.predictions[prediction_id] = predicted_value

    def record_outcome(self, model_name, prediction_id, actual_value):
        self.outcomes[prediction_id] = actual_value
        return {
            "model_name": model_name,
            "matched_prediction": prediction_id in self.predictions,
            "degraded": False,
        }


def test_decision_loop_scores_and_settles() -> None:
    async def _run() -> None:
        queue = InMemoryTickQueue()
        cache = RedisFeatureCache(redis_client=None)
        orchestrator = _StubOrchestrator()
        loop = RealTimeDecisionLoop(queue, cache, orchestrator, model_name="forecast_model")

        await queue.publish(TickEvent(symbol="BTC-USD", timestamp="2026-03-31T00:00:00Z", price=100.0, volume=1.0))
        await queue.publish(TickEvent(symbol="BTC-USD", timestamp="2026-03-31T00:00:01Z", price=101.0, volume=1.2))

        first = await loop.process_next()
        second = await loop.process_next()

        assert first["status"] == "scored"
        assert second["status"] == "scored"
        assert "prediction_id" in second

        settlement = loop.settle_prediction(second["prediction_id"], actual_value=0.9)
        assert settlement["matched_prediction"] is True

    asyncio.run(_run())
