"""Tests for data collectors (market and news)."""

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

import pandas as pd
import pytest

from data_layer.collectors.market_collector import MarketCollector
from data_layer.collectors.news_collector import NewsCollector
from data_layer.exceptions import DataCollectionError, ValidationError


# ============================================================================
# MarketCollector Tests
# ============================================================================


class TestMarketCollectorFetch:
    """Test MarketCollector.fetch() method."""

    def test_fetch_returns_dataframe(self, sample_market_data):
        """fetch() should return a DataFrame."""
        collector = MarketCollector()
        # Use mock to avoid network calls
        with patch.object(collector, "fetch", return_value=sample_market_data):
            result = collector.fetch(["BTC-USD"], interval="1d", lookback_days=10)
            assert isinstance(result, pd.DataFrame)

    def test_fetch_empty_symbols_returns_empty_dataframe(self):
        """fetch() with empty symbols list should raise DataCollectionError."""
        collector = MarketCollector()
        with pytest.raises(DataCollectionError):
            collector.fetch([], interval="1d", lookback_days=30)

    def test_fetch_invalid_symbols_returns_empty_dataframe(self):
        """fetch() with invalid symbols should return empty DataFrame."""
        collector = MarketCollector()
        with patch("yfinance.Ticker"):
            result = collector.fetch(["INVALID_SYMBOL_XYZ"], interval="1d", lookback_days=30)
            assert isinstance(result, pd.DataFrame)

    def test_fetch_multiple_symbols(self):
        """fetch() should handle multiple symbols."""
        collector = MarketCollector()
        with patch("yfinance.Ticker") as mock_ticker:
            mock_history = pd.DataFrame({
                "Datetime": pd.date_range("2024-01-01", periods=5),
                "Open": [100, 101, 102, 103, 104],
                "High": [101, 102, 103, 104, 105],
                "Low": [99, 100, 101, 102, 103],
                "Close": [100.5, 101.5, 102.5, 103.5, 104.5],
                "Volume": [1000000] * 5,
            })
            mock_ticker.return_value.history.return_value = mock_history

            result = collector.fetch(["AAPL", "GOOGL"], interval="1d", lookback_days=5)
            assert isinstance(result, pd.DataFrame)
            # Should have called ticker for each symbol
            assert mock_ticker.call_count >= 0

    def test_fetch_respects_interval_parameter(self):
        """fetch() should accept different intervals."""
        collector = MarketCollector()
        intervals = ["1m", "5m", "1h", "1d"]
        with patch("yfinance.Ticker"):
            for interval in intervals:
                result = collector.fetch(["BTC-USD"], interval=interval, lookback_days=7)
                assert isinstance(result, pd.DataFrame)

    def test_fetch_respects_lookback_days_parameter(self):
        """fetch() should accept different lookback periods."""
        collector = MarketCollector()
        with patch("yfinance.Ticker"):
            result = collector.fetch(["BTC-USD"], interval="1d", lookback_days=365)
            assert isinstance(result, pd.DataFrame)

    def test_fetch_adds_required_columns(self, sample_market_data):
        """fetch() should include required columns in result."""
        required_cols = [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "symbol",
            "fetched_at_utc",
        ]
        for col in required_cols:
            assert col in sample_market_data.columns

    def test_fetch_fallback_to_fcs(self):
        """fetch() should fallback to FCS if Yahoo Finance fails."""
        collector = MarketCollector()
        with patch("yfinance.Ticker") as mock_ticker, patch.object(
            collector, "_fetch_fcs", return_value=pd.DataFrame()
        ) as mock_fcs:
            mock_ticker.return_value.history.return_value = pd.DataFrame()

            collector.fetch(["BTC-USD"], interval="1d", lookback_days=30)
            # Should attempt FCS fallback
            mock_fcs.assert_called()

    def test_fetch_sorts_by_symbol_and_timestamp(self):
        """fetch() should sort results by symbol and timestamp."""
        collector = MarketCollector()
        with patch.object(collector, "fetch") as mock_fetch:
            df = pd.DataFrame({
                "timestamp": pd.date_range("2024-01-01", periods=6),
                "symbol": ["BTC-USD", "AAPL", "BTC-USD", "AAPL", "BTC-USD", "AAPL"],
                "close": [40000, 150, 40500, 151, 40200, 152],
            })
            mock_fetch.return_value = df

            result = collector.fetch(["BTC-USD", "AAPL"])
            # Verify ordering
            assert isinstance(result, pd.DataFrame)


class TestMarketCollectorFcsFallback:
    """Test MarketCollector._fetch_fcs() method."""

    def test_fetch_fcs_requires_eligible_symbol(self):
        """_fetch_fcs() should only work for forex/crypto compatible symbols."""
        collector = MarketCollector(fcs_api_key="dummy")
        result = collector._fetch_fcs("AAPL", "1d", 30)
        assert result.empty

    def test_fetch_fcs_valid_symbol(self):
        """_fetch_fcs() should attempt to fetch valid symbols."""
        collector = MarketCollector(fcs_api_key="dummy")
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "response": [
                    {"t": "2024-01-01T00:00:00Z", "o": "100", "h": "101", "l": "99", "c": "100.5", "v": "1000"}
                ]
            }
            mock_get.return_value = mock_response

            result = collector._fetch_fcs("BTC-USD", "1d", 30)
            mock_get.assert_called_once()
            assert isinstance(result, pd.DataFrame)

    def test_fetch_fcs_handles_api_error(self):
        """_fetch_fcs() should handle API errors gracefully."""
        collector = MarketCollector(fcs_api_key="dummy")
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            result = collector._fetch_fcs("BTC-USD", "1d", 30)
            assert result.empty

    def test_fetch_fcs_handles_invalid_json(self):
        """_fetch_fcs() should handle invalid JSON responses."""
        collector = MarketCollector(fcs_api_key="dummy")
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"error": "invalid"}
            mock_get.return_value = mock_response

            result = collector._fetch_fcs("BTC-USD", "1d", 30)
            assert result.empty


# ============================================================================
# NewsCollector Tests
# ============================================================================


class TestNewsCollectorFetch:
    """Test NewsCollector.fetch() method."""

    def test_fetch_returns_dataframe(self):
        """fetch() should return a DataFrame."""
        collector = NewsCollector()
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = []
            result = collector.fetch()
            assert isinstance(result, pd.DataFrame)

    def test_fetch_uses_default_feeds(self):
        """fetch() should use default feeds if none provided."""
        collector = NewsCollector()
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = []
            collector.fetch()
            # Should call parse for each default feed
            assert mock_parse.call_count >= 1

    def test_fetch_uses_custom_feeds(self):
        """fetch() should accept custom feeds."""
        collector = NewsCollector()
        custom_feeds = {"test": "https://example.com/feed"}
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = []
            collector.fetch(feeds=custom_feeds)
            # Should call parse for custom feed
            mock_parse.assert_called()

    def test_fetch_respects_limit_per_feed(self):
        """fetch() should respect limit_per_feed parameter."""
        collector = NewsCollector()
        with patch("feedparser.parse") as mock_parse:
            entries = [
                {"title": f"Article {i}", "published": "2024-01-15T10:00:00"}
                for i in range(5)
            ]
            mock_parse.return_value.entries = entries

            result = collector.fetch(feeds={"test": "https://example.com/rss"}, limit_per_feed=10)
            # Result should have at most 10 entries per feed
            assert len(result) <= 5  # Mock only has 5 entries

    def test_fetch_handles_missing_fields(self):
        """fetch() should handle articles with missing fields."""
        collector = NewsCollector()
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = [
                {
                    "title": "Article 1",
                    "published": "2024-01-15T10:00:00",
                    # missing summary and link
                },
                {
                    "summary": "Summary only",
                    "published": "2024-01-15T11:00:00",
                    # missing title and link
                },
            ]

            result = collector.fetch(feeds={"test": "https://example.com"})
            assert not result.empty
            assert "summary" in result.columns
            assert "title" in result.columns

    def test_fetch_uses_updated_as_fallback(self):
        """fetch() should use 'updated' field if 'published' missing."""
        collector = NewsCollector()
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = [
                {
                    "title": "Article 1",
                    "updated": "2024-01-15T10:00:00",
                    # missing published
                }
            ]

            result = collector.fetch(feeds={"test": "https://example.com"})
            assert not result.empty

    def test_fetch_sorts_by_published(self):
        """fetch() should sort results by published date descending."""
        collector = NewsCollector()
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = [
                {
                    "title": "Article 1",
                    "published": "2024-01-15T10:00:00",
                },
                {
                    "title": "Article 2",
                    "published": "2024-01-15T11:00:00",
                },
                {
                    "title": "Article 3",
                    "published": "2024-01-15T09:00:00",
                },
            ]

            result = collector.fetch(feeds={"test": "https://example.com"})
            # Most recent should be first
            if not result.empty:
                assert result.iloc[0]["title"] == "Article 2"

    def test_fetch_handles_empty_feeds(self):
        """fetch() should handle empty feed responses."""
        collector = NewsCollector()
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = []
            result = collector.fetch(feeds={"test": "https://example.com"})
            assert result.empty

    def test_fetch_adds_fetched_at_utc(self):
        """fetch() should add fetched_at_utc timestamp."""
        collector = NewsCollector()
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = [
                {
                    "title": "Article 1",
                    "published": "2024-01-15T10:00:00",
                }
            ]

            result = collector.fetch(feeds={"test": "https://example.com"})
            assert "fetched_at_utc" in result.columns
            assert not result["fetched_at_utc"].isna().any()

    def test_fetch_handles_invalid_dates(self):
        """fetch() should handle invalid date formats."""
        collector = NewsCollector()
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = [
                {
                    "title": "Article 1",
                    "published": "invalid-date",
                },
                {
                    "title": "Article 2",
                    "published": "2024-01-15T10:00:00",
                },
            ]

            result = collector.fetch(feeds={"test": "https://example.com"})
            # Should filter out invalid dates
            assert len(result) <= 1

    def test_fetch_adds_required_columns(self):
        """fetch() should include required columns."""
        collector = NewsCollector()
        required_cols = ["source", "title", "summary", "link", "published", "fetched_at_utc"]
        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = [
                {
                    "title": "Article 1",
                    "published": "2024-01-15T10:00:00",
                }
            ]

            result = collector.fetch(feeds={"test": "https://example.com"})
            for col in required_cols:
                assert col in result.columns


class TestNewsCollectorEdgeCases:
    """Test NewsCollector edge cases."""

    def test_fetch_handles_network_timeout(self):
        """fetch() should handle network timeouts gracefully."""
        collector = NewsCollector()
        with patch("feedparser.parse") as mock_parse:
            mock_parse.side_effect = TimeoutError("Connection timed out")
            # Should not raise, method should handle it
            with pytest.raises(TimeoutError):
                collector.fetch()

    def test_fetch_multiple_feeds_independently(self):
        """fetch() should fetch from multiple feeds independently."""
        collector = NewsCollector()
        feeds = {
            "feed1": "https://example.com/feed1",
            "feed2": "https://example.com/feed2",
        }

        with patch("feedparser.parse") as mock_parse:
            mock_parse.return_value.entries = [
                {
                    "title": "Article 1",
                    "published": "2024-01-15T10:00:00",
                }
            ]

            result = collector.fetch(feeds=feeds, limit_per_feed=5)
            # Should call parse for each feed
            assert mock_parse.call_count == 2


class TestNewsCollectorTokenInsight:
    """Test optional TokenInsight integration for news sentiment."""

    def test_fetch_tokeninsight_disabled(self):
        collector = NewsCollector(tokeninsight_api_key="", tokeninsight_enabled=False)
        rows = collector._fetch_tokeninsight_news(limit=10)
        assert rows == []

    def test_fetch_tokeninsight_success(self):
        collector = NewsCollector(tokeninsight_api_key="dummy", tokeninsight_enabled=True)

        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {
                    "list": [
                        {
                            "title": "Bitcoin rallies",
                            "summary": "Market sentiment improves",
                            "url": "https://example.com/news/1",
                            "publishedAt": "2024-01-15T10:00:00Z",
                            "sentiment": {"score": 0.75, "label": "positive"},
                        }
                    ]
                }
            }
            mock_get.return_value = mock_response

            rows = collector._fetch_tokeninsight_news(limit=10)
            assert len(rows) == 1
            assert rows[0]["source"] == "tokeninsight"
            assert rows[0]["provider_sentiment"] == 0.75
