from __future__ import annotations

import unittest

from app.monitoring.circuit_breaker import (
    CircuitBreaker,
)
from app.trader.execution_watchdog import (
    evaluate_execution_watchdog,
)


class ExecutionWatchdogTests(
    unittest.TestCase
):
    def test_healthy_recovery_allows_cycle(self):
        breaker = CircuitBreaker()

        result = evaluate_execution_watchdog(
            position_sync={
                "status": "success",
            },
            order_recovery={
                "status": "success",
                "audit_after": {
                    "status": "consistent",
                },
            },
            health_function=lambda: {
                "healthy": True,
                "status": "healthy",
            },
            circuit_breaker=breaker,
        )

        self.assertTrue(
            result["allowed"]
        )

    def test_unresolved_drift_blocks_cycle(self):
        breaker = CircuitBreaker()

        result = evaluate_execution_watchdog(
            position_sync={
                "status": "success",
            },
            order_recovery={
                "status": "drift_detected",
                "audit_after": {
                    "status": "drift_detected",
                },
            },
            health_function=lambda: {
                "healthy": True,
                "status": "healthy",
            },
            circuit_breaker=breaker,
        )

        self.assertFalse(
            result["allowed"]
        )


if __name__ == "__main__":
    unittest.main()
