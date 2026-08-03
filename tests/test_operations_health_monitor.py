from __future__ import annotations

import collections
import unittest
from unittest.mock import patch

from app.operations.health_monitor import (
    check_operations_health,
)


class OperationsHealthMonitorTests(
    unittest.TestCase
):
    def test_healthy_snapshot(self):
        disk = collections.namedtuple(
            "DiskUsage",
            "total used free",
        )

        with patch(
            "app.operations.health_monitor."
            "_check_database",
            return_value={
                "status": "healthy",
                "available": True,
                "path": "db",
                "error": None,
            },
        ):
            result = check_operations_health(
                exchange_health_function=lambda: {
                    "status": "healthy",
                    "healthy": True,
                },
                service_state_function=lambda: {
                    "status": "ready",
                },
                disk_usage_function=lambda path: (
                    disk(
                        1000,
                        400,
                        600,
                    )
                ),
                memory_function=lambda: 100.0,
                maximum_memory_mb=500.0,
                minimum_free_disk_percent=10.0,
            )

        self.assertEqual(
            result["status"],
            "HEALTHY",
        )
        self.assertTrue(
            result["read_only"]
        )

    def test_low_disk_is_critical(self):
        disk = collections.namedtuple(
            "DiskUsage",
            "total used free",
        )

        with patch(
            "app.operations.health_monitor."
            "_check_database",
            return_value={
                "status": "healthy",
                "available": True,
                "path": "db",
                "error": None,
            },
        ):
            result = check_operations_health(
                exchange_health_function=lambda: {
                    "status": "healthy",
                    "healthy": True,
                },
                service_state_function=lambda: {
                    "status": "ready",
                },
                disk_usage_function=lambda path: (
                    disk(
                        1000,
                        990,
                        10,
                    )
                ),
                memory_function=lambda: 100.0,
                minimum_free_disk_percent=10.0,
            )

        self.assertEqual(
            result["status"],
            "CRITICAL",
        )


if __name__ == "__main__":
    unittest.main()
