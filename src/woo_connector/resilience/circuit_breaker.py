from __future__ import annotations

import time
from collections.abc import Callable

from ..models.errors import CircuitOpenError


class CircuitBreaker:
    """Fail fast when the store is clearly down.

    Only server-side/network failures count. A 429 is throttling, not an
    outage, so it never trips the breaker.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_after_s: float = 30.0,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        
        if reset_after_s <= 0:
            raise ValueError("reset_after_s must be positive")
        
        self.failure_threshold = failure_threshold
        self.reset_after_s = reset_after_s
        self._clock = clock
        self._failures = 0
        self._opened_at: float | None = None
        self._half_open = False

    @property
    def state(self) -> str:
        if self._opened_at is None:
            return "closed"
        
        if self._clock() - self._opened_at >= self.reset_after_s:
            return "half_open"
        
        return "open"

    def before_call(self) -> None:
        if self._opened_at is None:
            return
        
        elapsed = self._clock() - self._opened_at
        
        if elapsed < self.reset_after_s:
            raise CircuitOpenError(
                "The store has been failing repeatedly; calls are paused briefly.",
                retry_after_s=self.reset_after_s - elapsed,
            )
        self._half_open = True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._half_open = False

    def record_failure(self) -> None:
        self._failures += 1
        if self._half_open or self._failures >= self.failure_threshold:
            self._opened_at = self._clock()
            self._half_open = False
