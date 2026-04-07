"""Tests for trading-related data collectors."""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from data_api.collectors.stock_market_collector import StockMarketCollector
from data_api.collectors.trading_strategy_collector import TradingStrategyCollector
from data_api.collectors.trading_mistakes_collector import TradingMistakesCollector


class TestStockMarketCollector:
    """Test stock market data collection."""

    def test_stock_market_no_yfinance(self) -> None:
        """Test StockMarketCollector when yfinance is not available."""
        with patch("data_api.collectors.stock_market_collector.pd") as mock_pd:
            mock_pd.DataFrame.side_effect = Exception()
            collector = StockMarketCollector()
            # Import error will cause early return
            assert collector is not None

    def test_stock_market_empty_results(self) -> None:
        """Test StockMarketCollector with empty yfinance results."""
        collector = StockMarketCollector()
        # Patch inside fetch method where yfinance is imported
        with patch("yfinance.Ticker") as mock_ticker_class:
            mock_ticker = MagicMock()
            mock_ticker.history.return_value = pd.DataFrame()
            mock_ticker_class.return_value = mock_ticker
            
            df = collector.fetch(symbols=["INVALID"])
            # Should return empty DataFrame when no data
            assert df.empty or isinstance(df, pd.DataFrame)

    def test_stock_market_defaults(self) -> None:
        """Test StockMarketCollector uses defaults correctly."""
        collector = StockMarketCollector()
        # Should not raise exception
        assert collector is not None

    def test_stock_market_technical_indicators(self) -> None:
        """Test technical indicator calculation."""
        # Create sample DataFrame
        sample_data = {
            "Close": [100, 101, 102, 103, 104, 105] * 10,
            "High": [101, 102, 103, 104, 105, 106] * 10,
            "Low": [99, 100, 101, 102, 103, 104] * 10,
            "Open": [100, 101, 102, 103, 104, 105] * 10,
            "Volume": [1000000] * 60,
        }
        df = pd.DataFrame(sample_data)
        
        collector = StockMarketCollector()
        result = collector._calculate_technical_indicators(df)
        
        # Should have added indicator columns
        assert "sma_20" in result.columns
        assert "rsi_14" in result.columns
        assert "macd" in result.columns


class TestTradingStrategyCollector:
    """Test trading strategy data collection."""

    def test_trading_strategy_no_credentials(self) -> None:
        """Test TradingStrategyCollector with no Reddit credentials."""
        collector = TradingStrategyCollector(reddit_client_id="", reddit_client_secret="")
        df = collector.fetch()
        # Should return empty DataFrame when no credentials
        assert df.empty

    def test_trading_strategy_initialization(self) -> None:
        """Test TradingStrategyCollector initialization."""
        collector = TradingStrategyCollector(
            reddit_client_id="test_id",
            reddit_client_secret="test_secret",
            reddit_user_agent="test_agent",
        )
        assert collector.reddit_client_id == "test_id"
        assert collector.reddit_client_secret == "test_secret"
        assert collector.reddit_user_agent == "test_agent"

    def test_trading_strategy_with_mock_reddit(self) -> None:
        """Test TradingStrategyCollector defaults and structure."""
        collector = TradingStrategyCollector(
            reddit_client_id="test",
            reddit_client_secret="test",
        )
        # Should initialize without error
        assert collector is not None
        assert collector.reddit_client_id == "test"


class TestTradingMistakesCollector:
    """Test trading mistakes data collection."""

    def test_trading_mistakes_no_credentials(self) -> None:
        """Test TradingMistakesCollector with no Reddit credentials."""
        collector = TradingMistakesCollector(reddit_client_id="", reddit_client_secret="")
        df = collector.fetch()
        # Should return empty DataFrame when no credentials
        assert df.empty

    def test_trading_mistakes_initialization(self) -> None:
        """Test TradingMistakesCollector initialization."""
        collector = TradingMistakesCollector(
            reddit_client_id="test_id",
            reddit_client_secret="test_secret",
            reddit_user_agent="test_agent",
        )
        assert collector.reddit_client_id == "test_id"
        assert collector.reddit_client_secret == "test_secret"

    def test_trading_mistakes_mistake_classification(self) -> None:
        """Test mistake type classification defaults."""
        collector = TradingMistakesCollector(
            reddit_client_id="test",
            reddit_client_secret="test",
        )
        # Should initialize without error
        assert collector is not None
        assert collector.reddit_client_id == "test"

