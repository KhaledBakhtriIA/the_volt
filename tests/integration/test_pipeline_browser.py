"""Tests for browser-enabled pipeline behavior."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

from orchestration.jobs.pipeline import run_full_collection


def _settings(browser_enabled: bool) -> SimpleNamespace:
    return SimpleNamespace(
        interval="1d",
        lookback_days=30,
        crypto_symbols=["BTC-USD"],
        stock_symbols=[],
        macro_symbols=[],
        browser_enabled=browser_enabled,
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
        browser_targets={
            "tradingview": "https://www.tradingview.com/markets/cryptocurrencies/prices-all/",
        },
        raw_dir=Path("/tmp/raw"),
        processed_dir=Path("/tmp/processed"),
        export_dir=Path("/tmp/export"),
    )


def test_run_full_collection_browser_enabled_saves_browser_data() -> None:
    settings = _settings(browser_enabled=True)

    market_collector = MagicMock()
    news_collector = MagicMock()
    browser_collector = MagicMock()
    sentiment_processor = MagicMock()

    raw_store = MagicMock()
    processed_store = MagicMock()
    export_store = MagicMock()

    market_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=2, tz="UTC"),
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.0, 2.0],
            "volume": [100, 200],
            "symbol": ["BTC-USD", "BTC-USD"],
            "fetched_at_utc": ["2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"],
        }
    )
    news_df = pd.DataFrame(
        {
            "title": ["headline"],
            "summary": ["summary"],
            "published": ["2026-01-01T00:00:00Z"],
            "source": ["coindesk"],
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
    browser_df = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2026-01-01T00:00:00Z")],
            "source": ["tradingview"],
            "fetched_at_utc": ["2026-01-01T00:00:05Z"],
            "title": ["tv"],
            "value": ["row"],
            "target_url": ["https://www.tradingview.com"],
        }
    )

    market_collector.fetch.return_value = market_df
    news_collector.fetch.return_value = news_df
    sentiment_processor.score_news.return_value = scored_news_df
    browser_collector.fetch.return_value = browser_df

    raw_store.save.side_effect = [Path("/tmp/market.csv"), Path("/tmp/news.csv"), Path("/tmp/browser.csv")]
    processed_store.save.return_value = Path("/tmp/news_scored.csv")
    export_store.save.return_value = Path("/tmp/export.csv")

    result = run_full_collection(
        settings,
        market_collector=market_collector,
        news_collector=news_collector,
        browser_collector=browser_collector,
        sentiment_processor=sentiment_processor,
        raw_store=raw_store,
        processed_store=processed_store,
        export_store=export_store,
    )

    browser_collector.fetch.assert_called_once_with(targets=settings.browser_targets)
    assert result["browser_rows"] == "1"
    assert "browser_file" in result


def test_run_full_collection_browser_disabled_skips_browser_collector() -> None:
    settings = _settings(browser_enabled=False)

    market_collector = MagicMock()
    news_collector = MagicMock()
    browser_collector = MagicMock()
    sentiment_processor = MagicMock()

    raw_store = MagicMock()
    processed_store = MagicMock()
    export_store = MagicMock()

    market_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=2, tz="UTC"),
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.0, 2.0],
            "volume": [100, 200],
            "symbol": ["BTC-USD", "BTC-USD"],
            "fetched_at_utc": ["2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"],
        }
    )
    news_df = pd.DataFrame(
        {
            "title": ["headline"],
            "summary": ["summary"],
            "published": ["2026-01-01T00:00:00Z"],
            "source": ["coindesk"],
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

    raw_store.save.side_effect = [Path("/tmp/market.csv"), Path("/tmp/news.csv")]
    processed_store.save.return_value = Path("/tmp/news_scored.csv")
    export_store.save.return_value = Path("/tmp/export.csv")

    result = run_full_collection(
        settings,
        market_collector=market_collector,
        news_collector=news_collector,
        browser_collector=browser_collector,
        sentiment_processor=sentiment_processor,
        raw_store=raw_store,
        processed_store=processed_store,
        export_store=export_store,
    )

    browser_collector.fetch.assert_not_called()
    assert result["browser_rows"] == "0"
    assert "browser_file" not in result
