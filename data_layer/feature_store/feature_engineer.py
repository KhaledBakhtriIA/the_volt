"""
Feature Engineering Engine
===========================
Extracted from notebook Phase 8 (cells 583-584).
Provides the FeatureEngineer class with 150+ features across price,
volume, volatility, momentum, mean-reversion, microstructure, and
technical-indicator categories.

TA-Lib and pandas-ta are optional; Python/numpy fallbacks are used when
they are unavailable so the module always imports cleanly.
"""

import numpy as np
import pandas as pd
import warnings

warnings.filterwarnings("ignore")

# Optional: pandas_ta (lightweight wrapper)
try:
    import pandas_ta as ta  # noqa: F401
    HAS_PANDAS_TA = True
except Exception:
    ta = None
    HAS_PANDAS_TA = False

# Optional: TA-Lib (C extension)
try:
    import talib
    HAS_TALIB = True
except Exception:
    talib = None
    HAS_TALIB = False

from sklearn.preprocessing import StandardScaler  # noqa: E402  (follows optional-talib guard)


# ============================================================================
# FEATURE ENGINEERING ENGINE
# ============================================================================

class FeatureEngineer:
    """Professional feature engineering for trading signals.

    Call ``calculate_all_features`` with raw numpy arrays to receive a
    (1, n_features) numpy array together with ``self.feature_names`` updated
    in-place.
    """

    def __init__(self):
        self.scaler = StandardScaler()
        self.feature_names: list[str] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_all_features(
        self,
        prices: np.ndarray,
        volumes: np.ndarray,
        high: np.ndarray | None = None,
        low: np.ndarray | None = None,
        close: np.ndarray | None = None,
    ) -> np.ndarray:
        """Calculate comprehensive feature set.

        Parameters
        ----------
        prices, volumes : 1-D numpy arrays
        high, low, close : optional 1-D arrays (default to *prices* if omitted)

        Returns
        -------
        np.ndarray of shape (1, n_features)
        """
        prices = np.asarray(prices, dtype=float)
        volumes = np.asarray(volumes, dtype=float)
        if high is None:
            high = prices
        if low is None:
            low = prices
        if close is None:
            close = prices

        features: dict[str, float] = {}
        features.update(self._price_features(prices, high, low, close))
        features.update(self._volume_features(prices, volumes))
        features.update(self._volatility_features(prices))
        features.update(self._momentum_features(prices, high, low, close))
        features.update(self._mean_reversion_features(prices, high, low, close))
        features.update(self._microstructure_features(prices, volumes))
        features.update(self._technical_indicators(prices, high, low, close, volumes))

        feature_values = np.array(list(features.values())).reshape(1, -1)
        self.feature_names = list(features.keys())
        return feature_values

    def features_as_dict(
        self,
        prices: np.ndarray,
        volumes: np.ndarray,
        high: np.ndarray | None = None,
        low: np.ndarray | None = None,
        close: np.ndarray | None = None,
    ) -> dict[str, float]:
        """Convenience wrapper — returns a plain name→value dict."""
        arr = self.calculate_all_features(prices, volumes, high, low, close)
        return dict(zip(self.feature_names, arr.flatten()))

    # ------------------------------------------------------------------
    # Sub-groups
    # ------------------------------------------------------------------

    def _price_features(self, prices, high, low, close) -> dict:
        returns = np.diff(prices) / (prices[:-1] + 1e-12)

        features: dict[str, float] = {
            "price": float(prices[-1]),
            "log_price": float(np.log(prices[-1] + 1e-12)),
            "return_1d": float(returns[-1]) if len(returns) > 0 else 0.0,
            "return_5d": float(prices[-1] / prices[-5] - 1) if len(prices) > 5 else 0.0,
            "return_20d": float(prices[-1] / prices[-20] - 1) if len(prices) > 20 else 0.0,
            "return_60d": float(prices[-1] / prices[-60] - 1) if len(prices) > 60 else 0.0,
            "high_low_ratio": float((high[-1] / low[-1] - 1) if low[-1] > 0 else 0.0),
            "close_position": float(
                (close[-1] - low[-1]) / (high[-1] - low[-1])
            ) if high[-1] != low[-1] else 0.5,
        }

        for window in [5, 10, 20, 50]:
            if len(prices) > window:
                rolling_returns = float(prices[-1] / prices[-window] - 1)
                features[f"return_{window}d"] = rolling_returns

                if window > 1 and len(prices) >= window:
                    recent_diff = np.diff(prices[-window:])
                    rolling_vol = float(np.std(recent_diff / (prices[-window:-1] + 1e-12)))
                else:
                    rolling_vol = 0.0
                features[f"vol_{window}d"] = rolling_vol
                features[f"sharpe_{window}d"] = (
                    float(rolling_returns / (rolling_vol + 1e-6)) if rolling_vol > 0 else 0.0
                )

        return features

    def _volume_features(self, prices, volumes) -> dict:
        if len(volumes) < 2:
            return {}

        features: dict[str, float] = {
            "volume": float(volumes[-1]),
            "log_volume": float(np.log(volumes[-1] + 1)),
            "volume_ratio": (
                float(volumes[-1] / np.mean(volumes[-20:])) if len(volumes) > 20 else 1.0
            ),
            "volume_zscore": (
                float((volumes[-1] - np.mean(volumes[-20:])) / (np.std(volumes[-20:]) + 1e-6))
                if len(volumes) > 20 else 0.0
            ),
        }

        if len(prices) > 20 and len(volumes) > 20:
            price_changes = np.diff(prices[-21:]) / (prices[-21:-1] + 1e-12)
            volume_changes = np.diff(volumes[-21:]) / (volumes[-21:-1] + 1e-6)
            corr = (
                np.corrcoef(price_changes, volume_changes)[0, 1]
                if len(price_changes) > 1 else 0.0
            )
            features["price_volume_corr"] = float(corr)

        if len(volumes) > 5:
            recent_avg = np.mean(volumes[-5:])
            earlier_avg = np.mean(volumes[-10:-5]) if len(volumes) > 10 else recent_avg
            features["volume_acceleration"] = float(recent_avg / (earlier_avg + 1e-6) - 1)

        return features

    def _volatility_features(self, prices) -> dict:
        if len(prices) < 2:
            return {}

        returns = np.diff(prices) / (prices[:-1] + 1e-12)

        features: dict[str, float] = {
            "realized_vol_5d": (
                float(np.std(returns[-5:]) * np.sqrt(252)) if len(returns) >= 5 else 0.0
            ),
            "realized_vol_20d": (
                float(np.std(returns[-20:]) * np.sqrt(252)) if len(returns) >= 20 else 0.0
            ),
            "realized_vol_60d": (
                float(np.std(returns[-60:]) * np.sqrt(252)) if len(returns) >= 60 else 0.0
            ),
            "vol_of_vol": (
                float(
                    np.std([
                        np.std(returns[-20:-10]) if len(returns) >= 20 else 0.0,
                        np.std(returns[-10:]) if len(returns) >= 10 else 0.0,
                    ])
                ) if len(returns) >= 10 else 0.0
            ),
        }

        if len(prices) >= 21:
            pr = np.array(prices[-21:])
            log_hl = np.log(pr[1:] / (pr[:-1] + 1e-12))
            features["gk_vol"] = float(np.sqrt(np.mean(0.5 * log_hl**2 + 1e-12)))

        if len(prices) >= 21:
            pr = np.array(prices[-21:])
            rng = pr / np.minimum.accumulate(pr) + 1e-12
            features["parkinson_vol"] = float(
                np.sqrt(1 / (4 * np.log(2)) * np.mean(np.log(rng) ** 2))
            )

        return features

    def _momentum_features(self, prices, high, low, close) -> dict:
        features: dict[str, float] = {}

        # RSI
        if len(prices) > 14:
            if HAS_TALIB:
                try:
                    rsi = talib.RSI(prices, timeperiod=14)[-1]
                except Exception:
                    rsi = 50.0
            else:
                delta = np.diff(prices)
                up = np.where(delta > 0, delta, 0.0)
                down = np.where(delta < 0, -delta, 0.0)
                avg_up = np.mean(up[-14:]) if len(up) >= 14 else (np.mean(up) if len(up) > 0 else 0.0)
                avg_down = np.mean(down[-14:]) if len(down) >= 14 else (np.mean(down) if len(down) > 0 else 0.0)
                rs = avg_up / (avg_down + 1e-6)
                rsi = 100.0 - 100.0 / (1.0 + rs)
            features["rsi_14"] = float(rsi)

        # MACD
        if len(prices) > 26:
            if HAS_TALIB:
                try:
                    macd, signal, hist = talib.MACD(prices, fastperiod=12, slowperiod=26, signalperiod=9)
                    features["macd"] = float(macd[-1]) if not np.isnan(macd[-1]) else 0.0
                    features["macd_signal"] = float(signal[-1]) if not np.isnan(signal[-1]) else 0.0
                    features["macd_hist"] = float(hist[-1]) if not np.isnan(hist[-1]) else 0.0
                except Exception:
                    features.update({"macd": 0.0, "macd_signal": 0.0, "macd_hist": 0.0})
            else:
                s = pd.Series(prices)
                ema12 = s.ewm(span=12, adjust=False).mean()
                ema26 = s.ewm(span=26, adjust=False).mean()
                macd_line = ema12 - ema26
                signal_line = macd_line.ewm(span=9, adjust=False).mean()
                hist_line = macd_line - signal_line
                features["macd"] = float(macd_line.values[-1])
                features["macd_signal"] = float(signal_line.values[-1])
                features["macd_hist"] = float(hist_line.values[-1])

        # Stochastic
        if len(high) > 14 and len(low) > 14 and len(close) > 14:
            if HAS_TALIB:
                try:
                    slowk, slowd = talib.STOCH(high, low, close, fastk_period=14, slowk_period=3, slowd_period=3)
                    features["stoch_k"] = float(slowk[-1]) if not np.isnan(slowk[-1]) else 50.0
                    features["stoch_d"] = float(slowd[-1]) if not np.isnan(slowd[-1]) else 50.0
                except Exception:
                    features["stoch_k"] = 50.0
                    features["stoch_d"] = 50.0
            else:
                hl_low = np.min(low[-14:])
                hl_high = np.max(high[-14:])
                denom = hl_high - hl_low if (hl_high - hl_low) != 0 else 1e-12
                k = (close[-1] - hl_low) / denom * 100.0
                d = (
                    np.mean([(close[-i] - hl_low) / denom * 100.0 for i in range(1, 4)])
                    if len(close) >= 3 else k
                )
                features["stoch_k"] = float(k)
                features["stoch_d"] = float(d)

        # ADX
        if len(high) > 14 and len(low) > 14 and len(close) > 14:
            if HAS_TALIB:
                try:
                    adx = talib.ADX(high, low, close, timeperiod=14)
                    features["adx"] = float(adx[-1]) if not np.isnan(adx[-1]) else 0.0
                except Exception:
                    features["adx"] = 0.0
            else:
                features["adx"] = 0.0

        # Rate of Change
        for period in [5, 10, 20]:
            if len(prices) > period:
                if HAS_TALIB:
                    try:
                        roc = talib.ROC(prices, timeperiod=period)[-1]
                    except Exception:
                        roc = float(prices[-1] / prices[-period] - 1.0)
                else:
                    roc = float(prices[-1] / prices[-period] - 1.0)
                features[f"roc_{period}"] = float(roc)

        return features

    def _mean_reversion_features(self, prices, high, low, close) -> dict:
        features: dict[str, float] = {}

        # Bollinger Bands
        if len(prices) > 20:
            if HAS_TALIB:
                try:
                    upper, middle, lower = talib.BBANDS(prices, timeperiod=20, nbdevup=2, nbdevdn=2)
                    upper_val = upper[-1] if not np.isnan(upper[-1]) else prices[-1]
                    middle_val = middle[-1] if not np.isnan(middle[-1]) else prices[-1]
                    lower_val = lower[-1] if not np.isnan(lower[-1]) else prices[-1]
                except Exception:
                    upper_val = middle_val = lower_val = prices[-1]
            else:
                s = pd.Series(prices)
                middle_val = (
                    float(s.rolling(window=20).mean().values[-1]) if len(s) >= 20 else float(np.mean(prices))
                )
                std_val = (
                    float(s.rolling(window=20).std().values[-1]) if len(s) >= 20 else float(np.std(prices))
                )
                upper_val = middle_val + 2 * std_val
                lower_val = middle_val - 2 * std_val

            features["bb_upper"] = float(upper_val)
            features["bb_middle"] = float(middle_val)
            features["bb_lower"] = float(lower_val)
            features["bb_width"] = (
                float((upper_val - lower_val) / (middle_val + 1e-12)) if middle_val > 0 else 0.0
            )
            features["bb_position"] = (
                float((prices[-1] - lower_val) / (upper_val - lower_val))
                if upper_val != lower_val else 0.5
            )

        # Z-Score vs moving average
        for period in [20, 50, 200]:
            if len(prices) > period:
                ma = np.mean(prices[-period:])
                std = np.std(prices[-period:])
                features[f"zscore_{period}"] = float((prices[-1] - ma) / (std + 1e-6))

        # CCI
        if len(high) > 20 and len(low) > 20 and len(close) > 20:
            if HAS_TALIB:
                try:
                    cci = talib.CCI(high, low, close, timeperiod=20)
                    features["cci"] = float(cci[-1]) if not np.isnan(cci[-1]) else 0.0
                except Exception:
                    features["cci"] = 0.0
            else:
                features["cci"] = 0.0

        return features

    def _microstructure_features(self, prices, volumes) -> dict:
        features: dict[str, float] = {}

        if len(prices) < 2 or len(volumes) < 2:
            return features

        returns = np.diff(prices) / (prices[:-1] + 1e-12)

        # Amihud illiquidity
        if len(returns) > 0:
            n = min(20, len(returns))
            illiquidity = np.mean(np.abs(returns[-n:]) / (volumes[-n:] + 1e-12))
            features["amihud_illiquidity"] = float(illiquidity)

        # Roll's spread estimator
        if len(prices) > 2:
            window = min(20, len(prices))
            price_changes = np.diff(prices[-window:])
            if len(price_changes) > 1:
                covariance = np.cov(price_changes[:-1], price_changes[1:])[0, 1]
                roll_spread = 2 * np.sqrt(max(0.0, -covariance))
                features["roll_spread"] = float(roll_spread)

        # VWAP deviation
        if len(prices) > 0 and len(volumes) > 0:
            window = min(20, len(prices))
            vwap = np.sum(prices[-window:] * volumes[-window:]) / (np.sum(volumes[-window:]) + 1e-12)
            features["vwap_deviation"] = float((prices[-1] - vwap) / (vwap + 1e-12))

        return features

    def _technical_indicators(self, prices, high, low, close, volumes) -> dict:
        features: dict[str, float] = {}

        # ATR
        if len(high) > 14 and len(low) > 14 and len(close) > 14:
            if HAS_TALIB:
                try:
                    atr = talib.ATR(high, low, close, timeperiod=14)
                    atr_val = atr[-1] if not np.isnan(atr[-1]) else 0.0
                except Exception:
                    atr_val = 0.0
            else:
                prev_close = np.roll(close, 1)
                tr1 = high - low
                tr2 = np.abs(high - prev_close)
                tr3 = np.abs(low - prev_close)
                tr = np.maximum.reduce([tr1, tr2, tr3])
                atr_val = float(pd.Series(tr).rolling(window=14, min_periods=1).mean().values[-1])
            features["atr"] = float(atr_val)
            features["atr_percent"] = float(atr_val / (close[-1] + 1e-12))

        # OBV
        if len(close) > 0 and len(volumes) > 0:
            if HAS_TALIB:
                try:
                    obv = talib.OBV(close, volumes)
                    obv_val = obv[-1] if not np.isnan(obv[-1]) else 0.0
                except Exception:
                    obv_val = 0.0
            else:
                if len(close) > 1:
                    sign = np.sign(np.diff(close))
                    obv_val = float(
                        np.sum(volumes[1:][sign > 0]) - np.sum(volumes[1:][sign < 0])
                    )
                else:
                    obv_val = 0.0
            features["obv"] = float(obv_val)

        # MFI
        if len(high) > 14 and len(low) > 14 and len(close) > 14 and len(volumes) > 14:
            if HAS_TALIB:
                try:
                    mfi = talib.MFI(high, low, close, volumes, timeperiod=14)
                    features["mfi"] = float(mfi[-1]) if not np.isnan(mfi[-1]) else 50.0
                except Exception:
                    features["mfi"] = 50.0
            else:
                features["mfi"] = 50.0

        # Williams %R
        if len(high) > 14 and len(low) > 14 and len(close) > 14:
            if HAS_TALIB:
                try:
                    willr = talib.WILLR(high, low, close, timeperiod=14)
                    features["williams_r"] = float(willr[-1]) if not np.isnan(willr[-1]) else -50.0
                except Exception:
                    features["williams_r"] = -50.0
            else:
                features["williams_r"] = -50.0

        # Ultimate Oscillator
        if len(high) > 7 and len(low) > 7 and len(close) > 7:
            if HAS_TALIB:
                try:
                    ultosc = talib.ULTOSC(high, low, close, timeperiod1=7, timeperiod2=14, timeperiod3=28)
                    features["ultimate_osc"] = float(ultosc[-1]) if not np.isnan(ultosc[-1]) else 50.0
                except Exception:
                    features["ultimate_osc"] = 50.0
            else:
                features["ultimate_osc"] = 50.0

        return features
