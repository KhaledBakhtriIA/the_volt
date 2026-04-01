from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from data_api.collectors.market_collector import MarketCollector
from data_api.exceptions import DataCollectionError


def test_market_collector_raises_data_collection_error_when_yahoo_fails() -> None:
    collector = MarketCollector()

    with patch("data_api.collectors.market_collector.yf.Ticker") as mock_ticker:
        ticker_obj = MagicMock()
        ticker_obj.history.side_effect = ConnectionError("yahoo down")
        mock_ticker.return_value = ticker_obj

        with pytest.raises(DataCollectionError) as exc_info:
            collector.fetch(["AAPL"], interval="1d", lookback_days=30)

    assert "Failed to fetch market data across all providers" in str(exc_info.value)


def test_market_collector_fallback_failure_includes_both_errors_in_context() -> None:
    collector = MarketCollector()

    with patch.object(collector, "_fetch_yahoo", side_effect=DataCollectionError("yahoo fail", context={"source": "yahoo"})), \
         patch.object(collector, "_fetch_fcs", side_effect=RuntimeError("fcs fail")), \
         patch.object(collector, "_fetch_binance", side_effect=RuntimeError("binance fail")):
        with pytest.raises(DataCollectionError) as exc_info:
            collector.fetch(["BTC-USD"], interval="1d", lookback_days=30)

    ctx = exc_info.value.context
    assert "errors" in ctx
    assert len(ctx["errors"]) == 1
    assert len(ctx["errors"][0]["fallback_errors"]) == 2


def test_market_collector_returns_dataframe_when_yahoo_succeeds() -> None:
    collector = MarketCollector()
    history = pd.DataFrame(
        {
            "Date": pd.date_range("2026-01-01", periods=3),
            "Open": [100.0, 101.0, 102.0],
            "High": [101.0, 102.0, 103.0],
            "Low": [99.0, 100.0, 101.0],
            "Close": [100.5, 101.5, 102.5],
            "Volume": [1000, 1200, 1100],
        }
    )

    with patch("data_api.collectors.market_collector.yf.Ticker") as mock_ticker:
        ticker_obj = MagicMock()
        ticker_obj.history.return_value = history
        mock_ticker.return_value = ticker_obj

        df = collector.fetch(["AAPL"], interval="1d", lookback_days=30)

    assert not df.empty
    assert set(["timestamp", "open", "high", "low", "close", "volume", "symbol"]).issubset(df.columns)
