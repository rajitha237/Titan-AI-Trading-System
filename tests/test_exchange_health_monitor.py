from __future__ import annotations

import unittest

from app.monitoring.exchange_health_monitor import (
    check_exchange_health,
)


class ExchangeHealthMonitorTests(
    unittest.TestCase
):
    def test_healthy_exchange_snapshot(self):
        result = check_exchange_health(
            server_time_function=lambda: 123456789,
            time_sync_status_function=lambda: {
                "offset_ms": 10,
            },
            maximum_latency_ms=5000,
        )

        self.assertTrue(
            result["healthy"]
        )
        self.assertEqual(
            result["status"],
            "healthy",
        )

    def test_server_failure_is_degraded(self):
        def fail():
            raise RuntimeError(
                "network unavailable"
            )

        result = check_exchange_health(
            server_time_function=fail,
            time_sync_status_function=lambda: {
                "offset_ms": 0,
            },
        )

        self.assertFalse(
            result["healthy"]
        )


if __name__ == "__main__":
    unittest.main()
