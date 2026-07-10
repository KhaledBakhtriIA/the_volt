"""Tests for FastAPI endpoints using dependency overrides."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.rest.app import AppDependencies, app, get_dependencies


@pytest.fixture
def market_request() -> dict:
    """Valid market request payload."""
    return {
        "symbols": ["BTC-USD", "AAPL"],
        "interval": "1d",
        "lookback_days": 30,
    }


@pytest.fixture
def news_request() -> dict:
    """Valid news request payload."""
    return {"limit_per_feed": 50}


@pytest.fixture
def mocked_dependencies() -> AppDependencies:
    """Create a mock dependency container for endpoint tests."""
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
def client(mocked_dependencies: AppDependencies) -> TestClient:
    """FastAPI test client with dependency overrides."""
    app.dependency_overrides[get_dependencies] = lambda: mocked_dependencies
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class TestHealthEndpoint:
    """Test /health endpoint."""

    def test_health_returns_ok(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestCollectMarketEndpoint:
    """Test POST /collect/market endpoint."""

    def test_collect_market_success(
        self,
        client: TestClient,
        mocked_dependencies: AppDependencies,
        market_request: dict,
    ) -> None:
        mock_df = pd.DataFrame(
            {
                "timestamp": pd.date_range("2024-01-01", periods=5),
                "open": [100, 101, 102, 103, 104],
                "close": [101, 102, 103, 104, 105],
                "symbol": ["BTC-USD"] * 5,
            }
        )
        mocked_dependencies.market_collector.fetch.return_value = mock_df
        mocked_dependencies.raw_store.save.return_value = Path("/tmp/market_20240115_120000.csv")

        response = client.post("/collect/market", json=market_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert int(data["rows"]) == 5
        assert "file" in data

    def test_collect_market_no_data(
        self,
        client: TestClient,
        mocked_dependencies: AppDependencies,
        market_request: dict,
    ) -> None:
        mocked_dependencies.market_collector.fetch.return_value = pd.DataFrame()

        response = client.post("/collect/market", json=market_request)

        assert response.status_code == 200
        assert response.json() == {"status": "no_data", "rows": "0"}

    def test_collect_market_passes_parameters(
        self,
        client: TestClient,
        mocked_dependencies: AppDependencies,
    ) -> None:
        payload = {
            "symbols": ["ETH-USD"],
            "interval": "1h",
            "lookback_days": 60,
        }
        mocked_dependencies.market_collector.fetch.return_value = pd.DataFrame()

        client.post("/collect/market", json=payload)

        mocked_dependencies.market_collector.fetch.assert_called_once_with(
            payload["symbols"],
            payload["interval"],
            payload["lookback_days"],
        )

    def test_collect_market_validation_invalid_interval(self, client: TestClient) -> None:
        payload = {
            "symbols": ["BTC-USD"],
            "interval": "invalid_interval",
            "lookback_days": 30,
        }
        response = client.post("/collect/market", json=payload)
        assert response.status_code == 422


class TestCollectNewsEndpoint:
    """Test POST /collect/news endpoint."""

    def test_collect_news_success(
        self,
        client: TestClient,
        mocked_dependencies: AppDependencies,
        news_request: dict,
    ) -> None:
        mock_news_df = pd.DataFrame(
            {
                "title": ["Article 1", "Article 2"],
                "summary": ["Summary 1", "Summary 2"],
                "published": pd.date_range("2024-01-01", periods=2),
            }
        )
        mock_scored_df = mock_news_df.copy()
        mock_scored_df["sentiment_compound"] = [0.5, -0.3]

        mocked_dependencies.news_collector.fetch.return_value = mock_news_df
        mocked_dependencies.sentiment_processor.score_news.return_value = mock_scored_df
        mocked_dependencies.raw_store.save.return_value = Path("/tmp/news.csv")
        mocked_dependencies.processed_store.save.return_value = Path("/tmp/news_scored.csv")

        response = client.post("/collect/news", json=news_request)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["rows"] == "2"
        assert "news_file" in data
        assert "news_scored_file" in data

    def test_collect_news_no_data(
        self,
        client: TestClient,
        mocked_dependencies: AppDependencies,
        news_request: dict,
    ) -> None:
        mocked_dependencies.news_collector.fetch.return_value = pd.DataFrame()

        response = client.post("/collect/news", json=news_request)

        assert response.status_code == 200
        assert response.json() == {"status": "no_data", "rows": "0"}

    def test_collect_news_passes_limit(
        self,
        client: TestClient,
        mocked_dependencies: AppDependencies,
    ) -> None:
        payload = {"limit_per_feed": 100}
        mocked_dependencies.news_collector.fetch.return_value = pd.DataFrame()

        client.post("/collect/news", json=payload)

        mocked_dependencies.news_collector.fetch.assert_called_once_with(limit_per_feed=100)


class TestLatestDatasetsEndpoint:
    """Test GET /datasets/latest endpoint."""

    def test_latest_datasets_success(self, client: TestClient, mocked_dependencies: AppDependencies) -> None:
        mocked_dependencies.raw_store.latest_file.side_effect = [
            Path("/tmp/market.csv"),
            Path("/tmp/news.csv"),
            Path("/tmp/browser.csv"),
            Path("/tmp/reddit.csv"),
            Path("/tmp/macro.csv"),
            Path("/tmp/desktop.csv"),
            Path("/tmp/stock_market.csv"),
            Path("/tmp/trading_strategy.csv"),
            Path("/tmp/trading_mistakes.csv"),
        ]
        mocked_dependencies.processed_store.latest_file.return_value = Path("/tmp/news_scored.csv")
        mocked_dependencies.export_store.latest_file.return_value = Path("/tmp/training_export.csv")

        response = client.get("/datasets/latest")

        assert response.status_code == 200
        assert response.json() == {
            "market": str(Path("/tmp/market.csv")),
            "news": str(Path("/tmp/news.csv")),
            "browser": str(Path("/tmp/browser.csv")),
            "reddit": str(Path("/tmp/reddit.csv")),
            "macro": str(Path("/tmp/macro.csv")),
            "desktop": str(Path("/tmp/desktop.csv")),
            "stock_market": str(Path("/tmp/stock_market.csv")),
            "trading_strategy": str(Path("/tmp/trading_strategy.csv")),
            "trading_mistakes": str(Path("/tmp/trading_mistakes.csv")),
            "news_scored": str(Path("/tmp/news_scored.csv")),
            "training_export": str(Path("/tmp/training_export.csv")),
        }

    def test_latest_datasets_empty_paths(self, client: TestClient, mocked_dependencies: AppDependencies) -> None:
        mocked_dependencies.raw_store.latest_file.return_value = None
        mocked_dependencies.processed_store.latest_file.return_value = None
        mocked_dependencies.export_store.latest_file.return_value = None

        response = client.get("/datasets/latest")

        assert response.status_code == 200
        assert response.json() == {
            "market": "",
            "news": "",
            "browser": "",
            "reddit": "",
            "macro": "",
            "desktop": "",
            "stock_market": "",
            "trading_strategy": "",
            "trading_mistakes": "",
            "news_scored": "",
            "training_export": "",
        }


class TestNewCollectorEndpoints:
    """Test browser/reddit/macro/desktop endpoints."""

    def test_collect_browser_success(self, client: TestClient, mocked_dependencies: AppDependencies) -> None:
        mocked_dependencies.browser_collector.fetch.return_value = pd.DataFrame({"timestamp": [pd.Timestamp.utcnow()]})
        mocked_dependencies.raw_store.save.return_value = Path("/tmp/browser.csv")

        response = client.post("/collect/browser", json={"max_rows_per_target": 10})

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mocked_dependencies.browser_collector.fetch.assert_called_once()

    def test_collect_reddit_success(self, client: TestClient, mocked_dependencies: AppDependencies) -> None:
        mocked_dependencies.reddit_collector.fetch.return_value = pd.DataFrame({"timestamp": [pd.Timestamp.utcnow()]})
        mocked_dependencies.raw_store.save.return_value = Path("/tmp/reddit.csv")

        payload = {"subreddits": ["bitcoin"], "query": "market", "limit_per_subreddit": 5}
        response = client.post("/collect/reddit", json=payload)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mocked_dependencies.reddit_collector.fetch.assert_called_once()

    def test_collect_macro_success(self, client: TestClient, mocked_dependencies: AppDependencies) -> None:
        mocked_dependencies.macro_collector.fetch.return_value = pd.DataFrame({"timestamp": [pd.Timestamp.utcnow()]})
        mocked_dependencies.raw_store.save.return_value = Path("/tmp/macro.csv")

        response = client.post("/collect/macro", json={"series": {"fed_funds_rate": "FEDFUNDS"}})

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mocked_dependencies.macro_collector.fetch.assert_called_once()

    def test_collect_desktop_success(self, client: TestClient, mocked_dependencies: AppDependencies) -> None:
        mocked_dependencies.desktop_collector.fetch.return_value = pd.DataFrame({"timestamp": [pd.Timestamp.utcnow()]})
        mocked_dependencies.raw_store.save.return_value = Path("/tmp/desktop.csv")

        response = client.post("/collect/desktop", json={"targets": {"terminal": "active_screen"}})

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mocked_dependencies.desktop_collector.fetch.assert_called_once()

    def test_finance_query_stream_config(self, client: TestClient) -> None:
        response = client.post("/stream/finance-query/config", json={"symbols": ["BTC-USD", "EURUSD=X"]})
        assert response.status_code == 200
        payload = response.json()
        assert "enabled" in payload
        assert "ws_url" in payload
        assert payload["subscription"]["symbols"] == ["BTC-USD", "EURUSD=X"]


class TestCollectFullEndpoint:
    """Test POST /collect/full endpoint."""

    def test_collect_full_calls_pipeline(self, client: TestClient) -> None:
        with patch("api.rest.app.run_full_collection") as mock_pipeline:
            mock_pipeline.return_value = {"status": "ok"}
            response = client.post("/collect/full")

            assert response.status_code == 200
            mock_pipeline.assert_called_once()

    def test_collect_full_passes_injected_dependencies(
        self,
        client: TestClient,
        mocked_dependencies: AppDependencies,
    ) -> None:
        with patch("api.rest.app.run_full_collection") as mock_pipeline:
            mock_pipeline.return_value = {"status": "ok"}
            client.post("/collect/full")

            _, kwargs = mock_pipeline.call_args
            assert kwargs["market_collector"] is mocked_dependencies.market_collector
            assert kwargs["news_collector"] is mocked_dependencies.news_collector
            assert kwargs["browser_collector"] is mocked_dependencies.browser_collector
            assert kwargs["reddit_collector"] is mocked_dependencies.reddit_collector
            assert kwargs["macro_collector"] is mocked_dependencies.macro_collector
            assert kwargs["desktop_collector"] is mocked_dependencies.desktop_collector
            assert kwargs["stock_market_collector"] is mocked_dependencies.stock_market_collector
            assert kwargs["trading_strategy_collector"] is mocked_dependencies.trading_strategy_collector
            assert kwargs["trading_mistakes_collector"] is mocked_dependencies.trading_mistakes_collector
            assert kwargs["sentiment_processor"] is mocked_dependencies.sentiment_processor
            assert kwargs["raw_store"] is mocked_dependencies.raw_store
            assert kwargs["processed_store"] is mocked_dependencies.processed_store
            assert kwargs["export_store"] is mocked_dependencies.export_store


class TestEndpointErrorHandling:
    """Test error propagation in endpoints."""

    def test_collect_market_handles_collector_error(
        self,
        client: TestClient,
        mocked_dependencies: AppDependencies,
        market_request: dict,
    ) -> None:
        mocked_dependencies.market_collector.fetch.side_effect = RuntimeError("API error")

        with pytest.raises(RuntimeError):
            client.post("/collect/market", json=market_request)

    def test_collect_news_handles_collector_error(
        self,
        client: TestClient,
        mocked_dependencies: AppDependencies,
        news_request: dict,
    ) -> None:
        mocked_dependencies.news_collector.fetch.side_effect = RuntimeError("API error")

        with pytest.raises(RuntimeError):
            client.post("/collect/news", json=news_request)
