from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Optional, Protocol


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickEvent:
    """Normalized market tick event for low-latency processing."""

    symbol: str
    timestamp: str
    price: float
    volume: float

    @staticmethod
    def from_payload(payload: Dict[str, Any]) -> "TickEvent":
        """Build a validated TickEvent from provider payload shape."""
        symbol = str(payload.get("symbol", "")).strip().upper()
        if not symbol:
            raise ValueError("tick symbol is required")

        price_raw = payload.get("price")
        volume_raw = payload.get("volume", 0.0)
        try:
            price = float(price_raw)
            volume = float(volume_raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("tick price/volume must be numeric") from exc

        if price <= 0:
            raise ValueError("tick price must be positive")

        timestamp_raw = payload.get("timestamp")
        if timestamp_raw is None:
            ts = datetime.now(timezone.utc).isoformat()
        else:
            ts = str(timestamp_raw)

        return TickEvent(symbol=symbol, timestamp=ts, price=price, volume=volume)


class TickProducer(Protocol):
    """Producer contract for publishing normalized ticks."""

    async def publish(self, tick: TickEvent) -> None:
        """Publish one tick to transport."""


class TickConsumer(Protocol):
    """Consumer contract for receiving normalized ticks."""

    async def read(self) -> TickEvent:
        """Read one tick from transport."""

    async def start(self) -> None:
        """Optional lifecycle hook for long-lived transports."""

    async def stop(self) -> None:
        """Optional lifecycle hook for long-lived transports."""


class InMemoryTickQueue(TickProducer, TickConsumer):
    """In-memory async queue adapter for local development and tests."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[TickEvent] = asyncio.Queue()

    async def publish(self, tick: TickEvent) -> None:
        await self._queue.put(tick)

    async def read(self) -> TickEvent:
        return await self._queue.get()

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


class KafkaTickProducer(TickProducer):
    """Kafka producer wrapper for durable tick transport.

    Import of aiokafka is deferred to runtime so unit tests do not require broker/client installation.
    """

    def __init__(self, bootstrap_servers: str, topic: str) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self._producer: Any = None

    async def _ensure_started(self) -> None:
        if self._producer is not None:
            return
        from aiokafka import AIOKafkaProducer  # type: ignore

        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda item: json.dumps(item).encode("utf-8"),
        )
        await self._producer.start()

    async def publish(self, tick: TickEvent) -> None:
        await self._ensure_started()
        await self._producer.send_and_wait(self.topic, {
            "symbol": tick.symbol,
            "timestamp": tick.timestamp,
            "price": tick.price,
            "volume": tick.volume,
        })


class KafkaTickConsumer(TickConsumer):
    """Kafka consumer wrapper for always-on tick consumption."""

    def __init__(self, bootstrap_servers: str, topic: str, group_id: str = "volt-realtime-consumer") -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self._consumer: Any = None

    async def start(self) -> None:
        if self._consumer is not None:
            return
        from aiokafka import AIOKafkaConsumer  # type: ignore

        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            auto_offset_reset="latest",
            enable_auto_commit=True,
            value_deserializer=lambda raw: json.loads(raw.decode("utf-8")),
        )
        await self._consumer.start()

    async def stop(self) -> None:
        if self._consumer is None:
            return
        await self._consumer.stop()
        self._consumer = None

    async def read(self) -> TickEvent:
        if self._consumer is None:
            await self.start()
        msg = await self._consumer.getone()
        payload = msg.value
        if not isinstance(payload, dict):
            raise ValueError("kafka payload must deserialize to dict")
        return TickEvent.from_payload(payload)


class RedisFeatureCache:
    """Low-latency cache for latest ticks and short rolling windows per symbol."""

    def __init__(self, redis_client: Optional[Any] = None, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis = redis_client
        self._redis_url = redis_url
        self._memory_latest: Dict[str, TickEvent] = {}
        self._memory_windows: Dict[str, Deque[TickEvent]] = {}

    def _ensure_client(self) -> Optional[Any]:
        if self._redis is not None:
            return self._redis
        try:
            import redis
        except ImportError:
            return None

        self._redis = redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    def update_tick(self, tick: TickEvent, window_size: int = 64) -> None:
        """Update latest price and rolling window state for a symbol."""
        client = self._ensure_client()
        if client is not None:
            key_latest = f"tick:latest:{tick.symbol}"
            key_stream = f"tick:window:{tick.symbol}"
            payload = {
                "symbol": tick.symbol,
                "timestamp": tick.timestamp,
                "price": tick.price,
                "volume": tick.volume,
            }
            client.set(key_latest, json.dumps(payload))
            client.lpush(key_stream, json.dumps(payload))
            client.ltrim(key_stream, 0, window_size - 1)
            return

        self._memory_latest[tick.symbol] = tick
        window = self._memory_windows.setdefault(tick.symbol, deque(maxlen=window_size))
        window.appendleft(tick)

    def latest(self, symbol: str) -> Optional[TickEvent]:
        """Return latest tick for symbol from Redis or in-memory fallback."""
        symbol = symbol.upper()
        client = self._ensure_client()
        if client is not None:
            key_latest = f"tick:latest:{symbol}"
            raw = client.get(key_latest)
            if not raw:
                return None
            payload = json.loads(raw)
            return TickEvent.from_payload(payload)

        return self._memory_latest.get(symbol)

    def feature_vector(self, symbol: str) -> Optional[list[float]]:
        """Build minimal low-latency features from cached tick state.

        Returns a 2-feature vector [price, return_1] for model scoring.
        """
        symbol = symbol.upper()
        client = self._ensure_client()
        if client is not None:
            key_stream = f"tick:window:{symbol}"
            rows = client.lrange(key_stream, 0, 1)
            if len(rows) < 1:
                return None
            latest = TickEvent.from_payload(json.loads(rows[0]))
            prev_price = latest.price
            if len(rows) > 1:
                prev = TickEvent.from_payload(json.loads(rows[1]))
                prev_price = prev.price
            ret_1 = 0.0 if prev_price == 0 else (latest.price - prev_price) / prev_price
            return [latest.price, ret_1]

        window = self._memory_windows.get(symbol)
        if not window:
            return None
        latest = window[0]
        prev_price = window[1].price if len(window) > 1 else latest.price
        ret_1 = 0.0 if prev_price == 0 else (latest.price - prev_price) / prev_price
        return [latest.price, ret_1]


class RealTimeDecisionLoop:
    """Consume live ticks, update low-latency state, and trigger model decisions."""

    def __init__(self, consumer: TickConsumer, cache: RedisFeatureCache, orchestrator: Any, model_name: str = "forecast_model") -> None:
        self.consumer = consumer
        self.cache = cache
        self.orchestrator = orchestrator
        self.model_name = model_name

    async def process_next(self) -> Dict[str, Any]:
        """Process one tick and return decision payload."""
        tick = await self.consumer.read()
        self.cache.update_tick(tick)
        vector = self.cache.feature_vector(tick.symbol)
        if vector is None:
            return {"status": "warmup", "symbol": tick.symbol}

        prediction_id = str(uuid.uuid4())
        try:
            prediction_raw = self.orchestrator.predict(self.model_name, [vector])
        except Exception as exc:
            return {
                "status": "prediction_unavailable",
                "symbol": tick.symbol,
                "error": str(exc),
            }
        prediction_value = float(prediction_raw[0])
        self.orchestrator.record_prediction(self.model_name, prediction_id, prediction_value)
        return {
            "status": "scored",
            "symbol": tick.symbol,
            "prediction_id": prediction_id,
            "prediction": prediction_value,
            "features": {"price": vector[0], "return_1": vector[1]},
        }

    def settle_prediction(self, prediction_id: str, actual_value: float) -> Dict[str, Any]:
        """Record realized outcome and return degradation summary."""
        return self.orchestrator.record_outcome(
            model_name=self.model_name,
            prediction_id=prediction_id,
            actual_value=actual_value,
        )


class RealtimeRuntimeService:
    """Always-on runtime that continuously consumes ticks and triggers decisions."""

    def __init__(self, decision_loop: RealTimeDecisionLoop, error_backoff_seconds: float = 1.0) -> None:
        self.decision_loop = decision_loop
        self.error_backoff_seconds = error_backoff_seconds
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start background consumer loop."""
        if self._running:
            return
        self._running = True
        consumer = self.decision_loop.consumer
        if hasattr(consumer, "start"):
            await consumer.start()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop background consumer loop and release transport resources."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        consumer = self.decision_loop.consumer
        if hasattr(consumer, "stop"):
            await consumer.stop()

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.decision_loop.process_next()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("Realtime runtime loop error: %s", exc)
                await asyncio.sleep(self.error_backoff_seconds)
