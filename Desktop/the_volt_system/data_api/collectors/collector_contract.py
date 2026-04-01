from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import pandas as pd

# Minimum cross-collector contract. Additional domain columns are allowed.
REQUIRED_COLLECTOR_COLUMNS = ("timestamp", "source", "fetched_at_utc")


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp string."""
    return datetime.now(timezone.utc).isoformat()


def ensure_collector_contract(df: pd.DataFrame, source: str, timestamp_col: str = "timestamp") -> pd.DataFrame:
    """Normalize collector output to the minimum shared schema.

    The hybrid pipeline assumes every collector can be represented as a DataFrame
    with at least: timestamp, source, fetched_at_utc.

    Args:
        df: Raw collector DataFrame.
        source: Source name to stamp when the column is missing.
        timestamp_col: Name of source timestamp column if not already `timestamp`.

    Returns:
        DataFrame with normalized required columns.
    """
    if df.empty:
        return pd.DataFrame(columns=list(REQUIRED_COLLECTOR_COLUMNS))

    out = df.copy()

    if timestamp_col != "timestamp" and timestamp_col in out.columns and "timestamp" not in out.columns:
        out = out.rename(columns={timestamp_col: "timestamp"})

    if "timestamp" in out.columns:
        out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
        out = out.dropna(subset=["timestamp"]) 
    else:
        out["timestamp"] = pd.NaT

    if "source" not in out.columns:
        out["source"] = source
    else:
        out["source"] = out["source"].fillna(source)

    if "fetched_at_utc" not in out.columns:
        out["fetched_at_utc"] = utc_now_iso()
    else:
        out["fetched_at_utc"] = out["fetched_at_utc"].fillna(utc_now_iso())

    return out.reset_index(drop=True)


def has_required_columns(columns: Iterable[str]) -> bool:
    """Return True when all required cross-collector columns are present."""
    available = set(columns)
    return all(name in available for name in REQUIRED_COLLECTOR_COLUMNS)
