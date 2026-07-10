from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import joblib
import pandas as pd

from data_layer.feature_store.feature_store_engine import FeatureStoreEngine
from models.registry.model_registry import ModelRegistry
from models.evaluation.prediction_error_monitor import ErrorSummary, PredictionErrorMonitor


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


class AnalysisOrchestrator:
    """Canonical orchestrator with idempotent step markers and full export-only flow."""

    def __init__(self, exports_dir: str = "exports", feature_store_engine: Optional[FeatureStoreEngine] = None):
        """Initialize orchestrator runtime and reliability dependencies."""
        self.exports_dir = Path(exports_dir)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir = self.exports_dir / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.require_human_approval = _bool_env("REQUIRE_HUMAN_APPROVAL", default=False)
        self.registry = ModelRegistry(
            str(self.exports_dir / "model_registry.db"),
            require_human_approval=self.require_human_approval,
        )
        self.feature_store_engine = feature_store_engine or FeatureStoreEngine()
        self.error_monitor = PredictionErrorMonitor(str(self.exports_dir / "prediction_monitor.db"))
        self._model_lock = threading.RLock()
        self._active_models: Dict[str, tuple[str, object]] = {}

    def preprocess_features(self, raw_df: pd.DataFrame, dataset: str = "realtime", strict: bool = True) -> Dict[str, Any]:
        """Process and validate raw data before orchestration steps consume it."""
        cleaned_df, quality = self.feature_store_engine.process(raw_df, dataset=dataset, strict=strict)
        return {
            "rows_in": int(len(raw_df)),
            "rows_out": int(len(cleaned_df)),
            "quality": quality.as_dict(),
        }

    def _run_state_path(self, run_id: str) -> Path:
        """Return persisted run-state file path for a run ID."""
        return self.runs_dir / f"{run_id}.json"

    def _load_run_state(self, run_id: str) -> Dict[str, Any]:
        """Load run-state marker file or initialize a new state payload."""
        path = self._run_state_path(run_id)
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {"run_id": run_id, "steps": {}, "created_at": datetime.utcnow().isoformat()}

    def _save_run_state(self, run_state: Dict[str, Any]) -> None:
        """Persist run-state markers atomically for restart-safe execution."""
        path = self._run_state_path(run_state["run_id"])
        self._atomic_write_text(path, json.dumps(run_state, indent=2))

    @staticmethod
    def _atomic_write_text(path: Path, content: str) -> None:
        """Write text via temp file and atomic replace."""
        tmp_path = Path(str(path) + ".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        os.replace(tmp_path, path)

    def _run_step_once(self, run_state: Dict[str, Any], step_name: str, fn: Callable[[], Any]) -> Any:
        """Execute step idempotently using persisted completion markers."""
        step_state = run_state["steps"].get(step_name)
        if step_state and step_state.get("status") == "COMPLETED":
            return step_state.get("result")

        result = fn()
        run_state["steps"][step_name] = {
            "status": "COMPLETED",
            "completed_at": datetime.utcnow().isoformat(),
            "result": result,
        }
        self._save_run_state(run_state)
        return result

    def export_only(self, artifacts: Dict[str, Any], run_id: Optional[str] = None) -> Dict[str, str]:
        """Persist export artifacts and register produced model versions."""
        run_id = run_id or datetime.utcnow().strftime("export_%Y%m%dT%H%M%SZ")
        run_path = self.exports_dir / run_id
        run_path.mkdir(parents=True, exist_ok=True)

        report_path = run_path / "report.json"
        models_path = run_path / "models.json"
        logs_path = run_path / "run.log"

        report_payload = {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": artifacts.get("metrics", {}),
            "summary": artifacts.get("summary", {}),
        }
        self._atomic_write_text(report_path, json.dumps(report_payload, indent=2))

        models_payload = artifacts.get("models", {})
        self._atomic_write_text(models_path, json.dumps(models_payload, indent=2))

        if isinstance(models_payload, dict):
            for model_name, model_info in models_payload.items():
                self.registry.register(
                    model_name=model_name,
                    file_path=str(model_info.get("file_path", "")),
                    metrics_json=json.dumps(model_info.get("metrics", {})),
                )

        self._atomic_write_text(logs_path, f"[{datetime.utcnow().isoformat()}] export_only completed for {run_id}\\n")

        return {
            "report": str(report_path),
            "models": str(models_path),
            "logs": str(logs_path),
        }

    def run_complete_analysis(self, run_id: Optional[str] = None, raw_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """Run canonical seven-step orchestration flow with restart-safe markers."""
        run_id = run_id or datetime.utcnow().strftime("run_%Y%m%dT%H%M%SZ")
        run_state = self._load_run_state(run_id)

        if raw_df is not None:
            data = self._run_step_once(
                run_state,
                "step_1_data",
                lambda: self.preprocess_features(raw_df, dataset="orchestrator_input", strict=True),
            )
            processed = self._run_step_once(
                run_state,
                "step_2_process",
                lambda: {
                    "processed_rows": data["rows_out"],
                    "quality_passed": bool(data["quality"].get("passed", False)),
                },
            )
        else:
            data = self._run_step_once(run_state, "step_1_data", lambda: {"rows": 1000})
            processed = self._run_step_once(run_state, "step_2_process", lambda: {"processed_rows": data["rows"]})
        forecast = self._run_step_once(run_state, "step_3_forecast", lambda: {"horizon_days": 30})
        segments = self._run_step_once(run_state, "step_4_segment", lambda: {"segments": 4})
        metrics = self._run_step_once(run_state, "step_5_metrics", lambda: {"health": 92.0})
        visuals = self._run_step_once(run_state, "step_6_visuals", lambda: {"charts": 6})

        export_result = self._run_step_once(
            run_state,
            "step_7_export",
            lambda: self.export_only(
                {
                    "metrics": metrics,
                    "summary": {
                        "data": data,
                        "processed": processed,
                        "forecast": forecast,
                        "segments": segments,
                        "visuals": visuals,
                    },
                    "models": {
                        "forecast_model": {
                            "file_path": str(self.exports_dir / run_id / "forecast_model.pkl"),
                            "metrics": {"mae": 0.12, "rmse": 0.19},
                        }
                    },
                },
                run_id=run_id,
            ),
        )

        return {
            "run_id": run_id,
            "data": data,
            "processed": processed,
            "forecast": forecast,
            "segments": segments,
            "metrics": metrics,
            "visuals": visuals,
            "export": export_result,
            "step_markers": run_state["steps"],
        }

    def check_for_updates(self, model_name: str) -> bool:
        """Hot-swap active model weights when the active registry UUID changes."""
        version_uuid, file_path = self.registry.get_active_version(model_name)
        if not version_uuid or not file_path:
            return False

        current_version = self._active_models.get(model_name, (None, None))[0]
        if current_version == version_uuid:
            return False

        loaded_model = joblib.load(file_path)
        with self._model_lock:
            self._active_models[model_name] = (version_uuid, loaded_model)
        return True

    def predict(self, model_name: str, X: Any) -> Any:
        """Predict using the currently pinned active model reference."""
        if model_name not in self._active_models:
            self.check_for_updates(model_name)
        if model_name not in self._active_models:
            raise ValueError(f"active_model_not_loaded:{model_name}")

        with self._model_lock:
            model = self._active_models[model_name][1]
        result = model.predict(X)
        return result

    def record_prediction(self, model_name: str, prediction_id: str, predicted_value: float) -> None:
        """Record a model prediction for later realized-error evaluation."""
        self.error_monitor.record_prediction(model_name, prediction_id, predicted_value)

    def record_outcome(
        self,
        model_name: str,
        prediction_id: str,
        actual_value: float,
        window: int = 100,
        mae_threshold: float = 1.0,
        rmse_threshold: float = 1.25,
        min_direction_accuracy: float = 0.45,
    ) -> Dict[str, float | int | bool | str]:
        """Record realized outcome and return rolling degradation summary."""
        matched = self.error_monitor.record_outcome(model_name, prediction_id, actual_value)
        summary: ErrorSummary = self.error_monitor.summarize(
            model_name=model_name,
            window=window,
            mae_threshold=mae_threshold,
            rmse_threshold=rmse_threshold,
            min_direction_accuracy=min_direction_accuracy,
        )
        result = summary.as_dict()
        result["matched_prediction"] = matched
        return result

    def approve_model_version(self, model_name: str, version_tag: str, approved_by: str = "human") -> bool:
        """Approve a pending model version so it can become active."""
        return self.registry.approve_version(model_name, version_tag, approved_by=approved_by)
