from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Iterable, Optional


@dataclass
class EscalationConfig:
    degraded_threshold: float = 70.0
    halt_threshold: float = 50.0
    sustain_minutes: int = 5


class PipelineSupervisor:
    """Canonical supervisor with health tracking and escalation policy."""

    def __init__(self, model_names: Iterable[str], stale_seconds: int = 300, escalation: Optional[EscalationConfig] = None):
        self.model_names = list(model_names)
        self.stale_seconds = stale_seconds
        self.last_update: Dict[str, Optional[datetime]] = {name: None for name in self.model_names}
        self.update_count: Dict[str, int] = {name: 0 for name in self.model_names}
        self.escalation = escalation or EscalationConfig()
        self.mode = "NORMAL"
        self._below_70_since: Optional[datetime] = None

    def update(self, name: str) -> None:
        if name not in self.last_update:
            self.last_update[name] = None
            self.update_count[name] = 0
        self.last_update[name] = datetime.utcnow()
        self.update_count[name] += 1

    def health_score(self) -> float:
        now = datetime.utcnow()
        active = 0
        for name, ts in self.last_update.items():
            if ts and (now - ts).total_seconds() <= self.stale_seconds:
                active += 1
        if not self.last_update:
            return 0.0
        return round(100.0 * active / len(self.last_update), 2)

    def evaluate_escalation(self) -> Dict[str, str]:
        score = self.health_score()
        now = datetime.utcnow()

        if score < self.escalation.halt_threshold:
            self.mode = "HALT"
            return {"mode": self.mode, "reason": "health_below_50"}

        if score < self.escalation.degraded_threshold:
            if self._below_70_since is None:
                self._below_70_since = now
            sustained = now - self._below_70_since >= timedelta(minutes=self.escalation.sustain_minutes)
            if sustained:
                self.mode = "DEGRADED"
                return {"mode": self.mode, "reason": "health_below_70_for_5m"}
            return {"mode": self.mode, "reason": "monitoring_low_health"}

        self._below_70_since = None
        self.mode = "NORMAL"
        return {"mode": self.mode, "reason": "healthy"}
