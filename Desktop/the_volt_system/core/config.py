"""Model input contract.

Source of Truth for the model input order exported from Kaggle training and realtime Feature Store validation.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

# ---------------------------------------------------------
# 1. Base / Required Identity Columns
# ---------------------------------------------------------
BASE_IDENTIFIERS: List[str] = ["symbol", "timestamp"]

# ---------------------------------------------------------
# 2. Strategy Specific Feature Schemas
# ---------------------------------------------------------
MOMENTUM_FEATURES: List[str] = [
    "price", 
    "volume", 
    "rsi_14", 
    "macd", 
    "macd_signal", 
    "macd_hist"
]

MEAN_REVERSION_FEATURES: List[str] = [
    "price", 
    "volume", 
    "bb_upper", 
    "bb_lower", 
    "bb_mid", 
    "rsi_14"
]

# Provide a unified master list of all expected numeric features across strategies.
# Order here serves as the baseline REQUIRED_FEATURES for export alignment.
REQUIRED_FEATURES: List[str] = list(dict.fromkeys(MOMENTUM_FEATURES + MEAN_REVERSION_FEATURES))

# Example: {"price": "float64", "volume": "float64", ...}
REQUIRED_DTYPES: Dict[str, str] = {feat: "float64" for feat in REQUIRED_FEATURES}

# Global fallback when no per-feature fill value is provided.
DEFAULT_FILL_VALUE: float = 0.0

# Optional per-feature fill values (e.g. fill RSI with 50.0).
DEFAULT_FILL: Dict[str, Any] = {
    "rsi_14": 50.0,
    "volume": 0.0
}

# Optional scaler metadata copied from Kaggle for traceability.
SCALER_PARAMS: Dict[str, Any] = {}


def validate_contract() -> None:
    """Validate contract consistency between feature order and type mapping."""
    if not REQUIRED_FEATURES:
        raise ValueError(
            "REQUIRED_FEATURES is empty. Paste the Kaggle feature list into core/config.py."
        )

    missing_dtypes = [name for name in REQUIRED_FEATURES if name not in REQUIRED_DTYPES]
    if missing_dtypes:
        raise ValueError(
            "REQUIRED_DTYPES is missing entries for: " + ", ".join(missing_dtypes)
        )


def align_features(df: pd.DataFrame) -> pd.DataFrame:
    """Return a model-ready DataFrame in the exact training column order.

    - Adds missing required columns using DEFAULT_FILL/DEFAULT_FILL_VALUE.
    - Drops extra columns not present in REQUIRED_FEATURES.
    - Casts columns to REQUIRED_DTYPES when possible.
    """
    validate_contract()

    aligned = df.copy()

    for col in REQUIRED_FEATURES:
        if col not in aligned.columns:
            aligned[col] = DEFAULT_FILL.get(col, DEFAULT_FILL_VALUE)

    aligned = aligned[REQUIRED_FEATURES]

    for col in REQUIRED_FEATURES:
        fill_value = DEFAULT_FILL.get(col, DEFAULT_FILL_VALUE)
        aligned[col] = aligned[col].fillna(fill_value)
        target_dtype = REQUIRED_DTYPES[col]
        try:
            aligned[col] = aligned[col].astype(target_dtype)
        except Exception as exc:
            raise TypeError(f"Failed to cast '{col}' to '{target_dtype}': {exc}") from exc

    return aligned
