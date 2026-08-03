from __future__ import annotations
import unittest
from app.config.startup_checks import evaluate_startup_readiness


class StartupChecksTests(unittest.TestCase):
    def test_default_analysis_is_ready(self):
        result = evaluate_startup_readiness(
            execute_trade_requested=False,
            environ={},
        )
        self.assertTrue(result["startup_allowed"])
        self.assertTrue(result["secrets_redacted"])

    def test_execution_without_opt_in_is_blocked(self):
        result = evaluate_startup_readiness(
            execute_trade_requested=True,
            environ={},
        )
        self.assertFalse(result["startup_allowed"])


if __name__ == "__main__":
    unittest.main()
