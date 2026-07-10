from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict


@dataclass(frozen=True)
class ErrorSummary:
    """Rolling prediction error summary for a model."""

    model_name: str
    samples: int
    mae: float
    rmse: float
    direction_accuracy: float
    degraded: bool

    def as_dict(self) -> Dict[str, float | int | bool | str]:
        """Return a serializable representation for logs and APIs."""
        return {
            "model_name": self.model_name,
            "samples": self.samples,
            "mae": self.mae,
            "rmse": self.rmse,
            "direction_accuracy": self.direction_accuracy,
            "degraded": self.degraded,
        }


class PredictionErrorMonitor:
    """Persist prediction/outcome pairs and detect model performance degradation."""

    def __init__(self, db_path: str = "exports/prediction_monitor.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS prediction_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_name TEXT NOT NULL,
                    prediction_id TEXT NOT NULL,
                    predicted_value REAL NOT NULL,
                    actual_value REAL,
                    predicted_at TEXT NOT NULL,
                    actual_at TEXT,
                    error_abs REAL,
                    error_sq REAL
                )
                """
            )
            con.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_prediction_event_unique ON prediction_events(model_name, prediction_id)"
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_prediction_event_recent ON prediction_events(model_name, actual_at)"
            )

    def record_prediction(self, model_name: str, prediction_id: str, predicted_value: float) -> None:
        """Store a prediction so it can be joined with realized outcomes later."""
        with self._connect() as con:
            con.execute(
                """
                INSERT OR REPLACE INTO prediction_events(
                    model_name,
                    prediction_id,
                    predicted_value,
                    actual_value,
                    predicted_at,
                    actual_at,
                    error_abs,
                    error_sq
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    model_name,
                    prediction_id,
                    float(predicted_value),
                    None,
                    datetime.utcnow().isoformat(),
                    None,
                    None,
                    None,
                ),
            )

    def record_outcome(self, model_name: str, prediction_id: str, actual_value: float) -> bool:
        """Attach an observed outcome and compute error terms.

        Returns False when there is no matching prediction record.
        """
        with self._connect() as con:
            cur = con.execute(
                "SELECT predicted_value FROM prediction_events WHERE model_name = ? AND prediction_id = ?",
                (model_name, prediction_id),
            )
            row = cur.fetchone()
            if not row:
                return False

            predicted = float(row[0])
            actual = float(actual_value)
            err_abs = abs(actual - predicted)
            err_sq = (actual - predicted) ** 2
            con.execute(
                """
                UPDATE prediction_events
                SET actual_value = ?,
                    actual_at = ?,
                    error_abs = ?,
                    error_sq = ?
                WHERE model_name = ? AND prediction_id = ?
                """,
                (
                    actual,
                    datetime.utcnow().isoformat(),
                    err_abs,
                    err_sq,
                    model_name,
                    prediction_id,
                ),
            )
            return True

    def summarize(
        self,
        model_name: str,
        window: int = 100,
        mae_threshold: float = 1.0,
        rmse_threshold: float = 1.25,
        min_direction_accuracy: float = 0.45,
    ) -> ErrorSummary:
        """Compute rolling error statistics and degradation flag."""
        with self._connect() as con:
            rows = con.execute(
                """
                SELECT predicted_value, actual_value, error_abs, error_sq
                FROM prediction_events
                WHERE model_name = ? AND actual_value IS NOT NULL
                ORDER BY id DESC
                LIMIT ?
                """,
                (model_name, window),
            ).fetchall()

        if not rows:
            return ErrorSummary(
                model_name=model_name,
                samples=0,
                mae=0.0,
                rmse=0.0,
                direction_accuracy=0.0,
                degraded=False,
            )

        samples = len(rows)
        mae = sum(float(r[2]) for r in rows) / samples
        rmse = (sum(float(r[3]) for r in rows) / samples) ** 0.5

        directional_hits = 0
        for predicted, actual, _, _ in rows:
            predicted_sign = 1 if float(predicted) >= 0 else -1
            actual_sign = 1 if float(actual) >= 0 else -1
            if predicted_sign == actual_sign:
                directional_hits += 1
        direction_accuracy = directional_hits / samples

        degraded = mae > mae_threshold or rmse > rmse_threshold or direction_accuracy < min_direction_accuracy

        return ErrorSummary(
            model_name=model_name,
            samples=samples,
            mae=mae,
            rmse=rmse,
            direction_accuracy=direction_accuracy,
            degraded=degraded,
        )
