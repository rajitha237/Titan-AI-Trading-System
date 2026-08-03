"""Persistent Circuit Breaker v30."""

from __future__ import annotations

import time
from typing import Any

from app.monitoring.circuit_breaker import (
    CircuitBreaker,
)
from app.service.service_state_store import (
    get_state,
    set_state,
)


class PersistentCircuitBreaker(
    CircuitBreaker
):
    def __init__(
        self,
        *,
        state_key: str,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        self.state_key = str(state_key)
        super().__init__(
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=(
                recovery_timeout_seconds
            ),
        )
        self._restore()

    def _restore(self) -> None:
        state = get_state(
            self.state_key,
            {},
        )

        if not isinstance(state, dict):
            return

        self._failure_count = int(
            state.get(
                "failure_count",
                0,
            )
        )
        self._last_error = state.get(
            "last_error"
        )

        remaining = float(
            state.get(
                "recovery_remaining_seconds",
                0.0,
            )
            or 0.0
        )

        state_name = str(
            state.get(
                "state",
                "CLOSED",
            )
        ).upper()

        if (
            state_name == "OPEN"
            and remaining > 0
        ):
            elapsed = max(
                0.0,
                self.recovery_timeout_seconds
                - remaining,
            )
            self._opened_at_monotonic = (
                time.monotonic() - elapsed
            )
        elif state_name == "HALF_OPEN":
            self._opened_at_monotonic = (
                time.monotonic()
                - self.recovery_timeout_seconds
            )
        else:
            self._opened_at_monotonic = None

    def _persist(self) -> None:
        set_state(
            self.state_key,
            self.snapshot(),
        )

    def record_success(self) -> None:
        super().record_success()
        self._persist()

    def record_failure(
        self,
        error: Any,
    ) -> None:
        super().record_failure(error)
        self._persist()
