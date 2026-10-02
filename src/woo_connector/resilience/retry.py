from __future__ import annotations
import math, random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable

def parse_retry_after(value: str | None, *, now: datetime | None = None) -> float | None:
    if not value: return None
    value = value.strip()
    try:
        secs = float(value)
        return max(secs, 0.0) if math.isfinite(secs) else None
    except ValueError: pass
    try: dt = parsedate_to_datetime(value)
    except (TypeError, ValueError): return None
    if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return max((dt-now).total_seconds(), 0.0)

def backoff_delay(attempt: int, *, base: float=0.5, cap: float=8.0,
                  rng: Callable[[], float]=random.random) -> float:
    ceiling=min(cap, base*(2**attempt))
    return ceiling/2 + rng()*ceiling/2
