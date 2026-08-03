"""Order consistency audit tests."""

from __future__ import annotations

import unittest

from app.trader.order_consistency_audit import (
    build_order_consistency_audit,
)


class OrderConsistencyAuditTests(
    unittest.TestCase
):
    def test_empty_snapshots_are_consistent(self):
        result = build_order_consistency_audit(
            exchange_orders=[],
            local_open_orders=[],
            open_positions=[],
        )

        self.assertEqual(
            result["status"],
            "consistent",
        )

    def test_orphan_reduce_only_is_reported(self):
        result = build_order_consistency_audit(
            exchange_orders=[
                {
                    "symbol": "ETHUSDT",
                    "side": "SELL",
                    "type": "STOP_MARKET",
                    "orderId": 42,
                    "origQty": "0.01",
                    "stopPrice": "2400",
                    "reduceOnly": True,
                }
            ],
            local_open_orders=[],
            open_positions=[],
        )

        self.assertEqual(
            len(
                result[
                    "orphan_reduce_only_orders"
                ]
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()
