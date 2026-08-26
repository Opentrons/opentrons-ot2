import time
from typing import Callable, Optional


class Debouncer:
    def __init__(
        self,
        debounce_seconds: float,
        get_monotonic_seconds: Callable[[], float] = time.monotonic,
    ) -> None:
        self._debounce_seconds = debounce_seconds
        self._get_monotonic_seconds = get_monotonic_seconds
        self._last_triggered_at: Optional[float] = None

    def trigger(self) -> bool:
        """Return true if it's been at least `debounce_seconds` since the last successful trigger."""
        now = self._get_monotonic_seconds()
        if (
            self._last_triggered_at is None
            or now - self._last_triggered_at > self._debounce_seconds
        ):
            self._last_triggered_at = now
            return True
        else:
            return False
