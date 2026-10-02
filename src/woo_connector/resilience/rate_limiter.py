"""Client-side rate limiting primitives."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable


class TokenBucket:
    """Small dependency-free token bucket; clock/sleep are injectable for tests."""

    def __init__(
        self,
        rate_per_s: float,
        capacity: float,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if rate_per_s <= 0 or capacity <= 0:
            raise ValueError("rate_per_s and capacity must be positive")
        self.rate = float(rate_per_s)
        self.capacity = float(capacity)
        self._tokens = float(capacity)
        self._clock = clock
        self._sleep = sleep
        self._last = clock()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(
            self.capacity,
            self._tokens + max(0.0, now - self._last) * self.rate,
        )
        self._last = now

    async def acquire(self, n: float = 1.0) -> None:
        if n <= 0 or n > self.capacity:
            raise ValueError("requested token count must be > 0 and <= capacity")
        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    return
                await self._sleep((n - self._tokens) / self.rate)
                self._refill()
