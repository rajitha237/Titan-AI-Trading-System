from __future__ import annotations
import unittest
from app.trader.pnl_reconciliation_engine import reconcile_completed_trade_pnl


class PnlReconciliationTests(unittest.TestCase):
    def test_exact_trade_reconciles(self):
        result = reconcile_completed_trade_pnl({
            "gross_pnl": 5.0,
            "fees": 1.0,
            "net_pnl": 4.0,
            "metadata": {
                "exact_binance_data": True,
                "closing_fills": [
                    {"realizedPnl": "5", "commission": "1"}
                ],
            },
        })
        self.assertTrue(result["reconciled"])

    def test_invalid_net_is_detected(self):
        result = reconcile_completed_trade_pnl({
            "gross_pnl": 5.0,
            "fees": 1.0,
            "net_pnl": 5.0,
        })
        self.assertFalse(result["reconciled"])


if __name__ == "__main__":
    unittest.main()
