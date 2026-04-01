from __future__ import annotations

from datetime import datetime, timezone
from typing import List

import pandas as pd
import requests
import yfinance as yf
import logging

from data_api.exceptions import DataCollectionError

logger = logging.getLogger(__name__)


class MarketCollector:
    """Collect market OHLCV data with Yahoo-first, FCS fallback strategy."""

    _BINANCE_INTERVALS = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w"}
    _FCS_INTERVALS = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
    }

    def __init__(self, fcs_api_key: str = "") -> None:
        self.fcs_api_key = fcs_api_key

    def _is_fcs_eligible_symbol(self, symbol: str) -> bool:
        """Return True for forex/crypto symbols suitable for FCS fallback."""
        if symbol.endswith("-USD"):
            return True  # crypto pairs like BTC-USD, ETH-USD
        if symbol.endswith("=X"):
            return True  # forex pairs like EURUSD=X
        if "/" in symbol:
            return True  # normalized forex pairs like EUR/USD
        return False

    def _normalize_fcs_symbol(self, symbol: str) -> str:
        """Map yfinance-style symbols into FCS symbol format."""
        if "/" in symbol:
            return symbol.upper()

        if symbol.endswith("-USD"):
            base = symbol.replace("-USD", "").upper()
            return f"{base}/USD"

        if symbol.endswith("=X"):
            token = symbol.replace("=X", "").upper()
            if len(token) == 6:
                return f"{token[:3]}/{token[3:]}"

        return ""

    def _extract_fcs_rows(self, payload: dict, symbol: str) -> pd.DataFrame:
        """Parse flexible FCS payloads into normalized OHLCV rows."""
        rows = payload.get("response")
        if rows is None:
            data = payload.get("data")
            if isinstance(data, dict):
                rows = data.get("items") or data.get("list")
            elif isinstance(data, list):
                rows = data

        if not isinstance(rows, list) or not rows:
            return pd.DataFrame()

        normalized = []
        fetched = datetime.now(timezone.utc).isoformat()
        for item in rows:
            if not isinstance(item, dict):
                continue

            ts_raw = item.get("t") or item.get("timestamp") or item.get("time") or item.get("date")
            open_raw = item.get("o") if item.get("o") is not None else item.get("open")
            high_raw = item.get("h") if item.get("h") is not None else item.get("high")
            low_raw = item.get("l") if item.get("l") is not None else item.get("low")
            close_raw = item.get("c") if item.get("c") is not None else item.get("close")
            volume_raw = item.get("v") if item.get("v") is not None else item.get("volume")

            ts = pd.to_datetime(ts_raw, utc=True, errors="coerce")
            if pd.isna(ts):
                continue

            try:
                normalized.append(
                    {
                        "timestamp": ts,
                        "open": float(open_raw),
                        "high": float(high_raw),
                        "low": float(low_raw),
                        "close": float(close_raw),
                        "volume": float(volume_raw or 0.0),
                        "symbol": symbol,
                        "fetched_at_utc": fetched,
                    }
                )
            except (TypeError, ValueError):
                continue

        return pd.DataFrame(normalized)

    def _fetch_fcs(self, symbol: str, interval: str, lookback_days: int) -> pd.DataFrame:
        """Fetch forex/crypto history from FCS when Yahoo has no data."""
        if not self.fcs_api_key:
            return pd.DataFrame()
        if not self._is_fcs_eligible_symbol(symbol):
            return pd.DataFrame()

        fcs_symbol = self._normalize_fcs_symbol(symbol)
        if not fcs_symbol:
            return pd.DataFrame()

        period = self._FCS_INTERVALS.get(interval, "1d")

        try:
            response = requests.get(
                "https://fcsapi.com/api-v3/forex/history",
                params={
                    "symbol": fcs_symbol,
                    "period": period,
                    "access_key": self.fcs_api_key,
                },
                timeout=20,
            )
        except requests.RequestException as exc:
            logger.warning("FCS request failed for %s: %s", fcs_symbol, exc)
            return pd.DataFrame()

        if response.status_code != 200:
            logger.warning("FCS request returned %s for %s", response.status_code, fcs_symbol)
            return pd.DataFrame()

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("FCS returned invalid JSON for %s: %s", fcs_symbol, exc)
            return pd.DataFrame()

        if not isinstance(payload, dict):
            return pd.DataFrame()

        df = self._extract_fcs_rows(payload, symbol)
        if df.empty:
            return df

        # Keep only requested lookback window.
        cutoff = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=lookback_days)
        df = df[df["timestamp"] >= cutoff]
        return df.reset_index(drop=True)

    def _fetch_binance(self, symbol: str, interval: str, lookback_days: int) -> pd.DataFrame:
        """Fetch market data from Binance for `-USD` crypto symbols."""
        if not symbol.endswith("-USD"):
            return pd.DataFrame()

        base = symbol.replace("-USD", "")
        market = f"{base}USDT"
        klines_interval = interval if interval in self._BINANCE_INTERVALS else "1d"
        
        # Binance max limit is 1000 records per request.
        # For daily: ~365 days per year, estimate records needed
        if interval == "1d":
            limit = 1000  # 1000 days ~ 3 years
        elif interval in {"1w", "3d"}:
            limit = 1000  # enough for 3+ years
        else:
            limit = min(1000, max(24, lookback_days * 24))

        try:
            response = requests.get(
                "https://api.binance.com/api/v3/klines",
                params={"symbol": market, "interval": klines_interval, "limit": limit},
                timeout=20,
            )
        except requests.RequestException as exc:
            logger.warning("Binance request failed for %s: %s", market, exc)
            return pd.DataFrame()

        if response.status_code != 200:
            logger.warning("Binance request returned %s for %s", response.status_code, market)
            return pd.DataFrame()

        try:
            payload = response.json()
        except ValueError as exc:
            logger.warning("Binance returned invalid JSON for %s: %s", market, exc)
            return pd.DataFrame()

        if not isinstance(payload, list) or not payload:
            logger.warning("Binance returned empty/invalid payload for %s", market)
            return pd.DataFrame()

        rows = []
        for item in payload:
            rows.append(
                {
                    "timestamp": pd.to_datetime(item[0], unit="ms", utc=True),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                    "symbol": symbol,
                    "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            )

        return pd.DataFrame(rows)

    def _fetch_yahoo(self, symbol: str, interval: str, lookback_days: int) -> pd.DataFrame:
        """Fetch market data from Yahoo Finance and normalize core columns."""
        source_name = "yahoo"
        try:
            ticker = yf.Ticker(symbol)
            history = ticker.history(period=f"{lookback_days}d", interval=interval, auto_adjust=False)
        except Exception as e:
            logger.error(
                "Market data fetch failed",
                extra={"source": source_name, "symbols": [symbol], "error": str(e)},
            )
            raise DataCollectionError(
                f"Failed to fetch market data from {source_name}",
                context={"symbols": [symbol], "source": source_name, "original_error": str(e)},
            ) from e

        if history.empty:
            return pd.DataFrame()

        history = history.reset_index()
        if "Datetime" in history.columns:
            history = history.rename(columns={"Datetime": "timestamp"})
        elif "Date" in history.columns:
            history = history.rename(columns={"Date": "timestamp"})

        history.columns = [str(col).lower() for col in history.columns]
        history["symbol"] = symbol
        history["fetched_at_utc"] = datetime.now(timezone.utc).isoformat()
        return history

    def fetch(self, symbols: List[str], interval: str = "1h", lookback_days: int = 30) -> pd.DataFrame:
        """Fetch OHLCV market data from Yahoo Finance with FCS fallback.
        
        Args:
            symbols: List of ticker symbols (e.g., ['BTC-USD', 'AAPL']).
            interval: Candle interval ('1m', '1h', '1d', etc.). Defaults to '1h'.
            lookback_days: Historical lookback window in days. Defaults to 30.
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume, symbol, fetched_at_utc.
            Returns empty DataFrame if no data available.
        
        Raises:
            DataCollectionError: If symbols is empty or invalid.
        """
        if not symbols or not isinstance(symbols, list):
            logger.error("Invalid symbols: must be non-empty list")
            raise DataCollectionError("symbols must be a non-empty list")
        
        frames: List[pd.DataFrame] = []
        symbol_errors: List[dict] = []

        for symbol in symbols:
            first_error: DataCollectionError | None = None
            fallback_errors: List[dict] = []

            history = pd.DataFrame()
            try:
                history = self._fetch_yahoo(symbol, interval, lookback_days)
            except DataCollectionError as e:
                first_error = e

            if not history.empty:
                frames.append(history)
                continue

            # Fallback chain for Yahoo gaps: FCS first (forex/crypto), then Binance.
            fcs_df = pd.DataFrame()
            try:
                fcs_df = self._fetch_fcs(symbol, interval, lookback_days)
            except Exception as e:
                source_name = "fcs"
                logger.error(
                    "Market data fetch failed",
                    extra={"source": source_name, "symbols": [symbol], "error": str(e)},
                )
                fallback_errors.append({"source": source_name, "error": str(e)})
            if not fcs_df.empty:
                frames.append(fcs_df)
                continue

            binance_df = pd.DataFrame()
            try:
                binance_df = self._fetch_binance(symbol, interval, lookback_days)
            except Exception as e:
                source_name = "binance"
                logger.error(
                    "Market data fetch failed",
                    extra={"source": source_name, "symbols": [symbol], "error": str(e)},
                )
                fallback_errors.append({"source": source_name, "error": str(e)})
            if not binance_df.empty:
                frames.append(binance_df)
                continue

            if first_error is not None:
                symbol_errors.append(
                    {
                        "symbol": symbol,
                        "yahoo_error": first_error.context,
                        "fallback_errors": fallback_errors,
                    }
                )

        if not frames:
            if symbol_errors:
                raise DataCollectionError(
                    "Failed to fetch market data across all providers",
                    context={"symbols": symbols, "errors": symbol_errors},
                )
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)
        combined["timestamp"] = pd.to_datetime(combined["timestamp"], utc=True, errors="coerce")
        combined = combined.dropna(subset=["timestamp"])
        combined = combined.sort_values(["symbol", "timestamp"]).reset_index(drop=True)
        return combined
