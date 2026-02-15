from __future__ import annotations

import threading
import time


class TokenBucketRateLimiter:
    """
    Simple token bucket for per-minute throttling.
    """

    def __init__(self, max_per_min: int) -> None:
        self.capacity = max_per_min
        self.tokens = float(max_per_min)
        self.refill_rate_per_sec = max_per_min / 60.0
        self.last = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self, tokens: float = 1.0) -> None:
        while True:
            with self.lock:
                now = time.monotonic()
                elapsed = now - self.last
                self.last = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate_per_sec)

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                needed = tokens - self.tokens
                wait = needed / self.refill_rate_per_sec if self.refill_rate_per_sec > 0 else 1.0

            time.sleep(max(wait, 0.05))
