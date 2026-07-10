"""
Meta-Controller
===============
Extracted from notebook Phase 8 (cell 594).
Provides the ``MetaController`` class with:

- Market regime detection (5 regimes: trend_up, trend_down, high_vol, low_vol, choppy)
- Online performance tracking per model via exponential moving average
- Regime-aware, confidence-weighted prediction combination
- 144-model weight vector updated each inference step
"""

import numpy as np


# ============================================================================
# META-CONTROLLER
# ============================================================================

class MetaController:
    """Intelligently combine signals from N predictive models.

    Parameters
    ----------
    n_models : int
        Number of models to manage (default 144 to match notebook).
    """

    REGIMES = ("trend_up", "trend_down", "high_vol", "low_vol", "choppy")

    def __init__(self, n_models: int = 144):
        self.n_models = n_models
        self.model_weights = np.ones(n_models) / n_models
        self.model_performance = np.ones(n_models) * 0.5
        self.model_consistency = np.ones(n_models)
        self.regime_weights: dict[str, np.ndarray] = {
            r: np.ones(n_models) / n_models for r in self.REGIMES
        }
        self.performance_history: list[dict] = []

    # ------------------------------------------------------------------
    # Regime detection
    # ------------------------------------------------------------------

    def detect_regime(self, features: dict | np.ndarray) -> str:
        """Classify the current market regime from a feature dict or array.

        When *features* is a dict, the keys ``realized_vol_20d``,
        ``return_20d``, ``rsi_14``, and ``adx`` are used (all optional,
        sensible defaults are applied for missing keys).
        """
        if isinstance(features, dict):
            volatility = features.get("realized_vol_20d", 0.2)
            trend = features.get("return_20d", 0.0)
            adx = features.get("adx", 25.0)
        else:
            volatility = 0.2
            trend = 0.0
            adx = 25.0

        if volatility > 0.3:
            return "high_vol"
        elif volatility < 0.1:
            return "low_vol"
        elif trend > 0.05 and adx > 30:
            return "trend_up"
        elif trend < -0.05 and adx > 30:
            return "trend_down"
        else:
            return "choppy"

    # ------------------------------------------------------------------
    # Performance tracking
    # ------------------------------------------------------------------

    def update_model_performance(
        self,
        model_id: int,
        actual_return: float,
        predicted_signal: float | None,
        confidence: float,
    ) -> None:
        """Online update of the performance EMA for *model_id*."""
        if predicted_signal is None:
            return

        direction_correct = 1 if np.sign(actual_return) == np.sign(predicted_signal) else 0
        magnitude_error = abs(abs(actual_return) - abs(predicted_signal))

        performance_score = direction_correct * 0.6 + (1 - min(magnitude_error, 1)) * 0.4

        alpha = 0.1
        self.model_performance[model_id] = (
            alpha * performance_score + (1 - alpha) * self.model_performance[model_id]
        )

        recent = (
            self.performance_history[-10:]
            if len(self.performance_history) > 10
            else self.performance_history
        )
        if recent:
            try:
                consistency = 1 - np.std(
                    [
                        p["performance"][model_id]
                        for p in recent
                        if model_id in p.get("performance", {})
                    ]
                )
                self.model_consistency[model_id] = float(np.clip(consistency, 0.0, 1.0))
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Weight calculation
    # ------------------------------------------------------------------

    def calculate_weights(
        self,
        current_regime: str,
        model_predictions: list[float],
        model_confidences: list[float],
    ) -> np.ndarray:
        """Return a normalised weight vector (shape = n_models) for the
        current regime and model predictions/confidences."""
        n = len(model_predictions)
        base_weights = np.ones(n) / n

        perf_weights = self.model_performance[:n].copy()
        perf_weights /= perf_weights.sum() + 1e-6

        conf_weights = np.array(model_confidences, dtype=float)
        conf_weights /= conf_weights.sum() + 1e-6

        regime_weights = self.regime_weights.get(current_regime, base_weights)[:n].copy()
        regime_weights /= regime_weights.sum() + 1e-6

        consistency_weights = self.model_consistency[:n].copy()
        consistency_weights /= consistency_weights.sum() + 1e-6

        combined = (
            base_weights * 0.1
            + perf_weights * 0.3
            + conf_weights * 0.2
            + regime_weights * 0.3
            + consistency_weights * 0.1
        )
        combined /= combined.sum() + 1e-6
        self.model_weights[:n] = combined
        return combined

    # ------------------------------------------------------------------
    # Signal combination
    # ------------------------------------------------------------------

    def combine_predictions(
        self,
        model_predictions: list[float],
        model_confidences: list[float],
        current_regime: str,
    ) -> tuple[float, float, dict]:
        """Weighted average combination of model signals.

        Returns
        -------
        (weighted_prediction, weighted_confidence, meta_info_dict)
        """
        if not model_predictions:
            return 0.0, 0.0, {}

        weights = self.calculate_weights(current_regime, model_predictions, model_confidences)

        weighted_prediction = float(np.average(model_predictions, weights=weights))
        weighted_confidence = float(np.average(model_confidences, weights=weights))

        positive_votes = sum(1 for p in model_predictions if p > 0)
        negative_votes = sum(1 for p in model_predictions if p < 0)
        consensus_ratio = max(positive_votes, negative_votes) / len(model_predictions)

        signal_strength = min(abs(weighted_prediction) * 10.0, 1.0)

        return weighted_prediction, weighted_confidence, {
            "weights": weights.tolist(),
            "consensus_ratio": float(consensus_ratio),
            "signal_strength": float(signal_strength),
            "regime": current_regime,
            "positive_votes": int(positive_votes),
            "negative_votes": int(negative_votes),
            "n_models": len(model_predictions),
        }
