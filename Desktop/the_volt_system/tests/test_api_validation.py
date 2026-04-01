from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock
from typing import Generator

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from data_api.app import AppDependencies, app, get_dependencies


@pytest.fixture
def mocked_dependencies() -> AppDependencies:
    market_collector = MagicMock()
    news_collector = MagicMock()
    browser_collector = MagicMock()
    reddit_collector = MagicMock()
    macro_collector = MagicMock()
    desktop_collector = MagicMock()
    stock_market_collector = MagicMock()
    trading_strategy_collector = MagicMock()
    trading_mistakes_collector = MagicMock()
    sentiment_processor = MagicMock()
    raw_store = MagicMock()
    processed_store = MagicMock()
    export_store = MagicMock()

    return AppDependencies(
        market_collector=market_collector,
        news_collector=news_collector,
        browser_collector=browser_collector,
        reddit_collector=reddit_collector,
        macro_collector=macro_collector,
        desktop_collector=desktop_collector,
        stock_market_collector=stock_market_collector,
        trading_strategy_collector=trading_strategy_collector,
        trading_mistakes_collector=trading_mistakes_collector,
        sentiment_processor=sentiment_processor,
        raw_store=raw_store,
        processed_store=processed_store,
        export_store=export_store,
    )


@pytest.fixture
def client(mocked_dependencies: AppDependencies) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_dependencies] = lambda: mocked_dependencies
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_collect_market_symbols_empty_returns_422(client: TestClient) -> None:
    response = client.post("/collect/market", json={"symbols": [], "interval": "1d", "lookback_days": 30})
    assert response.status_code == 422


def test_collect_market_lookback_out_of_range_returns_422(client: TestClient) -> None:
    response = client.post("/collect/market", json={"symbols": ["AAPL"], "interval": "1d", "lookback_days": 500})
    assert response.status_code == 422


def test_collect_market_interval_invalid_returns_422(client: TestClient) -> None:
    response = client.post("/collect/market", json={"symbols": ["AAPL"], "interval": "invalid", "lookback_days": 30})
    assert response.status_code == 422


def test_collect_news_limit_zero_returns_422(client: TestClient) -> None:
    response = client.post("/collect/news", json={"limit_per_feed": 0})
    assert response.status_code == 422


def test_process_sentiment_empty_text_returns_422(client: TestClient) -> None:
    response = client.post("/process/sentiment", json={"text": ""})
    assert response.status_code == 422


def test_process_sentiment_too_long_returns_422(client: TestClient) -> None:
    response = client.post("/process/sentiment", json={"text": "x" * 6000})
    assert response.status_code == 422


def test_valid_requests_return_200(client: TestClient, mocked_dependencies: AppDependencies) -> None:
    market_df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=2),
            "open": [1.0, 2.0],
            "close": [1.5, 2.5],
            "symbol": ["AAPL", "AAPL"],
        }
    )
    news_df = pd.DataFrame(
        {
            "title": ["headline"],
            "summary": ["summary"],
            "published": [pd.Timestamp("2026-01-01", tz="UTC")],
        }
    )
    scored_df = news_df.assign(sentiment_neg=0.1, sentiment_neu=0.7, sentiment_pos=0.2, sentiment_compound=0.1)
    sent_df = pd.DataFrame(
        {
            "title": ["x"],
            "summary": [""],
            "sentiment_neg": [0.0],
            "sentiment_neu": [1.0],
            "sentiment_pos": [0.0],
            "sentiment_compound": [0.0],
        }
    )

    mocked_dependencies.market_collector.fetch.return_value = market_df
    mocked_dependencies.news_collector.fetch.return_value = news_df
    mocked_dependencies.sentiment_processor.score_news.side_effect = [scored_df, sent_df]
    mocked_dependencies.raw_store.save.return_value = Path("/tmp/raw.csv")
    mocked_dependencies.processed_store.save.return_value = Path("/tmp/scored.csv")

    market_resp = client.post("/collect/market", json={"symbols": ["AAPL"], "interval": "1d", "lookback_days": 30})
    news_resp = client.post("/collect/news", json={"sources": [], "limit_per_feed": 10})
    sentiment_resp = client.post("/process/sentiment", json={"text": "hello"})

    assert market_resp.status_code == 200
    assert news_resp.status_code == 200
    assert sentiment_resp.status_code == 200
