"""Live analysis-only schema test for Auto Testnet Runner v27."""

from __future__ import annotations

import asyncio
import os
import unittest

from app.trader.auto_testnet_runner import run_auto_testnet_cycle


@unittest.skipUnless(
    os.getenv("TITANAI_RUN_PIPELINE_TESTS") == "1",
    "Set TITANAI_RUN_PIPELINE_TESTS=1 to run analysis-only pipeline test",
)
class RunnerSchemaTests(unittest.TestCase):
    def test_analysis_only_runner_never_submits_order(self):
        result = asyncio.run(
            run_auto_testnet_cycle(
                execute_trade=False,
                balance=30.0,
                risk_percent=1.0,
                leverage=5.0,
                scan_limit=5,
            )
        )

        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("version"), "v27")
        self.assertIn("status", result)
        self.assertIn("mode", result)
        self.assertIn("execution", result)
        self.assertIn("position_lifecycle", result)
        self.assertIn("performance_analytics", result)
        self.assertIn("ai_learning_snapshot", result)
        self.assertIn("daily_risk", result)
        self.assertIn("candidate_attempts", result)
        self.assertIn("execution_blocks", result)

        execution = result.get("execution") or {}
        self.assertIs(execution.get("submitted"), False)
        self.assertNotIn(
            str(execution.get("status", "")).lower(),
            {"protected", "filled", "verified_filled"},
        )


if __name__ == "__main__":
    unittest.main()
