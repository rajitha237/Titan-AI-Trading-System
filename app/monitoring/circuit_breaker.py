"""TitanAI in-process Circuit Breaker v29."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 60.0
    _failure_count: int = 0
    _opened_at_monotonic: float | None = None
    _last_error: str | None = None
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        repr=False,
    )

    def _recovery_elapsed(self) -> bool:
        if self._opened_at_monotonic is None:
            return False

        return (
            time.monotonic()
            - self._opened_at_monotonic
            >= max(
                0.0,
                self.recovery_timeout_seconds,
            )
        )

    def allow_request(self) -> bool:
        with self._lock:
            if self._opened_at_monotonic is None:
                return True

            if self._recovery_elapsed():
                # Half-open: permit one probe cycle.
                return True

            return False

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._opened_at_monotonic = None
            self._last_error = None

    def record_failure(
        self,
        error: Any,
    ) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_error = str(error)

            if (
                self._failure_count
                >= max(
                    1,
                    self.failure_threshold,
                )
            ):
                self._opened_at_monotonic = (
                    time.monotonic()
                )

    def snapshot(self) -> dict:
        with self._lock:
            if self._opened_at_monotonic is None:
                state = "CLOSED"
                remaining = 0.0
            elif self._recovery_elapsed():
                state = "HALF_OPEN"
                remaining = 0.0
            else:
                state = "OPEN"
                elapsed = (
                    time.monotonic()
                    - self._opened_at_monotonic
                )
                remaining = max(
                    0.0,
                    self.recovery_timeout_seconds
                    - elapsed,
                )

            return {
                "state": state,
                "failure_count": (
                    self._failure_count
                ),
                "failure_threshold": (
                    self.failure_threshold
                ),
                "recovery_timeout_seconds": (
                    self.recovery_timeout_seconds
                ),
                "recovery_remaining_seconds": round(
                    remaining,
                    3,
                ),
                "last_error": self._last_error,
            }
