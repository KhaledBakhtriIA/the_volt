"""
Predictive Model Classes
========================
Extracted from notebook Phase 8 (cells 585-592).
Provides a base ``PredictiveModel`` class and six specialised subclasses:

- MeanReversionModel   — RandomForestRegressor
- VolatilityModel      — GradientBoostingRegressor
- SentimentModel       — MLPRegressor
- MacroModel           — Ridge regression
- RiskModel            — RandomForestRegressor (risk-tuned)
- ExecutionModel       — LinearRegression (slippage estimation)
- MomentumModel        — XGBoost (inline, requires xgboost)

Each subclass inherits ``train`` / ``predict`` / ``get_performance_stats``
from the base class and only overrides ``__init__`` and ``_fallback_prediction``.
"""

import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

try:
    import xgboost as xgb
    HAS_XGB = True
except ImportError:
    xgb = None  # type: ignore[assignment]
    HAS_XGB = False


# ============================================================================
# BASE CLASS
# ============================================================================

class PredictiveModel:
    """Base class for all predictive trading models.

    Subclasses must set ``self.model`` to a scikit-learn–style estimator in
    their ``__init__`` (or override ``_fallback_prediction`` for untrained
    behaviour).
    """

    def __init__(self, name: str, model_type: str, feature_importance: dict | None = None):
        self.name = name
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.feature_importance: dict = feature_importance or {}
        self.performance_history: list[dict] = []
        self.training_samples = 0

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, X: np.ndarray, y: np.ndarray, sample_weight: np.ndarray | None = None) -> bool:
        """Fit the model; returns ``True`` on success."""
        if len(X) < 10:
            return False

        X_scaled = self.scaler.fit_transform(X)

        if sample_weight is not None:
            try:
                self.model.fit(X_scaled, y, sample_weight=sample_weight)
            except TypeError:
                self.model.fit(X_scaled, y)
        else:
            self.model.fit(X_scaled, y)

        try:
            train_score = self.model.score(X_scaled, y)
        except Exception:
            train_score = 0.0

        self.performance_history.append(
            {"timestamp": pd.Timestamp.now(), "score": train_score, "samples": len(X)}
        )
        self.training_samples += len(X)
        return True

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def predict(self, X: np.ndarray) -> tuple[float, float]:
        """Return ``(prediction, confidence)``."""
        if self.model is None or X is None or len(X) == 0:
            return self._fallback_prediction(X), 0.1

        try:
            X_scaled = self.scaler.transform(X)
            pred = self.model.predict(X_scaled)
            prediction = float(pred[0]) if hasattr(pred, "__len__") else float(pred)

            sample_confidence = min(0.9, self.training_samples / 1_000.0)

            if self.performance_history:
                perf_confidence = (
                    np.mean([p["score"] for p in self.performance_history[-5:]]) * 2.0
                )
            else:
                perf_confidence = 0.5

            magnitude_confidence = min(0.8, abs(prediction) * 10.0)

            confidence = float(
                np.clip(
                    sample_confidence * 0.3 + perf_confidence * 0.4 + magnitude_confidence * 0.3,
                    0.0,
                    1.0,
                )
            )
            return prediction, confidence

        except Exception:
            return self._fallback_prediction(X), 0.1

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fallback_prediction(self, X) -> float:  # noqa: ANN001
        """Override in subclasses for domain-specific untrained behaviour."""
        return 0.0

    def get_feature_importance(self) -> dict:
        return self.feature_importance

    def get_performance_stats(self) -> dict:
        if not self.performance_history:
            return {}
        scores = [p["score"] for p in self.performance_history]
        return {
            "avg_score": float(np.mean(scores)),
            "std_score": float(np.std(scores)),
            "latest_score": float(scores[-1]),
            "training_samples": int(self.training_samples),
            "model_type": self.model_type,
        }


# ============================================================================
# SPECIALISED SUBCLASSES
# ============================================================================

class MomentumModel(PredictiveModel):
    """XGBoost-backed momentum model.

    Falls back to a simple trend-following heuristic when untrained or when
    XGBoost is not installed.
    """

    def __init__(self, name: str):
        super().__init__(name, "momentum")
        if HAS_XGB:
            self.model = xgb.XGBRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbosity=0,
            )
        else:
            # Graceful degradation: use GBR when xgboost unavailable
            self.model = GradientBoostingRegressor(
                n_estimators=100, max_depth=5, learning_rate=0.05
            )

    def _fallback_prediction(self, X) -> float:
        if X is None or len(X) == 0:
            return 0.0
        try:
            prices = X[:, 0] if hasattr(X, "ndim") and X.ndim > 1 else np.array(X).flatten()
        except Exception:
            prices = np.array(X).flatten()
        if len(prices) > 10:
            returns = np.diff(prices[-10:]) / (prices[-11:-1] + 1e-12)
            momentum = np.mean(returns)
            return float(momentum * 100.0)
        return 0.0


class MeanReversionModel(PredictiveModel):
    """Random-forest mean-reversion model."""

    def __init__(self, name: str):
        super().__init__(name, "mean_reversion")
        self.model = RandomForestRegressor(
            n_estimators=100, max_depth=7, min_samples_split=10, random_state=42
        )

    def _fallback_prediction(self, X) -> float:
        if X is None or len(X) == 0:
            return 0.0
        try:
            prices = X[:, 0] if hasattr(X, "ndim") and X.ndim > 1 else np.array(X).flatten()
        except Exception:
            prices = np.array(X).flatten()
        if len(prices) > 50:
            mean = np.mean(prices[-50:])
            std = np.std(prices[-50:])
            zscore = (prices[-1] - mean) / (std + 1e-6)
            return float(-zscore * 0.1)
        return 0.0


class VolatilityModel(PredictiveModel):
    """Gradient-boosting volatility-forecast model."""

    def __init__(self, name: str):
        super().__init__(name, "volatility")
        self.model = GradientBoostingRegressor(
            n_estimators=80, max_depth=4, learning_rate=0.05
        )

    def _fallback_prediction(self, X) -> float:
        if X is None or len(X) == 0:
            return 0.02
        try:
            prices = X[:, 0] if hasattr(X, "ndim") and X.ndim > 1 else np.array(X).flatten()
        except Exception:
            prices = np.array(X).flatten()
        if len(prices) > 10:
            returns = np.diff(prices) / (prices[:-1] + 1e-12)
            vol = np.std(returns[-10:]) * np.sqrt(252)
            return float(min(max(vol, 0.1), 0.5))
        return 0.02


class SentimentModel(PredictiveModel):
    """MLP-based sentiment proxy model."""

    def __init__(self, name: str):
        super().__init__(name, "sentiment")
        self.model = MLPRegressor(
            hidden_layer_sizes=(50, 25), activation="relu", max_iter=500, random_state=42
        )
        self._sentiment_memory: list[float] = []

    def _fallback_prediction(self, X) -> float:
        if not self._sentiment_memory:
            self._sentiment_memory.append(np.random.uniform(-0.1, 0.1))
        last = self._sentiment_memory[-1]
        new = last * 0.8 + np.random.uniform(-0.05, 0.05)
        self._sentiment_memory.append(new)
        if len(self._sentiment_memory) > 100:
            self._sentiment_memory.pop(0)
        return float(new * 2.0)


class MacroModel(PredictiveModel):
    """Ridge-regression macro/trend model."""

    def __init__(self, name: str):
        super().__init__(name, "macro")
        self.model = Ridge(alpha=1.0)
        self._trend_memory: list[float] = []

    def _fallback_prediction(self, X) -> float:
        if X is None or len(X) == 0:
            return 0.0
        try:
            prices = X[:, 0] if hasattr(X, "ndim") and X.ndim > 1 else np.array(X).flatten()
        except Exception:
            prices = np.array(X).flatten()
        if len(prices) > 50:
            x_idx = np.arange(len(prices[-50:]))
            y = np.array(prices[-50:])
            slope, _ = np.polyfit(x_idx, y, 1)
            trend_strength = slope / (np.mean(y) + 1e-6)
            self._trend_memory.append(trend_strength)
            if len(self._trend_memory) > 20:
                self._trend_memory.pop(0)
            smoothed = np.mean(self._trend_memory[-5:]) if self._trend_memory else trend_strength
            return float(smoothed * 100.0)
        return 0.0


class RiskModel(PredictiveModel):
    """Random-forest risk/volatility-forecast model."""

    def __init__(self, name: str):
        super().__init__(name, "risk")
        self.model = RandomForestRegressor(
            n_estimators=60, max_depth=5, min_samples_split=15
        )

    def _fallback_prediction(self, X) -> float:
        if X is None or len(X) == 0:
            return 0.03
        try:
            prices = X[:, 0] if hasattr(X, "ndim") and X.ndim > 1 else np.array(X).flatten()
        except Exception:
            prices = np.array(X).flatten()
        if len(prices) > 20:
            returns = np.diff(prices) / (prices[:-1] + 1e-12)
            recent_vol = np.std(returns[-5:]) * np.sqrt(252)
            older_vol = np.std(returns[-20:-10]) * np.sqrt(252) if len(returns) > 10 else recent_vol
            predicted_vol = recent_vol * 0.7 + older_vol * 0.3
            return float(min(max(predicted_vol, 0.15), 0.6))
        return 0.03


class ExecutionModel(PredictiveModel):
    """Linear regression model for execution cost / slippage estimation."""

    def __init__(self, name: str):
        super().__init__(name, "execution")
        self.model = LinearRegression()

    def _fallback_prediction(self, X) -> float:
        base_slippage = 0.001  # 10 basis points
        if X is not None and len(X) > 0:
            try:
                prices = X[:, 0] if hasattr(X, "ndim") and X.ndim > 1 else np.array(X).flatten()
            except Exception:
                prices = np.array(X).flatten()
            if len(prices) > 10:
                vol = np.std(
                    np.diff(prices[-10:]) / (prices[-11:-1] + 1e-12)
                ) * np.sqrt(252)
                return float(base_slippage + vol * 0.002)
        return float(base_slippage)


# ============================================================================
# Registry helper
# ============================================================================

MODEL_REGISTRY: dict[str, type] = {
    "momentum": MomentumModel,
    "mean_reversion": MeanReversionModel,
    "volatility": VolatilityModel,
    "sentiment": SentimentModel,
    "macro": MacroModel,
    "risk": RiskModel,
    "execution": ExecutionModel,
}

__all__ = [
    "PredictiveModel",
    "MomentumModel",
    "MeanReversionModel",
    "VolatilityModel",
    "SentimentModel",
    "MacroModel",
    "RiskModel",
    "ExecutionModel",
    "MODEL_REGISTRY",
]
