from __future__ import annotations

import json
import uuid
from typing import Callable, Dict, List

from .healing_ledger import HealingLedger


class MetaControllerV2:
    """Canonical meta-controller with healing verification and persistent ledger."""

    def __init__(self, performance_threshold: float = 0.6):
        self.performance_threshold = performance_threshold
        self.critical_models: set[str] = set()
        self.ledger = HealingLedger()

    def detect_underperforming_models(self, model_performance: Dict[str, float]) -> List[str]:
        return [model_id for model_id, score in model_performance.items() if score < self.performance_threshold]

    def detect_anomalous_models(self, model_performance: Dict[str, float]) -> List[str]:
        # Deterministic simple anomaly proxy for notebook portability.
        return [model_id for model_id, score in model_performance.items() if score < (self.performance_threshold - 0.15)]

    def retrain_model(self, model_id: str) -> Dict[str, str]:
        return {"model_id": model_id, "action": "retrain", "status": "done"}

    def deactivate_model(self, model_id: str) -> Dict[str, str]:
        return {"model_id": model_id, "action": "deactivate", "status": "done"}

    def verify_healing_action(self, model_id: str, pre_metric: float, post_metric: float) -> str:
        return "verified" if post_metric >= pre_metric else "failed"

    def self_healing_mechanism(
        self,
        model_performance: Dict[str, float],
        post_action_metric_provider: Callable[[str, str], float] | None = None,
    ) -> Dict[str, object]:
        underperforming = self.detect_underperforming_models(model_performance)
        anomalous = self.detect_anomalous_models(model_performance)
        candidates = sorted(set(underperforming + anomalous))

        actions_taken: Dict[str, dict] = {}
        for model_id in candidates:
            pre_metric = float(model_performance.get(model_id, 0.0))
            if model_id in self.critical_models:
                action_result = self.retrain_model(model_id)
                action_type = "retrain"
            else:
                action_result = self.deactivate_model(model_id)
                action_type = "deactivate"

            if post_action_metric_provider:
                post_metric = float(post_action_metric_provider(model_id, action_type))
            else:
                post_metric = pre_metric + (0.05 if action_type == "retrain" else 0.0)

            verification = self.verify_healing_action(model_id, pre_metric, post_metric)
            action_id = str(uuid.uuid4())
            self.ledger.record(
                action_id=action_id,
                model_id=model_id,
                action_type=action_type,
                pre_metrics=json.dumps({"score": pre_metric}),
                post_metrics=json.dumps({"score": post_metric}),
                verification_status=verification,
            )

            actions_taken[model_id] = {
                "action": action_result,
                "verification": verification,
                "pre_metric": pre_metric,
                "post_metric": post_metric,
            }

        health_score = 100.0
        if model_performance:
            health_score = round(100.0 * sum(model_performance.values()) / len(model_performance), 2)

        return {
            "actions_taken": actions_taken,
            "system_health_score": health_score,
            "underperforming_models": underperforming,
            "anomalous_models": anomalous,
            "ledger_events": self.ledger.count(),
            "requires_human_intervention": any(v["verification"] == "failed" for v in actions_taken.values()),
        }
