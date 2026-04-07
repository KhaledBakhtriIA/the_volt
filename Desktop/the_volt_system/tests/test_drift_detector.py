from __future__ import annotations

import pandas as pd

from src.canonical.drift_detector import DriftDetector, check_target_leakage


def test_drift_detector_save_reference_and_detect(tmp_path) -> None:
    reference_path = tmp_path / "reference_stats.json"
    detector = DriftDetector(str(reference_path))

    reference_df = pd.DataFrame({
        "feature_a": [1.0, 1.1, 0.9, 1.05, 1.0, 1.2],
        "feature_b": [10.0, 10.1, 9.9, 10.2, 9.8, 10.0],
    })
    detector.save_reference(reference_df, str(reference_path))

    shifted_df = pd.DataFrame({
        "feature_a": [5.0, 5.1, 4.9, 5.2, 5.05, 5.15],
        "feature_b": [10.0, 10.1, 9.9, 10.2, 9.8, 10.0],
    })
    result = detector.detect(shifted_df)

    assert "feature_a" in result
    assert "drifted" in result["feature_a"]


def test_drift_detector_summary_lists_drifted_features() -> None:
    detector = DriftDetector("non_existent_reference.json")
    summary = detector.summary(
        {
            "x": {"ks_pvalue": 0.001, "psi": 0.4, "drifted": True},
            "y": {"ks_pvalue": 0.9, "psi": 0.01, "drifted": False},
        }
    )

    assert "Drift detected in:" in summary
    assert "x(psi=0.400" in summary


def test_check_target_leakage_flags_high_correlation() -> None:
    frame = pd.DataFrame(
        {
            "feature_1": [1, 2, 3, 4, 5],
            "feature_2": [2, 4, 6, 8, 10],
            "target": [3, 6, 9, 12, 15],
        }
    )

    leakage = check_target_leakage(frame, target_col="target", threshold=0.95)

    assert any(item.startswith("LEAKAGE_RISK:feature_1") for item in leakage)
    assert any(item.startswith("LEAKAGE_RISK:feature_2") for item in leakage)
