"""Order recovery store tests."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.trader import order_recovery_store
from app.trader.order_recovery_store import (
    list_order_states,
    mark_disappeared_orders,
    upsert_open_order,
)


class OrderRecoveryStoreTests(
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

    def test_upsert_and_disappearance(self):
        upsert_open_order(
            {
                "order_key": (
                    "BTCUSDT:NORMAL:1"
                ),
                "symbol": "BTCUSDT",
                "order_id": "1",
                "client_order_id": "x",
                "order_type": "LIMIT",
                "side": "BUY",
                "reduce_only": False,
                "is_algo_order": False,
                "quantity": 0.001,
                "price": 60000.0,
                "stop_price": 0.0,
            }
        )

        self.assertEqual(
            len(
                list_order_states(
                    status="OPEN"
                )
            ),
            1,
        )

        disappeared = (
            mark_disappeared_orders(
                set()
            )
        )

        self.assertEqual(
            disappeared[0]["status"],
            "MISSING_FROM_EXCHANGE",
        )


if __name__ == "__main__":
    unittest.main()
