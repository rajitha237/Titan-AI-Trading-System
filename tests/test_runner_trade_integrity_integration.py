from __future__ import annotations
import unittest
from unittest.mock import patch
from app.trader.auto_testnet_runner import save_result


class RunnerTradeIntegrityIntegrationTests(unittest.TestCase):
    def test_save_result_attaches_trade_integrity(self):
        result = {"status": "skipped", "execution": {"submitted": False}}
        with (
            patch(
                "app.trader.auto_testnet_runner.build_trade_integrity_snapshot",
                return_value={"status": "success", "report": {"status": "healthy"}},
            ),
            patch(
                "app.trader.auto_testnet_runner.build_production_readiness_report",
                return_value={"status": "READY", "ready": True},
            ),
            patch(
                "app.trader.auto_testnet_runner.build_backup_operations_snapshot",
                return_value={"status": "success"},
            ),
            patch(
                "app.trader.auto_testnet_runner.build_operations_snapshot",
                return_value={"status": "success"},
            ),
            patch(
                "app.trader.auto_testnet_runner.build_and_store_performance",
                return_value={"status": "success", "dashboard": {}, "snapshot": None},
            ),
            patch(
                "app.trader.auto_testnet_runner.route_notifications",
                return_value={"status": "success", "events": [], "errors": []},
            ),
            patch("app.trader.auto_testnet_runner.save_cycle_result", return_value=None),
            patch("app.trader.auto_testnet_runner.save_memory_record", return_value=None),
        ):
            save_result(result)
        self.assertEqual(result["trade_integrity"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
