import asyncio
import json
import logging
from typing import Callable, Coroutine, Dict, Any, List
import pandas as pd
from datetime import datetime, timezone

from src.canonical.feature_store_engine import FeatureStoreEngine, DataQualityError

logger = logging.getLogger(__name__)

class StreamWorker:
    """Consumes real-time stream messages, buffers them, and delegates processing to the FeatureStoreEngine."""

    def __init__(
        self,
        engine: FeatureStoreEngine,
        batch_size: int = 100,
        flush_interval_seconds: float = 5.0
    ):
        self.engine = engine
        self.batch_size = batch_size
        self.flush_interval_seconds = flush_interval_seconds
        self._buffer: List[Dict[str, Any]] = []
        self._running = False
        self._flush_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("StreamWorker started.")

    async def stop(self) -> None:
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        await self.flush()
        logger.info("StreamWorker stopped.")

    async def on_message(self, message: str | bytes) -> None:
        """Callback for incoming websocket messages."""
        try:
            data = json.loads(message)
            # Normalize depending on expected structure from finance_query
            if "type" in data and data["type"] == "trade":
                row = {
                    "symbol": data.get("symbol"),
                    "timestamp": data.get("timestamp", datetime.now(timezone.utc).isoformat()),
                    "price": float(data.get("price", 0.0)),
                    "volume": float(data.get("volume", 0.0)),
                }
                self._buffer.append(row)

            if len(self._buffer) >= self.batch_size:
                await self.flush()
                
        except json.JSONDecodeError:
            logger.warning("Unparsable message received.")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def flush(self) -> None:
        """Flushes the current buffer to the Feature Store Engine."""
        if not self._buffer:
            return
            
        current_batch = self._buffer[:]
        self._buffer.clear()
        
        try:
            # We temporarily drop strictly enforcing all required columns if the stream is only raw "ticks"
            # But we want to construct a dataframe and process it.
            # Usually streams provide raw columns, and feature engineer transforms them.
            # But the FSE cleans the stream. FSE strictly needs the columns configured for it.
            df = pd.DataFrame(current_batch)
            # Process in FSE
            # The streaming dataset can just be named "realtime_ticks"
            # Since FSE now expects MOMENTUM/MEAN_REVERSION features by default, 
            # we should process it with strict=False or configure FSE specifically for ticks.
            cleaned, report = self.engine.process(df, dataset="realtime_ticks", strict=False)
            logger.info(f"Flushed batch of {len(current_batch)} items. Cleaned rows: {len(cleaned)}")
        except DataQualityError as e:
            logger.error(f"Data quality error on flush: {e}")
        except Exception as e:
            logger.error(f"Failed to process batch: {e}")

    async def _flush_loop(self) -> None:
        while self._running:
            await asyncio.sleep(self.flush_interval_seconds)
            await self.flush()

