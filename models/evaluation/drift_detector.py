from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp


class DriftDetector:
    """Detect feature drift against a persisted numeric baseline."""

    def __init__(self, reference_stats_path: str):
        self.reference_stats_path = Path(reference_stats_path)
        self.reference: Dict[str, Dict[str, object]] = {}
        if self.reference_stats_path.exists():
            with open(self.reference_stats_path, "r", encoding="utf-8") as f:
                self.reference = json.load(f)

    @property
    def has_reference(self) -> bool:
        return bool(self.reference)

    def save_reference(self, df: pd.DataFrame, path: str) -> None:
        numeric_df = df.select_dtypes(include=[np.number])
        baseline: Dict[str, Dict[str, object]] = {}
        for col in numeric_df.columns:
            values = numeric_df[col].dropna().to_numpy(dtype=float)
            if values.size == 0:
                continue
            counts, edges = np.histogram(values, bins=20)
            histogram: List[Dict[str, float]] = []
            for idx, count in enumerate(counts.tolist()):
                histogram.append(
                    {
                        "left": float(edges[idx]),
                        "right": float(edges[idx + 1]),
                        "count": int(count),
                    }
                )
            baseline[col] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values, ddof=0)),
                "histogram": histogram,
            }

        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = Path(str(out_path) + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(baseline, f, indent=2)
        os.replace(tmp_path, out_path)

        self.reference_stats_path = out_path
        self.reference = baseline

    @staticmethod
    def _reconstruct_reference_samples(histogram: List[Dict[str, float]]) -> np.ndarray:
        if not histogram:
            return np.array([], dtype=float)
        values: List[float] = []
        for bucket in histogram:
            left = float(bucket["left"])
            right = float(bucket["right"])
            count = int(bucket["count"])
            if count <= 0:
                continue
            midpoint = (left + right) / 2.0
            values.extend(np.repeat(midpoint, count).tolist())
        return np.array(values, dtype=float)

    @staticmethod
    def _psi(expected_counts: np.ndarray, actual_counts: np.ndarray) -> float:
        eps = 1e-6
        expected_pct = expected_counts / max(expected_counts.sum(), 1)
        actual_pct = actual_counts / max(actual_counts.sum(), 1)
        psi_values = (actual_pct - expected_pct) * np.log((actual_pct + eps) / (expected_pct + eps))
        return float(np.sum(psi_values))

    def detect(self, df: pd.DataFrame) -> Dict[str, Dict[str, float | bool]]:
        if not self.reference:
            return {}

        numeric_df = df.select_dtypes(include=[np.number])
        result: Dict[str, Dict[str, float | bool]] = {}

        for col in numeric_df.columns:
            if col not in self.reference:
                continue
            values = numeric_df[col].dropna().to_numpy(dtype=float)
            reference_histogram = self.reference[col].get("histogram", [])
            if not isinstance(reference_histogram, list):
                continue
            ref_samples = self._reconstruct_reference_samples(reference_histogram)
            if values.size == 0 or ref_samples.size == 0:
                continue

            ks_stat = ks_2samp(values, ref_samples)
            ks_pvalue = float(ks_stat.pvalue)

            expected_counts = np.array([int(bucket.get("count", 0)) for bucket in reference_histogram], dtype=float)
            edges = [float(reference_histogram[0]["left"])]
            for bucket in reference_histogram:
                edges.append(float(bucket["right"]))
            actual_counts, _ = np.histogram(values, bins=np.array(edges, dtype=float))
            psi = self._psi(expected_counts, actual_counts.astype(float))

            drifted = ks_pvalue < 0.05 or psi > 0.2
            result[col] = {
                "ks_pvalue": ks_pvalue,
                "psi": psi,
                "drifted": drifted,
            }

        return result

    def summary(self, result: Dict[str, Dict[str, float | bool]]) -> str:
        drifted = [
            f"{name}(psi={metrics['psi']:.3f}, p={metrics['ks_pvalue']:.4f})"
            for name, metrics in result.items()
            if bool(metrics.get("drifted", False))
        ]
        if not drifted:
            return "No drift detected."
        return "Drift detected in: " + ", ".join(drifted)


def check_target_leakage(feature_df: pd.DataFrame, target_col: str, threshold: float = 0.95) -> list[str]:
    issues: list[str] = []
    if target_col not in feature_df.columns:
        return issues

    target = pd.to_numeric(feature_df[target_col], errors="coerce")
    for col in feature_df.columns:
        if col == target_col:
            continue
        series = pd.to_numeric(feature_df[col], errors="coerce")
        joined = pd.concat([series, target], axis=1).dropna()
        if joined.empty:
            continue
        corr = joined.iloc[:, 0].corr(joined.iloc[:, 1], method="pearson")
        if pd.isna(corr):
            continue
        if abs(float(corr)) > threshold:
            issues.append(f"LEAKAGE_RISK:{col}:{float(corr):.3f}")
    return issues
