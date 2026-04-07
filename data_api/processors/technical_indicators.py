from __future__ import annotations

import pandas as pd


class TechnicalIndicatorProcessor:
    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index (RSI)."""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate MACD (Moving Average Convergence Divergence)."""
        ema_fast = series.ewm(span=fast).mean()
        ema_slow = series.ewm(span=slow).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def bollinger_bands(series: pd.Series, period: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate Bollinger Bands."""
        sma = series.rolling(window=period).mean()
        std = series.rolling(window=period).std()
        upper = sma + (std * num_std)
        lower = sma - (std * num_std)
        return upper, sma, lower

    @staticmethod
    def add_indicators_to_df(df: pd.DataFrame, price_col: str = "close") -> pd.DataFrame:
        """Add all technical indicators to a dataframe grouped by symbol."""
        result = df.copy()

        for symbol in result["symbol"].unique():
            mask = result["symbol"] == symbol
            symbol_data = result.loc[mask].sort_values("timestamp")

            if len(symbol_data) > 20:
                prices = symbol_data[price_col]
                result.loc[mask, "rsi_14"] = TechnicalIndicatorProcessor.rsi(prices, 14).values
                macd, signal, hist = TechnicalIndicatorProcessor.macd(prices, 12, 26, 9)
                result.loc[mask, "macd"] = macd.values
                result.loc[mask, "macd_signal"] = signal.values
                result.loc[mask, "macd_histogram"] = hist.values
                upper, middle, lower = TechnicalIndicatorProcessor.bollinger_bands(prices, 20, 2.0)
                result.loc[mask, "bb_upper"] = upper.values
                result.loc[mask, "bb_middle"] = middle.values
                result.loc[mask, "bb_lower"] = lower.values
            else:
                result.loc[mask, "rsi_14"] = None
                result.loc[mask, "macd"] = None
                result.loc[mask, "macd_signal"] = None
                result.loc[mask, "macd_histogram"] = None
                result.loc[mask, "bb_upper"] = None
                result.loc[mask, "bb_middle"] = None
                result.loc[mask, "bb_lower"] = None

        return result
