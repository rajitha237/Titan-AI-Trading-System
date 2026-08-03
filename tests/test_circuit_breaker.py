from __future__ import annotations

import unittest

from app.monitoring.circuit_breaker import (
    CircuitBreaker,
)


class CircuitBreakerTests(
    unittest.TestCase
):
    def test_threshold_opens_breaker(self):
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout_seconds=60,
        )

        breaker.record_failure("one")
        self.assertTrue(
            breaker.allow_request()
        )

        breaker.record_failure("two")
        self.assertFalse(
            breaker.allow_request()
        )
        self.assertEqual(
            breaker.snapshot()["state"],
            "OPEN",
        )

    def test_success_resets_breaker(self):
        breaker = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout_seconds=60,
        )
        breaker.record_failure("error")
        breaker.record_success()

        self.assertEqual(
            breaker.snapshot()["state"],
            "CLOSED",
        )


if __name__ == "__main__":
    unittest.main()
