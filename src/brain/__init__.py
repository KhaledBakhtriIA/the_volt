from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

import pandas as pd
import xgboost as xgb

from .features import add_3sigma_target, calculate_atr, calculate_std
from .models import xgboost_dispatcher


@dataclass(frozen=True)
class BrainTargetConfig:
    """Contract for breakout target and volatility feature parameters."""

    std_window: int = 20
    atr_window: int = 14
    horizon: int = 4


@dataclass(frozen=True)
class BrainTrainingConfig:
    """Contract for model split and optional XGBoost hyperparameters."""

    train_size: float = 0.8
    xgb_params: Optional[Dict[str, Any]] = None


def build_brain_frame(df: pd.DataFrame, config: BrainTargetConfig) -> pd.DataFrame:
    """
    Build a pure training frame with volatility features and 3-sigma breakout target.

    Expected input columns: high, low, close.
    """
    out = add_3sigma_target(df=df, std_window=config.std_window, horizon=config.horizon)
    out["atr"] = calculate_atr(out, window=config.atr_window)
    out["std"] = calculate_std(out, window=config.std_window, column="close")
    return out


def train_breakout_dispatcher(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    target_column: str,
    training: BrainTrainingConfig,
) -> Tuple[xgb.Booster, pd.Series]:
    """
    Train and dispatch breakout probabilities using the package-level model contract.
    """
    model_frame = frame.dropna(subset=[target_column]).copy()
    X = model_frame.loc[:, list(feature_columns)]
    y = model_frame.loc[:, target_column].astype(int)
    return xgboost_dispatcher(
        X=X,
        y=y,
        train_size=training.train_size,
        params=training.xgb_params,
    )


__all__ = [
    "BrainTargetConfig",
    "BrainTrainingConfig",
    "build_brain_frame",
    "train_breakout_dispatcher",
    "calculate_std",
    "calculate_atr",
    "add_3sigma_target",
    "xgboost_dispatcher",
]
