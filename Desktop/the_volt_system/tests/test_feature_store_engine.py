from __future__ import annotations

import pandas as pd
import pytest

from src.canonical.feature_store_engine import DataQualityError, FeatureStoreConfig, FeatureStoreEngine
from src.canonical.orchestrator import AnalysisOrchestrator


def test_feature_store_engine_cleans_and_validates_batch() -> None:
    engine = FeatureStoreEngine(
        FeatureStoreConfig(
            required_columns=["symbol", "timestamp", "price"],
            numeric_columns=["price", "volume"],
            max_missing_ratio=0.4,
            max_duplicate_ratio=0.5,
            max_outlier_ratio=0.8,
        )
    )

    raw = pd.DataFrame(
        {
            "symbol": ["BTC-USD", "BTC-USD", "BTC-USD", None],
            "timestamp": ["2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z", "invalid"],
            "price": [100.0, 100.0, None, 120.0],
            "volume": [10, 10, 15, None],
        }
    )

    cleaned, report = engine.process(raw, dataset="ticks", strict=False)

    assert not cleaned.empty
    assert report.schema_valid is True
    assert report.total_rows == 4
    assert report.rows_after_cleaning <= 4
    assert "timestamp" in cleaned.columns
    assert len(engine.latest("ticks")) == len(cleaned)


def test_feature_store_engine_strict_validation_raises_on_bad_schema() -> None:
    engine = FeatureStoreEngine()
    raw = pd.DataFrame({"timestamp": ["2026-01-01T00:00:00Z"], "price": [10.0]})

    with pytest.raises(DataQualityError):
        engine.process(raw, dataset="ticks", strict=True)


def test_orchestrator_preprocesses_raw_data_before_steps(tmp_path) -> None:
    engine = FeatureStoreEngine(FeatureStoreConfig(required_columns=["symbol", "timestamp", "price"], numeric_columns=["price"]))
    orchestrator = AnalysisOrchestrator(exports_dir=str(tmp_path / "exports"), feature_store_engine=engine)  
    raw = pd.DataFrame(
        {
            "symbol": ["ETH-USD", "ETH-USD"],
            "timestamp": ["2026-01-01T00:00:00Z", "2026-01-01T00:01:00Z"],
            "price": [2500.0, 2501.0],
        }
    )

    result = orchestrator.run_complete_analysis(run_id="qa_feature_store_run", raw_df=raw)

    assert result["data"]["rows_in"] == 2
    assert result["processed"]["quality_passed"] is True
    assert result["processed"]["processed_rows"] == result["data"]["rows_out"]
import json
from pathlib import Path

def test_feature_store_engine_offline_persistence(tmp_path: Path) -> None:
    offline_dir = tmp_path / "refined"
    
    engine = FeatureStoreEngine(
        FeatureStoreConfig(
            required_columns=["symbol", "price"],
            numeric_columns=["price"],
            persist_offline=True,
            offline_store_path=str(offline_dir)
        )
    )
    
    raw = pd.DataFrame({
        "symbol": ["SOL-USD", "SOL-USD"],
        "price": [150.0, 155.0]
    })
    
    cleaned, report = engine.process(raw, dataset="trades")
    
    dataset_dir = offline_dir / "trades"
    assert dataset_dir.exists(), "Offline storage directory was not created."
    
    parquet_files = list(dataset_dir.glob("*.parquet"))
    csv_files = list(dataset_dir.glob("*.csv"))
    json_files = list(dataset_dir.glob("*_meta.json"))
    
    assert (len(parquet_files) == 1 or len(csv_files) == 1), "Data file (parquet or fallback csv) was not saved."
    assert len(json_files) == 1, "Metadata JSON sidecar was not saved."
    
    with open(json_files[0]) as f:
        meta = json.load(f)
        
    assert meta["dataset"] == "trades"
    assert "report" in meta
    assert meta["report"]["schema_valid"] is True
    assert meta["report"]["passed"] is True
