import asyncio
import json
import logging
import multiprocessing
import pytest
from src.canonical.learning_loop import NeuroplasticityLoop

def test_neuroplasticity_observer_loop(tmp_path):
    refined_dir = tmp_path / "refined"
    ticks_dir = refined_dir / "realtime_ticks"
    ticks_dir.mkdir(parents=True, exist_ok=True)
    registry_db = tmp_path / "obs_registry.db"
    
    loop = NeuroplasticityLoop(data_dir=str(refined_dir), registry_db=str(registry_db))
    
    async def run_test():
        await loop._check_for_growth()
        # No files yet
        assert loop._last_file_count == 0
        
        # Create files
        (ticks_dir / "1.parquet").touch()
        (ticks_dir / "2.parquet").touch() # should hit threshold=2
        
        # Needs to run multiprocessing safely in pytest
        multiprocessing.set_start_method("spawn", force=True)
        
        await loop._check_for_growth()
        assert loop._last_file_count == 2
        
    asyncio.run(run_test())
    
    from src.canonical.model_registry import ModelRegistry
    import time
    
    # Wait for the multiprocessing job a bit
    for _ in range(10):
        time.sleep(0.5)
        r = ModelRegistry(str(registry_db))
        if r.active_version("xgb_momentum"):
            break
            
    r = ModelRegistry(str(registry_db))
    active = r.active_version("xgb_momentum")
    assert active is not None
    assert "metrics_json" in active
