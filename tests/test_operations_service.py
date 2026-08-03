from __future__ import annotations

import unittest
from unittest.mock import patch

from app.operations.operations_service import (
    build_operations_snapshot,
)


class OperationsServiceTests(
    unittest.TestCase
):
    def test_snapshot_combines_health_and_supervision(self):
        with (
            patch(
                "app.operations.operations_service."
                "check_operations_health",
                return_value={
                    "status": "HEALTHY",
                },
            ),
            patch(
                "app.operations.operations_service."
                "supervise_service_health",
                return_value={
                    "status": "success",
                    "action": "CONTINUE",
                },
            ),
        ):
            result = (
                build_operations_snapshot()
            )

        self.assertEqual(
            result["status"],
            "success",
        )
        self.assertTrue(
            result["non_blocking"]
        )


if __name__ == "__main__":
    unittest.main()
