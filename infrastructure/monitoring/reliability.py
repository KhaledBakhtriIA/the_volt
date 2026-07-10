from __future__ import annotations

import random
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional, TypeVar

T = TypeVar("T")


@dataclass
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.2


class CircuitBreakerOpen(Exception):
    pass


class CircuitBreaker:
    def __init__(self, name: str, failure_threshold: int = 5, open_seconds: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.open_seconds = open_seconds
        self.failure_count = 0
        self.opened_at: Optional[datetime] = None

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if datetime.utcnow() - self.opened_at >= timedelta(seconds=self.open_seconds):
            self.opened_at = None
            self.failure_count = 0
            return False
        return True

    def before_call(self) -> None:
        if self.is_open():
            raise CircuitBreakerOpen(f"Circuit breaker '{self.name}' is open")

    def on_success(self) -> None:
        self.failure_count = 0
        self.opened_at = None

    def on_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.opened_at = datetime.utcnow()


def retry_call(
    fn: Callable[[], T],
    policy: Optional[RetryPolicy] = None,
    breaker: Optional[CircuitBreaker] = None,
) -> T:
    policy = policy or RetryPolicy()
    last_exc: Optional[Exception] = None

    for attempt in range(1, policy.max_attempts + 1):
        try:
            if breaker:
                breaker.before_call()
            result = fn()
            if breaker:
                breaker.on_success()
            return result
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if breaker:
                breaker.on_failure()
            if attempt >= policy.max_attempts:
                break
            backoff = min(policy.base_delay_seconds * (2 ** (attempt - 1)), policy.max_delay_seconds)
            jitter = random.uniform(0.0, policy.jitter_seconds)
            time.sleep(backoff + jitter)

    raise RuntimeError(f"Retry budget exhausted: {last_exc}") from last_exc
