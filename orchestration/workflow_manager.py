"""Named, ordered workflows over the agent orchestrator.

A workflow is a sequence of steps the supervisor can trigger on a schedule or
on demand (e.g. a per-tick trade cycle, or a nightly retrain-and-approve run).
Kept intentionally small: it sequences callables and records their outcomes."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class WorkflowManager:
    """Registry of named workflows plus a runner that captures step results."""

    workflows: Dict[str, List[tuple]] = field(default_factory=dict)

    def register(self, name: str, steps: List[tuple]) -> None:
        """steps: list of (step_name, callable) run in order."""
        self.workflows[name] = steps

    def run(self, name: str) -> List[StepResult]:
        if name not in self.workflows:
            raise KeyError(f"unknown workflow: {name}")
        results: List[StepResult] = []
        for step_name, fn in self.workflows[name]:
            try:
                detail = fn()
                results.append(StepResult(step_name, True, str(detail) if detail is not None else ""))
            except Exception as exc:  # noqa: BLE001 - workflows isolate step failures
                logger.exception("workflow %s step %s failed", name, step_name)
                results.append(StepResult(step_name, False, str(exc)))
                break
        return results


__all__ = ["WorkflowManager", "StepResult"]
