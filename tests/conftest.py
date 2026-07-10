"""Pytest configuration and shared fixtures for all tests."""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_market_data():
    """Sample market data DataFrame for testing."""
    return pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=10, freq="D"),
        "open": [100.0, 101.5, 102.3, 101.8, 103.2, 104.1, 103.5, 105.2, 104.8, 106.3],
        "high": [101.0, 102.5, 103.3, 102.8, 104.2, 105.1, 104.5, 106.2, 105.8, 107.3],
        "low": [99.5, 100.8, 101.5, 101.0, 102.5, 103.2, 102.8, 104.5, 104.0, 105.5],
        "close": [100.5, 101.8, 102.0, 102.0, 103.5, 103.8, 103.2, 105.0, 105.0, 106.0],
        "volume": [1000000, 1200000, 950000, 1100000, 1300000, 1150000, 1050000, 1250000, 1100000, 1400000],
        "symbol": ["BTC-USD"] * 10,
        "fetched_at_utc": pd.Timestamp.utcnow(),
    })


@pytest.fixture
def sample_news_data():
    """Sample news data for testing."""
    return [
        {
            "title": "Bitcoin Breaks $40K Resistance",
            "source": "coindesk",
            "link": "https://coindesk.com/article1",
            "published": "2024-01-15T10:30:00",
        },
        {
            "title": "Ethereum Upgrade Delayed",
            "source": "cointelegraph",
            "link": "https://cointelegraph.com/article2",
            "published": "2024-01-15T11:45:00",
        },
    ]


@pytest.fixture
def mock_settings():
    """Mock settings configuration."""
    mock = MagicMock()
    mock.raw_dir = Path("/tmp/raw")
    mock.processed_dir = Path("/tmp/processed")
    mock.models_dir = Path("/tmp/models")
    mock.log_dir = Path("/tmp/logs")
    mock.debug = False
    return mock


@pytest.fixture
def mock_market_collector():
    """Mock MarketCollector for API tests."""
    with patch("api.rest.app.MarketCollector") as mock:
        instance = MagicMock()
        instance.fetch.return_value = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="D"),
            "open": [100.0, 101.5, 102.3, 101.8, 103.2],
            "high": [101.0, 102.5, 103.3, 102.8, 104.2],
            "low": [99.5, 100.8, 101.5, 101.0, 102.5],
            "close": [100.5, 101.8, 102.0, 102.0, 103.5],
            "volume": [1000000, 1200000, 950000, 1100000, 1300000],
            "symbol": ["BTC-USD"] * 5,
            "fetched_at_utc": pd.Timestamp.utcnow(),
        })
        mock.return_value = instance
        yield mock


@pytest.fixture
def mock_news_collector():
    """Mock NewsCollector for API tests."""
    with patch("api.rest.app.NewsCollector") as mock:
        instance = MagicMock()
        instance.fetch.return_value = [
            {
                "title": "Bitcoin Breaks $40K",
                "source": "coindesk",
                "link": "https://coindesk.com/article",
                "published": "2024-01-15T10:30:00",
            }
        ]
        mock.return_value = instance
        yield mock


@pytest.fixture
def mock_sentiment_processor():
    """Mock SentimentProcessor for API tests."""
    with patch("api.rest.app.SentimentProcessor") as mock:
        instance = MagicMock()
        instance.analyze.return_value = {
            "compound": 0.75,
            "positive": 0.85,
            "negative": 0.0,
            "neutral": 0.15,
        }
        mock.return_value = instance
        yield mock
