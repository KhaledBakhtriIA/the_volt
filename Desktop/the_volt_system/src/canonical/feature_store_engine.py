from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from core.contract import BASE_IDENTIFIERS, REQUIRED_FEATURES

MARKET_HOURS = {
    "stock": ("09:30", "16:00", "America/New_York"),
    "crypto": None,
}


@dataclass
class FeatureStoreConfig:
    """Configuration for real-time feature processing and quality checks."""

    required_columns: List[str] = field(default_factory=lambda: BASE_IDENTIFIERS + REQUIRED_FEATURES)
    numeric_columns: List[str] = field(default_factory=lambda: REQUIRED_FEATURES)
    max_missing_ratio: float = 0.20
    max_duplicate_ratio: float = 0.10
    max_outlier_ratio: float = 0.15
    outlier_z_threshold: float = 4.0
    history_limit: int = 5000
    persist_offline: bool = False
    offline_store_path: str = "data_api/data/refined"
    latest_cache_rows: int = 500


@dataclass
class QualityReport:
    """Structured quality report returned for each processed batch."""

    total_rows: int
    rows_after_cleaning: int
    missing_ratio: float
    duplicate_ratio: float
    outlier_ratio: float
    schema_valid: bool
    passed: bool
    issues: List[str]

    def as_dict(self) -> Dict[str, object]:
        return {
            "total_rows": self.total_rows,
            "rows_after_cleaning": self.rows_after_cleaning,
            "missing_ratio": round(self.missing_ratio, 6),
            "duplicate_ratio": round(self.duplicate_ratio, 6),
            "outlier_ratio": round(self.outlier_ratio, 6),
            "schema_valid": self.schema_valid,
            "passed": self.passed,
            "issues": self.issues,
        }


class DataQualityError(ValueError):
    """Raised when strict quality validation fails."""


class FeatureStoreEngine:
    """Autonomous feature-store engine for real-time preprocessing and validation."""

    def __init__(self, config: FeatureStoreConfig | None = None) -> None:
        self.config = config or FeatureStoreConfig()
        self._latest_cache: Dict[str, pd.DataFrame] = {}

    def _validate_schema(self, df: pd.DataFrame) -> Tuple[bool, List[str]]:
        missing = [col for col in self.config.required_columns if col not in df.columns]
        if missing:
            return False, [f"missing_required_columns:{','.join(missing)}"]
        return True, []

    def _coerce_types(self, df: pd.DataFrame) -> pd.DataFrame:
        work = df.copy()
        if "timestamp" in work.columns:
            work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce", utc=True)

        for col in self.config.numeric_columns:
            if col in work.columns:
                work[col] = pd.to_numeric(work[col], errors="coerce")

        for col in ("open", "high", "low", "close", "volume"):
            if col in work.columns:
                work[col] = pd.to_numeric(work[col], errors="coerce")

        return work

    def _detect_outlier_ratio(self, df: pd.DataFrame) -> float:
        present_numeric = [c for c in self.config.numeric_columns if c in df.columns]
        if not present_numeric or df.empty:
            return 0.0

        num = df[present_numeric]
        means = num.mean()
        stds = num.std(ddof=0).replace(0, np.nan)
        z = ((num - means) / stds).abs()
        outlier_mask = (z > self.config.outlier_z_threshold).any(axis=1).fillna(False)
        return float(outlier_mask.mean()) if len(outlier_mask) else 0.0

    @staticmethod
    def _decimal_places(value: object) -> int:
        try:
            exponent = Decimal(str(value)).as_tuple().exponent
        except (InvalidOperation, ValueError, TypeError):
            return 0
        return int(-exponent) if exponent < 0 else 0

    def _validate_financial_domain(self, df: pd.DataFrame, asset_type: str) -> List[str]:
        issues: List[str] = []
        if "symbol" not in df.columns:
            return issues

        for symbol, group in df.groupby("symbol", dropna=True):
            symbol_name = str(symbol)
            ordered = group.copy()
            if "timestamp" in ordered.columns:
                ordered = ordered.sort_values("timestamp")

            if {"close", "volume"}.issubset(ordered.columns):
                close_series = ordered["close"]
                volume_series = ordered["volume"]
                same_close = close_series.eq(close_series.shift())
                run_id = close_series.ne(close_series.shift()).cumsum()
                run_len = close_series.groupby(run_id).transform("size")
                run_min_volume = volume_series.groupby(run_id).transform("min")
                stale_mask = same_close & (run_len >= 10) & (run_min_volume > 1000)
                if stale_mask.any():
                    issues.append(f"STALE_FEED:{symbol_name}")

            price_cols = [col for col in ("open", "high", "low", "close") if col in ordered.columns]
            if price_cols:
                has_non_positive = False
                for col in price_cols:
                    values = pd.to_numeric(ordered[col], errors="coerce").dropna()
                    if values.empty:
                        continue
                    if (values <= 0).any():
                        has_non_positive = True
                    if asset_type == "stock":
                        if any(self._decimal_places(v) > 6 for v in values.tolist()):
                            issues.append(f"PRECISION_VIOLATION:{symbol_name}:{col}")
                if has_non_positive:
                    issues.append(f"ZERO_OR_NEGATIVE_PRICE:{symbol_name}")

            if asset_type == "stock" and "timestamp" in ordered.columns:
                market_cfg = MARKET_HOURS.get("stock")
                if market_cfg is not None:
                    open_str, close_str, tz_name = market_cfg
                    local_ts = ordered["timestamp"].dropna()
                    if not local_ts.empty:
                        local_ts = local_ts.dt.tz_convert(tz_name)
                        frame = pd.DataFrame({"local_ts": local_ts}).sort_values("local_ts")
                        frame["date"] = frame["local_ts"].dt.date

                        try:
                            import pandas_market_calendars as mcal  # type: ignore

                            nyse = mcal.get_calendar("NYSE")
                            schedule = nyse.valid_days(
                                start_date=frame["local_ts"].min().date(),
                                end_date=frame["local_ts"].max().date(),
                            )
                            valid_days = set(pd.to_datetime(schedule).date)
                        except Exception:
                            valid_days = set(d for d in frame["date"] if pd.Timestamp(d).weekday() < 5)

                        start_time = pd.to_datetime(open_str).time()
                        end_time = pd.to_datetime(close_str).time()

                        market_frame = frame[frame["date"].isin(valid_days)]
                        market_frame = market_frame[
                            (market_frame["local_ts"].dt.time >= start_time)
                            & (market_frame["local_ts"].dt.time <= end_time)
                        ]

                        if len(market_frame) >= 2:
                            gaps = market_frame["local_ts"].diff().dt.total_seconds().div(60.0)
                            large_gaps = gaps[gaps > 5.0].dropna()
                            for gap in large_gaps.tolist():
                                issues.append(f"MARKET_HOUR_GAP:{symbol_name}:{int(round(float(gap)))}min")

        return issues

    def _clean(self, df: pd.DataFrame) -> pd.DataFrame:
        work = df.copy()
        work = work.drop_duplicates().reset_index(drop=True)

        for col in work.columns:
            if work[col].isna().any():
                if pd.api.types.is_numeric_dtype(work[col]):
                    work[col] = work[col].fillna(work[col].median())
                else:
                    mode_vals = work[col].mode(dropna=True)
                    fallback = mode_vals.iloc[0] if not mode_vals.empty else "unknown"
                    work[col] = work[col].fillna(fallback)

        for col in self.config.numeric_columns:
            if col in work.columns and not work[col].empty:
                low = work[col].quantile(0.01)
                high = work[col].quantile(0.99)
                work[col] = work[col].clip(lower=low, upper=high)

        if "timestamp" in work.columns:
            work = work.dropna(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)

        return work

    def _quality_report(
        self,
        raw_df: pd.DataFrame,
        cleaned_df: pd.DataFrame,
        schema_valid: bool,
        schema_issues: List[str],
        financial_issues: List[str],
        outlier_ratio: float,
    ) -> QualityReport:
        total_cells = max(raw_df.shape[0] * max(raw_df.shape[1], 1), 1)
        missing_ratio = float(raw_df.isna().sum().sum() / total_cells) if not raw_df.empty else 0.0
        duplicate_ratio = float(raw_df.duplicated().mean()) if not raw_df.empty else 0.0

        issues = list(schema_issues)
        issues.extend(financial_issues)
        if missing_ratio > self.config.max_missing_ratio:
            issues.append("missing_ratio_above_threshold")
        if duplicate_ratio > self.config.max_duplicate_ratio:
            issues.append("duplicate_ratio_above_threshold")
        if outlier_ratio > self.config.max_outlier_ratio:
            issues.append("outlier_ratio_above_threshold")

        passed = schema_valid and not issues
        return QualityReport(
            total_rows=len(raw_df),
            rows_after_cleaning=len(cleaned_df),
            missing_ratio=missing_ratio,
            duplicate_ratio=duplicate_ratio,
            outlier_ratio=outlier_ratio,
            schema_valid=schema_valid,
            passed=passed,
            issues=issues,
        )

    def _persist_offline(self, dataset: str, df: pd.DataFrame, report: QualityReport) -> None:
        base_path = Path(self.config.offline_store_path) / dataset
        base_path.mkdir(parents=True, exist_ok=True)

        timestamp = pd.Timestamp.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        parquet_path = base_path / f"batch_{timestamp}.parquet"
        parquet_tmp_path = Path(str(parquet_path) + ".tmp")
        df.to_parquet(parquet_tmp_path, index=False, compression="snappy")
        os.replace(parquet_tmp_path, parquet_path)

        json_path = base_path / f"{dataset}_{timestamp}_meta.json"
        json_tmp_path = Path(str(json_path) + ".tmp")
        metadata = {
            "timestamp": timestamp,
            "dataset": dataset,
            "data_file": parquet_path.name,
            "report": report.as_dict(),
        }
        with open(json_tmp_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        os.replace(json_tmp_path, json_path)

    def _update_latest_cache(self, dataset: str, cleaned_df: pd.DataFrame) -> None:
        existing = self._latest_cache.get(dataset)
        if existing is None or existing.empty:
            combined = cleaned_df.copy()
        else:
            combined = pd.concat([existing, cleaned_df], ignore_index=True)
        self._latest_cache[dataset] = combined.tail(self.config.latest_cache_rows).reset_index(drop=True)

    def load_history(self, dataset_name: str, max_rows: int = 500000) -> pd.DataFrame:
        dataset_dir = Path(self.config.offline_store_path) / dataset_name
        if not dataset_dir.exists():
            return pd.DataFrame()

        parquet_files = sorted(dataset_dir.glob("batch_*.parquet"))
        if not parquet_files:
            return pd.DataFrame()

        collected: List[pd.DataFrame] = []
        rows_accum = 0
        for file_path in reversed(parquet_files):
            chunk = pd.read_parquet(file_path)
            if chunk.empty:
                continue
            remaining = max_rows - rows_accum
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                chunk = chunk.tail(remaining)
            collected.append(chunk)
            rows_accum += len(chunk)
            if rows_accum >= max_rows:
                break

        if not collected:
            return pd.DataFrame()

        combined = pd.concat(reversed(collected), ignore_index=True)
        return combined.tail(max_rows).reset_index(drop=True)

    def process(
        self,
        df: pd.DataFrame,
        dataset: str = "realtime",
        strict: bool = False,
        asset_type: str = "crypto",
    ) -> Tuple[pd.DataFrame, QualityReport]:
        """Validate, clean, and store a batch before orchestration consumes it."""
        if df is None:
            raise DataQualityError("input_dataframe_is_none")

        coerced = self._coerce_types(df)
        schema_valid, schema_issues = self._validate_schema(coerced)
        financial_issues = self._validate_financial_domain(coerced, asset_type=asset_type)
        outlier_ratio = self._detect_outlier_ratio(coerced)
        cleaned = self._clean(coerced)
        report = self._quality_report(
            coerced,
            cleaned,
            schema_valid,
            schema_issues,
            financial_issues,
            outlier_ratio,
        )

        if strict and report.issues:
            raise DataQualityError(f"quality_validation_failed:{';'.join(report.issues)}")

        self._update_latest_cache(dataset, cleaned)
        self._persist_offline(dataset, cleaned, report)
        return cleaned, report

    def latest(self, dataset: str = "realtime") -> pd.DataFrame:
        """Return the latest processed frame for a dataset."""
        if dataset not in self._latest_cache:
            return pd.DataFrame()
        return self._latest_cache[dataset].copy(deep=True)
