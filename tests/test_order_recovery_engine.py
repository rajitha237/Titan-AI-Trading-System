"""Order Recovery Engine v28 tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.trader import order_recovery_store
from app.trader.order_recovery_engine import (
    recover_open_orders,
)


class OrderRecoveryEngineTests(
    unittest.TestCase
):
    def setUp(self):
        self.temp_dir = (
            tempfile.TemporaryDirectory()
        )
        self.patch = patch.object(
            order_recovery_store,
            "DB_PATH",
            Path(self.temp_dir.name)
            / "orders.db",
        )
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.temp_dir.cleanup()

    @patch(
        "app.trader.order_recovery_engine."
        "record_event",
        return_value=1,
    )
    def test_verified_order_snapshot_recovers_state(
        self,
        _record_event,
    ):
        result = recover_open_orders(
            exchange_orders=[
                {
                    "symbol": "BTCUSDT",
                    "side": "SELL",
                    "type": "STOP_MARKET",
                    "orderId": 1,
                    "origQty": "0.001",
                    "stopPrice": "59000",
                    "reduceOnly": True,
                }
            ],
            open_positions=[
                {
                    "symbol": "BTCUSDT",
                    "positionAmt": "0.001",
                }
            ],
        )

        self.assertIn(
            result["status"],
            {
                "success",
                "review_required",
            },
        )
        self.assertEqual(
            result["audit_after"][
                "status"
            ],
            "consistent",
        )
        self.assertEqual(
            result["orders_cancelled"],
            0,
        )

    def test_invalid_snapshot_is_blocked(self):
        result = recover_open_orders(
            exchange_orders=None,
            open_positions=[],
        )

        self.assertEqual(
            result["status"],
            "blocked",
        )
        self.assertFalse(
            result["mutation_performed"]
        )


if __name__ == "__main__":
    unittest.main()
