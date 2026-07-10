"""Compatibility module for model feature contract.

Import from this file when prompts or code expect `core/contract.py`.
"""

from data_layer.schemas.config import (
    BASE_IDENTIFIERS,
    MOMENTUM_FEATURES,
    MEAN_REVERSION_FEATURES,
    DEFAULT_FILL,
    DEFAULT_FILL_VALUE,
    REQUIRED_DTYPES,
    REQUIRED_FEATURES,
    SCALER_PARAMS,
    align_features,
    validate_contract,
)

__all__ = [
    "BASE_IDENTIFIERS",
    "MOMENTUM_FEATURES",
    "MEAN_REVERSION_FEATURES",
    "REQUIRED_FEATURES",
    "REQUIRED_DTYPES",
    "DEFAULT_FILL_VALUE",
    "DEFAULT_FILL",
    "SCALER_PARAMS",
    "validate_contract",
    "align_features",
]
