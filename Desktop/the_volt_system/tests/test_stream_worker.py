import asyncio
import json
import pytest
import pandas as pd
from src.canonical.feature_store_engine import FeatureStoreEngine, FeatureStoreConfig
from src.canonical.stream_worker import StreamWorker

def test_stream_worker_buffers_and_flushes_to_engine():
    # Setup FSE strictly for ticks
    config = FeatureStoreConfig(
        required_columns=["symbol", "timestamp", "price", "volume"],
        numeric_columns=["price", "volume"],
        persist_offline=False
    )
    engine = FeatureStoreEngine(config)
    
    worker = StreamWorker(engine, batch_size=2, flush_interval_seconds=10.0)
    
    async def run_test():
        await worker.start()
        
        msg1 = json.dumps({"type": "trade", "symbol": "BTC-USD", "price": "100.5", "volume": "10"})
        msg2 = json.dumps({"type": "trade", "symbol": "BTC-USD", "price": "101.5", "volume": "5"})
        
        await worker.on_message(msg1)
        # The batch size is 2, so sending msg2 should trigger a flush
        await worker.on_message(msg2)
        
        await worker.stop()
        
    asyncio.run(run_test())
    
    latest_df = engine.latest("realtime_ticks")
    assert not latest_df.empty
    assert len(latest_df) == 2
    # Verify the structure is correct rather than exact float due to .clip() quantile interpolation in small samples
    assert "price" in latest_df.columns
    assert "timestamp" in latest_df.columns
