from __future__ import annotations
import unittest
from unittest.mock import patch
from app.operations.production_report import build_production_readiness_report


class ProductionReportTests(unittest.TestCase):
    def test_ready_report(self):
        with (
            patch("app.operations.production_report.evaluate_startup_readiness",
                  return_value={"startup_allowed": True, "profile": {"environment": "TESTNET"}}),
            patch("app.operations.production_report.build_operations_snapshot",
                  return_value={"health": {"status": "HEALTHY"}, "supervision": {"action": "CONTINUE"}}),
            patch("app.operations.production_report.build_backup_operations_snapshot",
                  return_value={"status": "success"}),
            patch("app.operations.production_report.build_and_store_performance",
                  return_value={"status": "success"}),
        ):
            result = build_production_readiness_report()
        self.assertTrue(result["ready"])


if __name__ == "__main__":
    unittest.main()
