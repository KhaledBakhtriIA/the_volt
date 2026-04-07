from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Dict, List

import pandas as pd

from data_api.collectors.collector_contract import ensure_collector_contract

logger = logging.getLogger(__name__)


class MacroCollector:
    """Collect macroeconomic time series from FRED."""

    def __init__(self, fred_api_key: str = "") -> None:
        self.fred_api_key = fred_api_key

    def _fetch_with_fredapi(self, series_id: str) -> pd.DataFrame:
        try:
            from fredapi import Fred  # type: ignore
        except Exception:
            return pd.DataFrame()

        if not self.fred_api_key:
            return pd.DataFrame()

        try:
            fred = Fred(api_key=self.fred_api_key)
            series = fred.get_series(series_id)
            if series is None or len(series) == 0:
                return pd.DataFrame()
            df = series.reset_index()
            df.columns = ["timestamp", "value"]
            return df
        except Exception as exc:
            logger.warning("FRED API fetch failed for %s via fredapi: %s", series_id, exc)
            return pd.DataFrame()

    def _fetch_with_requests(self, series_id: str) -> pd.DataFrame:
        if not self.fred_api_key:
            return pd.DataFrame()

        try:
            import requests
        except Exception:
            return pd.DataFrame()

        try:
            response = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self.fred_api_key,
                    "file_type": "json",
                },
                timeout=20,
            )
            if response.status_code != 200:
                return pd.DataFrame()
            payload = response.json()
            observations = payload.get("observations", [])
            rows: List[dict] = []
            for obs in observations:
                value = obs.get("value")
                if value in (None, "."):
                    continue
                rows.append({"timestamp": obs.get("date"), "value": float(value)})
            return pd.DataFrame(rows)
        except Exception as exc:
            logger.warning("FRED API fetch failed for %s via requests: %s", series_id, exc)
            return pd.DataFrame()

    def fetch(self, series_map: Dict[str, str]) -> pd.DataFrame:
        """Fetch one or more named FRED series IDs."""
        if not series_map:
            return pd.DataFrame(columns=["timestamp", "source", "fetched_at_utc"])

        rows: List[pd.DataFrame] = []
        for alias, series_id in series_map.items():
            series_df = self._fetch_with_fredapi(series_id)
            if series_df.empty:
                series_df = self._fetch_with_requests(series_id)
            if series_df.empty:
                continue

            series_df["series_alias"] = alias
            series_df["series_id"] = series_id
            series_df["source"] = "fred"
            series_df["fetched_at_utc"] = datetime.now(timezone.utc).isoformat()
            rows.append(series_df)

        if not rows:
            return pd.DataFrame(columns=["timestamp", "source", "fetched_at_utc"])

        result = pd.concat(rows, ignore_index=True)
        result = ensure_collector_contract(result, source="fred", timestamp_col="timestamp")
        if "value" in result.columns:
            result["value"] = pd.to_numeric(result["value"], errors="coerce")
        result = result.dropna(subset=["value"]) if "value" in result.columns else result
        return result.sort_values(["series_alias", "timestamp"], ascending=[True, False]).reset_index(drop=True)
