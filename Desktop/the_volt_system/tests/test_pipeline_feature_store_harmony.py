from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

from data_api.jobs.pipeline import run_full_collection
from src.canonical.feature_store_engine import FeatureStoreEngine
from src.canonical.orchestrator import AnalysisOrchestrator


def _settings(tmp_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        interval="1d",
        lookback_days=5,
        crypto_symbols=["BTC-USD"],
        stock_symbols=[],
        macro_symbols=[],
        browser_enabled=False,
        browser_headless=True,
        browser_timeout_ms=30000,
        reddit_enabled=False,
        macro_enabled=False,
        desktop_enabled=False,
        vision_enabled=False,
        stock_market_enabled=False,
        trading_strategy_enabled=False,
        trading_mistakes_enabled=False,
        reddit_client_id="",
        reddit_client_secret="",
        reddit_user_agent="volt-data-api/1.0",
        fred_api_key="",
        fcs_api_key="",
        tokeninsight_api_key="",
        tokeninsight_enabled=False,
        reddit_subreddits=["bitcoin"],
        reddit_query="market",
        reddit_limit_per_subreddit=5,
        trading_strategy_subreddits=["stocks"],
        trading_strategy_query="strategy",
        trading_strategy_limit_per_subreddit=10,
        trading_mistakes_subreddits=["stocks"],
        trading_mistakes_queries=["loss"],
        trading_mistakes_limit_per_subreddit=10,
        stock_market_period="1y",
        stock_market_interval="1d",
        fred_series={"fed_funds_rate": "FEDFUNDS"},
        desktop_targets={"terminal": "active_screen"},
        browser_targets={},
        raw_dir=tmp_path / "raw",
        processed_dir=tmp_path / "processed",
        export_dir=tmp_path / "export",
    )


def test_pipeline_feature_store_orchestrator_harmony(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    market_collector = MagicMock()
    news_collector = MagicMock()
    sentiment_processor = MagicMock()

    raw_store = MagicMock()
    processed_store = MagicMock()
    export_store = MagicMock()

    market_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=4, tz="UTC"),
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [100.5, 101.5, 102.5, 103.5],
            "price": [100.5, 101.5, 102.5, 103.5],
            "volume": [1000, 1200, 1100, 1300],
            "symbol": ["BTC-USD", "BTC-USD", "BTC-USD", "BTC-USD"],
            "fetched_at_utc": ["2026-01-01T00:00:00Z"] * 4,
        }
    )

    news_df = pd.DataFrame(
        {
            "title": ["headline"],
            "summary": ["summary"],
            "published": ["2026-01-01T00:00:00Z"],
            "source": ["feed"],
            "fetched_at_utc": ["2026-01-01T00:00:00Z"],
            "link": ["https://example.com"],
        }
    )

    scored_news_df = news_df.assign(
        sentiment_neg=0.1,
        sentiment_neu=0.6,
        sentiment_pos=0.3,
        sentiment_compound=0.2,
    )

    market_collector.fetch.return_value = market_df
    news_collector.fetch.return_value = news_df
    sentiment_processor.score_news.return_value = scored_news_df

    raw_store.save.side_effect = [
        tmp_path / "raw_market.csv",
        tmp_path / "raw_news.csv",
    ]
    processed_store.save.return_value = tmp_path / "processed_news.csv"
    export_store.save.return_value = tmp_path / "training_export.csv"

    result = run_full_collection(
        settings,
        market_collector=market_collector,
        news_collector=news_collector,
        sentiment_processor=sentiment_processor,
        raw_store=raw_store,
        processed_store=processed_store,
        export_store=export_store,
    )

    assert result["market_rows"] == "4"
    assert "market_file" in result

    from src.canonical.feature_store_engine import FeatureStoreConfig
    feature_store = FeatureStoreEngine(FeatureStoreConfig(required_columns=["symbol", "timestamp", "price", "volume"], numeric_columns=["price", "volume"]))
    cleaned_df, report = feature_store.process(market_df[["symbol", "timestamp", "price", "volume"]], dataset="market", strict=True)

    assert report.passed is True
    assert not cleaned_df.empty

    orchestrator = AnalysisOrchestrator(exports_dir=str(tmp_path / "exports"), feature_store_engine=feature_store)
    orchestration = orchestrator.run_complete_analysis(run_id="pipeline_harmony_run", raw_df=cleaned_df)

    assert orchestration["data"]["quality"]["passed"] is True
    assert orchestration["processed"]["quality_passed"] is True
    assert orchestration["processed"]["processed_rows"] == orchestration["data"]["rows_out"]
