from __future__ import annotations

import unittest
from unittest.mock import patch

from app.trader.auto_testnet_runner import (
    save_result,
)


class RunnerOperationsIntegrationTests(
    unittest.TestCase
):
    def test_save_result_attaches_operations(self):
        result = {
            "status": "skipped",
            "execution": {
                "submitted": False,
            },
        }

        with (
            patch(
                "app.trader.auto_testnet_runner."
                "build_operations_snapshot",
                return_value={
                    "status": "success",
                    "health": {
                        "status": "HEALTHY",
                    },
                    "supervision": {
                        "action": "CONTINUE",
                    },
                    "non_blocking": True,
                    "read_only": True,
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "build_and_store_performance",
                return_value={
                    "status": "success",
                    "dashboard": {},
                    "snapshot": None,
                    "non_blocking": True,
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "route_notifications",
                return_value={
                    "status": "success",
                    "event_count": 0,
                    "stored_count": 0,
                    "telegram_sent_count": 0,
                    "events": [],
                    "errors": [],
                    "non_blocking": True,
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "save_cycle_result",
                return_value=None,
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "save_memory_record",
                return_value=None,
            ),
        ):
            save_result(result)

        self.assertEqual(
            result["operations"]["status"],
            "success",
        )

    def test_operations_error_is_non_blocking(self):
        result = {
            "status": "skipped",
            "execution": {
                "submitted": False,
            },
        }

        with (
            patch(
                "app.trader.auto_testnet_runner."
                "build_operations_snapshot",
                side_effect=RuntimeError(
                    "operations failure"
                ),
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "build_and_store_performance",
                return_value={
                    "status": "success",
                    "dashboard": {},
                    "snapshot": None,
                    "non_blocking": True,
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "route_notifications",
                return_value={
                    "status": "success",
                    "event_count": 0,
                    "stored_count": 0,
                    "telegram_sent_count": 0,
                    "events": [],
                    "errors": [],
                    "non_blocking": True,
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "save_cycle_result",
                return_value=None,
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "save_memory_record",
                return_value=None,
            ),
        ):
            save_result(result)

        self.assertEqual(
            result["operations"]["status"],
            "error",
        )


if __name__ == "__main__":
    unittest.main()
