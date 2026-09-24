"""A hard cap on LLM requests, so traffic can never exhaust the OpenRouter daily quota."""

import threading
import time
from collections import deque
from collections.abc import Callable

DAY_SECONDS = 24 * 60 * 60


class RequestBudget:
    """Allows at most `limit` requests in any rolling `window_seconds`. Thread-safe."""

    def __init__(self, limit: int, window_seconds: float = DAY_SECONDS, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self._window = window_seconds
        self._clock = clock
        self._spent: deque[float] = deque()
        self._lock = threading.Lock()

    def _expire(self, now: float) -> None:
        while self._spent and now - self._spent[0] >= self._window:
            self._spent.popleft()

    def try_spend(self) -> bool:
        """Records one request and returns True if the budget allows it; otherwise returns False."""
        with self._lock:
            now = self._clock()
            self._expire(now)
            if len(self._spent) >= self.limit:
                return False
            self._spent.append(now)
            return True

    def remaining(self) -> int:
        with self._lock:
            self._expire(self._clock())
            return max(self.limit - len(self._spent), 0)
