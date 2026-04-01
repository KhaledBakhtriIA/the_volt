"""Stock market data collector using yfinance with technical indicators."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

import pandas as pd

from data_api.collectors.collector_contract import ensure_collector_contract

logger = logging.getLogger(__name__)


class StockMarketCollector:
    """Collect stock market price data with technical indicators."""

    def __init__(self) -> None:
        pass

    def _calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators (RSI, MACD, Bollinger Bands, SMA) to price data."""
        if df.empty:
            return df

        try:
            # Simple Moving Averages
            df["sma_20"] = df["Close"].rolling(window=20, min_periods=1).mean()
            df["sma_50"] = df["Close"].rolling(window=50, min_periods=1).mean()

            # Relative Strength Index (RSI)
            delta = df["Close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=1).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=1).mean()
            rs = gain / (loss + 1e-9)
            df["rsi_14"] = 100 - (100 / (1 + rs))

            # MACD
            ema_12 = df["Close"].ewm(span=12, adjust=False).mean()
            ema_26 = df["Close"].ewm(span=26, adjust=False).mean()
            df["macd"] = ema_12 - ema_26
            df["signal_line"] = df["macd"].ewm(span=9, adjust=False).mean()

            # Bollinger Bands
            bb_middle = df["Close"].rolling(window=20, min_periods=1).mean()
            bb_std = df["Close"].rolling(window=20, min_periods=1).std()
            df["bb_upper"] = bb_middle + (bb_std * 2)
            df["bb_lower"] = bb_middle - (bb_std * 2)

            # Volume indicators
            df["volume_sma_20"] = df["Volume"].rolling(window=20, min_periods=1).mean()

            # Daily returns
            df["daily_return"] = df["Close"].pct_change() * 100

        except Exception as exc:
            logger.warning("Technical indicator calculation failed: %s", exc)

        return df

    def fetch(
        self,
        symbols: List[str] | None = None,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        Fetch historical stock data with technical indicators.

        Args:
            symbols: List of stock symbols (e.g., ["AAPL", "MSFT", "NVDA"])
            period: Historical period ("1y", "2y", "5y", "10y", "max")
            interval: Data interval ("1d", "1wk", "1mo")

        Returns:
            DataFrame with columns: timestamp, source, fetched_at_utc, symbol, close, high, low, open, volume, rsi_14, macd, sma_20, sma_50, bb_upper, bb_lower, daily_return
        """
        if not symbols:
            symbols = [
                "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
                "TSLA", "META", "NFLX", "ADBE", "INTC",
            ]

        all_data = []
        fetched_at_utc = datetime.now(timezone.utc)

        try:
            import yfinance  # type: ignore
        except Exception:
            logger.warning("yfinance not available; stock data collection disabled")
            return pd.DataFrame()

        for symbol in symbols:
            try:
                ticker = yfinance.Ticker(symbol)
                hist = ticker.history(period=period, interval=interval)

                if hist.empty:
                    logger.debug("No historical data for symbol %s", symbol)
                    continue

                hist = hist.reset_index()
                hist.columns = [col.lower() for col in hist.columns]

                # Add technical indicators
                hist = self._calculate_technical_indicators(hist)

                # Normalize column names
                hist["timestamp"] = pd.to_datetime(hist.get("date", hist.index))
                hist["symbol"] = symbol
                hist["source"] = f"yfinance_{symbol}"
                hist["fetched_at_utc"] = fetched_at_utc

                # Select and rename relevant columns
                cols_to_keep = [
                    "timestamp", "source", "fetched_at_utc", "symbol",
                    "close", "high", "low", "open", "volume",
                    "rsi_14", "macd", "signal_line", "sma_20", "sma_50",
                    "bb_upper", "bb_lower", "daily_return",
                ]
                hist_clean = hist[[col for col in cols_to_keep if col in hist.columns]].copy()
                hist_clean = hist_clean.fillna(0)

                all_data.append(hist_clean)
                logger.debug("Collected %d rows for symbol %s", len(hist_clean), symbol)

            except Exception as exc:
                logger.warning("Failed to fetch stock data for %s: %s", symbol, exc)
                continue

        if not all_data:
            logger.warning("No stock data collected for any symbol")
            return pd.DataFrame()

        combined = pd.concat(all_data, ignore_index=True)
        return ensure_collector_contract(combined, "stock_market", "timestamp")
