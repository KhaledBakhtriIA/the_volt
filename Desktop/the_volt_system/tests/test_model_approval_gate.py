from __future__ import annotations

import os

import joblib

from src.canonical.model_registry import ModelRegistry
from src.canonical.orchestrator import AnalysisOrchestrator


class _DummyModel:
    def predict(self, X):
        return [42.0 for _ in range(len(X))]


def test_registry_requires_approval_before_activation(tmp_path) -> None:
    db_path = tmp_path / "registry.db"
    model_path = tmp_path / "model.pkl"
    model_path.write_text("weights", encoding="utf-8")

    registry = ModelRegistry(str(db_path), require_human_approval=True)
    version_tag = registry.register("forecast_model", str(model_path), "{}")

    assert registry.active_version("forecast_model") is None

    approved = registry.approve_version("forecast_model", version_tag, approved_by="qa")
    active = registry.active_version("forecast_model")

    assert approved is True
    assert active is not None
    assert active["version_tag"] == version_tag


def test_orchestrator_gate_blocks_swap_until_approved(tmp_path) -> None:
    os.environ["REQUIRE_HUMAN_APPROVAL"] = "true"
    try:
        exports_dir = tmp_path / "exports"
        model_path = exports_dir / "candidate.pkl"
        model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(_DummyModel(), model_path)

        orchestrator = AnalysisOrchestrator(exports_dir=str(exports_dir))

        version_tag = orchestrator.registry.register("forecast_model", str(model_path), "{}")

        swapped_before_approval = orchestrator.check_for_updates("forecast_model")
        assert swapped_before_approval is False

        approved = orchestrator.approve_model_version("forecast_model", version_tag, approved_by="qa")
        swapped_after_approval = orchestrator.check_for_updates("forecast_model")
        prediction = orchestrator.predict("forecast_model", [[1.0], [2.0]])

        assert approved is True
        assert swapped_after_approval is True
        assert prediction == [42.0, 42.0]
    finally:
        os.environ.pop("REQUIRE_HUMAN_APPROVAL", None)
