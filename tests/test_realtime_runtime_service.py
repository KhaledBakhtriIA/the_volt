from __future__ import annotations

import asyncio
from unittest.mock import patch

from src.canonical.realtime_runtime import (
    InMemoryTickQueue,
    RealTimeDecisionLoop,
    RedisFeatureCache,
    RealtimeRuntimeService,
    TickEvent,
)


class _StubOrchestrator:
    def __init__(self) -> None:
        self.predictions: list[float] = []

    def predict(self, model_name, X):
        return [0.5]

    def record_prediction(self, model_name, prediction_id, predicted_value):
        self.predictions.append(float(predicted_value))

    def record_outcome(self, model_name, prediction_id, actual_value):
        return {"matched_prediction": True, "degraded": False}


@patch.dict('sys.modules', {'redis': None})
def test_realtime_runtime_service_consumes_continuously() -> None:
    async def _run() -> None:
        queue = InMemoryTickQueue()
        cache = RedisFeatureCache(redis_client=None)
        orchestrator = _StubOrchestrator()
        loop = RealTimeDecisionLoop(queue, cache, orchestrator)
        service = RealtimeRuntimeService(loop, error_backoff_seconds=0.01)

        await service.start()
        await queue.publish(TickEvent(symbol="BTC-USD", timestamp="2026-03-31T00:00:00Z", price=100.0, volume=1.0))
        await queue.publish(TickEvent(symbol="BTC-USD", timestamp="2026-03-31T00:00:01Z", price=100.5, volume=1.1))

        await asyncio.sleep(0.1)
        await service.stop()

        assert len(orchestrator.predictions) >= 2

    asyncio.run(_run())
