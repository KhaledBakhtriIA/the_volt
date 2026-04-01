from __future__ import annotations

from src.canonical.prediction_error_monitor import PredictionErrorMonitor


def test_prediction_monitor_detects_degradation(tmp_path) -> None:
    monitor = PredictionErrorMonitor(str(tmp_path / "pred_monitor.db"))

    for i in range(6):
        monitor.record_prediction("forecast_model", f"pred-{i}", predicted_value=1.0)
        monitor.record_outcome("forecast_model", f"pred-{i}", actual_value=5.0)

    summary = monitor.summarize(
        model_name="forecast_model",
        window=10,
        mae_threshold=1.0,
        rmse_threshold=1.25,
        min_direction_accuracy=0.45,
    )

    assert summary.samples == 6
    assert summary.mae > 1.0
    assert summary.rmse > 1.25
    assert summary.degraded is True


def test_prediction_monitor_reports_healthy_when_error_is_low(tmp_path) -> None:
    monitor = PredictionErrorMonitor(str(tmp_path / "pred_monitor.db"))

    for i in range(6):
        prediction = 1.0 + (0.01 * i)
        actual = prediction + 0.02
        monitor.record_prediction("forecast_model", f"ok-{i}", predicted_value=prediction)
        monitor.record_outcome("forecast_model", f"ok-{i}", actual_value=actual)

    summary = monitor.summarize(
        model_name="forecast_model",
        window=10,
        mae_threshold=1.0,
        rmse_threshold=1.25,
        min_direction_accuracy=0.45,
    )

    assert summary.samples == 6
    assert summary.mae < 1.0
    assert summary.rmse < 1.25
    assert summary.degraded is False


def test_record_outcome_returns_false_for_unknown_prediction(tmp_path) -> None:
    monitor = PredictionErrorMonitor(str(tmp_path / "pred_monitor.db"))

    matched = monitor.record_outcome("forecast_model", "missing-id", actual_value=1.23)

    assert matched is False
